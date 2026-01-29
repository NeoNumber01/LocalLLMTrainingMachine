import { FastifyInstance } from 'fastify';
import { ReportResponse, GenerateReportRequest } from '../types/index.js';
import { spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { prisma } from '../db/prisma-client.js';
import { getPython } from '../utils/python-utils.js';

// Get scripts directory path
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SCRIPTS_DIR = path.resolve(__dirname, '../../scripts');
const REPORTS_DIR = path.resolve(__dirname, '../../storage/reports');
const STORAGE_DIR = path.resolve(__dirname, '../../storage');

// Ensure reports directory exists
if (!fs.existsSync(REPORTS_DIR)) {
    fs.mkdirSync(REPORTS_DIR, { recursive: true });
}

/**
 * Generate report using Python report generator (HTML or Markdown)
 */
async function generatePythonReport(
    runId: string,
    title?: string,
    format: 'html' | 'markdown' = 'html'
): Promise<{ content: string; outputPath: string }> {
    // Get Run data for generating temporary config file
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

    // Parse configuration and results
    let config = {};
    let evalResult = {};
    let metricsJson = {};
    try { config = JSON.parse(run.configJson || '{}'); } catch { }
    try { evalResult = JSON.parse(run.evalResultJson || '{}'); } catch { }
    try { metricsJson = JSON.parse(run.metricsJson || '{}'); } catch { }

    // Build complete configuration object for Python script
    // Support both flattened and nested configuration formats
    const flatConfig = config as any;

    // Training metrics - first calculate rawLoggedSteps and effectiveSteps (for later trainingConfig use)
    // Save original metrics count (including warmup/pre-log)
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

    // P0-FIX: Filter out steps without lr or lr=0 (warmup/pre-update)
    // lr=0 indicates logging during gradient accumulation, no actual parameter update
    const metrics = rawMetrics.filter(m => m.lr != null && m.lr > 0);
    const effectiveSteps = metrics.length;

    // Extract training config from configJson (support both flat and nested formats)
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

    // Ensure total_steps is correctly passed (prioritize run record value, then config value)
    trainingConfig.total_steps = run.totalSteps || trainingConfig.total_steps;
    // Pass raw logged steps and effective steps (for report to display three types of steps)
    trainingConfig.raw_logged_steps = rawLoggedSteps;
    trainingConfig.effective_steps = effectiveSteps;

    // Extract LoRA config from configJson and loraStats
    const loraConfigFromJson = flatConfig.lora || {
        enabled: flatConfig.useLora !== false,
        rank: flatConfig.loraRank,
        alpha: flatConfig.loraAlpha,
        targetModules: flatConfig.loraTargetModules,
        quantization: flatConfig.quantization,
    };

    // Merge data from run.loraStats
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
            // P0-1: samples should be train_samples value (if dataset.samples is 0)
            samples: run.dataset.samples || run.datasetMeta?.trainSamples || 0,
            // Use nullish coalescing to ensure 0 values are valid
            train_samples: run.datasetMeta?.trainSamples ?? run.dataset.samples ?? 0,
            val_samples: run.datasetMeta?.valSamples,
            // Prioritize data from ExperimentMeta/DatasetMeta, then from Run
            total_tokens: run.datasetMeta?.totalTokens ?? run.totalTokens,
        },
        training: trainingConfig,
        lora: loraConfig,
        // Keep other top-level config items
        ...flatConfig,
    };

    // Build experiment metadata
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

    // LoRA statistics (collected during training)
    const loraStats = run.loraStats ? {
        trainable_params: run.loraStats.trainableParams,
        total_params: run.loraStats.totalParams,
        trainable_percent: run.loraStats.trainablePercent,
        rank: run.loraStats.rank,
        alpha: run.loraStats.alpha,
        dropout: run.loraStats.dropout,
        target_modules: run.loraStats.targetModules ? JSON.parse(run.loraStats.targetModules) : undefined,
    } : {};

    // Create temporary directory for data files
    const tempDir = path.join(REPORTS_DIR, `temp-${runId}-${Date.now()}`);
    fs.mkdirSync(tempDir, { recursive: true });

    // Write data files
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

    // Output path
    const ext = format === 'markdown' ? 'md' : 'html';
    const outputFilename = `report-${runId}-${Date.now()}.${ext}`;
    const outputPath = path.join(REPORTS_DIR, outputFilename);

    // Call Python report generator
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
            // Clean up temporary directory
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
            // Clean up temporary directory
            try {
                fs.rmSync(tempDir, { recursive: true, force: true });
            } catch { }
            reject(new Error(`Failed to spawn Python: ${err.message}`));
        });
    });
}

