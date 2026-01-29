import { FastifyInstance } from 'fastify';
import { CompareRequest, CompareResponse } from '../types/index.js';
import { prisma } from '../db/prisma-client.js';

export async function compareRoutes(fastify: FastifyInstance) {

    // POST /api/compare - 比较两个运行
    fastify.post('/', {
        schema: {
            tags: ['Compare'],
            summary: '比较两个运行',
            body: {
                type: 'object',
                required: ['baseRunId', 'candidateRunId'],
                properties: {
                    baseRunId: { type: 'string' },
                    candidateRunId: { type: 'string' },
                },
            },
        },
    }, async (request, reply) => {
        const { baseRunId, candidateRunId } = request.body as CompareRequest;

        const [baseRun, candidateRun] = await Promise.all([
            prisma.run.findUnique({ where: { id: baseRunId } }),
            prisma.run.findUnique({ where: { id: candidateRunId } }),
        ]);

        if (!baseRun || !candidateRun) {
            return reply.status(404).send({ error: 'One or both runs not found' });
        }

        // Helper to safely parse JSON
        const safeParse = (jsonString: string | null | undefined, fallback: any = {}) => {
            if (!jsonString) return fallback;
            try {
                return JSON.parse(jsonString);
            } catch (e) {
                console.error('Failed to parse JSON:', e);
                return fallback;
            }
        };

        const baseMetrics = safeParse(baseRun.metricsJson);
        const candidateMetrics = safeParse(candidateRun.metricsJson);

        // Also check evalResultJson for metrics (especially for eval runs)
        const baseEval = safeParse(baseRun.evalResultJson);
        const candidateEval = safeParse(candidateRun.evalResultJson);

        // Merge metrics: prioritize metricsJson, but fallback/enhance with eval results
        // For eval runs, evalResultJson usually contains the rich data
        if (baseEval?.metrics_overall) {
            Object.assign(baseMetrics, baseEval.metrics_overall);
        }
        if (candidateEval?.metrics_overall) {
            Object.assign(candidateMetrics, candidateEval.metrics_overall);
        }

        const baseConfig = JSON.parse(baseRun.configJson);
        const candidateConfig = JSON.parse(candidateRun.configJson);

        // 定义训练参数和评测参数
        const trainingParams = ['lr', 'epochs', 'batchSize', 'gradAccum', 'maxSeqLen', 'quantization', 'useLora', 'loraRank', 'loraAlpha', 'optimizer', 'scheduler', 'warmupRatio', 'precision'];
        const evalParams = ['evaluator', 'k', 'temperature', 'numSamples', 'timeout', 'maxTokens', 'memoryLimit', 'generateReport', 'saveFailureCases'];

        // 计算配置差异
        const configDiff: Array<{ param: string; base: any; candidate: any; category?: string }> = [];
        const allKeys = new Set([...Object.keys(baseConfig), ...Object.keys(candidateConfig)]);

        const sameType = baseRun.type === candidateRun.type;

        for (const key of allKeys) {
            const baseValue = baseConfig[key];
            const candidateValue = candidateConfig[key];

            // 跳过两边都是 null/undefined 的情况
            if ((baseValue === null || baseValue === undefined) &&
                (candidateValue === null || candidateValue === undefined)) {
                continue;
            }

            // 确定参数分类
            let category = 'other';
            if (trainingParams.includes(key)) {
                category = 'training';
            } else if (evalParams.includes(key)) {
                category = 'evaluation';
            }

            if (sameType) {
                // 同类型运行：只显示不同的配置
                if (JSON.stringify(baseValue) !== JSON.stringify(candidateValue)) {
                    configDiff.push({
                        param: key,
                        base: baseValue ?? null,
                        candidate: candidateValue ?? null,
                        category,
                    });
                }
            } else {
                // 不同类型运行：显示有值的配置（跳过不相关的 null）
                // 训练运行显示训练参数，评测运行显示评测参数
                const trainingTypes = ['finetune', 'lora', 'pretrain'];
                const baseIsTraining = trainingTypes.includes(baseRun.type);
                const candidateIsTraining = trainingTypes.includes(candidateRun.type);

                // 训练参数：只在有训练运行时显示
                if (category === 'training' && !baseIsTraining && !candidateIsTraining) {
                    continue;
                }
                // 评测参数：只在有评测运行时显示
                if (category === 'evaluation' && baseIsTraining && candidateIsTraining) {
                    continue;
                }

                configDiff.push({
                    param: key,
                    base: baseValue ?? null,
                    candidate: candidateValue ?? null,
                    category,
                });
            }
        }

        // 按分类排序：training -> evaluation -> other
        const categoryOrder = { training: 0, evaluation: 1, other: 2 };
        configDiff.sort((a, b) => (categoryOrder[a.category as keyof typeof categoryOrder] || 2) - (categoryOrder[b.category as keyof typeof categoryOrder] || 2));

        // Collect all unique metric keys
        const metricKeys = new Set([...Object.keys(baseMetrics), ...Object.keys(candidateMetrics)]);
        const metrics: Record<string, { base: number | null; candidate: number | null; delta: number | null }> = {};

        for (const key of metricKeys) {
            const baseVal = baseMetrics[key];
            const candidateVal = candidateMetrics[key];

            // Only include number types for comparison
            if (typeof baseVal !== 'number' && typeof candidateVal !== 'number') continue;
            // Skip if both are null/undefined
            if (baseVal == null && candidateVal == null) continue;

            const b = typeof baseVal === 'number' ? baseVal : null;
            const c = typeof candidateVal === 'number' ? candidateVal : null;
            let delta: number | null = null;

            if (b !== null && c !== null) {
                delta = c - b;
            }

            metrics[key] = {
                base: b,
                candidate: c,
                delta
            };
        }

        // Fetch full metric history for both runs
        const [baseHistoryRaw, candidateHistoryRaw] = await Promise.all([
            prisma.runMetric.findMany({
                where: { runId: baseRunId },
                orderBy: { step: 'asc' },
                select: {
                    timestamp: true,
                    step: true,
                    loss: true,
                    passAt1: true,
                    compileRate: true,
                    extraJson: true // Assuming this might have other metrics
                }
            }),
            prisma.runMetric.findMany({
                where: { runId: candidateRunId },
                orderBy: { step: 'asc' },
                select: {
                    timestamp: true,
                    step: true,
                    loss: true,
                    passAt1: true,
                    compileRate: true,
                    extraJson: true
                }
            })
        ]);

        // Transform history into standard MetricEvent format
        const transformHistory = (metrics: typeof baseHistoryRaw) => {
            return metrics
                .map(m => {
                    const extra = m.extraJson ? JSON.parse(m.extraJson) : {};
                    return {
                        type: 'metric' as const,
                        timestamp: m.timestamp.toISOString(),
                        step: m.step,
                        loss: m.loss ?? undefined,
                        passAt1: m.passAt1 ?? undefined,
                        compileRate: m.compileRate ?? undefined,
                        lr: extra.lr,
                        ...extra
                    };
                })
                .filter(m => m.loss != null || m.passAt1 != null);  // 保留有 loss 或 passAt1 的有效记录
        };

        const response: CompareResponse = {
            metrics,
            configDiff,
            regressions: [],
            history: {
                base: transformHistory(baseHistoryRaw),
                candidate: transformHistory(candidateHistoryRaw)
            }
        };

        return response;
    });
}
