/**
 * Academic Report Generator
 * 
 * 直接、详细、丰富的报告生成服务
 * 原则：直接从数据库读取，不做复杂推断，展示所有可用数据
 */

import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

// ============================================================================
// Types - 完整的报告数据结构
// ============================================================================

export interface AcademicReport {
    // 元信息
    runId: string;
    runName: string;
    runType: string;
    status: string;
    startTime: string;
    endTime: string;
    duration: string;
    seed: number | null;
    gitCommit: string | null;

    // 环境版本 - 全部字段
    environment: {
        os: string | null;
        python: string | null;
        pytorch: string | null;
        transformers: string | null;
        trl: string | null;
        peft: string | null;
        cuda: string | null;
        cudnn: string | null;
        bitsandbytes: string | null;
    };

    // 硬件配置
    hardware: {
        gpu: string | null;
        gpuMemory: string | null;
        cpu: string | null;
        ram: string | null;
    };

    // 数据集信息
    dataset: {
        id: string;
        name: string;
        path: string;
        samples: number | null;
        source: string | null;
        trainSamples: number | null;
        valSamples: number | null;
        testSamples: number | null;
        totalTokens: number | null;
        promptTemplate: string | null;
        outputFormat: string | null;
        dedupeMethod: string | null;
        splitMethod: string | null;
    };

    // 基座模型
    model: {
        id: string;
        name: string;
        path: string;
        params: string;
        quantization: string;
    };

    // 训练配置 - 完整字段
    training: {
        batchSize: number;
        gradientAccumulationSteps: number;
        effectiveBatchSize: number;
        learningRate: string;
        scheduler: string;
        warmupRatio: number;
        epochs: number;
        maxSeqLength: number;
        optimizer: string;
        weightDecay: number;
        precision: string;
    };

    // LoRA 配置 - 完整字段
    lora: {
        enabled: boolean;
        rank: number | null;
        alpha: number | null;
        dropout: number | null;
        targetModules: string[];
        quantization: string | null;
        trainableParams: number | null;
        totalParams: number | null;
        trainablePercent: number | null;
    };

    // 训练统计
    trainingStats: {
        totalSteps: number | null;
        totalTokens: number | null;
        tokensPerSecond: number | null;
        gpuHours: number | null;
        finalLoss: number | null;
    };

    // 评估指标 - 完整字段
    evaluation: {
        passAt1: number | null;
        passAt5: number | null;
        passAt10: number | null;
        compileRate: number | null;
        errorStats: {
            syntaxErrorRate: number | null;
            runtimeErrorRate: number | null;
            timeoutRate: number | null;
            assertionErrorRate: number | null;
            importErrorRate: number | null;
            memoryErrorRate: number | null;
        };
        timeStats: {
            meanRuntimeMs: number | null;
            p50RuntimeMs: number | null;
            p95RuntimeMs: number | null;
            maxRuntimeMs: number | null;
        };
    };

    // 后处理对比(如有)
    postProcess: {
        enabled: boolean;
        passAt1Before: number | null;
        passAt1After: number | null;
        syntaxErrorBefore: number | null;
        syntaxErrorAfter: number | null;
        runtimeErrorBefore: number | null;
        runtimeErrorAfter: number | null;
        fixReasonDistribution: Record<string, number>;
    } | null;

    // 训练曲线数据
    lossCurve: { step: number; loss: number; lr?: number; epoch?: number }[];

    // 检查点列表
    checkpoints: { step: number; epoch: number | null; loss: number | null; path: string; createdAt: string }[];

    // P1: 评测方法论 (仅评测报告)
    evaluationProtocol: {
        passAtKDefinition: string;
        samplesPerTask: number;
        temperature: number;
        topP: number;
        sortingMethod: string;
        compileRateDefinition: string;
        timeoutHandling: string;
        memoryLimitHandling: string;
    } | null;

    // P2: 代码质量指标 (仅评测报告)
    codeQuality: {
        avgCodeLength: number | null;
        avgLineCount: number | null;
        extraIORate: number | null;
        interfaceComplianceRate: number | null;
    } | null;

    // P1: 可复现性信息
    reproducibility: {
        pythonSeed: number | null;
        numpySeed: number | null;
        torchSeed: number | null;
        evaluatorVersion: string | null;
        checkpointHash: string | null;
    } | null;

    // 原始配置 JSON（供调试和完整记录）
    rawConfig: any;
    rawMetrics: any;
    rawEvalResult: any;
}

// ============================================================================
// Academic Report Generator Class
// ============================================================================

