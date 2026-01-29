import { EventEmitter } from 'events';
import { v4 as uuid } from 'uuid';
import { getProviderFactory } from '../providers/factory.js';
import { resolveConfig, Config } from '../config/index.js';
import { RunStatus, SSEEvent } from '../types/index.js';
import * as path from 'path';
import * as fs from 'fs';
import { prisma } from '../db/prisma-client.js';
import { autoBackupNewAdapter } from './adapter-guard.js';
import { createNotification } from './notification-service.js';

// ============================================================
// P0-FIX: Batch log buffer - resolve SQLite high-frequency write pressure
// ============================================================
interface LogEvent {
    runId: string;
    level: string;
    message: string;
}

class LogEventBuffer {
    private buffer: LogEvent[] = [];
    private flushTimer: NodeJS.Timeout | null = null;
    private readonly maxSize: number;
    private readonly flushIntervalMs: number;

    constructor(maxSize = 50, flushIntervalMs = 2000) {
        this.maxSize = maxSize;
        this.flushIntervalMs = flushIntervalMs;
    }

    /**
     * Add log event to buffer
     * Auto flush when reaching maxSize
     */
    push(event: LogEvent): void {
        this.buffer.push(event);

        // Start timer on first add
        if (this.buffer.length === 1 && !this.flushTimer) {
            this.flushTimer = setTimeout(() => this.flush(), this.flushIntervalMs);
        }

        // Flush immediately when limit is reached
        if (this.buffer.length >= this.maxSize) {
            this.flush();
        }
    }

    /**
     * Batch write all logs in buffer
     */
    async flush(): Promise<void> {
        if (this.flushTimer) {
            clearTimeout(this.flushTimer);
            this.flushTimer = null;
        }

        if (this.buffer.length === 0) return;

        const eventsToWrite = [...this.buffer];
        this.buffer = [];

        try {
            await prisma.runEvent.createMany({
                data: eventsToWrite,
            });
            // console.log(`[LogEventBuffer] Flushed ${eventsToWrite.length} events`);
        } catch (error) {
            console.error('[LogEventBuffer] Failed to flush events:', error);
            // Try writing one by one on failure to avoid data loss
            for (const event of eventsToWrite) {
                try {
                    await prisma.runEvent.create({ data: event });
                } catch (e) {
                    console.error('[LogEventBuffer] Failed to write single event:', e);
                }
            }
        }
    }

    /**
     * Clear buffer (without writing)
     */
    clear(): void {
        if (this.flushTimer) {
            clearTimeout(this.flushTimer);
            this.flushTimer = null;
        }
        this.buffer = [];
    }
}

// One buffer per Run
const logBuffers = new Map<string, LogEventBuffer>();

function getLogBuffer(runId: string): LogEventBuffer {
    if (!logBuffers.has(runId)) {
        logBuffers.set(runId, new LogEventBuffer());
    }
    return logBuffers.get(runId)!;
}

async function removeLogBuffer(runId: string): Promise<void> {
    const buffer = logBuffers.get(runId);
    if (buffer) {
        await buffer.flush(); // Ensure all logs are written
        logBuffers.delete(runId);
    }
}

// Run event management
const runEmitters = new Map<string, EventEmitter>();

export function getRunEmitter(runId: string): EventEmitter {
    if (!runEmitters.has(runId)) {
        runEmitters.set(runId, new EventEmitter());
    }
    return runEmitters.get(runId)!;
}

export function removeRunEmitter(runId: string): void {
    const emitter = runEmitters.get(runId);
    if (emitter) {
        emitter.removeAllListeners();
        runEmitters.delete(runId);
    }
}

// Simple task queue
interface QueuedRun {
    runId: string;
    config: Config;
}

const runQueue: QueuedRun[] = [];
let isProcessing = false;

// Track active processes so they can be stopped
import type { TrainerProvider, EvalProvider } from '../providers/interfaces.js';
interface ActiveRun {
    trainer?: TrainerProvider;
    evaluator?: EvalProvider;
}
const activeRuns = new Map<string, ActiveRun>();

