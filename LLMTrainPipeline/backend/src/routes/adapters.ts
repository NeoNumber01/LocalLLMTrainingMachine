import { FastifyInstance } from 'fastify';
import { getProviderFactory } from '../providers/factory.js';
import { getConfig } from '../config/index.js';
import { AdapterResponse } from '../types/index.js';
import { prisma } from '../db/prisma-client.js';
import { getPython } from '../utils/python-utils.js';
import { checkAllAdaptersHealth, backupAdapter } from '../services/adapter-guard.js';

export async function adaptersRoutes(fastify: FastifyInstance) {

    // GET /api/adapters - Get all adapters
    fastify.get('/', {
        schema: {
            tags: ['Adapters'],
            summary: 'Get all adapters',
        },
    }, async (request, reply) => {
        const adapters = await prisma.adapter.findMany({
            orderBy: { createdAt: 'desc' },
        });

        const response: AdapterResponse[] = adapters.map(a => ({
            id: a.id,
            name: a.name,
            baseModel: a.baseModel,
            trainDataset: a.trainDataset,
            rank: a.rank,
            alpha: a.alpha,
            status: a.status,
            created: a.createdAt.toISOString(),
            metrics: {
                passAt1: a.passAt1 || 0,
                compileRate: a.compileRate || 0,
            },
        }));

        return response;
    });

    // GET /api/adapters/:id - Get adapter details
    fastify.get<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Adapters'],
            summary: 'Get adapter details',
        },
    }, async (request, reply) => {
        const adapter = await prisma.adapter.findUnique({
            where: { id: request.params.id },
        });

        if (!adapter) {
            return reply.status(404).send({ error: 'Adapter not found' });
        }

        return {
            id: adapter.id,
            name: adapter.name,
            baseModel: adapter.baseModel,
            trainDataset: adapter.trainDataset,
            rank: adapter.rank,
            alpha: adapter.alpha,
            status: adapter.status,
            created: adapter.createdAt.toISOString(),
            path: adapter.path,
            metrics: {
                passAt1: adapter.passAt1 || 0,
                compileRate: adapter.compileRate || 0,
            },
        };
    });

    // POST /api/adapters/rescan - Rescan adapters directory
    fastify.post('/rescan', {
        schema: {
            tags: ['Adapters'],
            summary: 'Rescan adapters directory',
        },
    }, async (request, reply) => {
        const config = getConfig();
        const factory = getProviderFactory(config);
        const scanner = factory.getScanner();

        // P2-FIX: Read dynamic path from Settings, fallback to default config
        let adaptersDir = config.storage.adaptersDir;
        try {
            const watchFoldersSetting = await prisma.setting.findUnique({
                where: { key: 'watchFolders' }
            });
            if (watchFoldersSetting) {
                const watchFolders = JSON.parse(watchFoldersSetting.valueJson);
                if (watchFolders?.adapters) {
                    adaptersDir = watchFolders.adapters;
                }
            }
        } catch (e) {
            console.warn('[Adapters] Failed to read watchFolders setting:', e);
        }

        const result = await scanner.scanAdapters(adaptersDir);

        return {
            success: true,
            added: result.added,
            updated: result.updated,
            removed: result.removed,
            errors: result.errors,
        };
    });

    // POST /api/adapters/:id/merge - Merge adapter to base model
    fastify.post<{ Params: { id: string }; Body: { outputName?: string } }>('/:id/merge', {
        schema: {
            tags: ['Adapters'],
            summary: 'Merge LoRA adapter to base model',
        },
    }, async (request, reply) => {
        const { id } = request.params;
        const { outputName } = request.body || {};

        // Get adapter information
        const adapter = await prisma.adapter.findUnique({
            where: { id },
        });

        if (!adapter) {
            return reply.status(404).send({ error: 'Adapter not found' });
        }

        // Get base model path
        const baseModel = await prisma.model.findFirst({
            where: { name: adapter.baseModel },
        });

        if (!baseModel) {
            return reply.status(400).send({ error: `Base model "${adapter.baseModel}" not found in registry` });
        }

        const config = getConfig();
        const path = await import('path');
        const { spawn } = await import('child_process');
        const fs = await import('fs/promises');
        const { fileURLToPath } = await import('url');

        const __filename = fileURLToPath(import.meta.url);
        const __dirname = path.dirname(__filename);

        // Determine output directory
        const mergedName = outputName || `${adapter.name}-merged`;
        const outputDir = path.join(config.storage.modelsDir, mergedName);
        const scriptPath = path.resolve(__dirname, '../../scripts/merge_adapter.py');

        // Check if script exists
        try {
            await fs.access(scriptPath);
        } catch {
            return reply.status(500).send({ error: 'Merge script not found' });
        }

        // Use SSE to return progress
        reply.raw.writeHead(200, {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        });

        const sendEvent = (data: any) => {
            reply.raw.write(`data: ${JSON.stringify(data)}\n\n`);
        };

        sendEvent({ status: 'running', message: 'Starting merge process...', progress: 0 });

        const pythonCmd = getPython();
        const mergeProcess = spawn(pythonCmd, [
            scriptPath,
            '--base_model', baseModel.path,
            '--adapter', adapter.path!,
            '--output', outputDir,
        ], {
            stdio: ['pipe', 'pipe', 'pipe'],
        });

        let lastError = '';

        mergeProcess.stdout.on('data', (data: Buffer) => {
            const lines = data.toString().split('\n').filter(l => l.trim());
            for (const line of lines) {
                try {
                    const event = JSON.parse(line);
                    sendEvent(event);
                } catch {
                    // Non-JSON output, treat as regular log
                    sendEvent({ status: 'running', message: line });
                }
            }
        });

        mergeProcess.stderr.on('data', (data: Buffer) => {
            lastError = data.toString();
            console.error('[Merge Error]', lastError);
        });

        mergeProcess.on('close', async (code) => {
            if (code === 0) {
                // Merge successful, register new model
                try {
                    await prisma.model.create({
                        data: {
                            name: mergedName,
                            path: outputDir,
                            params: baseModel.params,
                            backend: baseModel.backend,
                            quantization: 'None',
                            source: 'Merged',
                            status: 'Valid',
                        },
                    });
                    sendEvent({ status: 'success', message: 'Merge completed!', modelName: mergedName, progress: 100 });
                } catch (e: any) {
                    sendEvent({ status: 'error', message: `Merge succeeded but failed to register model: ${e.message}` });
                }
            } else {
                sendEvent({ status: 'error', message: lastError || 'Merge process failed' });
            }
            reply.raw.end();
        });

        mergeProcess.on('error', (err) => {
            sendEvent({ status: 'error', message: `Failed to start merge: ${err.message}` });
            reply.raw.end();
        });
    });

    // DELETE /api/adapters/:id - Delete adapter record and optionally delete local files
    fastify.delete<{ Params: { id: string }; Querystring: { deleteFiles?: string } }>('/:id', {
        schema: {
            tags: ['Adapters'],
            summary: 'Delete adapter record and optionally delete local files',
            querystring: {
                type: 'object',
                properties: {
                    deleteFiles: { type: 'string', enum: ['true', 'false'], default: 'false' }
                }
            }
        },
    }, async (request, reply) => {
        const deleteFiles = request.query.deleteFiles === 'true'; // Default: do not delete files

        const adapter = await prisma.adapter.findUnique({
            where: { id: request.params.id },
        });

        if (!adapter) {
            return reply.status(404).send({ error: 'Adapter not found' });
        }

        // Delete database record
        await prisma.adapter.delete({
            where: { id: request.params.id },
        });

        // Optionally delete local files
        let fileDeleted = false;
        let deleteError: string | undefined;

        if (deleteFiles && adapter.path) {
            const fs = await import('fs');
            if (fs.existsSync(adapter.path)) {
                try {
                    const stats = fs.statSync(adapter.path);
                    if (stats.isDirectory()) {
                        fs.rmSync(adapter.path, { recursive: true, force: true });
                    } else {
                        fs.unlinkSync(adapter.path);
                    }
                    fileDeleted = true;
                } catch (e: any) {
                    deleteError = e.message;
                }
            }
        }

        return {
            success: true,
            message: fileDeleted
                ? 'Adapter and local files deleted'
                : 'Adapter record deleted (local files preserved)',
            fileDeleted,
            error: deleteError
        };
    });

    // GET /api/adapters/health - Check health status of all adapters
    fastify.get('/health', {
        schema: {
            tags: ['Adapters'],
            summary: 'Check health status of all adapters',
        },
    }, async (request, reply) => {
        const healthStatuses = await checkAllAdaptersHealth();

        const summary = {
            total: healthStatuses.length,
            valid: healthStatuses.filter(s => s.exists && s.isComplete).length,
            missing: healthStatuses.filter(s => !s.exists).length,
            incomplete: healthStatuses.filter(s => s.exists && !s.isComplete).length,
            withBackup: healthStatuses.filter(s => s.hasBackup).length,
        };

        return {
            summary,
            adapters: healthStatuses,
        };
    });

    // POST /api/adapters/:id/backup - Manually backup adapter
    fastify.post<{ Params: { id: string } }>('/:id/backup', {
        schema: {
            tags: ['Adapters'],
            summary: 'Manually backup specified adapter',
        },
    }, async (request, reply) => {
        const adapter = await prisma.adapter.findUnique({
            where: { id: request.params.id },
        });

        if (!adapter) {
            return reply.status(404).send({ error: 'Adapter not found' });
        }

        if (!adapter.path) {
            return reply.status(400).send({ error: 'Adapter has no path' });
        }

        const result = backupAdapter(adapter.path, adapter.name);

        if (result.success) {
            return {
                success: true,
                message: 'Backup created successfully',
                backupPath: result.backupPath,
            };
        } else {
            return reply.status(500).send({
                success: false,
                error: result.error,
            });
        }
    });
}