export class AcademicReportGenerator {
    /**
     * 从数据库生成完整学术报告 - 直接读取，不推断
     */
    async generateReport(runId: string): Promise<AcademicReport> {
        // 获取 Run 及所有关联数据
        const run = await prisma.run.findUnique({
            where: { id: runId },
            include: {
                model: true,
                dataset: true,
                experimentMeta: true,
                datasetMeta: true,
                loraStats: true,
                postProcessLogs: true,
                artifacts: {
                    orderBy: { createdAt: 'asc' }
                },
                metrics: {
                    orderBy: { step: 'asc' }
                }
            }
        });

        if (!run) {
            throw new Error(`Run not found: ${runId}`);
        }

        // 直接解析 JSON 字段
        let config: any = {};
        let evalResult: any = {};
        let metrics: any = {};

        try { config = JSON.parse(run.configJson || '{}'); } catch { }
        try { evalResult = JSON.parse(run.evalResultJson || '{}'); } catch { }
        try { metrics = JSON.parse(run.metricsJson || '{}'); } catch { }

        // 训练配置 - 支持扁平格式和嵌套格式 (与 reports.ts 保持一致)
        const flatConfig = config as any;
        const trainingConfig = flatConfig.training || {
            lr: flatConfig.lr,
            learningRate: flatConfig.learningRate || flatConfig.lr,
            epochs: flatConfig.epochs,
            batchSize: flatConfig.batchSize,
            gradAccum: flatConfig.gradAccum,
            gradientAccumulation: flatConfig.gradAccum,
            maxSeqLen: flatConfig.maxSeqLen,
            maxLength: flatConfig.maxSeqLen,
            warmupRatio: flatConfig.warmupRatio,
            weightDecay: flatConfig.weightDecay,
            optimizer: flatConfig.optimizer,
            scheduler: flatConfig.scheduler,
            precision: flatConfig.precision,
        };
        const loraConfig = flatConfig.lora || {
            enabled: flatConfig.useLora !== false,
            rank: flatConfig.loraRank,
            alpha: flatConfig.loraAlpha,
            dropout: flatConfig.loraDropout,
            targetModules: flatConfig.loraTargetModules,
            quantization: flatConfig.quantization,
        };

        // 计算持续时间
        const duration = this.calculateDuration(run.startedAt, run.completedAt) || run.duration || '';

        // 构建完整报告
        const report: AcademicReport = {
            // === 元信息 ===
            runId: run.id,
            runName: run.name,
            runType: run.type,
            status: run.status,
            startTime: run.startedAt?.toISOString() || run.createdAt.toISOString(),
            endTime: run.completedAt?.toISOString() || '',
            duration,
            seed: run.seed,
            gitCommit: run.gitCommit,

            // === 环境版本 - 直接读取 experimentMeta ===
            environment: {
                os: run.experimentMeta?.osVersion || null,
                python: run.experimentMeta?.pythonVersion || null,
                pytorch: run.experimentMeta?.pytorchVersion || null,
                transformers: run.experimentMeta?.transformersVersion || null,
                trl: run.experimentMeta?.trlVersion || null,
                peft: run.experimentMeta?.peftVersion || null,
                cuda: run.experimentMeta?.cudaVersion || null,
                cudnn: run.experimentMeta?.cudnnVersion || null,
                bitsandbytes: run.experimentMeta?.bitsandbytesVersion || null,
            },

            // === 硬件配置 - 直接读取 ===
            hardware: {
                gpu: run.experimentMeta?.gpuModel || null,
                gpuMemory: run.experimentMeta?.gpuMemoryGB ? `${run.experimentMeta.gpuMemoryGB.toFixed(1)} GB` : null,
                cpu: run.experimentMeta?.cpuModel || null,
                ram: run.experimentMeta?.ramGB ? `${run.experimentMeta.ramGB.toFixed(1)} GB` : null,
            },

            // === 数据集 - 完整信息 ===
            dataset: {
                id: run.dataset.id,
                name: run.dataset.name,
                path: run.dataset.path,
                samples: run.dataset.samples,
                source: run.datasetMeta?.source || null,
                trainSamples: run.datasetMeta?.trainSamples || null,
                valSamples: run.datasetMeta?.valSamples || null,
                testSamples: run.datasetMeta?.testSamples || null,
                totalTokens: run.datasetMeta?.totalTokens || run.totalTokens || null,
                promptTemplate: run.datasetMeta?.promptTemplate || null,
                outputFormat: run.datasetMeta?.outputFormat || null,
                dedupeMethod: run.datasetMeta?.dedupeMethod || null,
                splitMethod: run.datasetMeta?.splitMethod || null,
            },

            // === 模型 - 完整信息 ===
            model: {
                id: run.model.id,
                name: run.model.name,
                path: run.model.path,
                params: run.model.params,
                quantization: loraConfig.quantization || run.model.quantization || 'None',
            },

            // === 训练配置 - 直接读取 configJson ===
            training: {
                batchSize: trainingConfig.batchSize || 1,
                gradientAccumulationSteps: trainingConfig.gradientAccumulation || trainingConfig.gradAccum || 8,
                effectiveBatchSize: (trainingConfig.batchSize || 1) * (trainingConfig.gradientAccumulation || trainingConfig.gradAccum || 8),
                learningRate: trainingConfig.lr || trainingConfig.learningRate || '2e-4',
                scheduler: trainingConfig.scheduler || 'cosine',
                warmupRatio: trainingConfig.warmupRatio ?? 0.03,
                epochs: trainingConfig.epochs || 3,
                maxSeqLength: trainingConfig.maxSeqLen || trainingConfig.maxLength || 512,
                optimizer: trainingConfig.optimizer || 'adamw_torch',
                weightDecay: trainingConfig.weightDecay ?? 0.01,
                precision: trainingConfig.precision || 'fp16',
            },

            // === LoRA 配置 - 直接读取 ===
            lora: {
                enabled: loraConfig.enabled !== false,
                rank: run.loraStats?.rank || loraConfig.rank || null,
                alpha: run.loraStats?.alpha || loraConfig.alpha || null,
                dropout: run.loraStats?.dropout ?? loraConfig.dropout ?? null,
                targetModules: this.parseTargetModules(run.loraStats?.targetModules, loraConfig.targetModules),
                quantization: loraConfig.quantization || null,
                trainableParams: run.loraStats?.trainableParams ? Number(run.loraStats.trainableParams) : null,
                totalParams: run.loraStats?.totalParams ? Number(run.loraStats.totalParams) : null,
                trainablePercent: run.loraStats?.trainablePercent || null,
            },

            // === 训练统计 ===
            trainingStats: {
                // P0-FIX: 使用有效的最后 step（有 lr 的 step）
                totalSteps: run.totalSteps || this.getValidStepCount(run.metrics),
                totalTokens: run.totalTokens || null,
                tokensPerSecond: run.tokensPerSecond || null,
                gpuHours: run.gpuHours || this.calculateGpuHours(run.startedAt, run.completedAt),
                // P0-FIX: 获取有效的最后 loss（有 lr 的 step，排除 epoch 平均值）
                finalLoss: this.getValidFinalLoss(run.metrics),
            },

            // === 评估指标 ===
            evaluation: {
                passAt1: metrics.passAt1 ?? evalResult.passAt1 ?? null,
                // P0-FIX: 使用正确的字段名 passAt5/passAt10（而非 passAtK['5']）
                passAt5: evalResult.passAt5 ?? evalResult.passAtK?.['5'] ?? null,
                passAt10: evalResult.passAt10 ?? evalResult.passAtK?.['10'] ?? null,
                compileRate: metrics.compileRate ?? evalResult.compileRate ?? null,
                errorStats: {
                    syntaxErrorRate: evalResult.errorStats?.syntaxErrorRate ?? null,
                    runtimeErrorRate: evalResult.errorStats?.runtimeErrorRate ?? null,
                    timeoutRate: evalResult.errorStats?.timeoutRate ?? null,
                    assertionErrorRate: evalResult.errorStats?.assertionErrorRate ?? null,
                    importErrorRate: evalResult.errorStats?.importErrorRate ?? null,
                    memoryErrorRate: evalResult.errorStats?.memoryErrorRate ?? null,
                },
                timeStats: {
                    meanRuntimeMs: evalResult.timeStats?.meanRuntimeMs ?? null,
                    p50RuntimeMs: evalResult.timeStats?.p50RuntimeMs ?? null,
                    p95RuntimeMs: evalResult.timeStats?.p95RuntimeMs ?? null,
                    maxRuntimeMs: evalResult.timeStats?.maxRuntimeMs ?? null,
                },
            },

            // === 后处理 ===
            postProcess: run.postProcessLogs.length > 0 ? {
                enabled: true,
                passAt1Before: run.postProcessLogs[0]?.passAt1Before ?? null,
                passAt1After: run.postProcessLogs[0]?.passAt1After ?? null,
                syntaxErrorBefore: run.postProcessLogs[0]?.syntaxErrorBefore ?? null,
                syntaxErrorAfter: run.postProcessLogs[0]?.syntaxErrorAfter ?? null,
                runtimeErrorBefore: run.postProcessLogs[0]?.runtimeErrorBefore ?? null,
                runtimeErrorAfter: run.postProcessLogs[0]?.runtimeErrorAfter ?? null,
                fixReasonDistribution: this.parseJson(run.postProcessLogs[0]?.fixReasonDistribution, {}),
            } : null,

            // === 训练曲线 ===
            // P0-FIX: 过滤掉没有 lr 的异常步骤（HuggingFace Trainer 最后的额外 log）
            lossCurve: run.metrics
                .map(m => {
                    let extra: any = {};
                    try { extra = JSON.parse(m.extraJson || '{}'); } catch { }
                    return {
                        step: m.step,
                        loss: m.loss || 0,
                        lr: extra.lr,
                        epoch: extra.epoch,
                    };
                })
                .filter(m => m.lr != null),  // 只保留有 lr 的有效训练步骤


            // === 检查点列表 - 从 artifacts 中过滤 checkpoint 类型 ===
            checkpoints: run.artifacts
                .filter(a => a.kind === 'checkpoint')
                .map(a => {
                    // 从path中提取step信息，如 checkpoint-100
                    const stepMatch = a.path.match(/checkpoint-?(\d+)/i);
                    const step = stepMatch ? parseInt(stepMatch[1]) : 0;
                    return {
                        step,
                        epoch: null,
                        loss: null,
                        path: a.path,
                        createdAt: a.createdAt.toISOString(),
                    };
                }),

            // === P1: 评测方法论 (仅评测报告) ===
            evaluationProtocol: run.type === 'eval' ? {
                passAtKDefinition: evalResult.evaluationProtocol?.passAtKDefinition ??
                    'success if any of the first k samples passes all tests',
                samplesPerTask: config.numSamples ?? evalResult.evaluationProtocol?.samplesPerTask ?? 1,
                temperature: config.temperature ?? evalResult.evaluationProtocol?.temperature ?? 0.2,
                topP: config.topP ?? evalResult.evaluationProtocol?.topP ?? 0.95,
                sortingMethod: evalResult.evaluationProtocol?.sortingMethod ?? 'generation_order',
                compileRateDefinition: evalResult.evaluationProtocol?.compileRateDefinition ??
                    '% of samples without SyntaxError during exec',
                timeoutHandling: evalResult.evaluationProtocol?.timeoutHandling ??
                    `counted as failure (TLE) after ${config.timeout ?? 10}s`,
                memoryLimitHandling: evalResult.evaluationProtocol?.memoryLimitHandling ?? 'no limit',
            } : null,

            // === P2: 代码质量指标 (仅评测报告) ===
            codeQuality: evalResult.codeQuality ? {
                avgCodeLength: evalResult.codeQuality.avgCodeLength ?? evalResult.codeQuality.avg_code_length ?? null,
                avgLineCount: evalResult.codeQuality.avgLineCount ?? evalResult.codeQuality.avg_line_count ?? null,
                extraIORate: evalResult.codeQuality.extraIORate ?? evalResult.codeQuality.extra_io_rate ?? null,
                interfaceComplianceRate: evalResult.codeQuality.interfaceComplianceRate ??
                    evalResult.codeQuality.interface_compliance_rate ?? null,
            } : null,

            // === P1: 可复现性信息 ===
            reproducibility: evalResult.reproducibilityInfo ? {
                pythonSeed: evalResult.reproducibilityInfo.pythonSeed ?? evalResult.reproducibilityInfo.python_seed ?? null,
                numpySeed: evalResult.reproducibilityInfo.numpySeed ?? evalResult.reproducibilityInfo.numpy_seed ?? null,
                torchSeed: evalResult.reproducibilityInfo.torchSeed ?? evalResult.reproducibilityInfo.torch_seed ?? null,
                evaluatorVersion: evalResult.reproducibilityInfo.evaluatorVersion ??
                    evalResult.reproducibilityInfo.evaluator_version ?? '1.0.0',
                checkpointHash: evalResult.reproducibilityInfo.checkpointHash ??
                    evalResult.reproducibilityInfo.checkpoint_hash ?? null,
            } : null,

            // === 原始数据（调试用）===
            rawConfig: config,
            rawMetrics: metrics,
            rawEvalResult: evalResult,
        };

        return report;
    }

