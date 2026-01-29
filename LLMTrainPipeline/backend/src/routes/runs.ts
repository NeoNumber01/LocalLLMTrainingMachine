import { FastifyInstance } from 'fastify';
import { v4 as uuid } from 'uuid';
import { enqueueRun, stopRun, getRunEmitter, getQueue, reorderQueue, getActiveRun } from '../services/run-executor.js';
import { CreateRunDto, RunResponse } from '../types/index.js';
import { prisma } from '../db/prisma-client.js';
import { ConfigSchema } from '../config/schema.js';

export async function runsRoutes(fastify: FastifyInstance) {

    // GET /api/runs - 获取所有运行
    fastify.get('/', {
        schema: {
            tags: ['Runs'],
            summary: '获取所有训练运行',
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

    // POST /api/runs - 创建新运行
    fastify.post('/', {
        schema: {
            tags: ['Runs'],
            summary: '创建新训练运行',
            body: {
                type: 'object',
                required: ['name', 'type', 'modelId', 'datasetId', 'config'],
                properties: {
                    name: { type: 'string' },
                    type: { type: 'string', enum: ['finetune', 'pretrain', 'lora', 'evaluation'] },
                    modelId: { type: 'string' },
                    datasetId: { type: 'string' },
                    evalDatasetId: { type: 'string' },
                    adapterId: { type: 'string' },  // 用于评测时指定使用的 adapter
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

        // 验证 model 和 dataset 存在
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

        // 创建运行记录
        const run = await prisma.run.create({
            data: {
                id: `run_${uuid().slice(0, 5)}`,
                name: body.name,
                type: body.type,
                status: 'queued',
                modelId: body.modelId,
                datasetId: body.datasetId,
                evalDatasetId: body.evalDatasetId,
                sourceRunId: (body as any).sourceRunId,  // P1: 关联来源训练 run
                profileName: body.profileName || 'single_gpu',
                configJson: JSON.stringify(body.config),
            },
            include: { model: true, dataset: true },
        });

        // 如果提供了 adapterId，创建 adapter artifact 以便评测时使用
        // 这样 run-executor.ts 中的评测逻辑就能通过 Artifact 找到 adapterPath
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

        // 加入队列执行
        await enqueueRun(run.id, run.profileName, body.config);

        return {
            id: run.id,
            name: run.name,
            type: run.type,
            status: run.status,
            createdAt: run.createdAt.toISOString(),
        };
    });

    // GET /api/runs/:id - 获取运行详情
    fastify.get<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Runs'],
            summary: '获取运行详情',
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
            loraStats: run.loraStats, // P0-FEAT: 返回 LoRA 统计信息
        };
    });

    // POST /api/runs/:id/stop - 停止运行
    fastify.post<{ Params: { id: string } }>('/:id/stop', {
        schema: {
            tags: ['Runs'],
            summary: '停止运行',
        },
    }, async (request, reply) => {
        try {
            await stopRun(request.params.id);
            return { success: true };
        } catch (error) {
            return reply.status(400).send({ error: String(error) });
        }
    });

    // ============== 任务队列管理 API ==============

    // GET /api/runs/queue - 获取队列中的所有任务
    fastify.get('/queue', {
        schema: {
            tags: ['Runs'],
            summary: '获取任务队列列表',
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

    // POST /api/runs/:id/reorder - 重排任务在队列中的位置
    fastify.post<{ Params: { id: string }; Body: { position: number } }>('/:id/reorder', {
        schema: {
            tags: ['Runs'],
            summary: '重排队列任务位置',
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

    // POST /api/runs/:id/cancel-queue - 取消排队（将任务从队列中移除）
    fastify.post<{ Params: { id: string } }>('/:id/cancel-queue', {
        schema: {
            tags: ['Runs'],
            summary: '取消任务排队',
        },
    }, async (request, reply) => {
        try {
            // 使用现有的 stopRun，它已支持停止 queued 状态的任务
            await stopRun(request.params.id);
            return { success: true, message: 'Run removed from queue' };
        } catch (error) {
            return reply.status(400).send({ error: String(error) });
        }
    });

    // POST /api/runs/:id/clone - 克隆运行配置
    fastify.post<{ Params: { id: string } }>('/:id/clone', {
        schema: {
            tags: ['Runs'],
            summary: '克隆运行配置',
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

        // 加入执行队列
        const config = JSON.parse(sourceRun.configJson);
        await enqueueRun(newRun.id, sourceRun.profileName, config);

        return { id: newRun.id, name: newRun.name };
    });

    // DELETE /api/runs/:id - 删除运行及其关联文件
    fastify.delete<{ Params: { id: string }; Querystring: { deleteFiles?: string } }>('/:id', {
        schema: {
            tags: ['Runs'],
            summary: '删除运行及其关联文件',
            querystring: {
                type: 'object',
                properties: {
                    deleteFiles: { type: 'string', enum: ['true', 'false'], default: 'true' }
                }
            }
        },
    }, async (request, reply) => {
        const runId = request.params.id;
        const deleteFiles = request.query.deleteFiles !== 'false'; // 默认删除文件

        // 1. 查找 Run 以获取相关信息
        const run = await prisma.run.findUnique({
            where: { id: runId },
            include: { artifacts: true }
        });

        if (!run) {
            return reply.status(404).send({ error: 'Run not found' });
        }

        // 2. 删除数据库记录 (级联删除会自动清理 RunEvent, RunMetric, Artifact 等)
        await prisma.run.delete({
            where: { id: runId },
        });

        // 3. 删除本地文件
        const deletedPaths: string[] = [];
        const errors: string[] = [];

        if (deleteFiles) {
            const fs = await import('fs');
            const path = await import('path');

            // 删除 run 输出目录
            const runOutputDir = path.resolve(`./storage/runs/${runId}`);
            if (fs.existsSync(runOutputDir)) {
                try {
                    fs.rmSync(runOutputDir, { recursive: true, force: true });
                    deletedPaths.push(runOutputDir);
                } catch (e: any) {
                    errors.push(`Failed to delete ${runOutputDir}: ${e.message}`);
                }
            }

            // 删除 artifacts 中记录的其他文件 (如果路径在 run 目录外)
            for (const artifact of run.artifacts) {
                const artifactPath = path.isAbsolute(artifact.path)
                    ? artifact.path
                    : path.resolve(artifact.path);

                // 避免重复删除已在 runOutputDir 中的文件
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

    // GET /api/runs/:id/logs/stream - SSE 日志流
    fastify.get<{ Params: { id: string } }>('/:id/logs/stream', {
        schema: {
            tags: ['Runs'],
            summary: 'SSE 日志流',
        },
    }, async (request, reply) => {
        const runId = request.params.id;

        // 检查 run 是否存在
        const run = await prisma.run.findUnique({ where: { id: runId } });
        if (!run) {
            return reply.status(404).send({ error: 'Run not found' });
        }

        // 设置 SSE headers
        reply.raw.writeHead(200, {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
        });

        // 首先发送历史日志
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

        // 订阅实时事件
        const emitter = getRunEmitter(runId);
        const handler = (event: any) => {
            reply.raw.write(`data: ${JSON.stringify(event)}\n\n`);
        };

        emitter.on('event', handler);

        // 客户端断开时清理
        request.raw.on('close', () => {
            emitter.off('event', handler);
        });
    });

    // GET /api/runs/:id/metrics - 获取指标
    fastify.get<{ Params: { id: string } }>('/:id/metrics', {
        schema: {
            tags: ['Runs'],
            summary: '获取运行指标',
        },
    }, async (request, reply) => {
        const metrics = await prisma.runMetric.findMany({
            where: { runId: request.params.id },
            orderBy: { step: 'asc' },
        });

        // P0-FIX: 过滤掉没有 lr 的异常步骤
        return metrics
            .map(m => {
                const extra = m.extraJson ? JSON.parse(m.extraJson) : null;
                // 转换字段名以匹配前端期望的格式 (gradNorm -> grad_norm)
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
            .filter(m => m.extra?.lr != null);  // 只保留有 lr 的有效训练步骤
    });

    // GET /api/runs/:id/eval - 获取完整评估结果
    fastify.get<{ Params: { id: string } }>('/:id/eval', {
        schema: {
            tags: ['Runs'],
            summary: '获取完整评估结果',
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

    // GET /api/runs/:id/artifacts - 获取产物列表
    fastify.get<{ Params: { id: string } }>('/:id/artifacts', {
        schema: {
            tags: ['Runs'],
            summary: '获取产物列表',
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

    // GET /api/runs/:id/artifacts/:artifactId/download - 下载产物文件
    fastify.get<{ Params: { id: string; artifactId: string } }>('/:id/artifacts/:artifactId/download', {
        schema: {
            tags: ['Runs'],
            summary: '下载产物文件',
        },
    }, async (request, reply) => {
        const artifact = await prisma.artifact.findUnique({
            where: { id: request.params.artifactId },
        });

        if (!artifact || artifact.runId !== request.params.id) {
            return reply.status(404).send({ error: 'Artifact not found' });
        }

        // 构建文件路径
        const fs = await import('fs');
        const path = await import('path');
        const archiver = await import('archiver');

        const artifactPathRaw = artifact.path;
        let artifactPath = '';

        if (path.isAbsolute(artifactPathRaw)) {
            // 绝对路径直接使用
            artifactPath = artifactPathRaw;
        } else if (artifactPathRaw.startsWith('./') || artifactPathRaw.startsWith('../')) {
            // 相对于项目根目录的路径（如 ./storage/runs/run_xxx/checkpoint-10）
            artifactPath = path.resolve(artifactPathRaw);
        } else {
            // 相对于 run 输出目录的路径（如 checkpoint-10）
            artifactPath = path.resolve(`./storage/runs/${request.params.id}`, artifactPathRaw);
        }

        console.log(`[Download] Artifact path raw: ${artifactPathRaw}, resolved: ${artifactPath}`);

        if (!fs.existsSync(artifactPath)) {
            console.error(`Artifact file not found: ${artifactPath}`);
            return reply.status(404).send({ error: 'Artifact file not found on disk' });
        }

        const stats = fs.statSync(artifactPath);

        if (stats.isDirectory()) {
            // 如果是目录，自动打包成 zip 文件下载
            const dirName = path.basename(artifactPath);
            const zipFileName = `${dirName}.zip`;

            reply.header('Content-Disposition', `attachment; filename="${zipFileName}"`);
            reply.header('Content-Type', 'application/zip');

            // archiver 是 CommonJS 模块，需要从 default 导出获取
            const archiverFn = (archiver as any).default || archiver;
            const archive = archiverFn('zip', { zlib: { level: 6 } });

            archive.on('error', (err: any) => {
                console.error('Archive error:', err);
                // 避免因错误抛出未处理异常
            });

            // 将目录内容添加到 zip
            archive.directory(artifactPath, dirName);
            archive.finalize();

            return reply.send(archive);
        } else {
            // 普通文件直接下载
            const fileName = path.basename(artifact.path);
            const fileStream = fs.createReadStream(artifactPath);

            reply.header('Content-Disposition', `attachment; filename="${fileName}"`);
            reply.header('Content-Type', 'application/octet-stream');

            return reply.send(fileStream);
        }
    });
}