// Helper: Convert frontend flat config to nested structure
function prepareConfigOverride(configOverride: any): any {
    const nestedOverride: any = {};

    // Training config
    if (configOverride.lr !== undefined ||
        configOverride.epochs !== undefined ||
        configOverride.batchSize !== undefined ||
        configOverride.gradAccum !== undefined ||
        configOverride.maxSeqLen !== undefined ||
        configOverride.warmupRatio !== undefined ||
        configOverride.weightDecay !== undefined ||
        configOverride.optimizer !== undefined ||
        configOverride.scheduler !== undefined ||
        configOverride.precision !== undefined ||
        configOverride.seed !== undefined ||
        configOverride.loggingSteps !== undefined ||
        configOverride.saveSteps !== undefined ||
        configOverride.saveTotalLimit !== undefined ||
        configOverride.gradientClipping !== undefined ||
        configOverride.warmupType !== undefined ||
        configOverride.warmupSteps !== undefined ||
        configOverride.evalStrategy !== undefined ||
        configOverride.evalSteps !== undefined ||
        configOverride.earlyStoppingEnabled !== undefined ||
        configOverride.earlyStoppingPatience !== undefined ||
        configOverride.earlyStoppingThreshold !== undefined ||
        configOverride.loadBestModelAtEnd !== undefined ||
        configOverride.metricForBestModel !== undefined) {
        nestedOverride.training = {
            ...(configOverride.lr !== undefined && { lr: configOverride.lr }),
            ...(configOverride.epochs !== undefined && { epochs: configOverride.epochs }),
            ...(configOverride.batchSize !== undefined && { batchSize: configOverride.batchSize }),
            ...(configOverride.gradAccum !== undefined && { gradAccum: configOverride.gradAccum }),
            ...(configOverride.maxSeqLen !== undefined && { maxSeqLen: configOverride.maxSeqLen }),
            ...(configOverride.warmupRatio !== undefined && { warmupRatio: configOverride.warmupRatio }),
            ...(configOverride.weightDecay !== undefined && { weightDecay: configOverride.weightDecay }),
            ...(configOverride.optimizer !== undefined && { optimizer: configOverride.optimizer }),
            ...(configOverride.scheduler !== undefined && { scheduler: configOverride.scheduler }),
            ...(configOverride.precision !== undefined && { precision: configOverride.precision }),
            ...(configOverride.seed !== undefined && { seed: configOverride.seed }),
            ...(configOverride.loggingSteps !== undefined && { loggingSteps: configOverride.loggingSteps }),
            ...(configOverride.saveSteps !== undefined && { saveSteps: configOverride.saveSteps }),
            ...(configOverride.saveTotalLimit !== undefined && { saveTotalLimit: configOverride.saveTotalLimit }),
            ...(configOverride.gradientClipping !== undefined && { gradientClipping: configOverride.gradientClipping }),
            ...(configOverride.warmupType !== undefined && { warmupType: configOverride.warmupType }),
            ...(configOverride.warmupSteps !== undefined && { warmupSteps: configOverride.warmupSteps }),
            ...(configOverride.evalStrategy !== undefined && { evalStrategy: configOverride.evalStrategy }),
            ...(configOverride.evalSteps !== undefined && { evalSteps: configOverride.evalSteps }),
            ...(configOverride.earlyStoppingEnabled !== undefined && { earlyStoppingEnabled: configOverride.earlyStoppingEnabled }),
            ...(configOverride.earlyStoppingPatience !== undefined && { earlyStoppingPatience: configOverride.earlyStoppingPatience }),
            ...(configOverride.earlyStoppingThreshold !== undefined && { earlyStoppingThreshold: configOverride.earlyStoppingThreshold }),
            ...(configOverride.loadBestModelAtEnd !== undefined && { loadBestModelAtEnd: configOverride.loadBestModelAtEnd }),
            ...(configOverride.metricForBestModel !== undefined && { metricForBestModel: configOverride.metricForBestModel }),
        };
    }

    // LoRA config
    if (configOverride.useLora !== undefined ||
        configOverride.loraRank !== undefined ||
        configOverride.loraAlpha !== undefined ||
        configOverride.loraTargetModules !== undefined ||
        configOverride.quantization !== undefined ||
        configOverride.loraDropout !== undefined ||
        configOverride.loraBias !== undefined) {
        nestedOverride.lora = {
            ...(configOverride.useLora !== undefined && { enabled: configOverride.useLora }),
            ...(configOverride.loraRank !== undefined && { rank: configOverride.loraRank }),
            ...(configOverride.loraAlpha !== undefined && { alpha: configOverride.loraAlpha }),
            ...(configOverride.loraTargetModules !== undefined && { targetModules: configOverride.loraTargetModules }),
            ...(configOverride.quantization !== undefined && { quantization: configOverride.quantization }),
            ...(configOverride.loraDropout !== undefined && { dropout: configOverride.loraDropout }),
            ...(configOverride.loraBias !== undefined && { bias: configOverride.loraBias }),
        };
    }

    // Eval config
    if (configOverride.k !== undefined ||
        configOverride.numSamples !== undefined ||
        configOverride.temperature !== undefined ||
        configOverride.maxTokens !== undefined ||
        configOverride.timeout !== undefined ||
        configOverride.memoryLimit !== undefined ||
        configOverride.generateReport !== undefined ||
        configOverride.saveFailureCases !== undefined) {
        nestedOverride.eval = {
            ...(configOverride.k !== undefined && { k: configOverride.k }),
            ...(configOverride.numSamples !== undefined && { numSamples: configOverride.numSamples }),
            ...(configOverride.temperature !== undefined && { temperature: configOverride.temperature }),
            ...(configOverride.maxTokens !== undefined && { maxTokens: configOverride.maxTokens }),
            ...(configOverride.timeout !== undefined && { timeout: configOverride.timeout }),
            ...(configOverride.memoryLimit !== undefined && { memoryLimit: configOverride.memoryLimit }),
            ...(configOverride.generateReport !== undefined && { generateReport: configOverride.generateReport }),
            ...(configOverride.saveFailureCases !== undefined && { saveFailureCases: configOverride.saveFailureCases }),
        };
    }

    // Pass through existing nested configs
    if (configOverride.training) nestedOverride.training = { ...nestedOverride.training, ...configOverride.training };
    if (configOverride.lora) nestedOverride.lora = { ...nestedOverride.lora, ...configOverride.lora };
    if (configOverride.eval) nestedOverride.eval = configOverride.eval;
    if (configOverride.providers) nestedOverride.providers = configOverride.providers;
    if (configOverride.storage) nestedOverride.storage = configOverride.storage;

    return nestedOverride;
}

// P0-SAFETY: Restore queue state
export async function restoreQueue(): Promise<void> {
    console.log('[RunExecutor] Restoring queue state...');

    // 1. Handle unexpectedly interrupted running tasks -> restore to queue to continue execution (not mark failed)
    // This way server restart (e.g. tsx watch hot reload) won't cause task loss
    const interruptedRuns = await prisma.run.findMany({
        where: { status: 'running' },
    });

    for (const run of interruptedRuns) {
        console.log(`[RunExecutor] Restoring interrupted run ${run.id} to queue (will resume)`);

        // Calculate new queue position (put at front for priority execution)
        const minPositionRun = await prisma.run.findFirst({
            where: { status: 'queued', queuePosition: { not: null } },
            orderBy: { queuePosition: 'asc' },
        });
        const newPosition = Math.max(0, (minPositionRun?.queuePosition ?? 1) - 1);

        await prisma.run.update({
            where: { id: run.id },
            data: {
                status: 'queued',
                queuePosition: newPosition,
                // Keep startedAt for tracking
            },
        });
        await prisma.runEvent.create({
            data: {
                runId: run.id,
                level: 'warning',
                message: 'Run interrupted by server restart, automatically re-queued to resume',
            },
        });
    }

    // 2. Restore queued tasks to memory queue
    const queuedRuns = await prisma.run.findMany({
        where: { status: 'queued' },
        orderBy: { queuePosition: 'asc' },
    });

    if (queuedRuns.length > 0) {
        console.log(`[RunExecutor] Restoring ${queuedRuns.length} runs to queue`);
        for (const run of queuedRuns) {
            try {
                const overrides = JSON.parse(run.configJson);
                const nestedOverride = prepareConfigOverride(overrides);
                // P0-FIX: Resolve full config before pushing to queue
                const config = resolveConfig(run.profileName || 'single_gpu', nestedOverride);

                runQueue.push({ runId: run.id, config });
            } catch (e) {
                console.error(`[RunExecutor] Failed to restore run ${run.id}:`, e);
                // Mark as failed to avoid stuck in queued
                await prisma.run.update({
                    where: { id: run.id },
                    data: { status: 'failed' },
                });
            }
        }

        // If queue is not empty, start processing
        if (runQueue.length > 0) {
            processQueue();
        }
    }
}

