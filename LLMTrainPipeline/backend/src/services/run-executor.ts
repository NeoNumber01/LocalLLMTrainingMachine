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
// P0-FIX: 批量日志缓冲器 - 解决 SQLite 高频写入压力
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
     * 添加日志事件到缓冲区
     * 达到 maxSize 时自动刷新
     */
    push(event: LogEvent): void {
        this.buffer.push(event);

        // 首次添加时启动定时器
        if (this.buffer.length === 1 && !this.flushTimer) {
            this.flushTimer = setTimeout(() => this.flush(), this.flushIntervalMs);
        }

        // 达到上限立即刷新
        if (this.buffer.length >= this.maxSize) {
            this.flush();
        }
    }

    /**
     * 批量写入缓冲区中的所有日志
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
            // 失败时尝试逐条写入以避免数据丢失
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
     * 清空缓冲区（不写入）
     */
    clear(): void {
        if (this.flushTimer) {
            clearTimeout(this.flushTimer);
            this.flushTimer = null;
        }
        this.buffer = [];
    }
}

// 每个 Run 对应一个缓冲器
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
        await buffer.flush(); // 确保所有日志都写入
        logBuffers.delete(runId);
    }
}

// 运行事件管理
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

// 简单任务队列
interface QueuedRun {
    runId: string;
    config: Config;
}

const runQueue: QueuedRun[] = [];
let isProcessing = false;

// 追踪活跃的进程以便能够停止它们
import type { TrainerProvider, EvalProvider } from '../providers/interfaces.js';
interface ActiveRun {
    trainer?: TrainerProvider;
    evaluator?: EvalProvider;
}
const activeRuns = new Map<string, ActiveRun>();

// Helper: 将前端的扁平 config 转换为嵌套结构
function prepareConfigOverride(configOverride: any): any {
    const nestedOverride: any = {};

    // Training 配置
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

    // LoRA 配置
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

    // Eval 配置
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

// P0-SAFETY: 恢复队列状态
export async function restoreQueue(): Promise<void> {
    console.log('[RunExecutor] Restoring queue state...');

    // 1. 处理意外中断的 running 任务 -> 恢复到队列继续执行（而非标记失败）
    // 这样服务器重启（如 tsx watch 热重载）不会导致任务丢失
    const interruptedRuns = await prisma.run.findMany({
        where: { status: 'running' },
    });

    for (const run of interruptedRuns) {
        console.log(`[RunExecutor] Restoring interrupted run ${run.id} to queue (will resume)`);

        // 计算新的队列位置（放到队首优先执行）
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
                // 保留 startedAt 以便追踪
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

    // 2. 恢复 queued 任务到内存队列
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
                // 标记为失败，避免卡在 queued
                await prisma.run.update({
                    where: { id: run.id },
                    data: { status: 'failed' },
                });
            }
        }

        // 如果队列不为空，启动处理
        if (runQueue.length > 0) {
            processQueue();
        }
    }
}