/**
 * Generate evaluation report using Python eval report generator (HTML or Markdown)
 * P0-FIX: Added evaluation report generation support
 */
async function generateEvalReport(
    runId: string,
    title?: string,
    format: 'html' | 'markdown' = 'html'
): Promise<{ content: string; outputPath: string }> {
    // Get Run data
    const run = await prisma.run.findUnique({
        where: { id: runId },
    });

    if (!run) {
        throw new Error(`Run not found: ${runId}`);
    }

    // Must be evaluation type run
    if (run.type !== 'evaluation') {
        throw new Error(`Run ${runId} is not an evaluation run`);
    }

    // Parse evalResultJson
    let evalData: any = {};
    try {
        evalData = JSON.parse(run.evalResultJson || '{}');
    } catch {
        throw new Error('Invalid evalResultJson format');
    }

    // P0/P1-FIX: Try to read new fields from eval_summary.json directly (fallback mechanism)
    // This allows getting new fields from original file even if database data doesn't have them
    if (!evalData.perProblemStats || !evalData.failureExamplesByType) {
        const runStoragePath = path.join(STORAGE_DIR, 'runs', runId, 'eval_summary.json');
        if (fs.existsSync(runStoragePath)) {
            try {
                const evalSummaryRaw = fs.readFileSync(runStoragePath, 'utf-8');
                const evalSummary = JSON.parse(evalSummaryRaw);
                // Supplement new fields from original file
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

    // Create temporary directory for eval_summary.json
    const tempDir = path.join(REPORTS_DIR, `temp-eval-${runId}-${Date.now()}`);
    fs.mkdirSync(tempDir, { recursive: true });

    // Convert evalResultJson to eval_summary.json format
    // P0-FIX: Field mapping adaptation - run-executor.ts stored format -> eval_report_generator.py expected format
    const evalSummary = {
        eval_run_id: evalData.evalRunId || runId,
        eval_time: evalData.evalTime || run.completedAt?.toISOString(),
        seed: evalData.seed || run.seed,
        git_commit: evalData.gitCommit || run.gitCommit,
        base_model_name: evalData.baseModelName || 'Unknown',
        checkpoint_path: evalData.checkpointPath,

        // Dataset info
        dataset_info: evalData.datasetInfo || {},

        // Generation settings (field name mapping)
        generation_settings: evalData.generationConfig || evalData.generation_settings || {},

        // Judge settings (field name mapping)
        judge_settings: evalData.judgeConfig || evalData.judge_settings || {},

        // Metrics
        metrics_overall: {
            pass_at_1: evalData.passAt1 || 0,
            pass_at_5: evalData.passAt5 || 0,
            pass_at_10: evalData.passAt10 || 0,
            compile_rate: evalData.compileRate || 0,
        },

        // Error distribution (field name mapping)
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

        // Code quality (using actual data - need camelCase to snake_case)
        code_quality: {
            interface_compliance_rate: evalData.codeQuality?.interfaceComplianceRate ?? 0,
            extra_io_rate: evalData.codeQuality?.extraIORate ?? 0,
            avg_code_length: evalData.codeQuality?.avgCodeLength ?? 0,
            avg_line_count: evalData.codeQuality?.avgLineCount ?? 0,
        },

        // Segment breakdown (field name mapping - supporting both old field names and new segmentBreakdown)
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

    // Write temporary file
    const evalSummaryPath = path.join(tempDir, 'eval_summary.json');
    fs.writeFileSync(evalSummaryPath, JSON.stringify(evalSummary, null, 2));

    // Output path
    const ext = format === 'markdown' ? 'md' : 'html';
    const outputFilename = `eval-report-${runId}-${Date.now()}.${ext}`;
    const outputPath = path.join(REPORTS_DIR, outputFilename);

    // Call Python eval report generator
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
            // Clean up temporary directory
            try {
                fs.rmSync(tempDir, { recursive: true, force: true });
            } catch { }

            // Report generator outputs multiple formats, we need to find the correct file
            const expectedPrefix = 'eval_report';
            const expectedFile = path.join(REPORTS_DIR, `${expectedPrefix}.${ext}`);

            if (code === 0 && fs.existsSync(expectedFile)) {
                const content = fs.readFileSync(expectedFile, 'utf-8');
                // Rename to filename with runId
                fs.renameSync(expectedFile, outputPath);
                resolve({ content, outputPath });
            } else {
                reject(new Error(`Eval report generator failed (code ${code}): ${stderr || stdout}`));
            }
        });

        proc.on('error', (err) => {
            // Clean up temporary directory
            try {
                fs.rmSync(tempDir, { recursive: true, force: true });
            } catch { }
            reject(new Error(`Failed to spawn Python: ${err.message}`));
        });
    });
}

