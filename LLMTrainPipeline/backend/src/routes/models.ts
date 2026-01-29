import { FastifyInstance } from 'fastify';
import { getProviderFactory } from '../providers/factory.js';
import { getConfig } from '../config/index.js';
import { ModelResponse } from '../types/index.js';
import { prisma } from '../db/prisma-client.js';

export async function modelsRoutes(fastify: FastifyInstance) {

    // GET /api/models - 获取所有模型
    fastify.get('/', {
        schema: {
            tags: ['Models'],
            summary: '获取所有模型',
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

    // GET /api/models/:id - 获取模型详情
    fastify.get<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Models'],
            summary: '获取模型详情',
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

    // POST /api/models/rescan - 重新扫描模型目录
    fastify.post('/rescan', {
        schema: {
            tags: ['Models'],
            summary: '重新扫描模型目录',
        },
    }, async (request, reply) => {
        const config = getConfig();
        const factory = getProviderFactory(config);
        const scanner = factory.getScanner();

        // P2-FIX: 从 Settings 读取动态路径，fallback 到默认配置
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

    // POST /api/models/import - 导入本地模型
    fastify.post('/import', {
        schema: {
            tags: ['Models'],
            summary: '导入本地模型',
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

        // 验证路径存在
        if (!fs.existsSync(body.path)) {
            return reply.status(400).send({ error: `Path not found: ${body.path}` });
        }

        // 提取模型名
        const modelName = body.name || pathModule.basename(body.path);

        // 检测量化类型
        let quantization = 'None';
        if (modelName.toLowerCase().includes('gguf')) quantization = 'GGUF';
        else if (modelName.toLowerCase().includes('gptq') || modelName.toLowerCase().includes('4bit')) quantization = '4-bit';
        else if (modelName.toLowerCase().includes('awq')) quantization = 'AWQ';
        else if (modelName.toLowerCase().includes('8bit')) quantization = '8-bit';

        // 检测参数量
        let params = 'Unknown';
        const paramMatch = modelName.match(/(\d+(?:\.\d+)?)[Bb]/);
        if (paramMatch) {
            params = `${paramMatch[1]}B`;
        }

        // 创建模型记录
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

    // DELETE /api/models/:id - 删除模型记录（不删除本地文件）
    fastify.delete<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Models'],
            summary: '删除模型记录（不删除本地文件）',
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