export async function enqueueRun(runId: string, profileName: string, configOverride: any): Promise<void> {
    const nestedOverride = prepareConfigOverride(configOverride);
    const config = resolveConfig(profileName, nestedOverride);

    // 计算队列位置 - 获取当前最大位置 + 1
    const maxPositionRun = await prisma.run.findFirst({
        where: { status: 'queued', queuePosition: { not: null } },
        orderBy: { queuePosition: 'desc' },
    });
    const newPosition = (maxPositionRun?.queuePosition ?? 0) + 1;

    // 更新数据库中的队列位置
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
        // P1-FIX: 读取最大并发数设置
        const maxConcurrent = await getMaxSimultaneousRuns();

        while (runQueue.length > 0) {
            // 获取当前活跃运行数
            const currentActive = activeRuns.size;

            // 如果已达到最大并发数，等待
            if (currentActive >= maxConcurrent) {
                await new Promise(resolve => setTimeout(resolve, 1000));
                continue;
            }

            // 计算可以启动的任务数
            const slotsAvailable = maxConcurrent - currentActive;
            const jobsToStart = Math.min(slotsAvailable, runQueue.length);

            // 并发启动多个任务
            const startPromises: Promise<void>[] = [];
            for (let i = 0; i < jobsToStart; i++) {
                const job = runQueue.shift();
                if (job) {
                    // 使用不等待的方式启动任务，让它在后台运行
                    startPromises.push(executeRun(job.runId, job.config).catch(e => {
                        console.error(`[RunExecutor] Task ${job.runId} failed:`, e);
                    }));
                }
            }

            // 如果maxConcurrent > 1，并发启动后等待一小段时间再检查
            // 如果maxConcurrent = 1，等待当前任务完成
            if (maxConcurrent === 1 && startPromises.length > 0) {
                await Promise.all(startPromises);
            } else if (startPromises.length > 0) {
                // 等待一小段时间让任务注册到activeRuns
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }

        // 等待所有活跃任务完成
        while (activeRuns.size > 0) {
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    } finally {
        isProcessing = false;
    }
}

/**
 * P1-FIX: 获取最大并发运行数设置
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
    return 1;  // 默认单任务
}

async function executeRun(runId: string, config: Config): Promise<void> {
    const emitter = getRunEmitter(runId);
    const factory = getProviderFactory(config);

    try {
        // 更新状态为 running
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

        // 获取 run 信息
        const run = await prisma.run.findUnique({
            where: { id: runId },
            include: { model: true, dataset: true },
        });

        if (!run) throw new Error(`Run not found: ${runId}`);

        const startTime = Date.now();

        // 根据 run.type 分派执行
        if (run.type === 'evaluation') {
            // ===== 评测流程 =====
            console.log(`[RunExecutor] Starting evaluation for run ${runId}`);
            emitter.emit('event', {
                type: 'log',
                timestamp: new Date().toISOString(),
                level: 'info',
                message: 'Starting evaluation...',
            } as SSEEvent);

            // 保存初始日志事件到数据库
            await prisma.runEvent.create({
                data: {
                    runId,
                    level: 'info',
                    message: 'Starting evaluation...',
                },
            });

            const evaluator = factory.getEvalProvider();

            // 注册活跃进程以便可以停止
            activeRuns.set(runId, { evaluator });

            // 检查是否有可用的 adapter
            let adapterPath: string | undefined;
            const adapterArtifact = await prisma.artifact.findFirst({
                where: { runId: runId, kind: 'adapter' },
            });
            if (adapterArtifact) {
                adapterPath = adapterArtifact.path;
            }

            // 使用 evalDatasetId 如果有的话，否则使用 datasetId
            let evalDatasetPath = run.dataset.path;
            if ((run as any).evalDatasetId) {
                const evalDataset = await prisma.dataset.findUnique({
                    where: { id: (run as any).evalDatasetId },
                });
                if (evalDataset) {
                    evalDatasetPath = evalDataset.path;
                }
            }

            // 如果支持流式评测，使用流式方法
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
                        // P0-FIX: 使用缓冲器批量写入日志，减少 SQLite 写入压力
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
                        // P0-FIX: 错误日志也使用缓冲器
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

            // P0-FIX: 读取 eval_summary.json 获取完整元信息（包含 datasetInfo 等）
            // eval.py 在评测完成后会将完整日志保存到 eval_summary.json
            const evalSummaryPath = `./storage/runs/${runId}/eval_summary.json`;
            let fullEvalData: any = evalResult;
            try {
                const fs = await import('fs');
                if (fs.existsSync(evalSummaryPath)) {
                    const summaryContent = fs.readFileSync(evalSummaryPath, 'utf-8');
                    const evalSummary = JSON.parse(summaryContent);

                    // 合并完整元信息
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
                        // P0-FIX: 添加遗漏的 Pass@5 和 Pass@10 数据
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
                                traceback: s.traceback,  // 完整保存，不截断
                            })),
                    };
                    console.log(`[RunExecutor] Merged eval_summary.json for run ${runId} (dataset_info.total_problems: ${evalSummary.dataset_info?.total_problems || 'N/A'})`);
                }
            } catch (e) {
                console.warn(`[RunExecutor] Could not read eval_summary.json: ${e}`);
            }

            // 保存评测结果
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

            // 保存评测结果到 artifacts
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

            // 创建评测完成通知
            await createNotification(
                'run_completed',
                `Evaluation Completed: ${run.name}`,
                `Pass@1: ${evalResult.passAt1}%, Compile Rate: ${evalResult.compileRate}%`,
                runId
            );

        } else {
            // ===== 训练流程 =====
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

            // 注册活跃进程以便可以停止
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
                    // P0-FIX: 使用缓冲器批量写入日志，减少 SQLite 写入压力
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
                    // 保存指标 - 直接创建，不再使用 upsert（唯一约束已移除）
                    // console.log(`[RunExecutor] Saving metric for run ${runId}: step=${event.data.step}, loss=${event.data.loss}`);
                    await prisma.runMetric.create({
                        data: {
                            runId,
                            step: event.data.step,
                            loss: event.data.loss,
                            // P0-FIX: 添加 epoch 到 extraJson，用于报告分组统计
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
                    // 保存 checkpoint 信息
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
                    // 保存实验元信息 (来自 experiment_logger.py)
                    const expLog = event.data;

                    // 更新 Run 基础字段
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

                    // 保存环境元信息
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

                    // 保存 LoRA 统计 (带异常保护，避免中断后续流程如适配器注册)
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
                            // 记录警告但不中断执行，确保后续adapter注册能正常执行
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

                    // 保存数据集元信息
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
                    // 保存评测元信息 (来自 eval_logger.py)
                    // 注意：原代码引用了不存在的 Prisma 模型 (EvalRun/EvalMeta/EvalGenerationConfig 等)
                    // 这里改为将关键信息存入 Run.evalResultJson
                    const evalLog = event.data;

                    // 构建评测结果摘要
                    const evalSummary = {
                        evalRunId: evalLog.eval_run_id,
                        evalTime: evalLog.eval_time,
                        seed: evalLog.seed,
                        gitCommit: evalLog.git_commit,
                        baseModelName: evalLog.base_model_name,
                        checkpointPath: evalLog.checkpoint_path,
                        checkpointStep: evalLog.checkpoint_step,
                        checkpointEpoch: evalLog.checkpoint_epoch,
                        // 核心指标
                        passAt1: evalLog.metrics_overall?.pass_at_1,
                        passAt5: evalLog.metrics_overall?.pass_at_5,
                        passAt10: evalLog.metrics_overall?.pass_at_10,
                        compileRate: evalLog.metrics_overall?.compile_rate,
                        // 环境信息
                        environment: evalLog.environment,
                        // 生成配置
                        generationConfig: evalLog.generation_config,
                        // 判题配置
                        judgeConfig: evalLog.judge_config,
                        // 数据集信息
                        datasetInfo: evalLog.dataset_info,
                        // 后处理统计
                        postprocessStats: evalLog.postprocess_stats,
                        // 错误分布等高级统计
                        errorStats: evalLog.error_stats,
                        timeStats: evalLog.time_stats,
                        difficultyBreakdown: evalLog.difficulty_breakdown,
                        categoryBreakdown: evalLog.category_breakdown,
                        // 保存失败样例摘要（限制数量避免 JSON 过大）
                        failureSamples: evalLog.sample_results
                            ?.filter((s: any) => s.verdict !== 'passed')
                            ?.slice(0, 50)
                            ?.map((s: any) => ({
                                taskId: s.task_id,
                                difficulty: s.difficulty,
                                category: s.category,
                                verdict: s.verdict,
                                errorType: s.error_type,
                                traceback: s.traceback,  // 完整保存，不截断
                            })),
                        // P0-FIX: 添加遗漏的 codeQuality 字段
                        codeQuality: evalLog.code_quality ? {
                            avgCodeLength: evalLog.code_quality.avg_code_length,
                            avgLineCount: evalLog.code_quality.avg_line_count,
                            extraIORate: evalLog.code_quality.extra_io_rate,
                            interfaceComplianceRate: evalLog.code_quality.interface_compliance_rate,
                        } : undefined,
                        // P0-FIX: 添加分段统计（统一字段名）
                        segmentBreakdown: evalLog.segment_breakdown,
                    };

                    // 更新 Run 的评测结果
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
                    // 保存数据质量统计 (来自 analyze_data_quality.py)
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
                    // 保存训练摘要统计
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

            // for-await 循环结束，训练完成
            // 不再自动执行评估，评估现在是独立的流程
            // 用户可以在 Evaluation 页面手动启动评估

            // 生成产物
            const artifactStore = factory.getArtifactStore();

            // 保存训练日志
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

            // 注册训练产生的LoRA适配器
            if (config.lora.enabled) {
                const adapterDir = `./storage/runs/${runId}`;
                const adapterConfigPath = path.join(adapterDir, 'adapter_config.json');

                // 检查adapter是否真的被保存了
                if (fs.existsSync(adapterConfigPath)) {
                    // 读取adapter配置获取信息
                    let adapterConfig: any = {};
                    try {
                        adapterConfig = JSON.parse(fs.readFileSync(adapterConfigPath, 'utf-8'));
                    } catch (e) {
                        console.error('Failed to read adapter config:', e);
                    }

                    const adapterName = `${run.name}-adapter`;

                    // 在数据库中创建Adapter记录
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

                    // 同时保存到artifacts
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

                    // P0-SAFETY: 自动备份新训练的 adapter
                    await autoBackupNewAdapter(runId, path.resolve(adapterDir), adapterName);
                } else {
                    console.warn(`[RunExecutor] Adapter config not found at ${adapterConfigPath}`);
                }
            }

            // P1-FIX: 根据设置清理多余的checkpoints
            await cleanupCheckpoints(runId, `./storage/runs/${runId}`);

            // 计算时长
            const duration = formatDuration(Date.now() - startTime);

            // P0-FIX: 获取训练过程中记录的最后一个"有效" loss 值
            // 有效 loss = 有 learning rate 的 step（排除训练结束后的 epoch 平均 loss）
            const allMetrics = await prisma.runMetric.findMany({
                where: { runId },
                orderBy: { step: 'desc' },
            });

            // 优先找有 lr 的最后一个 step
            let finalLoss = 0;
            for (const m of allMetrics) {
                const extra = m.extraJson ? JSON.parse(m.extraJson) : null;
                if (extra?.lr != null || m.loss != null) {
                    finalLoss = m.loss ?? 0;
                    // 如果有 lr，说明是正常的 step，使用它
                    if (extra?.lr != null) break;
                }
            }
            // 如果所有 step 都没有 lr，使用最后一个非 0 的 loss
            if (finalLoss === 0 && allMetrics.length > 0) {
                finalLoss = allMetrics[0].loss ?? 0;
            }

            // 更新运行状态为成功 (不再包含评测结果)
            await prisma.run.update({
                where: { id: runId },
                data: {
                    status: 'success',
                    completedAt: new Date(),
                    duration,
                    metricsJson: JSON.stringify({
                        loss: finalLoss,
                        passAt1: 0,      // 评测需要手动运行
                        compileRate: 0,  // 评测需要手动运行
                    }),
                },
            });

            emitter.emit('event', {
                type: 'status',
                status: 'success',
            } as SSEEvent);

            // 创建训练完成通知
            await createNotification(
                'run_completed',
                `Training Completed: ${run.name}`,
                `Duration: ${duration}, Final Loss: ${finalLoss.toFixed(4)}`,
                runId
            );
        }

    } catch (error) {
        console.error(`Run ${runId} failed:`, error);

        // 记录错误
        await prisma.runEvent.create({
            data: {
                runId,
                level: 'error',
                message: String(error),
            },
        });

        // 更新状态为失败
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

        // 创建任务失败通知
        const run = await prisma.run.findUnique({ where: { id: runId } });
        await createNotification(
            'run_failed',
            `Run Failed: ${run?.name || runId}`,
            String(error).slice(0, 200),
            runId
        );
    } finally {
        // P0-FIX: 确保所有缓冲的日志都写入数据库
        await removeLogBuffer(runId);
        // 清理活跃进程追踪
        activeRuns.delete(runId);
        // 延迟清理 emitter，让客户端有时间接收最终状态
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
 * P1-FIX: 根据设置清理多余的checkpoints
 * 读取 storage.checkpointRetention 设置，删除超出保留数量的旧checkpoints
 * 支持数字格式（0=保留全部，N=保留最近N个）
 */
async function cleanupCheckpoints(runId: string, outputDir: string): Promise<void> {
    try {
        // 读取checkpoint保留设置
        const storageSetting = await prisma.setting.findUnique({
            where: { key: 'storage' }
        });

        let keepCount = 3;  // 默认保留3个
        if (storageSetting) {
            try {
                const storage = JSON.parse(storageSetting.valueJson);
                const retention = storage?.checkpointRetention;

                // 支持数字类型和旧的字符串类型
                if (typeof retention === 'number') {
                    keepCount = retention;
                } else if (typeof retention === 'string') {
                    // 兼容旧格式
                    if (retention === 'all') keepCount = 0;
                    else if (retention === 'last5') keepCount = 5;
                    else if (retention === 'last3') keepCount = 3;
                    else keepCount = parseInt(retention) || 3;
                }
            } catch (e) {
                // 解析失败使用默认值
            }
        }

        // 如果设置为0，保留全部
        if (keepCount === 0) {
            console.log(`[RunExecutor] Checkpoint cleanup skipped (retention=0, keep all)`);
            return;
        }

        // 扫描 outputDir 中的 checkpoint-* 目录
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
            .sort((a, b) => b.step - a.step);  // 按step降序排列

        // 保留最新的 keepCount 个，删除其余的
        const toDelete = checkpointDirs.slice(keepCount);

        if (toDelete.length === 0) {
            console.log(`[RunExecutor] Checkpoint cleanup: ${checkpointDirs.length} checkpoints found, keeping all (within limit)`);
            return;
        }

        console.log(`[RunExecutor] Checkpoint cleanup: deleting ${toDelete.length} old checkpoints (keeping ${keepCount})`);

        for (const cp of toDelete) {
            try {
                // 递归删除 checkpoint 目录
                fs.rmSync(cp.path, { recursive: true, force: true });
                console.log(`[RunExecutor] Deleted checkpoint: ${cp.name}`);

                // 从数据库中删除对应的 artifact 记录
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

// 停止运行
export async function stopRun(runId: string): Promise<void> {
    const run = await prisma.run.findUnique({ where: { id: runId } });
    if (!run) {
        throw new Error('Run not found');
    }

    // 支持停止 queued 和 running 状态
    if (run.status !== 'running' && run.status !== 'queued') {
        throw new Error(`Run cannot be stopped (current status: ${run.status})`);
    }

    // 如果是 queued 状态，从队列中移除
    if (run.status === 'queued') {
        const queueIndex = runQueue.findIndex(q => q.runId === runId);
        if (queueIndex !== -1) {
            runQueue.splice(queueIndex, 1);
        }
    }

    // 如果是 running 状态，尝试终止实际进程
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

// 获取队列状态
export function getQueueStatus(): { queueLength: number; isProcessing: boolean } {
    return {
        queueLength: runQueue.length,
        isProcessing,
    };
}

// 获取完整队列详情（从数据库读取，按 queuePosition 排序）
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

// 重排队列中任务的位置
export async function reorderQueue(runId: string, newPosition: number): Promise<void> {
    // 获取当前任务
    const run = await prisma.run.findUnique({ where: { id: runId } });
    if (!run) {
        throw new Error('Run not found');
    }
    if (run.status !== 'queued') {
        throw new Error('Can only reorder queued runs');
    }

    const currentPosition = run.queuePosition ?? 0;
    if (currentPosition === newPosition) return;

    // 获取所有队列中的任务
    const queuedRuns = await prisma.run.findMany({
        where: { status: 'queued', queuePosition: { not: null } },
        orderBy: { queuePosition: 'asc' },
    });

    // 验证 newPosition 范围
    if (newPosition < 1 || newPosition > queuedRuns.length) {
        throw new Error(`Invalid position: ${newPosition}. Must be between 1 and ${queuedRuns.length}`);
    }

    // 调整其他任务的位置
    if (newPosition < currentPosition) {
        // 向前移动：将 [newPosition, currentPosition-1] 范围内的任务位置 +1
        await prisma.run.updateMany({
            where: {
                status: 'queued',
                queuePosition: { gte: newPosition, lt: currentPosition },
            },
            data: { queuePosition: { increment: 1 } },
        });
    } else {
        // 向后移动：将 [currentPosition+1, newPosition] 范围内的任务位置 -1
        await prisma.run.updateMany({
            where: {
                status: 'queued',
                queuePosition: { gt: currentPosition, lte: newPosition },
            },
            data: { queuePosition: { decrement: 1 } },
        });
    }

    // 更新目标任务的位置
    await prisma.run.update({
        where: { id: runId },
        data: { queuePosition: newPosition },
    });

    // 同步内存队列顺序
    await syncMemoryQueue();
}

// 同步内存队列与数据库顺序
async function syncMemoryQueue(): Promise<void> {
    const queuedRuns = await prisma.run.findMany({
        where: { status: 'queued' },
        orderBy: { queuePosition: 'asc' },
    });

    // 保留内存中已有的 config，按数据库顺序重新排列
    const configMap = new Map(runQueue.map(q => [q.runId, q.config]));
    runQueue.length = 0;

    for (const run of queuedRuns) {
        const config = configMap.get(run.id);
        if (config) {
            runQueue.push({ runId: run.id, config });
        }
    }
}

// 获取正在运行的任务
export async function getActiveRun(): Promise<{ id: string; name: string } | null> {
    const activeRun = await prisma.run.findFirst({
        where: { status: 'running' },
        orderBy: { startedAt: 'desc' },
    });
    return activeRun ? { id: activeRun.id, name: activeRun.name } : null;
}