    /**
     * 解析 target modules
     */
    private parseTargetModules(dbValue: string | null | undefined, configValue: any): string[] {
        if (dbValue) {
            try { return JSON.parse(dbValue); } catch { }
        }
        if (Array.isArray(configValue)) return configValue;
        return [];
    }

    /**
     * 安全解析 JSON
     */
    private parseJson(value: string | null | undefined, defaultValue: any): any {
        if (!value) return defaultValue;
        try { return JSON.parse(value); } catch { return defaultValue; }
    }

    /**
     * 计算持续时间
     */
    private calculateDuration(start: Date | null, end: Date | null): string {
        if (!start || !end) return '';
        const ms = end.getTime() - start.getTime();
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);

        if (hours > 0) {
            return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        }
        return `${seconds}s`;
    }

    /**
     * P0-FIX: 获取有效的最终 loss（有 lr 的最后一个 step，排除 epoch 平均值）
     */
    private getValidFinalLoss(metrics: any[]): number | null {
        if (!metrics || metrics.length === 0) return null;

        // 从后往前找有 lr 的最后一个 step
        for (let i = metrics.length - 1; i >= 0; i--) {
            const m = metrics[i];
            let extra: any = {};
            try { extra = JSON.parse(m.extraJson || '{}'); } catch { }

            // 如果有 lr，说明是正常的训练 step
            if (extra.lr != null) {
                return m.loss;
            }
        }

        // 如果所有 step 都没有 lr，返回倒数第二个（可能最后一个是 epoch 平均值）
        if (metrics.length >= 2) {
            return metrics[metrics.length - 2].loss;
        }

        return metrics[metrics.length - 1].loss;
    }

    /**
     * P0-FIX: 获取有效的 step 数（有 lr 的最后一个 step）
     */
    private getValidStepCount(metrics: any[]): number | null {
        if (!metrics || metrics.length === 0) return null;

        // 从后往前找有 lr 的 step
        for (let i = metrics.length - 1; i >= 0; i--) {
            const m = metrics[i];
            try {
                const extra = JSON.parse(m.extraJson || '{}');
                if (extra.lr != null) return m.step;
            } catch { }
        }

        // 如果都没有 lr，返回倒数第二个
        if (metrics.length >= 2) {
            return metrics[metrics.length - 2].step;
        }

        return metrics[metrics.length - 1].step;
    }

    /**
     * 计算 GPU 小时
     */
    private calculateGpuHours(start: Date | null, end: Date | null): number | null {
        if (!start || !end) return null;
        const ms = end.getTime() - start.getTime();
        return parseFloat((ms / (1000 * 60 * 60)).toFixed(4));
    }

    /**
     * 格式化大数字
     */
    private formatNumber(num: number | null | undefined): string {
        if (num == null) return 'N/A';
        if (num >= 1_000_000_000) return `${(num / 1_000_000_000).toFixed(2)}B`;
        if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(2)}M`;
        if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
        return num.toString();
    }

    /**
     * 生成完整详细的 HTML 报告
     */
    async generateHtml(report: AcademicReport): Promise<string> {
        // 生成训练曲线 SVG
        const lossCurveSvg = this.generateLossCurveSvg(report.lossCurve);
        // 生成详细的 Loss 数据表格
        const lossTableHtml = this.generateLossTableHtml(report.lossCurve);
        // 生成 Per-Epoch 统计
        const perEpochHtml = this.generatePerEpochMetricsHtml(report.lossCurve);


        return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${report.runName} - Complete Training Report</title>
    <style>
        :root {
            --bg-primary: #0f0f1a;
            --bg-secondary: #1a1a2e;
            --bg-tertiary: #252540;
            --bg-card: #2d2d4a;
            --text-primary: #f0f0f5;
            --text-secondary: #a0a0b0;
            --text-muted: #707080;
            --accent: #4a9eff;
            --accent-light: #6bb3ff;
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
            --border: #3a3a5a;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 24px;
        }
        
        /* Header */
        .header {
            text-align: center;
            margin-bottom: 48px;
            padding-bottom: 32px;
            border-bottom: 1px solid var(--border);
        }
        
        .header h1 {
            color: var(--accent);
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 16px;
        }
        
        .header .meta {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 16px;
            color: var(--text-secondary);
            font-size: 14px;
        }
        
        .header .meta-item {
            background: var(--bg-secondary);
            padding: 8px 16px;
            border-radius: 8px;
            border: 1px solid var(--border);
        }
        
        .header .meta-item strong {
            color: var(--text-primary);
        }
        
        /* Status Badge */
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .status-badge.success { background: var(--success); color: white; }
        .status-badge.running { background: var(--accent); color: white; }
        .status-badge.failed { background: var(--error); color: white; }
        
        /* Key Metrics Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        
        .metric-card {
            background: linear-gradient(135deg, var(--bg-tertiary), var(--bg-secondary));
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            border: 1px solid var(--border);
        }
        
        .metric-card .value {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--accent);
            line-height: 1;
            margin-bottom: 8px;
        }
        
        .metric-card .value.success { color: var(--success); }
        .metric-card .value.warning { color: var(--warning); }
        .metric-card .value.error { color: var(--error); }
        
        .metric-card .label {
            color: var(--text-secondary);
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Section */
        .section {
            background: var(--bg-secondary);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
            border: 1px solid var(--border);
        }
        
        .section h2 {
            color: var(--accent);
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .section h2 .icon {
            font-size: 1.5rem;
        }
        
        /* Table */
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        
        th, td {
            padding: 14px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        
        th {
            color: var(--text-secondary);
            font-weight: 500;
            width: 40%;
            background: rgba(0,0,0,0.2);
        }
        
        td {
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            color: var(--text-primary);
        }
        
        td.highlight { color: var(--accent); font-weight: 600; }
        td.success { color: var(--success); }
        td.warning { color: var(--warning); }
        td.error { color: var(--error); }
        td.muted { color: var(--text-muted); font-style: italic; }
        
        /* Two Column Layout */
        .two-col {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
        }
        
        @media (max-width: 768px) {
            .two-col { grid-template-columns: 1fr; }
        }
        
        /* Chart Container */
        .chart-container {
            background: var(--bg-tertiary);
            border-radius: 12px;
            padding: 24px;
            margin-top: 20px;
        }
        
        .chart-container h3 {
            color: var(--text-secondary);
            font-size: 14px;
            margin-bottom: 16px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .chart-svg {
            width: 100%;
            height: 250px;
        }
        
        /* Collapsible Raw Data */
        .raw-data {
            background: var(--bg-tertiary);
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }
        
        .raw-data summary {
            cursor: pointer;
            color: var(--text-secondary);
            font-size: 14px;
            font-weight: 500;
            padding: 8px 0;
        }
        
        .raw-data pre {
            background: var(--bg-primary);
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 12px;
            line-height: 1.5;
            color: var(--text-secondary);
            margin-top: 12px;
        }
        
        /* Footer */
        footer {
            margin-top: 48px;
            text-align: center;
            color: var(--text-muted);
            font-size: 12px;
            padding: 24px;
            border-top: 1px solid var(--border);
        }
        
        /* Checkpoints List */
        .checkpoints-list {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 16px;
        }
        
        .checkpoint-item {
            background: var(--bg-tertiary);
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 13px;
            border: 1px solid var(--border);
        }
        
        .checkpoint-item .step {
            color: var(--accent);
            font-weight: 600;
        }
        
        .checkpoint-item .loss {
            color: var(--text-secondary);
            margin-left: 8px;
        }
    </style>
</head>
<body>
<div class="container">
    <!-- Header -->
    <div class="header">
        <h1>🧪 ${report.runName}</h1>
        <span class="status-badge ${report.status}">${report.status.toUpperCase()}</span>
        <div class="meta">
            <div class="meta-item">Run ID: <strong>${report.runId.slice(0, 8)}...</strong></div>
            <div class="meta-item">Type: <strong>${report.runType}</strong></div>
            <div class="meta-item">Duration: <strong>${report.duration || 'N/A'}</strong></div>
            <div class="meta-item">Seed: <strong>${report.seed ?? 'N/A'}</strong></div>
            ${report.gitCommit ? `<div class="meta-item">Git: <strong>${report.gitCommit.slice(0, 7)}</strong></div>` : ''}
        </div>
    </div>

    <!-- Key Metrics -->
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="value ${report.evaluation.passAt1 && report.evaluation.passAt1 > 50 ? 'success' : ''}">${this.formatValue(report.evaluation.passAt1, '%')}</div>
            <div class="label">Pass@1</div>
        </div>
        <div class="metric-card">
            <div class="value">${this.formatValue(report.evaluation.compileRate, '%')}</div>
            <div class="label">Compile Rate</div>
        </div>
        <div class="metric-card">
            <div class="value">${this.formatValue(report.trainingStats.finalLoss)}</div>
            <div class="label">Final Loss</div>
        </div>
        <div class="metric-card">
            <div class="value">${this.formatValue(report.trainingStats.tokensPerSecond)}</div>
            <div class="label">Tokens/sec</div>
        </div>
        <div class="metric-card">
            <div class="value">${this.formatValue(report.trainingStats.gpuHours, 'h', 2)}</div>
            <div class="label">GPU Hours</div>
        </div>
        <div class="metric-card">
            <div class="value">${this.formatNumber(report.lora.trainableParams)}</div>
            <div class="label">Trainable Params</div>
        </div>
    </div>

    <!-- Training Loss Curve -->
    ${report.lossCurve.length > 0 ? `
    <div class="section">
        <h2><span class="icon">📈</span> Training Loss Curve</h2>
        <div class="chart-container">
            ${lossCurveSvg}
        </div>
    </div>
    ` : ''}

    <!-- Per-Epoch Metrics -->
    ${perEpochHtml}

    <!-- Training Metrics Log Table -->
    ${lossTableHtml}


    <!-- Model & Dataset -->
    <div class="two-col">
        <div class="section">
            <h2><span class="icon">🤖</span> Base Model</h2>
            <table>
                <tr><th>Model Name</th><td class="highlight">${report.model.name}</td></tr>
                <tr><th>Parameters</th><td>${report.model.params}</td></tr>
                <tr><th>Path</th><td>${report.model.path}</td></tr>
                <tr><th>Quantization</th><td>${report.model.quantization}</td></tr>
            </table>
        </div>
        <div class="section">
            <h2><span class="icon">📊</span> Dataset</h2>
            <table>
                <tr><th>Dataset Name</th><td class="highlight">${report.dataset.name}</td></tr>
                <tr><th>Total Samples</th><td>${report.dataset.samples?.toLocaleString() ?? 'N/A'}</td></tr>
                <tr><th>Train Samples</th><td>${report.dataset.trainSamples?.toLocaleString() ?? 'N/A'}</td></tr>
                <tr><th>Val Samples</th><td>${report.dataset.valSamples?.toLocaleString() ?? 'N/A'}</td></tr>
                <tr><th>Total Tokens</th><td>${report.dataset.totalTokens?.toLocaleString() ?? 'N/A'}</td></tr>
                <tr><th>Path</th><td>${report.dataset.path}</td></tr>
            </table>
        </div>
    </div>

    <!-- Environment & Hardware -->
    <div class="two-col">
        <div class="section">
            <h2><span class="icon">🖥️</span> Environment</h2>
            <table>
                <tr><th>Operating System</th><td>${report.environment.os ?? '<span class="muted">Not collected</span>'}</td></tr>
                <tr><th>Python</th><td>${report.environment.python ?? '<span class="muted">Not collected</span>'}</td></tr>
                <tr><th>PyTorch</th><td>${report.environment.pytorch ?? '<span class="muted">Not collected</span>'}</td></tr>
                <tr><th>Transformers</th><td>${report.environment.transformers ?? '<span class="muted">Not collected</span>'}</td></tr>
                <tr><th>TRL</th><td>${report.environment.trl ?? '<span class="muted">Not collected</span>'}</td></tr>
                <tr><th>PEFT</th><td>${report.environment.peft ?? '<span class="muted">Not collected</span>'}</td></tr>
                <tr><th>CUDA</th><td>${report.environment.cuda ?? '<span class="muted">Not collected</span>'}</td></tr>
                <tr><th>cuDNN</th><td>${report.environment.cudnn ?? '<span class="muted">Not collected</span>'}</td></tr>
                <tr><th>bitsandbytes</th><td>${report.environment.bitsandbytes ?? '<span class="muted">Not collected</span>'}</td></tr>
            </table>
        </div>
        <div class="section">
            <h2><span class="icon">⚡</span> Hardware</h2>
            <table>
                <tr><th>GPU</th><td class="highlight">${report.hardware.gpu ?? '<span class="muted">Not collected</span>'}</td></tr>
                <tr><th>GPU Memory</th><td>${report.hardware.gpuMemory ?? '<span class="muted">Not collected</span>'}</td></tr>
                <tr><th>CPU</th><td>${report.hardware.cpu ?? '<span class="muted">Not collected</span>'}</td></tr>
                <tr><th>RAM</th><td>${report.hardware.ram ?? '<span class="muted">Not collected</span>'}</td></tr>
            </table>
        </div>
    </div>

    <!-- Training Configuration (仅训练报告) -->
    ${report.runType !== 'eval' ? `
    <div class="section">
        <h2><span class="icon">⚙️</span> Training Configuration</h2>
        <div class="two-col">
            <table>
                <tr><th>Batch Size (per device)</th><td>${report.training.batchSize}</td></tr>
                <tr><th>Gradient Accumulation</th><td>${report.training.gradientAccumulationSteps}</td></tr>
                <tr><th>Effective Batch Size</th><td class="highlight">${report.training.effectiveBatchSize}</td></tr>
                <tr><th>Learning Rate</th><td>${report.training.learningRate}</td></tr>
                <tr><th>Scheduler</th><td>${report.training.scheduler}</td></tr>
                <tr><th>Warmup Ratio</th><td>${report.training.warmupRatio}</td></tr>
            </table>
            <table>
                <tr><th>Epochs</th><td>${report.training.epochs}</td></tr>
                <tr><th>Max Sequence Length</th><td>${report.training.maxSeqLength}</td></tr>
                <tr><th>Optimizer</th><td>${report.training.optimizer}</td></tr>
                <tr><th>Weight Decay</th><td>${report.training.weightDecay}</td></tr>
                <tr><th>Precision</th><td>${report.training.precision}</td></tr>
                <tr><th>Total Steps</th><td class="highlight">${report.trainingStats.totalSteps?.toLocaleString() ?? 'N/A'}</td></tr>
            </table>
        </div>
    </div>
    ` : ''}

    <!-- LoRA Configuration (仅训练报告) -->
    ${report.runType !== 'eval' && report.lora.enabled ? `
    <div class="section">
        <h2><span class="icon">🔧</span> LoRA Configuration</h2>
        <div class="two-col">
            <table>
                <tr><th>Rank (r)</th><td>${report.lora.rank ?? 'N/A'}</td></tr>
                <tr><th>Alpha</th><td>${report.lora.alpha ?? 'N/A'}</td></tr>
                <tr><th>Dropout</th><td>${report.lora.dropout ?? 'N/A'}</td></tr>
                <tr><th>Quantization</th><td>${report.lora.quantization ?? 'None'}</td></tr>
            </table>
            <table>
                <tr><th>Target Modules</th><td>${report.lora.targetModules.join(', ') || 'N/A'}</td></tr>
                <tr><th>Trainable Parameters</th><td class="highlight">${this.formatNumber(report.lora.trainableParams)}</td></tr>
                <tr><th>Total Parameters</th><td>${this.formatNumber(report.lora.totalParams)}</td></tr>
                <tr><th>Trainable Percentage</th><td class="highlight">${report.lora.trainablePercent != null ? report.lora.trainablePercent.toFixed(4) + '%' : 'N/A'}</td></tr>
            </table>
        </div>
    </div>
    ` : ''}

    <!-- P1: Evaluation Protocol (仅评测报告) -->
    ${report.runType === 'eval' && report.evaluationProtocol ? `
    <div class="section">
        <h2><span class="icon">📋</span> Evaluation Protocol</h2>
        <p style="color: var(--text-secondary); font-size: 13px; margin-bottom: 16px;">
            <strong>Important:</strong> This section defines how metrics are computed for reproducibility.
        </p>
        <div class="two-col">
            <table>
                <tr><th>Pass@k Definition</th><td>${report.evaluationProtocol.passAtKDefinition}</td></tr>
                <tr><th>Samples per Task (N)</th><td class="highlight">${report.evaluationProtocol.samplesPerTask}</td></tr>
                <tr><th>Temperature</th><td>${report.evaluationProtocol.temperature}</td></tr>
                <tr><th>Top-p</th><td>${report.evaluationProtocol.topP}</td></tr>
            </table>
            <table>
                <tr><th>Sorting Method</th><td>${report.evaluationProtocol.sortingMethod}</td></tr>
                <tr><th>Compile Rate Def.</th><td>${report.evaluationProtocol.compileRateDefinition}</td></tr>
                <tr><th>Timeout Handling</th><td>${report.evaluationProtocol.timeoutHandling}</td></tr>
                <tr><th>Memory Limit</th><td>${report.evaluationProtocol.memoryLimitHandling}</td></tr>
            </table>
        </div>
    </div>
    ` : ''}

    <!-- P2: Code Quality (仅评测报告) -->
    ${report.runType === 'eval' && report.codeQuality ? `
    <div class="section">
        <h2><span class="icon">📊</span> Code Quality Metrics</h2>
        <table>
            <tr><th>Interface Compliance</th><td>${this.formatValue(report.codeQuality.interfaceComplianceRate, '%')}</td><td style="color: var(--text-muted);">Contains function definition</td></tr>
            <tr><th>Extra I/O Rate</th><td class="warning">${this.formatValue(report.codeQuality.extraIORate, '%')}</td><td style="color: var(--text-muted);">Contains print/input (may cause issues)</td></tr>
            <tr><th>Avg Code Length</th><td>${report.codeQuality.avgCodeLength?.toFixed(0) ?? 'N/A'} chars</td><td style="color: var(--text-muted);">Average character count</td></tr>
            <tr><th>Avg Line Count</th><td>${report.codeQuality.avgLineCount?.toFixed(1) ?? 'N/A'}</td><td style="color: var(--text-muted);">Average lines per solution</td></tr>
        </table>
    </div>
    ` : ''}

    <!-- Evaluation Results -->
    <div class="section">
        <h2><span class="icon">🎯</span> Evaluation Results</h2>
        <div class="two-col">
            <div>
                <h3 style="color: var(--text-secondary); font-size: 14px; margin-bottom: 12px;">Pass@k Metrics</h3>
                <table>
                    <tr><th>Pass@1</th><td class="highlight success">${this.formatValue(report.evaluation.passAt1, '%')}</td></tr>
                    <tr><th>Pass@5</th><td>${this.formatValue(report.evaluation.passAt5, '%')}</td></tr>
                    <tr><th>Pass@10</th><td>${this.formatValue(report.evaluation.passAt10, '%')}</td></tr>
                    <tr><th>Compile Rate</th><td>${this.formatValue(report.evaluation.compileRate, '%')}</td></tr>
                </table>
            </div>
            <div>
                <h3 style="color: var(--text-secondary); font-size: 14px; margin-bottom: 12px;">Error Distribution</h3>
                <table>
                    <tr><th>Syntax Error</th><td class="error">${this.formatValue(report.evaluation.errorStats.syntaxErrorRate, '%')}</td></tr>
                    <tr><th>Runtime Error</th><td class="warning">${this.formatValue(report.evaluation.errorStats.runtimeErrorRate, '%')}</td></tr>
                    <tr><th>Timeout</th><td>${this.formatValue(report.evaluation.errorStats.timeoutRate, '%')}</td></tr>
                    <tr><th>Assertion Error</th><td>${this.formatValue(report.evaluation.errorStats.assertionErrorRate, '%')}</td></tr>
                    <tr><th>Import Error</th><td>${this.formatValue(report.evaluation.errorStats.importErrorRate, '%')}</td></tr>
                    <tr><th>Memory Error</th><td>${this.formatValue(report.evaluation.errorStats.memoryErrorRate, '%')}</td></tr>
                </table>
            </div>
        </div>
        
        <h3 style="color: var(--text-secondary); font-size: 14px; margin: 20px 0 12px 0;">Execution Time Statistics</h3>
        <table>
            <tr>
                <th>Mean Runtime</th><td>${this.formatValue(report.evaluation.timeStats.meanRuntimeMs, 'ms')}</td>
                <th>P50 Runtime</th><td>${this.formatValue(report.evaluation.timeStats.p50RuntimeMs, 'ms')}</td>
            </tr>
            <tr>
                <th>P95 Runtime</th><td>${this.formatValue(report.evaluation.timeStats.p95RuntimeMs, 'ms')}</td>
                <th>Max Runtime</th><td>${this.formatValue(report.evaluation.timeStats.maxRuntimeMs, 'ms')}</td>
            </tr>
        </table>
    </div>

    <!-- Checkpoints -->
    ${report.checkpoints.length > 0 ? `
    <div class="section">
        <h2><span class="icon">💾</span> Checkpoints (${report.checkpoints.length})</h2>
        <div class="checkpoints-list">
            ${report.checkpoints.map(cp => `
                <div class="checkpoint-item">
                    <span class="step">Step ${cp.step}</span>
                    ${cp.epoch != null ? `<span class="loss">(Epoch ${cp.epoch})</span>` : ''}
                    ${cp.loss != null ? `<span class="loss">Loss: ${cp.loss.toFixed(4)}</span>` : ''}
                </div>
            `).join('')}
        </div>
    </div>
    ` : ''}

    <!-- Post-Processing -->
    ${report.postProcess ? `
    <div class="section">
        <h2><span class="icon">🔄</span> Post-Processing Results</h2>
        <table>
            <tr><th>Pass@1 (Before)</th><td>${this.formatValue(report.postProcess.passAt1Before, '%')}</td></tr>
            <tr><th>Pass@1 (After)</th><td class="success">${this.formatValue(report.postProcess.passAt1After, '%')}</td></tr>
            <tr><th>Syntax Error (Before)</th><td>${this.formatValue(report.postProcess.syntaxErrorBefore, '%')}</td></tr>
            <tr><th>Syntax Error (After)</th><td class="success">${this.formatValue(report.postProcess.syntaxErrorAfter, '%')}</td></tr>
            <tr><th>Runtime Error (Before)</th><td>${this.formatValue(report.postProcess.runtimeErrorBefore, '%')}</td></tr>
            <tr><th>Runtime Error (After)</th><td class="success">${this.formatValue(report.postProcess.runtimeErrorAfter, '%')}</td></tr>
        </table>
    </div>
    ` : ''}

    <!-- Raw Configuration Data -->
    <div class="section">
        <h2><span class="icon">📋</span> Raw Configuration</h2>
        <details class="raw-data">
            <summary>View Training Configuration JSON</summary>
            <pre>${JSON.stringify(report.rawConfig, null, 2)}</pre>
        </details>
        <details class="raw-data">
            <summary>View Metrics JSON</summary>
            <pre>${JSON.stringify(report.rawMetrics, null, 2)}</pre>
        </details>
        <details class="raw-data">
            <summary>View Evaluation Results JSON</summary>
            <pre>${JSON.stringify(report.rawEvalResult, null, 2)}</pre>
        </details>
    </div>

    <footer>
        <p>Generated by LLM Training Pipeline</p>
        <p>${new Date().toISOString()} | Run ID: ${report.runId}</p>
    </footer>
</div>
</body>
</html>`;
    }

    /**
     * 格式化显示值
     */
    private formatValue(value: number | null | undefined, suffix: string = '', decimals: number = 2): string {
        if (value == null) return 'N/A';
        return value.toFixed(decimals) + suffix;
    }

    /**
     * 生成 Per-Epoch Metrics HTML - 统计每个 epoch 的 loss 均值
     */
    private generatePerEpochMetricsHtml(lossCurve: { step: number; loss: number; lr?: number; epoch?: number }[]): string {
        if (lossCurve.length === 0) return '';

        // 按 epoch 分组
        // P0-FIX: HuggingFace Trainer 的 epoch 是小数形式（如 0.1, 0.2...），需要取整后分组
        const epochsData: Map<number, { losses: number[]; evalLoss?: number }> = new Map();

        for (const m of lossCurve) {
            const rawEpoch = m.epoch;
            // 如果没有 epoch 字段，默认为 1；否则取整（0.1->1, 0.9->1, 1.0->1, 1.1->2）
            const epoch = rawEpoch == null ? 1 : Math.max(1, Math.floor(rawEpoch) + (rawEpoch % 1 > 0 ? 1 : 0));
            if (!epochsData.has(epoch)) {
                epochsData.set(epoch, { losses: [] });
            }
            if (m.loss != null) {
                epochsData.get(epoch)!.losses.push(m.loss);
            }
        }

        // 如果只有一个 epoch，不显示此部分
        if (epochsData.size <= 1) return '';

        // 生成表格行
        const sortedEpochs = Array.from(epochsData.keys()).sort((a, b) => a - b);
        const rows = sortedEpochs.map(epoch => {
            const data = epochsData.get(epoch)!;
            const avgLoss = data.losses.length > 0
                ? (data.losses.reduce((a, b) => a + b, 0) / data.losses.length).toFixed(4)
                : 'N/A';
            const minLoss = data.losses.length > 0 ? Math.min(...data.losses).toFixed(4) : 'N/A';
            const maxLoss = data.losses.length > 0 ? Math.max(...data.losses).toFixed(4) : 'N/A';
            const stepsCount = data.losses.length;

            return `
                <tr>
                    <td class="highlight">${epoch}</td>
                    <td>${avgLoss}</td>
                    <td>${minLoss}</td>
                    <td>${maxLoss}</td>
                    <td>${stepsCount}</td>
                </tr>
            `;
        }).join('');

        return `
        <div class="section">
            <h2><span class="icon">📊</span> Per-Epoch Loss Statistics</h2>
            <p style="color: var(--text-secondary); margin-bottom: 16px;">
                Loss statistics grouped by training epoch
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Epoch</th>
                        <th>Avg Loss</th>
                        <th>Min Loss</th>
                        <th>Max Loss</th>
                        <th>Steps</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        </div>
        `;
    }


    /**
     * 生成 Per-Epoch Metrics Markdown - 统计每个 epoch 的 loss 均值
     */
    private generatePerEpochMarkdown(lossCurve: { step: number; loss: number; lr?: number; epoch?: number }[]): string {
        if (lossCurve.length === 0) return '';

        // 按 epoch 分组
        // P0-FIX: HuggingFace Trainer 的 epoch 是小数形式（如 0.1, 0.2...），需要取整后分组
        const epochsData: Map<number, { losses: number[] }> = new Map();

        for (const m of lossCurve) {
            const rawEpoch = m.epoch;
            // 如果没有 epoch 字段，默认为 1；否则取整（0.1->1, 0.9->1, 1.0->1, 1.1->2）
            const epoch = rawEpoch == null ? 1 : Math.max(1, Math.floor(rawEpoch) + (rawEpoch % 1 > 0 ? 1 : 0));
            if (!epochsData.has(epoch)) {
                epochsData.set(epoch, { losses: [] });
            }
            if (m.loss != null) {
                epochsData.get(epoch)!.losses.push(m.loss);
            }
        }

        // 如果只有一个 epoch，不显示此部分
        if (epochsData.size <= 1) return '';

        // 生成 Markdown 表格
        const sortedEpochs = Array.from(epochsData.keys()).sort((a, b) => a - b);
        const rows = sortedEpochs.map(epoch => {
            const data = epochsData.get(epoch)!;
            const avgLoss = data.losses.length > 0
                ? (data.losses.reduce((a, b) => a + b, 0) / data.losses.length).toFixed(4)
                : 'N/A';
            const minLoss = data.losses.length > 0 ? Math.min(...data.losses).toFixed(4) : 'N/A';
            const maxLoss = data.losses.length > 0 ? Math.max(...data.losses).toFixed(4) : 'N/A';
            const stepsCount = data.losses.length;

            return `| ${epoch} | ${avgLoss} | ${minLoss} | ${maxLoss} | ${stepsCount} |`;
        }).join('\n');

        return `### Per-Epoch Loss Statistics

| Epoch | Avg Loss | Min Loss | Max Loss | Steps |
|-------|----------|----------|----------|-------|
${rows}
`;
    }

    /**
     * 生成训练曲线 SVG
     */
    private generateLossCurveSvg(lossCurve: { step: number; loss: number }[]): string {

        if (lossCurve.length === 0) return '<p style="color: var(--text-muted); text-align: center;">No training data available</p>';

        const width = 800;
        const height = 220;
        const padding = { top: 20, right: 40, bottom: 40, left: 60 };
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;

        // 获取数据范围
        const steps = lossCurve.map(d => d.step);
        const losses = lossCurve.map(d => d.loss);
        const minStep = Math.min(...steps);
        const maxStep = Math.max(...steps);
        const minLoss = Math.min(...losses) * 0.9;
        const maxLoss = Math.max(...losses) * 1.1;

        // 缩放函数
        const scaleX = (step: number) => padding.left + ((step - minStep) / (maxStep - minStep || 1)) * chartWidth;
        const scaleY = (loss: number) => padding.top + chartHeight - ((loss - minLoss) / (maxLoss - minLoss || 1)) * chartHeight;

        // 生成路径
        const pathData = lossCurve.map((d, i) =>
            `${i === 0 ? 'M' : 'L'} ${scaleX(d.step).toFixed(1)} ${scaleY(d.loss).toFixed(1)}`
        ).join(' ');

        // 生成 Y 轴刻度
        const yTicks = [0, 0.25, 0.5, 0.75, 1].map(t => {
            const val = minLoss + t * (maxLoss - minLoss);
            return { y: scaleY(val), label: val.toFixed(2) };
        });

        // 生成 X 轴刻度
        const xTicks = [0, 0.25, 0.5, 0.75, 1].map(t => {
            const val = minStep + t * (maxStep - minStep);
            return { x: scaleX(val), label: Math.round(val).toString() };
        });

        return `
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet">
            <!-- Grid Lines -->
            ${yTicks.map(t => `<line x1="${padding.left}" y1="${t.y}" x2="${width - padding.right}" y2="${t.y}" stroke="#3a3a5a" stroke-dasharray="4"/>`).join('')}
            
            <!-- Axes -->
            <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${height - padding.bottom}" stroke="#4a4a6a" stroke-width="2"/>
            <line x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}" stroke="#4a4a6a" stroke-width="2"/>
            
            <!-- Y Axis Labels -->
            ${yTicks.map(t => `<text x="${padding.left - 10}" y="${t.y + 4}" text-anchor="end" fill="#a0a0b0" font-size="12">${t.label}</text>`).join('')}
            
            <!-- X Axis Labels -->
            ${xTicks.map(t => `<text x="${t.x}" y="${height - padding.bottom + 20}" text-anchor="middle" fill="#a0a0b0" font-size="12">${t.label}</text>`).join('')}
            
            <!-- Axis Titles -->
            <text x="${padding.left - 45}" y="${height / 2}" text-anchor="middle" fill="#707080" font-size="12" transform="rotate(-90 ${padding.left - 45} ${height / 2})">Loss</text>
            <text x="${width / 2}" y="${height - 5}" text-anchor="middle" fill="#707080" font-size="12">Step</text>
            
            <!-- Loss Curve -->
            <path d="${pathData}" fill="none" stroke="#4a9eff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            
            <!-- Start and End Points -->
            <circle cx="${scaleX(lossCurve[0].step)}" cy="${scaleY(lossCurve[0].loss)}" r="4" fill="#f59e0b"/>
            <circle cx="${scaleX(lossCurve[lossCurve.length - 1].step)}" cy="${scaleY(lossCurve[lossCurve.length - 1].loss)}" r="5" fill="#10b981"/>
        </svg>`;
    }

    /**
     * 生成详细的 Loss 数据表格 HTML
     */
    private generateLossTableHtml(lossCurve: { step: number; loss: number; lr?: number; epoch?: number }[]): string {
        if (lossCurve.length === 0) return '';

        // 统计信息
        const totalPoints = lossCurve.length;
        const losses = lossCurve.map(d => d.loss).filter(l => l != null);
        const minLoss = losses.length > 0 ? Math.min(...losses) : null;
        const maxLoss = losses.length > 0 ? Math.max(...losses) : null;
        const avgLoss = losses.length > 0 ? losses.reduce((a, b) => a + b, 0) / losses.length : null;

        // 找到最低 loss 对应的 step
        const minLossItem = lossCurve.find(d => d.loss === minLoss);
        const minLossStep = minLossItem?.step ?? null;

        // 确定要显示的关键点索引 - 使用 linspace 风格均匀采样
        const maxSamples = 30;
        let sortedIndices: number[];

        if (lossCurve.length <= maxSamples) {
            // 数据量小，直接使用所有索引
            sortedIndices = Array.from({ length: lossCurve.length }, (_, i) => i);
        } else {
            // 使用 linspace 风格等间距采样
            // 预留 1 个位置给最低 loss 点
            const effectiveSamples = maxSamples - 1;
            const sampleSet = new Set<number>();

            for (let i = 0; i < effectiveSamples; i++) {
                // linspace 公式: i * (n-1) / (samples-1) 确保包含首尾
                const idx = Math.round(i * (lossCurve.length - 1) / (effectiveSamples - 1));
                sampleSet.add(idx);
            }

            // 添加最低 loss 点
            const minLossIndex = lossCurve.findIndex(d => d.loss === minLoss);
            if (minLossIndex >= 0) sampleSet.add(minLossIndex);

            sortedIndices = Array.from(sampleSet).sort((a, b) => a - b);
        }

        // 生成摘要表格行
        const summaryRows = sortedIndices.map(idx => {
            const m = lossCurve[idx];
            const lossClass = m.loss === minLoss ? 'highlight' : '';
            return `
                <tr>
                    <td>${m.step}</td>
                    <td>${m.epoch ?? '-'}</td>
                    <td class="${lossClass}">${m.loss?.toFixed(6) ?? 'N/A'}</td>
                    <td>${m.lr != null ? m.lr.toExponential(2) : 'N/A'}</td>
                </tr>
            `;
        }).join('');

        // 生成完整数据行
        const allRows = lossCurve.map(m => `
            <tr>
                <td>${m.step}</td>
                <td>${m.epoch ?? '-'}</td>
                <td>${m.loss?.toFixed(6) ?? 'N/A'}</td>
                <td>${m.lr != null ? m.lr.toExponential(2) : 'N/A'}</td>
            </tr>
        `).join('');

        return `
        <div class="section">
            <h2><span class="icon">📊</span> Training Metrics Log</h2>
            
            <!-- 统计摘要 -->
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px;">
                <div style="background: var(--bg-tertiary); padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: var(--text-secondary); font-size: 12px;">Total Steps</div>
                    <div style="color: var(--accent); font-size: 18px; font-weight: 600;">${totalPoints}</div>
                </div>
                <div style="background: var(--bg-tertiary); padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: var(--text-secondary); font-size: 12px;">Min Loss (Step ${minLossStep ?? 'N/A'})</div>
                    <div style="color: var(--success); font-size: 18px; font-weight: 600;">${minLoss?.toFixed(6) ?? 'N/A'}</div>
                </div>
                <div style="background: var(--bg-tertiary); padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: var(--text-secondary); font-size: 12px;">Max Loss</div>
                    <div style="color: var(--warning); font-size: 18px; font-weight: 600;">${maxLoss?.toFixed(6) ?? 'N/A'}</div>
                </div>
                <div style="background: var(--bg-tertiary); padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: var(--text-secondary); font-size: 12px;">Avg Loss</div>
                    <div style="color: var(--text-primary); font-size: 18px; font-weight: 600;">${avgLoss?.toFixed(6) ?? 'N/A'}</div>
                </div>
            </div>
            
            <!-- 摘要表格 -->
            <h3 style="color: var(--text-secondary); font-size: 14px; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Key Data Points (${sortedIndices.length} of ${totalPoints})</h3>
            <table>
                <thead>
                    <tr>
                        <th>Step</th>
                        <th>Epoch</th>
                        <th>Loss</th>
                        <th>Learning Rate</th>
                    </tr>
                </thead>
                <tbody>
                    ${summaryRows}
                </tbody>
            </table>
            
            <!-- 完整数据（可展开） -->
            <details class="raw-data" style="margin-top: 20px;">
                <summary>📋 View All ${totalPoints} Data Points</summary>
                <div style="max-height: 400px; overflow-y: auto;">
                    <table style="font-size: 12px;">
                        <thead>
                            <tr>
                                <th>Step</th>
                                <th>Epoch</th>
                                <th>Loss</th>
                                <th>Learning Rate</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${allRows}
                        </tbody>
                    </table>
                </div>
            </details>
        </div>
        `;
    }

    /**
     * 生成 Markdown 格式报告
     */
    async generateMarkdown(report: AcademicReport): Promise<string> {
        return `# ${report.runName} - Complete Training Report

## Experiment Metadata

| Property | Value |
|----------|-------|
| Run ID | \`${report.runId}\` |
| Type | ${report.runType} |
| Status | ${report.status} |
| Start Time | ${report.startTime} |
| End Time | ${report.endTime || 'N/A'} |
| Duration | ${report.duration || 'N/A'} |
| Random Seed | ${report.seed ?? 'N/A'} |
| Git Commit | \`${report.gitCommit || 'N/A'}\` |

## Key Metrics

| Metric | Value |
|--------|-------|
| **Pass@1** | **${this.formatValue(report.evaluation.passAt1, '%')}** |
| Pass@5 | ${this.formatValue(report.evaluation.passAt5, '%')} |
| Pass@10 | ${this.formatValue(report.evaluation.passAt10, '%')} |
| Compile Rate | ${this.formatValue(report.evaluation.compileRate, '%')} |
| Final Loss | ${this.formatValue(report.trainingStats.finalLoss)} |
| GPU Hours | ${this.formatValue(report.trainingStats.gpuHours, 'h', 4)} |

## Base Model

| Property | Value |
|----------|-------|
| Model | ${report.model.name} |
| Parameters | ${report.model.params} |
| Quantization | ${report.model.quantization} |
| Path | \`${report.model.path}\` |

## Dataset

| Property | Value |
|----------|-------|
| Name | ${report.dataset.name} |
| Total Samples | ${report.dataset.samples?.toLocaleString() ?? 'N/A'} |
| Train Samples | ${report.dataset.trainSamples?.toLocaleString() ?? 'N/A'} |
| Val Samples | ${report.dataset.valSamples?.toLocaleString() ?? 'N/A'} |
| Total Tokens | ${report.dataset.totalTokens?.toLocaleString() ?? 'N/A'} |

## Environment Versions

| Component | Version |
|-----------|---------| 
| OS | ${report.environment.os ?? 'Not collected'} |
| Python | ${report.environment.python ?? 'Not collected'} |
| PyTorch | ${report.environment.pytorch ?? 'Not collected'} |
| Transformers | ${report.environment.transformers ?? 'Not collected'} |
| TRL | ${report.environment.trl ?? 'Not collected'} |
| PEFT | ${report.environment.peft ?? 'Not collected'} |
| CUDA | ${report.environment.cuda ?? 'Not collected'} |
| bitsandbytes | ${report.environment.bitsandbytes ?? 'Not collected'} |

## Hardware Configuration

| Component | Specification |
|-----------|---------------|
| GPU | ${report.hardware.gpu ?? 'Not collected'} |
| GPU Memory | ${report.hardware.gpuMemory ?? 'Not collected'} |
| CPU | ${report.hardware.cpu ?? 'Not collected'} |
| RAM | ${report.hardware.ram ?? 'Not collected'} |

## Training Hyperparameters

| Parameter | Value |
|-----------|-------|
| Batch Size | ${report.training.batchSize} |
| Gradient Accumulation | ${report.training.gradientAccumulationSteps} |
| **Effective Batch Size** | **${report.training.effectiveBatchSize}** |
| Learning Rate | ${report.training.learningRate} |
| Scheduler | ${report.training.scheduler} |
| Warmup Ratio | ${report.training.warmupRatio} |
| Epochs | ${report.training.epochs} |
| Max Sequence Length | ${report.training.maxSeqLength} |
| Optimizer | ${report.training.optimizer} |
| Weight Decay | ${report.training.weightDecay} |
| Precision | ${report.training.precision} |

## LoRA Configuration

| Parameter | Value |
|-----------|-------|
| Enabled | ${report.lora.enabled} |
| Rank (r) | ${report.lora.rank ?? 'N/A'} |
| Alpha | ${report.lora.alpha ?? 'N/A'} |
| Dropout | ${report.lora.dropout ?? 'N/A'} |
| Target Modules | ${report.lora.targetModules.join(', ') || 'N/A'} |
| Quantization | ${report.lora.quantization ?? 'None'} |
| Trainable Parameters | ${this.formatNumber(report.lora.trainableParams)} |
| Total Parameters | ${this.formatNumber(report.lora.totalParams)} |
| Trainable % | ${report.lora.trainablePercent != null ? report.lora.trainablePercent.toFixed(4) + '%' : 'N/A'} |

## Training Statistics

| Metric | Value |
|--------|-------|
| Total Steps | ${report.trainingStats.totalSteps?.toLocaleString() ?? 'N/A'} |
| Total Tokens | ${report.trainingStats.totalTokens?.toLocaleString() ?? 'N/A'} |
| Throughput | ${this.formatValue(report.trainingStats.tokensPerSecond)} tokens/sec |
| GPU Hours | ${this.formatValue(report.trainingStats.gpuHours, '', 4)} |
| Final Loss | ${this.formatValue(report.trainingStats.finalLoss, '', 4)} |

${report.lossCurve.length > 0 ? `
## Training Metrics Log

### Loss Statistics

| Metric | Value |
|--------|-------|
| Total Data Points | ${report.lossCurve.length} |
| Min Loss | ${Math.min(...report.lossCurve.map(d => d.loss)).toFixed(6)} (Step ${report.lossCurve.find(d => d.loss === Math.min(...report.lossCurve.map(x => x.loss)))?.step ?? 'N/A'}) |
| Max Loss | ${Math.max(...report.lossCurve.map(d => d.loss)).toFixed(6)} |
| Avg Loss | ${(report.lossCurve.reduce((a, b) => a + b.loss, 0) / report.lossCurve.length).toFixed(6)} |

${this.generatePerEpochMarkdown(report.lossCurve)}


### Detailed Training Log

| Step | Epoch | Loss | Learning Rate |
|------|-------|------|---------------|
${report.lossCurve.slice(0, 50).map(m => `| ${m.step} | ${m.epoch ?? '-'} | ${m.loss?.toFixed(6) ?? 'N/A'} | ${m.lr != null ? m.lr.toExponential(2) : 'N/A'} |`).join('\n')}
${report.lossCurve.length > 50 ? `\n*... and ${report.lossCurve.length - 50} more data points*` : ''}
` : ''}

## Evaluation Results

### Pass@k Metrics

| Metric | Value |
|--------|-------|
| **Pass@1** | **${this.formatValue(report.evaluation.passAt1, '%')}** |
| Pass@5 | ${this.formatValue(report.evaluation.passAt5, '%')} |
| Pass@10 | ${this.formatValue(report.evaluation.passAt10, '%')} |
| Compile Rate | ${this.formatValue(report.evaluation.compileRate, '%')} |

### Error Distribution

| Error Type | Rate |
|------------|------|
| Syntax Error | ${this.formatValue(report.evaluation.errorStats.syntaxErrorRate, '%')} |
| Runtime Error | ${this.formatValue(report.evaluation.errorStats.runtimeErrorRate, '%')} |
| Timeout | ${this.formatValue(report.evaluation.errorStats.timeoutRate, '%')} |
| Assertion Error | ${this.formatValue(report.evaluation.errorStats.assertionErrorRate, '%')} |
| Import Error | ${this.formatValue(report.evaluation.errorStats.importErrorRate, '%')} |
| Memory Error | ${this.formatValue(report.evaluation.errorStats.memoryErrorRate, '%')} |

### Execution Time

| Metric | Value |
|--------|-------|
| Mean | ${this.formatValue(report.evaluation.timeStats.meanRuntimeMs, ' ms')} |
| P50 | ${this.formatValue(report.evaluation.timeStats.p50RuntimeMs, ' ms')} |
| P95 | ${this.formatValue(report.evaluation.timeStats.p95RuntimeMs, ' ms')} |
| Max | ${this.formatValue(report.evaluation.timeStats.maxRuntimeMs, ' ms')} |

${report.checkpoints.length > 0 ? `
## Checkpoints

| Step | Epoch | Loss |
|------|-------|------|
${report.checkpoints.map(cp => `| ${cp.step} | ${cp.epoch ?? 'N/A'} | ${cp.loss?.toFixed(4) ?? 'N/A'} |`).join('\n')}
` : ''}

${report.postProcess ? `
## Post-Processing Results

| Metric | Before | After | Δ |
|--------|--------|-------|---|
| Pass@1 | ${this.formatValue(report.postProcess.passAt1Before, '%')} | ${this.formatValue(report.postProcess.passAt1After, '%')} | ${report.postProcess.passAt1Before != null && report.postProcess.passAt1After != null ? `+${(report.postProcess.passAt1After - report.postProcess.passAt1Before).toFixed(2)}%` : 'N/A'} |
| Syntax Error | ${this.formatValue(report.postProcess.syntaxErrorBefore, '%')} | ${this.formatValue(report.postProcess.syntaxErrorAfter, '%')} | ${report.postProcess.syntaxErrorBefore != null && report.postProcess.syntaxErrorAfter != null ? `${(report.postProcess.syntaxErrorAfter - report.postProcess.syntaxErrorBefore).toFixed(2)}%` : 'N/A'} |
| Runtime Error | ${this.formatValue(report.postProcess.runtimeErrorBefore, '%')} | ${this.formatValue(report.postProcess.runtimeErrorAfter, '%')} | ${report.postProcess.runtimeErrorBefore != null && report.postProcess.runtimeErrorAfter != null ? `${(report.postProcess.runtimeErrorAfter - report.postProcess.runtimeErrorBefore).toFixed(2)}%` : 'N/A'} |
` : ''}

---
*Generated by LLM Training Pipeline | ${new Date().toISOString()}*
`;
    }
}

export default AcademicReportGenerator;
