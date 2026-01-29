import { FastifyInstance } from 'fastify';
import { ReportResponse, GenerateReportRequest } from '../types/index.js';
import { spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { prisma } from '../db/prisma-client.js';
import { getPython } from '../utils/python-utils.js';

// 获取 scripts 目录路径
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SCRIPTS_DIR = path.resolve(__dirname, '../../scripts');
const REPORTS_DIR = path.resolve(__dirname, '../../storage/reports');
const STORAGE_DIR = path.resolve(__dirname, '../../storage');

// 确保报告目录存在
if (!fs.existsSync(REPORTS_DIR)) {
    fs.mkdirSync(REPORTS_DIR, { recursive: true });
}

/**
 * 使用 Python 报告生成器生成报告 (HTML 或 Markdown)
 */
async function generatePythonReport(
    runId: string,
    title?: string,
    format: 'html' | 'markdown' = 'html'
): Promise<{ content: string; outputPath: string }> {
    // 获取 Run 数据用于生成临时配置文件
    const run = await prisma.run.findUnique({
        where: { id: runId },
        include: {
            model: true,
            dataset: true,
            experimentMeta: true,
            datasetMeta: true,
            loraStats: true,
            metrics: { orderBy: { step: 'asc' } },
        }
    });

    if (!run) {
        throw new Error(`Run not found: ${runId}`);
    }

    // 解析配置和结果
    let config = {};
    let evalResult = {};
    let metricsJson = {};
    try { config = JSON.parse(run.configJson || '{}'); } catch { }
    try { evalResult = JSON.parse(run.evalResultJson || '{}'); } catch { }
    try { metricsJson = JSON.parse(run.metricsJson || '{}'); } catch { }

    // 构建完整的配置对象供 Python 脚本使用
    // 处理扁平化配置和嵌套配置两种格式
    const flatConfig = config as any;

    // 训练指标 - 先计算 rawLoggedSteps 和 effectiveSteps（供后续 trainingConfig 使用）
    // 保存原始 metrics 数量（包含 warmup/pre-log）
    const rawMetrics = run.metrics
        .map((m) => {
            let extra: any = {};
            try { extra = JSON.parse(m.extraJson || '{}'); } catch { }
            return {
                step: m.step,
                loss: m.loss,
                lr: extra.lr,
                ...extra,
            };
        });

    const rawLoggedSteps = rawMetrics.length;

    // P0-FIX: 过滤掉没有 lr 或 lr=0 的步骤（warmup/pre-update）
    // lr=0 表示梯度累积期间的日志，还没有真正的参数更新
    const metrics = rawMetrics.filter(m => m.lr != null && m.lr > 0);
    const effectiveSteps = metrics.length;

    // 从 configJson 中提取 training 配置 (支持扁平和嵌套两种格式)
    const trainingConfig = flatConfig.training || {
        lr: flatConfig.lr,
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

    // 确保 total_steps 被正确传递 (优先使用 run 记录中的，其次是 config 中的)
    trainingConfig.total_steps = run.totalSteps || trainingConfig.total_steps;
    // 传递原始日志步数和有效步数（用于报告显示三种 steps）
    trainingConfig.raw_logged_steps = rawLoggedSteps;
    trainingConfig.effective_steps = effectiveSteps;

    // 从 configJson 和 loraStats 中提取 LoRA 配置
    const loraConfigFromJson = flatConfig.lora || {
        enabled: flatConfig.useLora !== false,
        rank: flatConfig.loraRank,
        alpha: flatConfig.loraAlpha,
        targetModules: flatConfig.loraTargetModules,
        quantization: flatConfig.quantization,
    };

    // 合并来自 run.loraStats 的数据
    const loraConfig = {
        ...loraConfigFromJson,
        rank: loraConfigFromJson.rank || run.loraStats?.rank,
        alpha: loraConfigFromJson.alpha || run.loraStats?.alpha,
        dropout: loraConfigFromJson.dropout || run.loraStats?.dropout,
        targetModules: loraConfigFromJson.targetModules || (run.loraStats?.targetModules ? JSON.parse(run.loraStats.targetModules) : undefined),
        quantization: loraConfigFromJson.quantization || flatConfig.quantization,
    };

    const reportConfig = {
        run_name: run.name,
        run_id: run.id,
        seed: run.seed,
        start_time: run.startedAt?.toISOString(),
        end_time: run.completedAt?.toISOString(),
        duration: run.duration,
        git_commit: run.gitCommit,
        model: {
            name: run.model.name,
            path: run.model.path,
            params: run.model.params,
        },
        dataset: {
            name: run.dataset.name,
            path: run.dataset.path,
            // P0-1: samples 应该是 train_samples 的值（如果 dataset.samples 为 0）
            samples: run.dataset.samples || run.datasetMeta?.trainSamples || 0,
            // 使用 nullish coalescing 确保 0 值有效
            train_samples: run.datasetMeta?.trainSamples ?? run.dataset.samples ?? 0,
            val_samples: run.datasetMeta?.valSamples,
            // 优先使用 ExperimentMeta/DatasetMeta 中的数据，其次是 Run 中的数据
            total_tokens: run.datasetMeta?.totalTokens ?? run.totalTokens,
        },
        training: trainingConfig,
        lora: loraConfig,
        // 保留其他顶级配置项
        ...flatConfig,
    };

    // 构建实验元数据
    const experimentMeta = run.experimentMeta ? {
        osVersion: run.experimentMeta.osVersion,
        pythonVersion: run.experimentMeta.pythonVersion,
        pytorchVersion: run.experimentMeta.pytorchVersion,
        transformersVersion: run.experimentMeta.transformersVersion,
        trlVersion: run.experimentMeta.trlVersion,
        peftVersion: run.experimentMeta.peftVersion,
        cudaVersion: run.experimentMeta.cudaVersion,
        cudnnVersion: run.experimentMeta.cudnnVersion,
        bitsandbytesVersion: run.experimentMeta.bitsandbytesVersion,
        gpuModel: run.experimentMeta.gpuModel,
        gpuMemoryGB: run.experimentMeta.gpuMemoryGB,
        cpuModel: run.experimentMeta.cpuModel,
        ramGB: run.experimentMeta.ramGB,
    } : {};

    // LoRA 统计 (来自训练时收集的数据)
    const loraStats = run.loraStats ? {
        trainable_params: run.loraStats.trainableParams,
        total_params: run.loraStats.totalParams,
        trainable_percent: run.loraStats.trainablePercent,
        rank: run.loraStats.rank,
        alpha: run.loraStats.alpha,
        dropout: run.loraStats.dropout,
        target_modules: run.loraStats.targetModules ? JSON.parse(run.loraStats.targetModules) : undefined,
    } : {};

    // 创建临时目录存放数据文件
    const tempDir = path.join(REPORTS_DIR, `temp-${runId}-${Date.now()}`);
    fs.mkdirSync(tempDir, { recursive: true });

    // 写入数据文件
    const configPath = path.join(tempDir, 'config.json');
    const metricsPath = path.join(tempDir, 'metrics.json');
    const evalPath = path.join(tempDir, 'eval_result.json');
    const metaPath = path.join(tempDir, 'experiment_meta.json');
    const loraPath = path.join(tempDir, 'lora_stats.json');
    const runInfoPath = path.join(tempDir, 'run_info.json');

    fs.writeFileSync(configPath, JSON.stringify(reportConfig, null, 2));
    fs.writeFileSync(metricsPath, JSON.stringify(metrics, null, 2));
    fs.writeFileSync(evalPath, JSON.stringify(evalResult, null, 2));
    fs.writeFileSync(metaPath, JSON.stringify(experimentMeta, null, 2));
    fs.writeFileSync(loraPath, JSON.stringify(loraStats, null, 2));
    fs.writeFileSync(runInfoPath, JSON.stringify({
        id: run.id,
        name: run.name,
        start_time: run.startedAt?.toISOString(),
        end_time: run.completedAt?.toISOString(),
        duration: run.duration,
        git_commit: run.gitCommit,
    }, null, 2));

    // P2: Write data quality statistics (from DatasetMeta.statisticsJson)
    if (run.datasetMeta?.statisticsJson) {
        const qualityStatsPath = path.join(tempDir, 'data_quality_stats.json');
        try {
            const statsData = JSON.parse(run.datasetMeta.statisticsJson);
            fs.writeFileSync(qualityStatsPath, JSON.stringify(statsData, null, 2));
        } catch (e) {
            console.warn('Failed to parse statisticsJson:', e);
        }
    }

    // 输出路径
    const ext = format === 'markdown' ? 'md' : 'html';
    const outputFilename = `report-${runId}-${Date.now()}.${ext}`;
    const outputPath = path.join(REPORTS_DIR, outputFilename);

    // 调用 Python 报告生成器
    return new Promise((resolve, reject) => {
        const pythonScript = path.join(SCRIPTS_DIR, 'report_generator.py');

        const args = [
            pythonScript,
            '--run-dir', tempDir,
            '--output', outputPath,
            '--format', format === 'markdown' ? 'md' : 'html',
        ];

        if (title) {
            args.push('--title', title);
        }

        const pythonCmd = getPython();
        console.log(`[Report] Generating report with Python: ${pythonCmd} ${args.join(' ')}`);

        const proc = spawn(pythonCmd, args, {
            cwd: SCRIPTS_DIR,
            env: { ...process.env },
        });

        let stdout = '';
        let stderr = '';

        proc.stdout.on('data', (data) => {
            stdout += data.toString();
            console.log(`[Report] ${data.toString().trim()}`);
        });

        proc.stderr.on('data', (data) => {
            stderr += data.toString();
            console.error(`[Report Error] ${data.toString().trim()}`);
        });

        proc.on('close', (code) => {
            // 清理临时目录
            try {
                fs.rmSync(tempDir, { recursive: true, force: true });
            } catch { }

            if (code === 0 && fs.existsSync(outputPath)) {
                const content = fs.readFileSync(outputPath, 'utf-8');
                resolve({ content, outputPath });
            } else {
                reject(new Error(`Python report generator failed (code ${code}): ${stderr || stdout}`));
            }
        });

        proc.on('error', (err) => {
            // 清理临时目录
            try {
                fs.rmSync(tempDir, { recursive: true, force: true });
            } catch { }
            reject(new Error(`Failed to spawn Python: ${err.message}`));
        });
    });
}

/**
 * 使用 Python 评测报告生成器生成评测报告 (HTML 或 Markdown)
 * P0-FIX: 新增评测报告生成支持
 */
async function generateEvalReport(
    runId: string,
    title?: string,
    format: 'html' | 'markdown' = 'html'
): Promise<{ content: string; outputPath: string }> {
    // 获取 Run 数据
    const run = await prisma.run.findUnique({
        where: { id: runId },
    });

    if (!run) {
        throw new Error(`Run not found: ${runId}`);
    }

    // 必须是评测类型的运行
    if (run.type !== 'evaluation') {
        throw new Error(`Run ${runId} is not an evaluation run`);
    }

    // 解析 evalResultJson
    let evalData: any = {};
    try {
        evalData = JSON.parse(run.evalResultJson || '{}');
    } catch {
        throw new Error('Invalid evalResultJson format');
    }

    // P0/P1-FIX: 尝试从 eval_summary.json 直接读取新字段（回退机制）
    // 这样即使数据库中的旧数据没有新字段，也能从原始文件获取
    if (!evalData.perProblemStats || !evalData.failureExamplesByType) {
        const runStoragePath = path.join(STORAGE_DIR, 'runs', runId, 'eval_summary.json');
        if (fs.existsSync(runStoragePath)) {
            try {
                const evalSummaryRaw = fs.readFileSync(runStoragePath, 'utf-8');
                const evalSummary = JSON.parse(evalSummaryRaw);
                // 从原始文件补充新字段
                if (!evalData.perProblemStats && evalSummary.per_problem_stats) {
                    evalData.perProblemStats = evalSummary.per_problem_stats;
                }
                if (!evalData.failureExamplesByType && evalSummary.failure_examples_by_type) {
                    evalData.failureExamplesByType = evalSummary.failure_examples_by_type;
                }
                console.log(`[Reports] Loaded per_problem_stats and failure_examples_by_type from eval_summary.json for ${runId}`);
            } catch (e) {
                console.warn(`[Reports] Could not load new fields from eval_summary.json: ${e}`);
            }
        }
    }

    // 创建临时目录存放 eval_summary.json
    const tempDir = path.join(REPORTS_DIR, `temp-eval-${runId}-${Date.now()}`);
    fs.mkdirSync(tempDir, { recursive: true });

    // 将 evalResultJson 转换为 eval_summary.json 格式
    // P0-FIX: 字段映射适配 - run-executor.ts 存储的格式 -> eval_report_generator.py 期望的格式
    const evalSummary = {
        eval_run_id: evalData.evalRunId || runId,
        eval_time: evalData.evalTime || run.completedAt?.toISOString(),
        seed: evalData.seed || run.seed,
        git_commit: evalData.gitCommit || run.gitCommit,
        base_model_name: evalData.baseModelName || 'Unknown',
        checkpoint_path: evalData.checkpointPath,

        // Dataset info
        dataset_info: evalData.datasetInfo || {},

        // Generation settings (字段名映射)
        generation_settings: evalData.generationConfig || evalData.generation_settings || {},

        // Judge settings (字段名映射)
        judge_settings: evalData.judgeConfig || evalData.judge_settings || {},

        // Metrics
        metrics_overall: {
            pass_at_1: evalData.passAt1 || 0,
            pass_at_5: evalData.passAt5 || 0,
            pass_at_10: evalData.passAt10 || 0,
            compile_rate: evalData.compileRate || 0,
        },

        // Error distribution (字段名映射)
        error_distribution: {
            syntax_error_rate: evalData.errorStats?.syntaxErrorRate || 0,
            runtime_error_rate: evalData.errorStats?.runtimeErrorRate || 0,
            timeout_rate: evalData.errorStats?.timeoutRate || 0,
            assertion_error_rate: evalData.errorStats?.assertionErrorRate || 0,
            import_error_rate: evalData.errorStats?.importErrorRate || 0,
            memory_error_rate: evalData.errorStats?.memoryErrorRate || 0,
        },

        // Time stats
        time_stats: {
            mean_runtime_ms: evalData.timeStats?.meanRuntimeMs || 0,
            p50_runtime_ms: evalData.timeStats?.p50RuntimeMs || 0,
            p95_runtime_ms: evalData.timeStats?.p95RuntimeMs || 0,
            max_runtime_ms: evalData.timeStats?.maxRuntimeMs || 0,
        },

        // Code quality (使用实际数据 - 需要 camelCase 转 snake_case)
        code_quality: {
            interface_compliance_rate: evalData.codeQuality?.interfaceComplianceRate ?? 0,
            extra_io_rate: evalData.codeQuality?.extraIORate ?? 0,
            avg_code_length: evalData.codeQuality?.avgCodeLength ?? 0,
            avg_line_count: evalData.codeQuality?.avgLineCount ?? 0,
        },

        // Segment breakdown (字段名映射 - 同时支持旧字段名和新的 segmentBreakdown)
        segment_breakdown: evalData.segmentBreakdown || {
            by_difficulty: evalData.difficultyBreakdown || {},
            by_category: evalData.categoryBreakdown || {},
        },

        // P1: Per-problem pass distribution
        per_problem_stats: evalData.perProblemStats || null,

        // P0: Failure examples by error type
        failure_examples_by_type: evalData.failureExamplesByType || null,

        // Sample results for failure cases
        sample_results: evalData.failureSamples || [],

        // Environment
        environment_info: evalData.environment || {},
    };

    // 写入临时文件
    const evalSummaryPath = path.join(tempDir, 'eval_summary.json');
    fs.writeFileSync(evalSummaryPath, JSON.stringify(evalSummary, null, 2));

    // 输出路径
    const ext = format === 'markdown' ? 'md' : 'html';
    const outputFilename = `eval-report-${runId}-${Date.now()}.${ext}`;
    const outputPath = path.join(REPORTS_DIR, outputFilename);

    // 调用 Python 评测报告生成器
    return new Promise((resolve, reject) => {
        const pythonScript = path.join(SCRIPTS_DIR, 'eval_report_generator.py');

        const args = [
            pythonScript,
            evalSummaryPath,
            REPORTS_DIR,
        ];

        const pythonCmd = getPython();
        console.log(`[Report] Generating eval report with Python: ${pythonCmd} ${args.join(' ')}`);

        const proc = spawn(pythonCmd, args, {
            cwd: SCRIPTS_DIR,
            env: { ...process.env },
        });

        let stdout = '';
        let stderr = '';

        proc.stdout.on('data', (data) => {
            stdout += data.toString();
            console.log(`[EvalReport] ${data.toString().trim()}`);
        });

        proc.stderr.on('data', (data) => {
            stderr += data.toString();
            console.error(`[EvalReport Error] ${data.toString().trim()}`);
        });

        proc.on('close', (code) => {
            // 清理临时目录
            try {
                fs.rmSync(tempDir, { recursive: true, force: true });
            } catch { }

            // 报告生成器会输出多个格式，我们需要找到正确的文件
            const expectedPrefix = 'eval_report';
            const expectedFile = path.join(REPORTS_DIR, `${expectedPrefix}.${ext}`);

            if (code === 0 && fs.existsSync(expectedFile)) {
                const content = fs.readFileSync(expectedFile, 'utf-8');
                // 重命名为带 runId 的文件名
                fs.renameSync(expectedFile, outputPath);
                resolve({ content, outputPath });
            } else {
                reject(new Error(`Eval report generator failed (code ${code}): ${stderr || stdout}`));
            }
        });

        proc.on('error', (err) => {
            // 清理临时目录
            try {
                fs.rmSync(tempDir, { recursive: true, force: true });
            } catch { }
            reject(new Error(`Failed to spawn Python: ${err.message}`));
        });
    });
}

export async function reportsRoutes(fastify: FastifyInstance) {

    // ========================================================================
    // Python 报告生成 API（主要使用）
    // ========================================================================

    // POST /api/reports/generate - 使用 Python 生成报告
    fastify.post('/generate', {
        schema: {
            tags: ['Reports'],
            summary: '生成新报告（使用 Python 报告生成器）',
            body: {
                type: 'object',
                properties: {
                    runId: { type: 'string' },
                    title: { type: 'string' },
                    format: { type: 'string', enum: ['HTML', 'PDF', 'MARKDOWN', 'MD'] },
                },
            },
        },
    }, async (request, reply) => {
        const body = request.body as GenerateReportRequest & { title?: string };

        if (!body.runId) {
            return reply.status(400).send({ error: 'runId is required' });
        }

        try {
            // 获取 Run 信息
            const run = await prisma.run.findUnique({ where: { id: body.runId } });
            if (!run) {
                return reply.status(404).send({ error: 'Run not found' });
            }

            const title = body.title || `${run.name} ${run.type === 'evaluation' ? 'Evaluation' : 'Training'} Report`;

            // 确定格式
            const formatInput = (body.format || 'HTML').toUpperCase();
            const isMarkdown = formatInput === 'MARKDOWN' || formatInput === 'MD';
            const reportFormat: 'html' | 'markdown' = isMarkdown ? 'markdown' : 'html';

            // P0-FIX: 根据 Run 类型选择报告生成器
            console.log(`[Report] Generating ${reportFormat} ${run.type} report for run ${body.runId}...`);

            let content: string;
            let outputPath: string;

            if (run.type === 'evaluation') {
                // 使用评测报告生成器
                const result = await generateEvalReport(body.runId, title, reportFormat);
                content = result.content;
                outputPath = result.outputPath;
            } else {
                // 使用训练报告生成器
                const result = await generatePythonReport(body.runId, title, reportFormat);
                content = result.content;
                outputPath = result.outputPath;
            }

            // 保存报告记录到数据库
            const report = await prisma.report.create({
                data: {
                    title,
                    type: 'Academic',
                    format: isMarkdown ? 'Markdown' : 'HTML',
                    size: `${(content.length / 1024).toFixed(1)} KB`,
                    path: outputPath,
                    runId: body.runId,
                },
            });

            console.log(`[Report] Report generated successfully: ${report.id}`);

            return {
                id: report.id,
                title: report.title,
                status: 'generated',
                format: report.format,
                size: `${(content.length / 1024).toFixed(1)} KB`,
            };
        } catch (error: any) {
            console.error(`[Report] Failed to generate report:`, error);
            return reply.status(500).send({ error: error.message });
        }
    });

    // GET /api/reports - 获取所有报告
    fastify.get('/', {
        schema: {
            tags: ['Reports'],
            summary: '获取所有报告',
        },
    }, async (request, reply) => {
        const reports = await prisma.report.findMany({
            orderBy: { createdAt: 'desc' },
        });

        const response: ReportResponse[] = reports.map(r => ({
            id: r.id,
            title: r.title,
            type: r.type as any,
            date: r.createdAt.toISOString(),
            format: r.format as any,
            size: r.size,
        }));

        return response;
    });

    // GET /api/reports/:id - 获取单个报告详情
    fastify.get<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Reports'],
            summary: '获取报告详情',
        },
    }, async (request, reply) => {
        const report = await prisma.report.findUnique({
            where: { id: request.params.id },
        });

        if (!report) {
            return reply.status(404).send({ error: 'Report not found' });
        }

        return {
            id: report.id,
            title: report.title,
            type: report.type,
            format: report.format,
            size: report.size,
            path: report.path,
            date: report.createdAt.toISOString(),
        };
    });

    // GET /api/reports/:id/download - 下载报告
    fastify.get<{ Params: { id: string } }>('/:id/download', {
        schema: {
            tags: ['Reports'],
            summary: '下载报告',
        },
    }, async (request, reply) => {
        const report = await prisma.report.findUnique({
            where: { id: request.params.id },
        });

        if (!report) {
            return reply.status(404).send({ error: 'Report not found' });
        }

        // 根据报告格式设置正确的 content-type 和文件扩展名
        const isMarkdown = report.format === 'Markdown' || report.format === 'MD';
        const contentType = isMarkdown ? 'text/markdown; charset=utf-8' : 'text/html; charset=utf-8';
        const fileExt = isMarkdown ? 'md' : 'html';
        const filename = `${report.title.replace(/\s+/g, '_')}.${fileExt}`;

        // 如果报告文件存在，直接返回
        if (report.path && fs.existsSync(report.path)) {
            const content = fs.readFileSync(report.path, 'utf-8');
            reply.header('Content-Type', contentType);
            reply.header('Content-Disposition', `attachment; filename="${filename}"`);
            return reply.send(content);
        }

        // 如果文件不存在但有 runId，重新生成
        if (report.runId) {
            try {
                const reportFormat: 'html' | 'markdown' = isMarkdown ? 'markdown' : 'html';
                const { content } = await generatePythonReport(report.runId, report.title, reportFormat);
                reply.header('Content-Type', contentType);
                reply.header('Content-Disposition', `attachment; filename="${filename}"`);
                return reply.send(content);
            } catch (error: any) {
                console.error('Failed to regenerate report:', error);
            }
        }

        // 返回错误
        return reply.status(404).send({ error: 'Report file not found and cannot be regenerated' });
    });

    // GET /api/reports/:id/preview - 预览报告内容（返回 HTML）
    fastify.get<{ Params: { id: string } }>('/:id/preview', {
        schema: {
            tags: ['Reports'],
            summary: '预览报告内容',
        },
    }, async (request, reply) => {
        const report = await prisma.report.findUnique({
            where: { id: request.params.id },
        });

        if (!report) {
            return reply.status(404).send({ error: 'Report not found' });
        }

        // 检查是否有关联的 Run
        if (!report.runId) {
            return {
                id: report.id,
                title: report.title,
                type: report.type,
                format: report.format,
                date: report.createdAt.toISOString(),
                hasTrainingData: false,
                message: '此报告没有关联训练运行。可从 Run 详情页生成报告以包含真实数据。',
            };
        }

        // 获取 Run 数据
        const run = await prisma.run.findUnique({
            where: { id: report.runId },
            include: {
                model: true,
                dataset: true,
                experimentMeta: true,
                loraStats: true,
                metrics: {
                    orderBy: { step: 'asc' },
                    take: 500, // 增加限制以支持更全面的数据预览
                },
            }
        });

        if (!run) {
            return {
                id: report.id,
                title: report.title,
                type: report.type,
                format: report.format,
                date: report.createdAt.toISOString(),
                hasTrainingData: false,
                message: '关联的训练运行已被删除。',
            };
        }

        // 解析配置和结果
        let config: any = {};
        let evalResult: any = {};
        let metricsJson: any = {};
        try { config = JSON.parse(run.configJson || '{}'); } catch { }
        try { evalResult = JSON.parse(run.evalResultJson || '{}'); } catch { }
        try { metricsJson = JSON.parse(run.metricsJson || '{}'); } catch { }

        // 支持扁平格式和嵌套格式两种配置 (与 generatePythonReport 保持一致)
        const flatConfig = config as any;
        const trainingConfig = flatConfig.training || {
            lr: flatConfig.lr,
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
            targetModules: flatConfig.loraTargetModules,
            quantization: flatConfig.quantization,
        };

        // 返回预览数据
        return {
            id: report.id,
            title: report.title,
            // P0-FIX: 返回 run type，便于前端区分训练/评测报告
            type: run.type === 'evaluation' ? 'Evaluation' : report.type,
            format: report.format,
            date: report.createdAt.toISOString(),
            hasTrainingData: true,

            runInfo: {
                runId: run.id,
                runName: run.name,
                duration: run.duration,
                seed: run.seed,
                gitCommit: run.gitCommit,
            },

            model: {
                name: run.model.name,
                path: run.model.path,
                params: run.model.params,
                quantization: loraConfig.quantization || run.model.quantization || 'None',
            },

            dataset: {
                name: run.dataset.name,
                source: null,
                trainSamples: run.dataset.samples,
                valSamples: null,
                testSamples: null,
                totalTokens: run.totalTokens,
            },

            // 训练配置（仅训练报告，评测报告返回 null）
            training: run.type !== 'evaluation' ? {
                batchSize: trainingConfig.batchSize || 1,
                gradientAccumulationSteps: trainingConfig.gradientAccumulation || trainingConfig.gradAccum || 8,
                effectiveBatchSize: (trainingConfig.batchSize || 1) * (trainingConfig.gradientAccumulation || trainingConfig.gradAccum || 8),
                learningRate: trainingConfig.lr || '2e-4',
                scheduler: trainingConfig.scheduler || 'cosine',
                warmupRatio: trainingConfig.warmupRatio ?? 0.03,
                epochs: trainingConfig.epochs || 3,
                maxSeqLength: trainingConfig.maxSeqLen || 512,
                optimizer: trainingConfig.optimizer || 'adamw_torch',
                weightDecay: trainingConfig.weightDecay ?? 0.01,
                precision: trainingConfig.precision || 'fp16',
            } : null,

            // LoRA 配置（仅训练报告）
            lora: run.type !== 'evaluation' ? {
                enabled: loraConfig.enabled !== false,
                rank: run.loraStats?.rank || loraConfig.rank || null,
                alpha: run.loraStats?.alpha || loraConfig.alpha || null,
                dropout: run.loraStats?.dropout ?? loraConfig.dropout ?? null,
                targetModules: run.loraStats?.targetModules ? JSON.parse(run.loraStats.targetModules) : loraConfig.targetModules || [],
                trainableParams: run.loraStats?.trainableParams ? String(run.loraStats.trainableParams) : null,
                trainablePercent: run.loraStats?.trainablePercent ? `${run.loraStats.trainablePercent.toFixed(4)}%` : null,
            } : null,

            // 训练统计（仅训练报告）
            trainingStats: run.type !== 'evaluation' ? {
                // P0-FIX: 使用有 lr 的最后一步，排除可能的 epoch 平均 loss 步
                totalSteps: run.totalSteps || (() => {
                    if (run.metrics.length === 0) return null;
                    // 从后往前找有 lr 的 step
                    for (let i = run.metrics.length - 1; i >= 0; i--) {
                        const m = run.metrics[i];
                        try {
                            const extra = JSON.parse(m.extraJson || '{}');
                            if (extra.lr != null) return m.step;
                        } catch { }
                    }
                    // 如果都没有 lr，返回倒数第二个（避免 epoch 平均值）
                    return run.metrics.length >= 2
                        ? run.metrics[run.metrics.length - 2].step
                        : run.metrics[run.metrics.length - 1].step;
                })(),
                totalTokens: run.totalTokens,
                tokensPerSecond: run.tokensPerSecond,
                gpuHours: run.gpuHours,
            } : null,

            evaluation: {
                passAt1: metricsJson.passAt1 ?? evalResult.passAt1 ?? null,
                // P0-FIX: 使用正确的字段名 passAt5/passAt10
                passAt5: evalResult.passAt5 ?? evalResult.passAtK?.['5'] ?? null,
                passAt10: evalResult.passAt10 ?? evalResult.passAtK?.['10'] ?? null,
                compileRate: metricsJson.compileRate ?? evalResult.compileRate ?? null,
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

            environment: run.experimentMeta ? {
                os: run.experimentMeta.osVersion,
                python: run.experimentMeta.pythonVersion,
                pytorch: run.experimentMeta.pytorchVersion,
                transformers: run.experimentMeta.transformersVersion,
                trl: run.experimentMeta.trlVersion,
                peft: run.experimentMeta.peftVersion,
                cuda: run.experimentMeta.cudaVersion,
                cudnn: run.experimentMeta.cudnnVersion,
                bitsandbytes: run.experimentMeta.bitsandbytesVersion,
            } : null,

            hardware: run.experimentMeta ? {
                gpu: run.experimentMeta.gpuModel,
                gpuMemory: run.experimentMeta.gpuMemoryGB ? `${run.experimentMeta.gpuMemoryGB.toFixed(1)} GB` : null,
                cpu: run.experimentMeta.cpuModel,
                ram: run.experimentMeta.ramGB ? `${run.experimentMeta.ramGB.toFixed(1)} GB` : null,
            } : null,

            // 训练曲线数据
            lossCurve: run.metrics.map((m) => ({
                step: m.step,
                loss: m.loss || 0,
            })),
        };
    });

    // PUT /api/reports/:id - 更新报告
    fastify.put<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Reports'],
            summary: '更新报告',
            body: {
                type: 'object',
                properties: {
                    title: { type: 'string' },
                },
            },
        },
    }, async (request, reply) => {
        const { title } = request.body as { title?: string };

        const report = await prisma.report.findUnique({
            where: { id: request.params.id },
        });

        if (!report) {
            return reply.status(404).send({ error: 'Report not found' });
        }

        const updated = await prisma.report.update({
            where: { id: request.params.id },
            data: {
                title: title || report.title,
            },
        });

        return {
            id: updated.id,
            title: updated.title,
            success: true,
        };
    });

    // DELETE /api/reports/:id - 删除报告
    fastify.delete<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Reports'],
            summary: '删除报告',
        },
    }, async (request, reply) => {
        const report = await prisma.report.findUnique({
            where: { id: request.params.id },
        });

        if (!report) {
            return reply.status(404).send({ error: 'Report not found' });
        }

        // 删除报告文件
        if (report.path && fs.existsSync(report.path)) {
            try {
                fs.unlinkSync(report.path);
            } catch { }
        }

        await prisma.report.delete({
            where: { id: request.params.id },
        });

        return { success: true };
    });
}
