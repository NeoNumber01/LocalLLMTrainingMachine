import { FastifyInstance } from 'fastify';
import { resolveConfig } from '../config/index.js';
import { prisma } from '../db/prisma-client.js';

export async function configRoutes(fastify: FastifyInstance) {

    // GET /api/config/resolved - 获取合并后的配置
    fastify.get('/resolved', {
        schema: {
            tags: ['Config'],
            summary: '获取合并后生效配置',
            querystring: {
                type: 'object',
                properties: {
                    runId: { type: 'string' },
                    profileName: { type: 'string' },
                },
            },
        },
    }, async (request, reply) => {
        const query = request.query as { runId?: string; profileName?: string };

        let profileName = query.profileName || 'single_gpu';
        let runOverride = {};

        // 如果提供了 runId，从数据库加载运行配置
        if (query.runId) {
            const run = await prisma.run.findUnique({
                where: { id: query.runId },
            });

            if (run) {
                profileName = run.profileName;
                runOverride = JSON.parse(run.configJson);
            }
        }

        // 合并三层配置
        const config = resolveConfig(profileName, runOverride);

        return {
            profileName,
            resolved: config,
            layers: {
                defaults: 'src/config/defaults.yaml',
                profile: `src/config/profiles/${profileName}.yaml`,
                runOverride: query.runId ? `Run ${query.runId} config` : 'none',
            },
        };
    });

    // GET /api/config/profiles - 列出可用的配置文件
    fastify.get('/profiles', {
        schema: {
            tags: ['Config'],
            summary: '列出可用的配置文件',
        },
    }, async (request, reply) => {
        return {
            profiles: [
                { name: 'single_gpu', description: '单 GPU 配置' },
                { name: 'multi_gpu_fsdp', description: '多 GPU FSDP 配置' },
            ],
        };
    });
}
