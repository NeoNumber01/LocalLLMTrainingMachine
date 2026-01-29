import { FastifyInstance } from 'fastify';
import { prisma } from '../db/prisma-client.js';
import { SettingsResponse, UpdateSettingsDto } from '../types/index.js';

const DEFAULT_SETTINGS: SettingsResponse = {
    watchFolders: {
        models: './storage/models',
        datasets: './storage/datasets',
        adapters: './storage/adapters',
    },
    compute: {
        maxSimultaneousRuns: 1,
        gpuStrategy: 'DDP',
    },
    notifications: {
        runCompletion: true,
        resourceAlerts: true,
    },
    storage: {
        checkpointRetention: 3,  // 0 = keep all, N = keep last N
    },
};

export async function settingsRoutes(fastify: FastifyInstance) {

    // GET /api/settings - 获取设置
    fastify.get('/', {
        schema: {
            tags: ['Settings'],
            summary: '获取设置',
        },
    }, async (request, reply) => {
        // 尝试从数据库加载设置
        const settings: Record<string, any> = {};

        const dbSettings = await prisma.setting.findMany();
        for (const s of dbSettings) {
            settings[s.key] = JSON.parse(s.valueJson);
        }

        // 合并默认设置
        return {
            watchFolders: settings.watchFolders || DEFAULT_SETTINGS.watchFolders,
            compute: settings.compute || DEFAULT_SETTINGS.compute,
            notifications: settings.notifications || DEFAULT_SETTINGS.notifications,
            storage: settings.storage || DEFAULT_SETTINGS.storage,
        };
    });

    // PUT /api/settings - 更新设置
    fastify.put('/', {
        schema: {
            tags: ['Settings'],
            summary: '更新设置',
            body: {
                type: 'object',
                properties: {
                    watchFolders: {
                        type: 'object',
                        properties: {
                            models: { type: 'string' },
                            datasets: { type: 'string' },
                            adapters: { type: 'string' },
                        },
                    },
                    compute: {
                        type: 'object',
                        properties: {
                            maxSimultaneousRuns: { type: 'number' },
                            gpuStrategy: { type: 'string', enum: ['DDP', 'FSDP', 'DeepSpeed'] },
                        },
                    },
                    notifications: {
                        type: 'object',
                        properties: {
                            runCompletion: { type: 'boolean' },
                            resourceAlerts: { type: 'boolean' },
                        },
                    },
                    storage: {
                        type: 'object',
                        properties: {
                            checkpointRetention: { type: 'number', minimum: 0 },  // 0 = keep all
                        },
                    },
                },
            },
        },
    }, async (request, reply) => {
        const updates = request.body as UpdateSettingsDto;

        // 更新各个设置项
        for (const [key, value] of Object.entries(updates)) {
            if (value !== undefined) {
                await prisma.setting.upsert({
                    where: { key },
                    update: { valueJson: JSON.stringify(value) },
                    create: { key, valueJson: JSON.stringify(value) },
                });
            }
        }

        return { success: true };
    });
}
