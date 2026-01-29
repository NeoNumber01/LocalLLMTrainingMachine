import { FastifyInstance } from 'fastify';
import { getProviderFactory } from '../providers/factory.js';
import { getConfig } from '../config/index.js';
import { ModelResponse } from '../types/index.js';
import { prisma } from '../db/prisma-client.js';

export async function modelsRoutes(fastify: FastifyInstance) {

    // GET /api/models - Get all models
    fastify.get('/', {
        schema: {
            tags: ['Models'],
            summary: 'Get all models',
        },
    }, async (request, reply) => {
        const models = await prisma.model.findMany({
            orderBy: { updatedAt: 'desc' },
        });

        const response: ModelResponse[] = models.map(m => ({
            id: m.id,
            name: m.name,
            backend: m.backend as any,
            source: m.source as any,
            quantization: m.quantization as any,
            params: m.params,
            path: m.path,
            status: m.status === 'valid' ? 'Valid' : m.status === 'scanning' ? 'Scanning' : 'Error',
            lastModified: m.updatedAt.toISOString(),
        }));

        return response;
    });

    // GET /api/models/:id - Get model details
    fastify.get<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Models'],
            summary: 'Get model details',
        },
    }, async (request, reply) => {
        const model = await prisma.model.findUnique({
            where: { id: request.params.id },
        });

        if (!model) {
            return reply.status(404).send({ error: 'Model not found' });
        }

        return {
            id: model.id,
            name: model.name,
            backend: model.backend,
            source: model.source,
            quantization: model.quantization,
            params: model.params,
            path: model.path,
            status: model.status,
            lastModified: model.updatedAt.toISOString(),
            meta: model.metaJson ? JSON.parse(model.metaJson) : null,
        };
    });

    // POST /api/models/rescan - Rescan models directory
    fastify.post('/rescan', {
        schema: {
            tags: ['Models'],
            summary: 'Rescan models directory',
        },
    }, async (request, reply) => {
        const config = getConfig();
        const factory = getProviderFactory(config);
        const scanner = factory.getScanner();

        // P2-FIX: Read dynamic path from Settings, fallback to default config
        let modelsDir = config.storage.modelsDir;
        try {
            const watchFoldersSetting = await prisma.setting.findUnique({
                where: { key: 'watchFolders' }
            });
            if (watchFoldersSetting) {
                const watchFolders = JSON.parse(watchFoldersSetting.valueJson);
                if (watchFolders?.models) {
                    modelsDir = watchFolders.models;
                }
            }
        } catch (e) {
            console.warn('[Models] Failed to read watchFolders setting:', e);
        }

        const result = await scanner.scanModels(modelsDir);

        return {
            success: true,
            added: result.added,
            updated: result.updated,
            removed: result.removed,
            errors: result.errors,
        };
    });

    // POST /api/models/import - Import local model
    fastify.post('/import', {
        schema: {
            tags: ['Models'],
            summary: 'Import local model',
            body: {
                type: 'object',
                properties: {
                    path: { type: 'string' },
                    name: { type: 'string' },
                },
            },
        },
    }, async (request, reply) => {
        const body = request.body as { path: string; name?: string };
        const fs = await import('fs');
        const pathModule = await import('path');

        // Validate path exists
        if (!fs.existsSync(body.path)) {
            return reply.status(400).send({ error: `Path not found: ${body.path}` });
        }

        // Extract model name
        const modelName = body.name || pathModule.basename(body.path);

        // Detect quantization type
        let quantization = 'None';
        if (modelName.toLowerCase().includes('gguf')) quantization = 'GGUF';
        else if (modelName.toLowerCase().includes('gptq') || modelName.toLowerCase().includes('4bit')) quantization = '4-bit';
        else if (modelName.toLowerCase().includes('awq')) quantization = 'AWQ';
        else if (modelName.toLowerCase().includes('8bit')) quantization = '8-bit';

        // Detect parameter count
        let params = 'Unknown';
        const paramMatch = modelName.match(/(\d+(?:\.\d+)?)[Bb]/);
        if (paramMatch) {
            params = `${paramMatch[1]}B`;
        }

        // Create model record
        const model = await prisma.model.create({
            data: {
                name: modelName,
                path: body.path,
                backend: 'transformers',
                source: 'Local',
                quantization,
                params,
                status: 'valid',
            },
        });

        return { id: model.id, name: model.name, status: 'imported' };
    });

    // DELETE /api/models/:id - Delete model record (does not delete local files)
    fastify.delete<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Models'],
            summary: 'Delete model record (does not delete local files)',
        },
    }, async (request, reply) => {
        const model = await prisma.model.findUnique({
            where: { id: request.params.id },
        });

        if (!model) {
            return reply.status(404).send({ error: 'Model not found' });
        }

        await prisma.model.delete({
            where: { id: request.params.id },
        });

        return { success: true, message: 'Model record deleted (local files preserved)' };
    });
}
