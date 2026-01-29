import { FastifyInstance } from 'fastify';
import { CompareRequest, CompareResponse } from '../types/index.js';
import { prisma } from '../db/prisma-client.js';

export async function compareRoutes(fastify: FastifyInstance) {

    // POST /api/compare - Compare two runs
    fastify.post('/', {
        schema: {
            tags: ['Compare'],
            summary: 'Compare two runs',
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

        // Define training parameters and evaluation parameters
        const trainingParams = ['lr', 'epochs', 'batchSize', 'gradAccum', 'maxSeqLen', 'quantization', 'useLora', 'loraRank', 'loraAlpha', 'optimizer', 'scheduler', 'warmupRatio', 'precision'];
        const evalParams = ['evaluator', 'k', 'temperature', 'numSamples', 'timeout', 'maxTokens', 'memoryLimit', 'generateReport', 'saveFailureCases'];

        // Calculate configuration differences
        const configDiff: Array<{ param: string; base: any; candidate: any; category?: string }> = [];
        const allKeys = new Set([...Object.keys(baseConfig), ...Object.keys(candidateConfig)]);

        const sameType = baseRun.type === candidateRun.type;

        for (const key of allKeys) {
            const baseValue = baseConfig[key];
            const candidateValue = candidateConfig[key];

            // Skip cases where both are null/undefined
            if ((baseValue === null || baseValue === undefined) &&
                (candidateValue === null || candidateValue === undefined)) {
                continue;
            }

            // Determine parameter category
            let category = 'other';
            if (trainingParams.includes(key)) {
                category = 'training';
            } else if (evalParams.includes(key)) {
                category = 'evaluation';
            }

            if (sameType) {
                // Same type runs: only show different configurations
                if (JSON.stringify(baseValue) !== JSON.stringify(candidateValue)) {
                    configDiff.push({
                        param: key,
                        base: baseValue ?? null,
                        candidate: candidateValue ?? null,
                        category,
                    });
                }
            } else {
                // Different type runs: show configurations with values (skip irrelevant nulls)
                // Training runs show training params, evaluation runs show eval params
                const trainingTypes = ['finetune', 'lora', 'pretrain'];
                const baseIsTraining = trainingTypes.includes(baseRun.type);
                const candidateIsTraining = trainingTypes.includes(candidateRun.type);

                // Training params: only show when there is a training run
                if (category === 'training' && !baseIsTraining && !candidateIsTraining) {
                    continue;
                }
                // Eval params: only show when there is an evaluation run
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

        // Sort by category: training -> evaluation -> other
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
                .filter(m => m.loss != null || m.passAt1 != null);  // Keep valid records with loss or passAt1
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