export async function reportsRoutes(fastify: FastifyInstance) {

    // ========================================================================
    // Python Report Generation API (Primary)
    // ========================================================================

    // POST /api/reports/generate - Generate report using Python
    fastify.post('/generate', {
        schema: {
            tags: ['Reports'],
            summary: 'Generate new report (using Python report generator)',
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
            // Get Run information
            const run = await prisma.run.findUnique({ where: { id: body.runId } });
            if (!run) {
                return reply.status(404).send({ error: 'Run not found' });
            }

            const title = body.title || `${run.name} ${run.type === 'evaluation' ? 'Evaluation' : 'Training'} Report`;

            // Determine format
            const formatInput = (body.format || 'HTML').toUpperCase();
            const isMarkdown = formatInput === 'MARKDOWN' || formatInput === 'MD';
            const reportFormat: 'html' | 'markdown' = isMarkdown ? 'markdown' : 'html';

            // P0-FIX: Choose report generator based on Run type
            console.log(`[Report] Generating ${reportFormat} ${run.type} report for run ${body.runId}...`);

            let content: string;
            let outputPath: string;

            if (run.type === 'evaluation') {
                // Use evaluation report generator
                const result = await generateEvalReport(body.runId, title, reportFormat);
                content = result.content;
                outputPath = result.outputPath;
            } else {
                // Use training report generator
                const result = await generatePythonReport(body.runId, title, reportFormat);
                content = result.content;
                outputPath = result.outputPath;
            }

            // Save report record to database
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

    // GET /api/reports - Get all reports
    fastify.get('/', {
        schema: {
            tags: ['Reports'],
            summary: 'Get all reports',
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

    // GET /api/reports/:id - Get single report details
    fastify.get<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Reports'],
            summary: 'Get report details',
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

    // GET /api/reports/:id/download - Download report
    fastify.get<{ Params: { id: string } }>('/:id/download', {
        schema: {
            tags: ['Reports'],
            summary: 'Download report',
        },
    }, async (request, reply) => {
        const report = await prisma.report.findUnique({
            where: { id: request.params.id },
        });

        if (!report) {
            return reply.status(404).send({ error: 'Report not found' });
        }

        // Set correct content-type and file extension based on report format
        const isMarkdown = report.format === 'Markdown' || report.format === 'MD';
        const contentType = isMarkdown ? 'text/markdown; charset=utf-8' : 'text/html; charset=utf-8';
        const fileExt = isMarkdown ? 'md' : 'html';
        const filename = `${report.title.replace(/\s+/g, '_')}.${fileExt}`;

        // If report file exists, return directly
        if (report.path && fs.existsSync(report.path)) {
            const content = fs.readFileSync(report.path, 'utf-8');
            reply.header('Content-Type', contentType);
            reply.header('Content-Disposition', `attachment; filename="${filename}"`);
            return reply.send(content);
        }

        // If file doesn't exist but has runId, regenerate
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

        // Return error
        return reply.status(404).send({ error: 'Report file not found and cannot be regenerated' });
    });

    // GET /api/reports/:id/preview - Preview report content (returns HTML)
    fastify.get<{ Params: { id: string } }>('/:id/preview', {
        schema: {
            tags: ['Reports'],
            summary: 'Preview report content',
        },
    }, async (request, reply) => {
        const report = await prisma.report.findUnique({
            where: { id: request.params.id },
        });

        if (!report) {
            return reply.status(404).send({ error: 'Report not found' });
        }

        // Check if there is an associated Run
        if (!report.runId) {
            return {
                id: report.id,
                title: report.title,
                type: report.type,
                format: report.format,
                date: report.createdAt.toISOString(),
                hasTrainingData: false,
                message: 'This report has no associated training run. Generate report from Run details page to include real data.',
            };
        }

        // Get Run data
        const run = await prisma.run.findUnique({
            where: { id: report.runId },
            include: {
                model: true,
                dataset: true,
                experimentMeta: true,
                loraStats: true,
                metrics: {
                    orderBy: { step: 'asc' },
                    take: 500, // Increase limit to support more comprehensive data preview
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
                message: 'Associated training run has been deleted.',
            };
        }

        // Parse configuration and results
        let config: any = {};
        let evalResult: any = {};
        let metricsJson: any = {};
        try { config = JSON.parse(run.configJson || '{}'); } catch { }
        try { evalResult = JSON.parse(run.evalResultJson || '{}'); } catch { }
        try { metricsJson = JSON.parse(run.metricsJson || '{}'); } catch { }

        // Support both flat format and nested format configuration (consistent with generatePythonReport)
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

        // Return preview data
        return {
            id: report.id,
            title: report.title,
            // P0-FIX: Return run type for frontend to distinguish training/evaluation reports
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

            // Training configuration (training reports only, evaluation reports return null)
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

            // LoRA configuration (training reports only)
            lora: run.type !== 'evaluation' ? {
                enabled: loraConfig.enabled !== false,
                rank: run.loraStats?.rank || loraConfig.rank || null,
                alpha: run.loraStats?.alpha || loraConfig.alpha || null,
                dropout: run.loraStats?.dropout ?? loraConfig.dropout ?? null,
                targetModules: run.loraStats?.targetModules ? JSON.parse(run.loraStats.targetModules) : loraConfig.targetModules || [],
                trainableParams: run.loraStats?.trainableParams ? String(run.loraStats.trainableParams) : null,
                trainablePercent: run.loraStats?.trainablePercent ? `${run.loraStats.trainablePercent.toFixed(4)}%` : null,
            } : null,

            // Training statistics (training reports only)
            trainingStats: run.type !== 'evaluation' ? {
                // P0-FIX: Use last step with lr, exclude possible epoch average loss step
                totalSteps: run.totalSteps || (() => {
                    if (run.metrics.length === 0) return null;
                    // Find step with lr from back to front
                    for (let i = run.metrics.length - 1; i >= 0; i--) {
                        const m = run.metrics[i];
                        try {
                            const extra = JSON.parse(m.extraJson || '{}');
                            if (extra.lr != null) return m.step;
                        } catch { }
                    }
                    // If none have lr, return second to last (avoid epoch average value)
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
                // P0-FIX: Use correct field names passAt5/passAt10
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

            // Training curve data
            lossCurve: run.metrics.map((m) => ({
                step: m.step,
                loss: m.loss || 0,
            })),
        };
    });

    // PUT /api/reports/:id - Update report
    fastify.put<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Reports'],
            summary: 'Update report',
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

    // DELETE /api/reports/:id - Delete report
    fastify.delete<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Reports'],
            summary: 'Delete report',
        },
    }, async (request, reply) => {
        const report = await prisma.report.findUnique({
            where: { id: request.params.id },
        });

        if (!report) {
            return reply.status(404).send({ error: 'Report not found' });
        }

        // Delete report file
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
