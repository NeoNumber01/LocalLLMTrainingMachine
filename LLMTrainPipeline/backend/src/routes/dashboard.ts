import { FastifyInstance } from 'fastify';
import { getQueueStatus } from '../services/run-executor.js';
import { getDashboardSystemInfo } from '../services/system-monitor.js';
import { DashboardOverview, RunResponse } from '../types/index.js';
import { prisma } from '../db/prisma-client.js';

export async function dashboardRoutes(fastify: FastifyInstance) {
    // GET /api/dashboard/overview
    fastify.get('/overview', {
        schema: {
            tags: ['Dashboard'],
            summary: '获取仪表盘概览',
            response: {
                200: {
                    type: 'object',
                    properties: {
                        systemHealth: { type: 'string' },
                        activeRuns: { type: 'number' },
                        queuedRuns: { type: 'number' },
                        gpuUsage: { type: 'string' },
                        gpuAvailable: { type: 'boolean' },
                        gpuName: { type: 'string' },
                        storage: {
                            type: 'object',
                            properties: {
                                used: { type: 'string' },
                                free: { type: 'string' },
                            },
                        },
                        recentRuns: { type: 'array' },
                    },
                },
            },
        },
    }, async (request, reply) => {
        // 并行获取所有数据
        const [runStats, systemInfo] = await Promise.all([
            // 获取运行统计
            Promise.all([
                prisma.run.count({ where: { status: 'running' } }),
                prisma.run.count({ where: { status: 'queued' } }),
                prisma.run.findMany({
                    take: 10,
                    orderBy: { createdAt: 'desc' },
                    include: { model: true, dataset: true },
                }),
            ]),
            // 获取系统监控信息 (使用 backend storage 路径检测磁盘)
            getDashboardSystemInfo(process.cwd()),
        ]);

        const [activeRuns, queuedRuns, recentRuns] = runStats;

        // 转换 runs 为前端格式
        const formattedRuns: RunResponse[] = recentRuns.map(run => {
            const metrics = run.metricsJson ? JSON.parse(run.metricsJson) : { loss: 0, passAt1: 0, compileRate: 0 };
            const config = JSON.parse(run.configJson);

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
                artifacts: [],
            };
        });

        const overview: DashboardOverview & { gpuAvailable?: boolean; gpuName?: string } = {
            systemHealth: systemInfo.systemHealth as 'Healthy' | 'Warning' | 'Error',
            activeRuns,
            queuedRuns,
            gpuUsage: systemInfo.gpuUsage,
            gpuAvailable: systemInfo.gpuDeviceCount > 0,
            gpuName: systemInfo.gpuName,
            storage: systemInfo.storage,
            recentRuns: formattedRuns,
        };

        return overview;
    });
}
