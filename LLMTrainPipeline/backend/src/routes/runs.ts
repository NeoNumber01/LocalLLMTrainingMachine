import { FastifyInstance } from 'fastify';
import { v4 as uuid } from 'uuid';
import { enqueueRun, stopRun, getRunEmitter, getQueue, reorderQueue, getActiveRun } from '../services/run-executor.js';
import { CreateRunDto, RunResponse } from '../types/index.js';
import { prisma } from '../db/prisma-client.js';
import { ConfigSchema } from '../config/schema.js';

export async function runsRoutes(fastify: FastifyInstance) {

    // GET /api/runs - Get all runs
    fastify.get('/', {
        schema: {
            tags: ['Runs'],
            summary: 'Get all training runs',
            querystring: {
                type: 'object',
                properties: {
                    status: { type: 'string' },
                    limit: { type: 'number' },
                },
            },
        },
    }, async (request, reply) => {
        const query = request.query as { status?: string; limit?: number };

        const runs = await prisma.run.findMany({
            where: query.status ? { status: query.status } : undefined,
            take: query.limit || 100,
            orderBy: { createdAt: 'desc' },
            include: { model: true, dataset: true, artifacts: true },
        });

        const response: RunResponse[] = runs.map(run => {
            const metrics = run.metricsJson ? JSON.parse(run.metricsJson) : { loss: 0, passAt1: 0, compileRate: 0 };
            const config = JSON.parse(run.configJson);
            const evalResult = (run as any).evalResultJson ? JSON.parse((run as any).evalResultJson) : undefined;

            return {
                id: run.id,
                name: run.name,
                type: run.type,
                status: run.status as any,
                duration: run.duration,
                startedAt: run.startedAt?.toISOString() || null,
                createdAt: run.createdAt.toISOString(),
                baseModel: run.model.name,
                dataset: run.dataset.name,
                metrics,
                config,
                artifacts: run.artifacts.map(a => a.path),
                evalResult,
            };
        });

        return response;
    });

    // POST /api/runs - Create new run
    fastify.post('/', {
        schema: {
            tags: ['Runs'],
            summary: 'Create new training run',
            body: {
                type: 'object',
                required: ['name', 'type', 'modelId', 'datasetId', 'config'],
                properties: {
                    name: { type: 'string' },
                    type: { type: 'string', enum: ['finetune', 'pretrain', 'lora', 'evaluation'] },
                    modelId: { type: 'string' },
                    datasetId: { type: 'string' },
                    evalDatasetId: { type: 'string' },
                    adapterId: { type: 'string' },  // Specify adapter to use during evaluation
                    profileName: { type: 'string' },
                    config: { type: 'object' },
                },
            },
        },
    }, async (request, reply) => {
        const body = request.body as CreateRunDto;

        // P0-SAFETY: Validate config structure
        const validationResult = ConfigSchema.deepPartial().safeParse(body.config);
        if (!validationResult.success) {
            return reply.status(400).send({
                error: 'Invalid configuration',
                details: validationResult.error.format()
            });
        }

        // Validate model and dataset exist
        const [model, dataset] = await Promise.all([
            prisma.model.findUnique({ where: { id: body.modelId } }),
            prisma.dataset.findUnique({ where: { id: body.datasetId } }),
        ]);

        if (!model) {
            return reply.status(400).send({ error: 'Model not found' });
        }
        if (!dataset) {
            return reply.status(400).send({ error: 'Dataset not found' });
        }

        // Create run record
        const run = await prisma.run.create({
            data: {
                id: `run_${uuid().slice(0, 5)}`,
                name: body.name,
                type: body.type,
                status: 'queued',
                modelId: body.modelId,
                datasetId: body.datasetId,
                evalDatasetId: body.evalDatasetId,
                sourceRunId: (body as any).sourceRunId,  // P1: Link to source training run
                profileName: body.profileName || 'single_gpu',
                configJson: JSON.stringify(body.config),
            },
            include: { model: true, dataset: true },
        });

        // If adapterId is provided, create adapter artifact for evaluation use
        // So run-executor.ts evaluation logic can find adapterPath via Artifact
        if ((body as any).adapterId) {
            const adapter = await prisma.adapter.findUnique({ where: { id: (body as any).adapterId } });
            if (adapter && adapter.path) {
                await prisma.artifact.create({
                    data: {
                        runId: run.id,
                        kind: 'adapter',
                        path: adapter.path,
                        size: 0,
                    },
                });
                console.log(`[Runs] Created adapter artifact for run ${run.id}: ${adapter.path}`);
            }
        }

        // Add to execution queue
        await enqueueRun(run.id, run.profileName, body.config);

        return {
            id: run.id,
            name: run.name,
            type: run.type,
            status: run.status,
            createdAt: run.createdAt.toISOString(),
        };
    });

    // GET /api/runs/:id - Get run details
    fastify.get<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Runs'],
            summary: 'Get run details',
            params: {
                type: 'object',
                properties: { id: { type: 'string' } },
            },
        },
    }, async (request, reply) => {
        const run = await prisma.run.findUnique({
            where: { id: request.params.id },
            include: { model: true, dataset: true, artifacts: true, loraStats: true },
        });

        if (!run) {
            return reply.status(404).send({ error: 'Run not found' });
        }

        const metrics = run.metricsJson ? JSON.parse(run.metricsJson) : { loss: 0, passAt1: 0, compileRate: 0 };
        const config = JSON.parse(run.configJson);
        const evalResult = (run as any).evalResultJson ? JSON.parse((run as any).evalResultJson) : undefined;

        return {
            id: run.id,
            name: run.name,
            type: run.type,
            status: run.status,
            duration: run.duration,
            startedAt: run.startedAt?.toISOString() || null,
            createdAt: run.createdAt.toISOString(),
            baseModel: run.model.name,
            dataset: run.dataset.name,
            metrics,
            config,
            artifacts: run.artifacts.map(a => a.path),
            evalResult,
            loraStats: run.loraStats, // P0-FEAT: Return LoRA statistics
        };
    });

    // POST /api/runs/:id/stop - Stop run
    fastify.post<{ Params: { id: string } }>('/:id/stop', {
        schema: {
            tags: ['Runs'],
            summary: 'Stop run',
        },
    }, async (request, reply) => {
        try {
            await stopRun(request.params.id);
            return { success: true };
        } catch (error) {
            return reply.status(400).send({ error: String(error) });
        }
    });

    // ============== Task Queue Management API ==============

    // GET /api/runs/queue - Get all tasks in queue
    fastify.get('/queue', {
        schema: {
            tags: ['Runs'],
            summary: 'Get task queue list',
            response: {
                200: {
                    type: 'object',
                    properties: {
                        activeRun: {
                            type: 'object',
                            nullable: true,
                            properties: {
                                id: { type: 'string' },
                                name: { type: 'string' },
                            },
                        },
                        queue: {
                            type: 'array',
                            items: {
                                type: 'object',
                                properties: {
                                    id: { type: 'string' },
                                    name: { type: 'string' },
                                    type: { type: 'string' },
                                    queuePosition: { type: 'number' },
                                    createdAt: { type: 'string' },
                                    baseModel: { type: 'string' },
                                    dataset: { type: 'string' },
                                },
                            },
                        },
                    },
                },
            },
        },
    }, async (request, reply) => {
        const [activeRun, queue] = await Promise.all([
            getActiveRun(),
            getQueue(),
        ]);
        return { activeRun, queue };
    });

    // POST /api/runs/:id/reorder - Reorder task position in queue
    fastify.post<{ Params: { id: string }; Body: { position: number } }>('/:id/reorder', {
        schema: {
            tags: ['Runs'],
            summary: 'Reorder queue task position',
            params: {
                type: 'object',
                properties: { id: { type: 'string' } },
            },
            body: {
                type: 'object',
                required: ['position'],
                properties: {
                    position: { type: 'number', minimum: 1 },
                },
            },
        },
    }, async (request, reply) => {
        try {
            const { position } = request.body;
            await reorderQueue(request.params.id, position);
            return { success: true };
        } catch (error) {
            return reply.status(400).send({ error: String(error) });
        }
    });

    // POST /api/runs/:id/cancel-queue - Cancel queue (remove task from queue)
    fastify.post<{ Params: { id: string } }>('/:id/cancel-queue', {
        schema: {
            tags: ['Runs'],
            summary: 'Cancel task queue',
        },
    }, async (request, reply) => {
        try {
            // Use existing stopRun, it already supports stopping queued tasks
            await stopRun(request.params.id);
            return { success: true, message: 'Run removed from queue' };
        } catch (error) {
            return reply.status(400).send({ error: String(error) });
        }
    });

    // POST /api/runs/:id/clone - Clone run configuration
    fastify.post<{ Params: { id: string } }>('/:id/clone', {
        schema: {
            tags: ['Runs'],
            summary: 'Clone run configuration',
        },
    }, async (request, reply) => {
        const sourceRun = await prisma.run.findUnique({
            where: { id: request.params.id },
        });

        if (!sourceRun) {
            return reply.status(404).send({ error: 'Run not found' });
        }

        const newRun = await prisma.run.create({
            data: {
                id: `run_${uuid().slice(0, 5)}`,
                name: `${sourceRun.name}-clone`,
                type: sourceRun.type,
                status: 'queued',
                modelId: sourceRun.modelId,
                datasetId: sourceRun.datasetId,
                evalDatasetId: sourceRun.evalDatasetId,
                profileName: sourceRun.profileName,
                configJson: sourceRun.configJson,
            },
        });

        // Add to execution queue
        const config = JSON.parse(sourceRun.configJson);
        await enqueueRun(newRun.id, sourceRun.profileName, config);

        return { id: newRun.id, name: newRun.name };
    });

    // DELETE /api/runs/:id - Delete run and associated files
    fastify.delete<{ Params: { id: string }; Querystring: { deleteFiles?: string } }>('/:id', {
        schema: {
            tags: ['Runs'],
            summary: 'Delete run and associated files',
            querystring: {
                type: 'object',
                properties: {
                    deleteFiles: { type: 'string', enum: ['true', 'false'], default: 'true' }
                }
            }
        },
    }, async (request, reply) => {
        const runId = request.params.id;
        const deleteFiles = request.query.deleteFiles !== 'false'; // Default: delete files

        // 1. Find Run to get related information
        const run = await prisma.run.findUnique({
            where: { id: runId },
            include: { artifacts: true }
        });

        if (!run) {
            return reply.status(404).send({ error: 'Run not found' });
        }

        // 2. Delete database records (cascade delete automatically cleans up RunEvent, RunMetric, Artifact, etc.)
        await prisma.run.delete({
            where: { id: runId },
        });

        // 3. Delete local files
        const deletedPaths: string[] = [];
        const errors: string[] = [];

        if (deleteFiles) {
            const fs = await import('fs');
            const path = await import('path');

            // Delete run output directory
            const runOutputDir = path.resolve(`./storage/runs/${runId}`);
            if (fs.existsSync(runOutputDir)) {
                try {
                    fs.rmSync(runOutputDir, { recursive: true, force: true });
                    deletedPaths.push(runOutputDir);
                } catch (e: any) {
                    errors.push(`Failed to delete ${runOutputDir}: ${e.message}`);
                }
            }

            // Delete other files recorded in artifacts (if paths are outside run directory)
            for (const artifact of run.artifacts) {
                const artifactPath = path.isAbsolute(artifact.path)
                    ? artifact.path
                    : path.resolve(artifact.path);

                // Avoid re-deleting files already in runOutputDir
                if (!artifactPath.startsWith(runOutputDir) && fs.existsSync(artifactPath)) {
                    try {
                        const stats = fs.statSync(artifactPath);
                        if (stats.isDirectory()) {
                            fs.rmSync(artifactPath, { recursive: true, force: true });
                        } else {
                            fs.unlinkSync(artifactPath);
                        }
                        deletedPaths.push(artifactPath);
                    } catch (e: any) {
                        errors.push(`Failed to delete artifact ${artifactPath}: ${e.message}`);
                    }
                }
            }
        }

        return {
            success: true,
            message: deleteFiles
                ? `Run deleted with ${deletedPaths.length} file(s)/folder(s) removed`
                : 'Run record deleted (files preserved)',
            deletedPaths,
            errors: errors.length > 0 ? errors : undefined
        };
    });

    // GET /api/runs/:id/logs/stream - SSE log stream
    fastify.get<{ Params: { id: string } }>('/:id/logs/stream', {
        schema: {
            tags: ['Runs'],
            summary: 'SSE log stream',
        },
    }, async (request, reply) => {
        const runId = request.params.id;

        // Check if run exists
        const run = await prisma.run.findUnique({ where: { id: runId } });
        if (!run) {
            return reply.status(404).send({ error: 'Run not found' });
        }

        // Set SSE headers
        reply.raw.writeHead(200, {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
        });

        // First send historical logs
        const events = await prisma.runEvent.findMany({
            where: { runId },
            orderBy: { timestamp: 'asc' },
            take: 100,
        });

        for (const event of events) {
            const data = JSON.stringify({
                type: 'log',
                timestamp: event.timestamp.toISOString(),
                level: event.level,
                message: event.message,
            });
            reply.raw.write(`data: ${data}\n\n`);
        }

        // Subscribe to real-time events
        const emitter = getRunEmitter(runId);
        const handler = (event: any) => {
            reply.raw.write(`data: ${JSON.stringify(event)}\n\n`);
        };

        emitter.on('event', handler);

        // Clean up when client disconnects
        request.raw.on('close', () => {
            emitter.off('event', handler);
        });
    });

    // GET /api/runs/:id/metrics - Get metrics
    fastify.get<{ Params: { id: string } }>('/:id/metrics', {
        schema: {
            tags: ['Runs'],
            summary: 'Get run metrics',
        },
    }, async (request, reply) => {
        const metrics = await prisma.runMetric.findMany({
            where: { runId: request.params.id },
            orderBy: { step: 'asc' },
        });

        // P0-FIX: Filter out abnormal steps without lr
        return metrics
            .map(m => {
                const extra = m.extraJson ? JSON.parse(m.extraJson) : null;
                // Convert field names to match frontend expected format (gradNorm -> grad_norm)
                const normalizedExtra = extra ? {
                    lr: extra.lr,
                    grad_norm: extra.gradNorm ?? extra.grad_norm,
                    epoch: extra.epoch,
                } : null;
                return {
                    step: m.step,
                    timestamp: m.timestamp.toISOString(),
                    loss: m.loss,
                    passAt1: m.passAt1,
                    compileRate: m.compileRate,
                    extra: normalizedExtra,
                };
            })
            .filter(m => m.extra?.lr != null);  // Only keep valid training steps with lr
    });

    // GET /api/runs/:id/eval - Get full evaluation results
    fastify.get<{ Params: { id: string } }>('/:id/eval', {
        schema: {
            tags: ['Runs'],
            summary: 'Get full evaluation results',
        },
    }, async (request, reply) => {
        const run = await prisma.run.findUnique({
            where: { id: request.params.id },
        });

        if (!run) {
            return reply.status(404).send({ error: 'Run not found' });
        }

        // Return full eval result if available
        if ((run as any).evalResultJson) {
            return JSON.parse((run as any).evalResultJson);
        }

        // Fallback to basic metrics
        const metrics = run.metricsJson ? JSON.parse(run.metricsJson) : null;
        return {
            passAt1: metrics?.passAt1 || 0,
            compileRate: metrics?.compileRate || 0,
            passAtK: { '1': metrics?.passAt1 || 0 },
            errorStats: {
                syntaxErrorRate: 0,
                runtimeErrorRate: 0,
                timeoutRate: 0,
                invalidOutputRate: 0,
                assertionErrorRate: 0,
                importErrorRate: 0,
                memoryErrorRate: 0,
            },
            timeStats: {
                meanRuntimeMs: 0,
                p50RuntimeMs: 0,
                p95RuntimeMs: 0,
                maxRuntimeMs: 0,
                tleRate: 0,
            },
            failures: [],
            totalProblems: 0,
            totalSamples: 0,
        };
    });

    // GET /api/runs/:id/artifacts - Get artifact list
    fastify.get<{ Params: { id: string } }>('/:id/artifacts', {
        schema: {
            tags: ['Runs'],
            summary: 'Get artifact list',
        },
    }, async (request, reply) => {
        const artifacts = await prisma.artifact.findMany({
            where: { runId: request.params.id },
        });

        return artifacts.map(a => ({
            id: a.id,
            kind: a.kind,
            path: a.path,
            name: a.path,
            size: `${a.size} B`,
            createdAt: a.createdAt.toISOString(),
        }));
    });

    // GET /api/runs/:id/artifacts/:artifactId/download - Download artifact file
    fastify.get<{ Params: { id: string; artifactId: string } }>('/:id/artifacts/:artifactId/download', {
        schema: {
            tags: ['Runs'],
            summary: 'Download artifact file',
        },
    }, async (request, reply) => {
        const artifact = await prisma.artifact.findUnique({
            where: { id: request.params.artifactId },
        });

        if (!artifact || artifact.runId !== request.params.id) {
            return reply.status(404).send({ error: 'Artifact not found' });
        }

        // Build file path
        const fs = await import('fs');
        const path = await import('path');
        const archiver = await import('archiver');

        const artifactPathRaw = artifact.path;
        let artifactPath = '';

        if (path.isAbsolute(artifactPathRaw)) {
            // Absolute path, use directly
            artifactPath = artifactPathRaw;
        } else if (artifactPathRaw.startsWith('./') || artifactPathRaw.startsWith('../')) {
            // Relative to project root (e.g. ./storage/runs/run_xxx/checkpoint-10)
            artifactPath = path.resolve(artifactPathRaw);
        } else {
            // Relative to run output directory (e.g. checkpoint-10)
            artifactPath = path.resolve(`./storage/runs/${request.params.id}`, artifactPathRaw);
        }

        console.log(`[Download] Artifact path raw: ${artifactPathRaw}, resolved: ${artifactPath}`);

        if (!fs.existsSync(artifactPath)) {
            console.error(`Artifact file not found: ${artifactPath}`);
            return reply.status(404).send({ error: 'Artifact file not found on disk' });
        }

        const stats = fs.statSync(artifactPath);

        if (stats.isDirectory()) {
            // If directory, auto-package as zip for download
            const dirName = path.basename(artifactPath);
            const zipFileName = `${dirName}.zip`;

            reply.header('Content-Disposition', `attachment; filename="${zipFileName}"`);
            reply.header('Content-Type', 'application/zip');

            // archiver is CommonJS module, need to get from default export
            const archiverFn = (archiver as any).default || archiver;
            const archive = archiverFn('zip', { zlib: { level: 6 } });

            archive.on('error', (err: any) => {
                console.error('Archive error:', err);
                // Avoid throwing unhandled exception on error
            });

            // Add directory contents to zip
            archive.directory(artifactPath, dirName);
            archive.finalize();

            return reply.send(archive);
        } else {
            // Regular file, download directly
            const fileName = path.basename(artifact.path);
            const fileStream = fs.createReadStream(artifactPath);

            reply.header('Content-Disposition', `attachment; filename="${fileName}"`);
            reply.header('Content-Type', 'application/octet-stream');

            return reply.send(fileStream);
        }
    });
}