export async function enqueueRun(runId: string, profileName: string, configOverride: any): Promise<void> {
    const nestedOverride = prepareConfigOverride(configOverride);
    const config = resolveConfig(profileName, nestedOverride);

    // Calculate queue position - get current max position + 1
    const maxPositionRun = await prisma.run.findFirst({
        where: { status: 'queued', queuePosition: { not: null } },
        orderBy: { queuePosition: 'desc' },
    });
    const newPosition = (maxPositionRun?.queuePosition ?? 0) + 1;

    // Update queue position in database
    await prisma.run.update({
        where: { id: runId },
        data: { queuePosition: newPosition },
    });

    runQueue.push({ runId, config });

    if (!isProcessing) {
        processQueue();
    }
}

async function processQueue(): Promise<void> {
    if (isProcessing || runQueue.length === 0) return;

    isProcessing = true;

    try {
        // P1-FIX: Read max concurrent runs setting
        const maxConcurrent = await getMaxSimultaneousRuns();

        while (runQueue.length > 0) {
            // Get current active runs count
            const currentActive = activeRuns.size;

            // If max concurrent reached, wait
            if (currentActive >= maxConcurrent) {
                await new Promise(resolve => setTimeout(resolve, 1000));
                continue;
            }

            // Calculate number of tasks that can be started
            const slotsAvailable = maxConcurrent - currentActive;
            const jobsToStart = Math.min(slotsAvailable, runQueue.length);

            // Start multiple tasks concurrently
            const startPromises: Promise<void>[] = [];
            for (let i = 0; i < jobsToStart; i++) {
                const job = runQueue.shift();
                if (job) {
                    // Use non-blocking way to start task, let it run in background
                    startPromises.push(executeRun(job.runId, job.config).catch(e => {
                        console.error(`[RunExecutor] Task ${job.runId} failed:`, e);
                    }));
                }
            }

            // If maxConcurrent > 1, wait a short time after concurrent start before checking
            // If maxConcurrent = 1, wait for current task to complete
            if (maxConcurrent === 1 && startPromises.length > 0) {
                await Promise.all(startPromises);
            } else if (startPromises.length > 0) {
                // Wait a short time for tasks to register in activeRuns
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }

        // Wait for all active tasks to complete
        while (activeRuns.size > 0) {
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    } finally {
        isProcessing = false;
    }
}

/**
 * P1-FIX: Get max concurrent runs setting
 */
async function getMaxSimultaneousRuns(): Promise<number> {
    try {
        const setting = await prisma.setting.findUnique({
            where: { key: 'compute' }
        });
        if (setting) {
            const compute = JSON.parse(setting.valueJson);
            return compute?.maxSimultaneousRuns ?? 1;
        }
    } catch (e) {
        console.error('[RunExecutor] Failed to read maxSimultaneousRuns:', e);
    }
    return 1;  // Default single task
}

async function executeRun(runId: string, config: Config): Promise<void> {
    const emitter = getRunEmitter(runId);
    const factory = getProviderFactory(config);

    try {
        // Update status to running
        await prisma.run.update({
            where: { id: runId },
            data: {
                status: 'running',
                startedAt: new Date(),
            },
        });

        emitter.emit('event', {
            type: 'status',
            status: 'running',
        } as SSEEvent);

        // Get run information
        const run = await prisma.run.findUnique({
            where: { id: runId },
            include: { model: true, dataset: true },
        });

        if (!run) throw new Error(`Run not found: ${runId}`);

        const startTime = Date.now();

        // Dispatch execution based on run.type
        if (run.type === 'evaluation') {
            // ===== Evaluation Process =====
            console.log(`[RunExecutor] Starting evaluation for run ${runId}`);
            emitter.emit('event', {
                type: 'log',
                timestamp: new Date().toISOString(),
                level: 'info',
                message: 'Starting evaluation...',
            } as SSEEvent);

            // Save initial log event to database
            await prisma.runEvent.create({
                data: {
                    runId,
                    level: 'info',
                    message: 'Starting evaluation...',
                },
            });

            const evaluator = factory.getEvalProvider();

            // Register active process so it can be stopped
            activeRuns.set(runId, { evaluator });

            // Check if adapter is available
            let adapterPath: string | undefined;
            const adapterArtifact = await prisma.artifact.findFirst({
                where: { runId: runId, kind: 'adapter' },
            });
            if (adapterArtifact) {
                adapterPath = adapterArtifact.path;
            }

            // Use evalDatasetId if available, otherwise use datasetId
            let evalDatasetPath = run.dataset.path;
            if ((run as any).evalDatasetId) {
                const evalDataset = await prisma.dataset.findUnique({
                    where: { id: (run as any).evalDatasetId },
                });
                if (evalDataset) {
                    evalDatasetPath = evalDataset.path;
                }
            }

            // If streaming evaluation is supported, use streaming method
            let evalResult: any;
            if (evaluator.evaluateStream) {
                for await (const event of evaluator.evaluateStream({
                    runId,
                    modelPath: run.model.path,
                    adapterPath,
                    datasetPath: evalDatasetPath,
                    config,
                })) {
                    if (event.type === 'log') {
                        // P0-FIX: Use buffer for batch log writing, reduce SQLite write pressure
                        const logBuffer = getLogBuffer(runId);
                        logBuffer.push({
                            runId,
                            level: event.data.level || 'info',
                            message: event.data.message,
                        });

                        emitter.emit('event', {
                            type: 'log',
                            timestamp: event.timestamp.toISOString(),
                            level: event.data.level || 'info',
                            message: event.data.message,
                        } as SSEEvent);
                    } else if (event.type === 'progress') {
                        emitter.emit('event', {
                            type: 'progress',
                            timestamp: event.timestamp.toISOString(),
                            completed: event.data.completed,
                            total: event.data.total,
                            percent: event.data.percent,
                        } as SSEEvent);
                    } else if (event.type === 'complete') {
                        evalResult = event.data.result;
                    } else if (event.type === 'error') {
                        // P0-FIX: Error logs also use buffer
                        const logBuffer = getLogBuffer(runId);
                        logBuffer.push({
                            runId,
                            level: 'error',
                            message: event.data.message,
                        });

                        emitter.emit('event', {
                            type: 'log',
                            timestamp: event.timestamp.toISOString(),
                            level: 'error',
                            message: event.data.message,
                        } as SSEEvent);
                    } else if (event.type === 'metric') {
                        // P1: Handle real-time eval metrics from eval.py
                        const metricData = event.data;

                        // Save to RunMetric for historical tracking
                        await prisma.runMetric.create({
                            data: {
                                runId,
                                step: metricData.step,
                                loss: 0, // Evaluation doesn't have loss
                                extraJson: JSON.stringify({
                                    pass_at_1: metricData.pass_at_1,
                                    compile_rate: metricData.compile_rate,
                                    total_samples: metricData.total_samples,
                                    total_passed: metricData.total_passed,
                                    total_compiled: metricData.total_compiled,
                                    error_breakdown: metricData.error_breakdown,
                                }),
                            },
                        });

                        // Emit to frontend via SSE
                        emitter.emit('event', {
                            type: 'metric',
                            timestamp: event.timestamp.toISOString(),
                            step: metricData.step,
                            pass_at_1: metricData.pass_at_1,
                            compile_rate: metricData.compile_rate,
                            extra: {
                                total_samples: metricData.total_samples,
                                total_passed: metricData.total_passed,
                                total_compiled: metricData.total_compiled,
                                error_breakdown: metricData.error_breakdown,
                            }
                        } as SSEEvent);
                    } else if (event.type === 'artifact') {
                        const artifact = await prisma.artifact.create({
                            data: {
                                runId,
                                kind: event.data.kind || 'eval',
                                path: event.data.path,
                                size: event.data.size || 0,
                            },
                        });
                        emitter.emit('event', {
                            type: 'artifact',
                            artifact: {
                                id: artifact.id,
                                kind: artifact.kind,
                                path: artifact.path,
                                size: formatSize(artifact.size),
                                createdAt: artifact.createdAt.toISOString(),
                            }
                        } as any);
                    }
                }
            } else {
                // Fallback to non-streaming
                evalResult = await evaluator.evaluate({
                    runId,
                    modelPath: run.model.path,
                    adapterPath,
                    datasetPath: evalDatasetPath,
                    config,
                });
            }

            // P0-FIX: Read eval_summary.json to get complete metadata (including datasetInfo etc.)
            // eval.py saves complete logs to eval_summary.json after evaluation completes
            const evalSummaryPath = `./storage/runs/${runId}/eval_summary.json`;
            let fullEvalData: any = evalResult;
            try {
                const fs = await import('fs');
                if (fs.existsSync(evalSummaryPath)) {
                    const summaryContent = fs.readFileSync(evalSummaryPath, 'utf-8');
                    const evalSummary = JSON.parse(summaryContent);

                    // Merge complete metadata
                    fullEvalData = {
                        ...evalResult,
                        evalRunId: evalSummary.eval_run_id,
                        evalTime: evalSummary.eval_time,
                        seed: evalSummary.seed,
                        baseModelName: evalSummary.base_model_name,
                        checkpointPath: evalSummary.checkpoint_path,
                        datasetInfo: evalSummary.dataset_info,
                        generationConfig: evalSummary.generation_config,
                        judgeConfig: evalSummary.judge_config,
                        environment: evalSummary.environment,
                        // P0-FIX: Add missing Pass@5 and Pass@10 data
                        passAt1: evalSummary.metrics_overall?.pass_at_1 ?? evalResult.passAt1 ?? 0,
                        passAt5: evalSummary.metrics_overall?.pass_at_5 ?? 0,
                        passAt10: evalSummary.metrics_overall?.pass_at_10 ?? 0,
                        compileRate: evalSummary.metrics_overall?.compile_rate ?? evalResult.compileRate ?? 0,
                        codeQuality: evalSummary.code_quality ? {
                            avgCodeLength: evalSummary.code_quality.avg_code_length,
                            avgLineCount: evalSummary.code_quality.avg_line_count,
                            extraIORate: evalSummary.code_quality.extra_io_rate,
                            interfaceComplianceRate: evalSummary.code_quality.interface_compliance_rate,
                        } : evalResult.codeQuality,
                        segmentBreakdown: evalSummary.segment_breakdown,
                        // P1: Per-problem pass distribution
                        perProblemStats: evalSummary.per_problem_stats,
                        // P0: Failure examples by error type
                        failureExamplesByType: evalSummary.failure_examples_by_type,
                        // Sample results for failure cases
                        failureSamples: evalSummary.sample_results
                            ?.filter((s: any) => s.verdict !== 'passed')
                            ?.slice(0, 50)
                            ?.map((s: any) => ({
                                taskId: s.task_id,
                                difficulty: s.difficulty,
                                category: s.category,
                                verdict: s.verdict,
                                errorType: s.error_type,
                                traceback: s.traceback,  // Keep complete, don't truncate
                            })),
                    };
                    console.log(`[RunExecutor] Merged eval_summary.json for run ${runId} (dataset_info.total_problems: ${evalSummary.dataset_info?.total_problems || 'N/A'})`);
                }
            } catch (e) {
                console.warn(`[RunExecutor] Could not read eval_summary.json: ${e}`);
            }

            // Save evaluation results
            await prisma.run.update({
                where: { id: runId },
                data: {
                    status: 'success',
                    completedAt: new Date(),
                    duration: formatDuration(Date.now() - startTime),
                    evalResultJson: JSON.stringify(fullEvalData),
                    metricsJson: JSON.stringify({
                        loss: 0,
                        passAt1: evalResult.passAt1,
                        compileRate: evalResult.compileRate,
                    }),
                },
            });

            // Save evaluation results to artifacts
            const artifactStore = factory.getArtifactStore();
            const evalResultContent = JSON.stringify(evalResult, null, 2);
            await artifactStore.save(runId, 'eval', 'eval_result.json', Buffer.from(evalResultContent));
            const evalArtifact = await prisma.artifact.create({
                data: { runId, kind: 'eval', path: 'eval_result.json', size: evalResultContent.length },
            });
            emitter.emit('event', {
                type: 'artifact',
                artifact: {
                    id: evalArtifact.id,
                    kind: evalArtifact.kind,
                    path: evalArtifact.path,
                    size: formatSize(evalArtifact.size),
                    createdAt: evalArtifact.createdAt.toISOString(),
                }
            } as any);

            const completionMessage = `Evaluation completed. Pass@1: ${evalResult.passAt1}%, Compile Rate: ${evalResult.compileRate}%`;

            await prisma.runEvent.create({
                data: {
                    runId,
                    level: 'info',
                    message: completionMessage,
                },
            });

            emitter.emit('event', {
                type: 'log',
                timestamp: new Date().toISOString(),
                level: 'info',
                message: completionMessage,
            } as SSEEvent);

            emitter.emit('event', {
                type: 'status',
                status: 'success',
            } as SSEEvent);

            console.log(`[RunExecutor] Evaluation complete for run ${runId}: Pass@1=${evalResult.passAt1}%`);

            // Create evaluation completion notification
            await createNotification(
                'run_completed',
                `Evaluation Completed: ${run.name}`,
                `Pass@1: ${evalResult.passAt1}%, Compile Rate: ${evalResult.compileRate}%`,
                runId
            );

        } else {
            // ===== Training Process =====
            // Resolve eval dataset path for training if it exists
            let evalDatasetPath: string | undefined;
            if ((run as any).evalDatasetId) {
                const evalDataset = await prisma.dataset.findUnique({
                    where: { id: (run as any).evalDatasetId },
                });
                if (evalDataset) {
                    evalDatasetPath = evalDataset.path;
                }
            }

            const trainer = factory.getTrainerProvider();

            // Register active process so it can be stopped
            activeRuns.set(runId, { trainer });

            for await (const event of trainer.train({
                runId,
                modelPath: run.model.path,
                datasetPath: run.dataset.path,
                evalDatasetPath: evalDatasetPath,
                outputDir: `./storage/runs/${runId}`,
                config,
            })) {
                if (event.type === 'log') {
                    // P0-FIX: Use buffer for batch log writing, reduce SQLite write pressure
                    const logBuffer = getLogBuffer(runId);
                    logBuffer.push({
                        runId,
                        level: event.data.level,
                        message: event.data.message,
                    });

                    emitter.emit('event', {
                        type: 'log',
                        timestamp: event.timestamp.toISOString(),
                        level: event.data.level,
                        message: event.data.message,
                    } as SSEEvent);
                } else if (event.type === 'metric') {
                    // Save metrics - create directly, no longer using upsert (unique constraint removed)
                    // console.log(`[RunExecutor] Saving metric for run ${runId}: step=${event.data.step}, loss=${event.data.loss}`);
                    await prisma.runMetric.create({
                        data: {
                            runId,
                            step: event.data.step,
                            loss: event.data.loss,
                            // P0-FIX: Add epoch to extraJson for report grouping statistics
                            extraJson: JSON.stringify({
                                lr: event.data.lr,
                                gradNorm: event.data.gradNorm,
                                epoch: event.data.epoch,
                            }),
                        },
                    });

                    emitter.emit('event', {
                        type: 'metric',
                        timestamp: event.timestamp.toISOString(),
                        step: event.data.step,
                        loss: event.data.loss,
                        // Send structured data to match frontend fetchRunMetrics format
                        extra: {
                            lr: event.data.lr,
                            grad_norm: event.data.gradNorm,
                            epoch: event.data.epoch,
                        }
                    } as SSEEvent);
                } else if (event.type === 'checkpoint') {
                    // Save checkpoint information
                    console.log(`[RunExecutor] Checkpoint event received: ${event.data.path}`);
                    const cpArtifact = await prisma.artifact.create({
                        data: {
                            runId,
                            kind: 'checkpoint',
                            path: event.data.path,
                            size: 0,
                        },
                    });

                    emitter.emit('event', {
                        type: 'artifact',
                        artifact: {
                            id: cpArtifact.id,
                            kind: cpArtifact.kind,
                            path: cpArtifact.path, // Full path or relative? Frontend usually displays name/path
                            name: path.basename(cpArtifact.path),
                            size: '0 B', // Size unknown until scanned, or 0
                            createdAt: cpArtifact.createdAt.toISOString(),
                        }
                    } as any);
                } else if (event.type === 'experiment_log') {
                    // Save experiment metadata (from experiment_logger.py)
                    const expLog = event.data;

                    // Update Run base fields
                    await prisma.run.update({
                        where: { id: runId },
                        data: {
                            seed: expLog.seed,
                            gitCommit: expLog.git_commit,
                            totalTokens: expLog.total_tokens,
                            totalSteps: expLog.total_steps,
                            tokensPerSecond: expLog.tokens_per_second,
                            gpuHours: expLog.gpu_hours,
                        },
                    });

                    // Save environment metadata
                    if (expLog.environment) {
                        await prisma.experimentMeta.upsert({
                            where: { runId },
                            create: {
                                runId,
                                osVersion: expLog.environment.os_version,
                                pythonVersion: expLog.environment.python_version,
                                pytorchVersion: expLog.environment.pytorch_version,
                                transformersVersion: expLog.environment.transformers_version,
                                trlVersion: expLog.environment.trl_version,
                                peftVersion: expLog.environment.peft_version,
                                cudaVersion: expLog.environment.cuda_version,
                                cudnnVersion: expLog.environment.cudnn_version,
                                bitsandbytesVersion: expLog.environment.bitsandbytes_version,
                                gpuModel: expLog.hardware?.gpu_model,
                                gpuMemoryGB: expLog.hardware?.gpu_memory_gb,
                                cpuModel: expLog.hardware?.cpu_model,
                                ramGB: expLog.hardware?.ram_gb,
                                startTime: expLog.start_time ? new Date(expLog.start_time) : undefined,
                                endTime: expLog.end_time ? new Date(expLog.end_time) : undefined,
                            },
                            update: {
                                endTime: expLog.end_time ? new Date(expLog.end_time) : undefined,
                            },
                        });
                    }

                    // Save LoRA stats (with exception protection to avoid interrupting subsequent processes like adapter registration)
                    if (expLog.lora_stats) {
                        try {
                            await prisma.loraStats.upsert({
                                where: { runId },
                                create: {
                                    runId,
                                    rank: expLog.lora_stats.rank,
                                    alpha: expLog.lora_stats.alpha,
                                    dropout: expLog.lora_stats.dropout,
                                    targetModules: JSON.stringify(expLog.lora_stats.target_modules),
                                    trainableParams: expLog.lora_stats.trainable_params,
                                    totalParams: expLog.lora_stats.total_params,
                                    trainablePercent: expLog.lora_stats.trainable_percent,
                                },
                                update: {},
                            });
                        } catch (loraStatsError: any) {
                            console.error('[RunExecutor] Failed to save LoRA stats:', loraStatsError.message);
                            // Log warning but don't interrupt execution, ensure subsequent adapter registration can proceed
                            await prisma.runEvent.create({
                                data: {
                                    runId,
                                    level: 'warning',
                                    message: `Failed to save LoRA stats: ${loraStatsError.message}`,
                                },
                            });
                            emitter.emit('event', {
                                type: 'log',
                                timestamp: new Date().toISOString(),
                                level: 'warning',
                                message: `Failed to save LoRA stats: ${loraStatsError.message}`,
                            } as SSEEvent);
                        }
                    }

                    // Save dataset metadata
                    if (expLog.dataset_info) {
                        await prisma.datasetMeta.upsert({
                            where: { runId },
                            create: {
                                runId,
                                source: expLog.dataset_info.source,
                                trainSamples: expLog.dataset_info.train_samples,
                                valSamples: expLog.dataset_info.val_samples,
                                testSamples: expLog.dataset_info.test_samples,
                                totalProblems: expLog.dataset_info.total_problems,
                                totalTokens: expLog.dataset_info.total_tokens,
                                promptTemplate: expLog.dataset_info.prompt_template,
                                outputFormat: expLog.dataset_info.output_format,
                                dedupeMethod: expLog.dataset_info.dedupe_method,
                                lengthFilter: expLog.dataset_info.length_filter,
                                splitMethod: expLog.dataset_info.split_method,
                                splitRatios: expLog.dataset_info.split_ratios,
                            },
                            update: {},
                        });
                    }

                    emitter.emit('event', {
                        type: 'log',
                        timestamp: new Date().toISOString(),
                        level: 'info',
                        message: 'Experiment metadata saved',
                    } as SSEEvent);
                } else if (event.type === 'eval_log') {
                    // Save evaluation metadata (from eval_logger.py)
                    // Note: Original code referenced non-existent Prisma models (EvalRun/EvalMeta/EvalGenerationConfig etc.)
                    // Changed to save key info into Run.evalResultJson
                    const evalLog = event.data;

                    // Build evaluation result summary
                    const evalSummary = {
                        evalRunId: evalLog.eval_run_id,
                        evalTime: evalLog.eval_time,
                        seed: evalLog.seed,
                        gitCommit: evalLog.git_commit,
                        baseModelName: evalLog.base_model_name,
                        checkpointPath: evalLog.checkpoint_path,
                        checkpointStep: evalLog.checkpoint_step,
                        checkpointEpoch: evalLog.checkpoint_epoch,
                        // Core metrics
                        passAt1: evalLog.metrics_overall?.pass_at_1,
                        passAt5: evalLog.metrics_overall?.pass_at_5,
                        passAt10: evalLog.metrics_overall?.pass_at_10,
                        compileRate: evalLog.metrics_overall?.compile_rate,
                        // Environment info
                        environment: evalLog.environment,
                        // Generation config
                        generationConfig: evalLog.generation_config,
                        // Judge config
                        judgeConfig: evalLog.judge_config,
                        // Dataset info
                        datasetInfo: evalLog.dataset_info,
                        // Postprocess stats
                        postprocessStats: evalLog.postprocess_stats,
                        // Error distribution and advanced stats
                        errorStats: evalLog.error_stats,
                        timeStats: evalLog.time_stats,
                        difficultyBreakdown: evalLog.difficulty_breakdown,
                        categoryBreakdown: evalLog.category_breakdown,
                        // Save failure samples summary (limit count to avoid oversized JSON)
                        failureSamples: evalLog.sample_results
                            ?.filter((s: any) => s.verdict !== 'passed')
                            ?.slice(0, 50)
                            ?.map((s: any) => ({
                                taskId: s.task_id,
                                difficulty: s.difficulty,
                                category: s.category,
                                verdict: s.verdict,
                                errorType: s.error_type,
                                traceback: s.traceback,  // Keep complete, don't truncate
                            })),
                        // P0-FIX: Add missing codeQuality field
                        codeQuality: evalLog.code_quality ? {
                            avgCodeLength: evalLog.code_quality.avg_code_length,
                            avgLineCount: evalLog.code_quality.avg_line_count,
                            extraIORate: evalLog.code_quality.extra_io_rate,
                            interfaceComplianceRate: evalLog.code_quality.interface_compliance_rate,
                        } : undefined,
                        // P0-FIX: Add segment breakdown (standardize field name)
                        segmentBreakdown: evalLog.segment_breakdown,
                    };

                    // Update Run's evaluation results
                    await prisma.run.update({
                        where: { id: runId },
                        data: {
                            evalResultJson: JSON.stringify(evalSummary),
                            metricsJson: JSON.stringify({
                                loss: 0,
                                passAt1: evalLog.metrics_overall?.pass_at_1 || 0,
                                compileRate: evalLog.metrics_overall?.compile_rate || 0,
                            }),
                        },
                    });

                    console.log(`[RunExecutor] Eval log saved to Run.evalResultJson: ${evalLog.eval_run_id}`);

                    emitter.emit('event', {
                        type: 'log',
                        timestamp: new Date().toISOString(),
                        level: 'info',
                        message: `Eval metadata saved: ${evalLog.eval_run_id} (Pass@1: ${evalLog.metrics_overall?.pass_at_1 || 'N/A'}%)`,
                    } as SSEEvent);
                } else if (event.type === 'data_quality') {
                    // Save data quality stats (from analyze_data_quality.py)
                    const qualityStats = event.data;

                    // Update DatasetMeta with statistics JSON
                    await prisma.datasetMeta.upsert({
                        where: { runId },
                        create: {
                            runId,
                            trainSamples: qualityStats.train_samples,
                            valSamples: qualityStats.eval_samples,
                            statisticsJson: JSON.stringify(qualityStats),
                        },
                        update: {
                            statisticsJson: JSON.stringify(qualityStats),
                        },
                    });

                    emitter.emit('event', {
                        type: 'log',
                        timestamp: new Date().toISOString(),
                        level: 'info',
                        message: `Data quality stats saved: score=${qualityStats.quality_score}/100`,
                    } as SSEEvent);
                } else if (event.type === 'training_summary') {
                    // Save training summary stats
                    const summary = event.data;

                    await prisma.run.update({
                        where: { id: runId },
                        data: {
                            totalSteps: summary.actual_steps || summary.planned_steps,
                        },
                    });

                    emitter.emit('event', {
                        type: 'log',
                        timestamp: new Date().toISOString(),
                        level: 'info',
                        message: `Training summary: ${summary.actual_steps} steps, peak GPU: ${summary.peak_gpu_memory_mb?.toFixed(0) || 'N/A'}MB`,
                    } as SSEEvent);
                }
            }

            // for-await loop ended, training complete
            // No longer automatically execute evaluation, evaluation is now a separate process
            // User can manually start evaluation on the Evaluation page

            // Generate artifacts
            const artifactStore = factory.getArtifactStore();

            // Save training log
            const logContent = JSON.stringify({ runId, config }, null, 2);
            await artifactStore.save(runId, 'log', 'training_log.json', Buffer.from(logContent));
            const logArtifact = await prisma.artifact.create({
                data: { runId, kind: 'log', path: `training_log.json`, size: logContent.length },
            });
            emitter.emit('event', {
                type: 'artifact',
                artifact: {
                    id: logArtifact.id,
                    kind: logArtifact.kind,
                    path: logArtifact.path,
                    size: formatSize(logArtifact.size),
                    createdAt: logArtifact.createdAt.toISOString(),
                }
            } as any);

            // Register LoRA adapter produced by training
            if (config.lora.enabled) {
                const adapterDir = `./storage/runs/${runId}`;
                const adapterConfigPath = path.join(adapterDir, 'adapter_config.json');

                // Check if adapter was actually saved
                if (fs.existsSync(adapterConfigPath)) {
                    // Read adapter config to get info
                    let adapterConfig: any = {};
                    try {
                        adapterConfig = JSON.parse(fs.readFileSync(adapterConfigPath, 'utf-8'));
                    } catch (e) {
                        console.error('Failed to read adapter config:', e);
                    }

                    const adapterName = `${run.name}-adapter`;

                    // Create Adapter record in database
                    await prisma.adapter.upsert({
                        where: { name: adapterName },
                        create: {
                            name: adapterName,
                            path: path.resolve(adapterDir),
                            baseModel: run.model.name,
                            trainDataset: run.dataset.name,
                            rank: config.lora.rank,
                            alpha: config.lora.alpha,
                            status: 'success',
                        },
                        update: {
                            status: 'success',
                            path: path.resolve(adapterDir),
                        },
                    });

                    // Also save to artifacts
                    const adapterArtifact = await prisma.artifact.create({
                        data: { runId, kind: 'adapter', path: adapterDir, size: 0 },
                    });

                    emitter.emit('event', {
                        type: 'artifact',
                        artifact: {
                            id: adapterArtifact.id,
                            kind: adapterArtifact.kind,
                            path: adapterArtifact.path,
                            size: '0 B',
                            createdAt: adapterArtifact.createdAt.toISOString(),
                        }
                    } as any);

                    console.log(`[RunExecutor] Adapter registered: ${adapterDir}`);

                    // P0-SAFETY: Auto backup newly trained adapter
                    await autoBackupNewAdapter(runId, path.resolve(adapterDir), adapterName);
                } else {
                    console.warn(`[RunExecutor] Adapter config not found at ${adapterConfigPath}`);
                }
            }

            // P1-FIX: Clean up excess checkpoints based on settings
            await cleanupCheckpoints(runId, `./storage/runs/${runId}`);

            // Calculate duration
            const duration = formatDuration(Date.now() - startTime);

            // P0-FIX: Get the last "valid" loss value recorded during training
            // Valid loss = step with learning rate (exclude epoch average loss after training ends)
            const allMetrics = await prisma.runMetric.findMany({
                where: { runId },
                orderBy: { step: 'desc' },
            });

            // Prefer finding last step with lr
            let finalLoss = 0;
            for (const m of allMetrics) {
                const extra = m.extraJson ? JSON.parse(m.extraJson) : null;
                if (extra?.lr != null || m.loss != null) {
                    finalLoss = m.loss ?? 0;
                    // If has lr, this is a normal step, use it
                    if (extra?.lr != null) break;
                }
            }
            // If all steps have no lr, use last non-zero loss
            if (finalLoss === 0 && allMetrics.length > 0) {
                finalLoss = allMetrics[0].loss ?? 0;
            }

            // Update run status to success (no longer includes evaluation results)
            await prisma.run.update({
                where: { id: runId },
                data: {
                    status: 'success',
                    completedAt: new Date(),
                    duration,
                    metricsJson: JSON.stringify({
                        loss: finalLoss,
                        passAt1: 0,      // Evaluation needs to be run manually
                        compileRate: 0,  // Evaluation needs to be run manually
                    }),
                },
            });

            emitter.emit('event', {
                type: 'status',
                status: 'success',
            } as SSEEvent);

            // Create training completion notification
            await createNotification(
                'run_completed',
                `Training Completed: ${run.name}`,
                `Duration: ${duration}, Final Loss: ${finalLoss.toFixed(4)}`,
                runId
            );
        }

    } catch (error) {
        console.error(`Run ${runId} failed:`, error);

        // Log error
        await prisma.runEvent.create({
            data: {
                runId,
                level: 'error',
                message: String(error),
            },
        });

        // Update status to failed
        await prisma.run.update({
            where: { id: runId },
            data: {
                status: 'failed',
                completedAt: new Date(),
            },
        });

        emitter.emit('event', {
            type: 'status',
            status: 'failed',
        } as SSEEvent);

        // Create task failed notification
        const run = await prisma.run.findUnique({ where: { id: runId } });
        await createNotification(
            'run_failed',
            `Run Failed: ${run?.name || runId}`,
            String(error).slice(0, 200),
            runId
        );
    } finally {
        // P0-FIX: Ensure all buffered logs are written to database
        await removeLogBuffer(runId);
        // Clean up active process tracking
        activeRuns.delete(runId);
        // Delay cleaning emitter, give clients time to receive final status
        setTimeout(() => removeRunEmitter(runId), 5000);
    }
}

function formatDuration(ms: number): string {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
        return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
        return `${minutes}m ${seconds % 60}s`;
    } else {
        return `${seconds}s`;
    }
}

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

/**
 * P1-FIX: Clean up excess checkpoints based on settings
 * Read storage.checkpointRetention setting, delete checkpoints exceeding retention count
 * Supports number format (0=keep all, N=keep recent N)
 */
async function cleanupCheckpoints(runId: string, outputDir: string): Promise<void> {
    try {
        // Read checkpoint retention setting
        const storageSetting = await prisma.setting.findUnique({
            where: { key: 'storage' }
        });

        let keepCount = 3;  // Default keep 3
        if (storageSetting) {
            try {
                const storage = JSON.parse(storageSetting.valueJson);
                const retention = storage?.checkpointRetention;

                // Support number type and legacy string type
                if (typeof retention === 'number') {
                    keepCount = retention;
                } else if (typeof retention === 'string') {
                    // Compatible with legacy format
                    if (retention === 'all') keepCount = 0;
                    else if (retention === 'last5') keepCount = 5;
                    else if (retention === 'last3') keepCount = 3;
                    else keepCount = parseInt(retention) || 3;
                }
            } catch (e) {
                // Use default value on parse failure
            }
        }

        // If set to 0, keep all
        if (keepCount === 0) {
            console.log(`[RunExecutor] Checkpoint cleanup skipped (retention=0, keep all)`);
            return;
        }

        // Scan checkpoint-* directories in outputDir
        if (!fs.existsSync(outputDir)) {
            return;
        }

        const entries = fs.readdirSync(outputDir, { withFileTypes: true });
        const checkpointDirs = entries
            .filter(e => e.isDirectory() && e.name.startsWith('checkpoint-'))
            .map(e => ({
                name: e.name,
                path: path.join(outputDir, e.name),
                step: parseInt(e.name.replace('checkpoint-', '')) || 0,
            }))
            .sort((a, b) => b.step - a.step);  // Sort by step descending

        // Keep the latest keepCount, delete the rest
        const toDelete = checkpointDirs.slice(keepCount);

        if (toDelete.length === 0) {
            console.log(`[RunExecutor] Checkpoint cleanup: ${checkpointDirs.length} checkpoints found, keeping all (within limit)`);
            return;
        }

        console.log(`[RunExecutor] Checkpoint cleanup: deleting ${toDelete.length} old checkpoints (keeping ${keepCount})`);

        for (const cp of toDelete) {
            try {
                // Recursively delete checkpoint directory
                fs.rmSync(cp.path, { recursive: true, force: true });
                console.log(`[RunExecutor] Deleted checkpoint: ${cp.name}`);

                // Delete corresponding artifact record from database
                await prisma.artifact.deleteMany({
                    where: {
                        runId,
                        kind: 'checkpoint',
                        path: { contains: cp.name }
                    }
                });
            } catch (e) {
                console.error(`[RunExecutor] Failed to delete checkpoint ${cp.name}:`, e);
            }
        }

        console.log(`[RunExecutor] Checkpoint cleanup complete for run ${runId}`);
    } catch (e) {
        console.error(`[RunExecutor] Checkpoint cleanup failed:`, e);
    }
}

// Stop run
export async function stopRun(runId: string): Promise<void> {
    const run = await prisma.run.findUnique({ where: { id: runId } });
    if (!run) {
        throw new Error('Run not found');
    }

    // Support stopping queued and running status
    if (run.status !== 'running' && run.status !== 'queued') {
        throw new Error(`Run cannot be stopped (current status: ${run.status})`);
    }

    // If queued status, remove from queue
    if (run.status === 'queued') {
        const queueIndex = runQueue.findIndex(q => q.runId === runId);
        if (queueIndex !== -1) {
            runQueue.splice(queueIndex, 1);
        }
    }

    // If running status, try to terminate actual process
    if (run.status === 'running') {
        const activeRun = activeRuns.get(runId);
        if (activeRun) {
            try {
                if (activeRun.trainer?.stop) {
                    activeRun.trainer.stop();
                    console.log(`[RunExecutor] Stopped trainer process for run ${runId}`);
                }
                if (activeRun.evaluator?.stop) {
                    activeRun.evaluator.stop();
                    console.log(`[RunExecutor] Stopped evaluator process for run ${runId}`);
                }
            } catch (e) {
                console.error(`[RunExecutor] Error stopping process for run ${runId}:`, e);
            }
            activeRuns.delete(runId);
        }
    }

    await prisma.run.update({
        where: { id: runId },
        data: {
            status: 'stopped',
            completedAt: new Date(),
        },
    });

    await prisma.runEvent.create({
        data: {
            runId,
            level: 'warning',
            message: 'Run stopped by user',
        },
    });

    const emitter = getRunEmitter(runId);
    emitter.emit('event', {
        type: 'status',
        status: 'stopped',
    } as SSEEvent);
}

// Get queue status
export function getQueueStatus(): { queueLength: number; isProcessing: boolean } {
    return {
        queueLength: runQueue.length,
        isProcessing,
    };
}

// Get complete queue details (read from database, sorted by queuePosition)
export async function getQueue(): Promise<Array<{
    id: string;
    name: string;
    type: string;
    queuePosition: number;
    createdAt: string;
    baseModel: string;
    dataset: string;
    config: any;
}>> {
    const queuedRuns = await prisma.run.findMany({
        where: { status: 'queued' },
        orderBy: { queuePosition: 'asc' },
        include: { model: true, dataset: true },
    });

    return queuedRuns.map(run => ({
        id: run.id,
        name: run.name,
        type: run.type,
        queuePosition: run.queuePosition ?? 0,
        createdAt: run.createdAt.toISOString(),
        baseModel: run.model.name,
        dataset: run.dataset.name,
        config: JSON.parse(run.configJson),
    }));
}

// Reorder task position in queue
export async function reorderQueue(runId: string, newPosition: number): Promise<void> {
    // Get current task
    const run = await prisma.run.findUnique({ where: { id: runId } });
    if (!run) {
        throw new Error('Run not found');
    }
    if (run.status !== 'queued') {
        throw new Error('Can only reorder queued runs');
    }

    const currentPosition = run.queuePosition ?? 0;
    if (currentPosition === newPosition) return;

    // Get all queued tasks
    const queuedRuns = await prisma.run.findMany({
        where: { status: 'queued', queuePosition: { not: null } },
        orderBy: { queuePosition: 'asc' },
    });

    // Validate newPosition range
    if (newPosition < 1 || newPosition > queuedRuns.length) {
        throw new Error(`Invalid position: ${newPosition}. Must be between 1 and ${queuedRuns.length}`);
    }

    // Adjust positions of other tasks
    if (newPosition < currentPosition) {
        // Moving forward: increment position by 1 for tasks in [newPosition, currentPosition-1] range
        await prisma.run.updateMany({
            where: {
                status: 'queued',
                queuePosition: { gte: newPosition, lt: currentPosition },
            },
            data: { queuePosition: { increment: 1 } },
        });
    } else {
        // Moving backward: decrement position by 1 for tasks in [currentPosition+1, newPosition] range
        await prisma.run.updateMany({
            where: {
                status: 'queued',
                queuePosition: { gt: currentPosition, lte: newPosition },
            },
            data: { queuePosition: { decrement: 1 } },
        });
    }

    // Update target task position
    await prisma.run.update({
        where: { id: runId },
        data: { queuePosition: newPosition },
    });

    // Sync memory queue order
    await syncMemoryQueue();
}

// Sync memory queue with database order
async function syncMemoryQueue(): Promise<void> {
    const queuedRuns = await prisma.run.findMany({
        where: { status: 'queued' },
        orderBy: { queuePosition: 'asc' },
    });

    // Keep config from memory, reorder according to database order
    const configMap = new Map(runQueue.map(q => [q.runId, q.config]));
    runQueue.length = 0;

    for (const run of queuedRuns) {
        const config = configMap.get(run.id);
        if (config) {
            runQueue.push({ runId: run.id, config });
        }
    }
}

// Get currently running task
export async function getActiveRun(): Promise<{ id: string; name: string } | null> {
    const activeRun = await prisma.run.findFirst({
        where: { status: 'running' },
        orderBy: { startedAt: 'desc' },
    });
    return activeRun ? { id: activeRun.id, name: activeRun.name } : null;
}
