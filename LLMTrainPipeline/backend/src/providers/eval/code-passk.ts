import { EvalProvider, EvalConfig, EvalResult, ErrorStats, TimeStats, FailureCase, EvalEvent } from '../interfaces.js';
import { Config } from '../../config/index.js';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { getPython } from '../../utils/python-utils.js';

// ES Module dirname fix
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Path to eval.py script
const EVAL_SCRIPT = path.resolve(__dirname, '../../../scripts/eval.py');

export class CodePassKEval implements EvalProvider {
    name = 'code_passk';
    private config: Config;
    private process: ChildProcess | null = null;

    constructor(config: Config) {
        this.config = config;
    }

    stop(): void {
        if (this.process) {
            // Windows: SIGTERM doesn't work, use taskkill to kill process tree
            if (process.platform === 'win32' && this.process.pid) {
                spawn('taskkill', ['/F', '/T', '/PID', this.process.pid.toString()], { shell: true });
            } else {
                this.process.kill('SIGTERM');
            }
            this.process = null;
        }
    }

    async evaluate(evalConfig: EvalConfig): Promise<EvalResult> {
        console.log(`[CodePassKEval] Starting evaluation for run ${evalConfig.runId}`);

        // 检查评估脚本是否存在
        if (!fs.existsSync(EVAL_SCRIPT)) {
            console.warn(`[CodePassKEval] Eval script not found: ${EVAL_SCRIPT}`);
            console.log(`[CodePassKEval] Falling back to placeholder metrics`);
            return this.getPlaceholderResult();
        }

        // 检查评估数据集
        if (!evalConfig.datasetPath || !fs.existsSync(evalConfig.datasetPath)) {
            console.warn(`[CodePassKEval] Eval dataset not found: ${evalConfig.datasetPath}`);
            console.log(`[CodePassKEval] Falling back to placeholder metrics`);
            return this.getPlaceholderResult();
        }

        // 创建评估配置文件
        const evalConfigPath = path.join(`./storage/runs/${evalConfig.runId}`, 'eval_config.json');
        const pythonConfig = this.buildPythonConfig(evalConfig);

        // 确保目录存在
        const outputDir = path.dirname(evalConfigPath);
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }

        fs.writeFileSync(evalConfigPath, JSON.stringify(pythonConfig, null, 2));

        console.log(`[CodePassKEval] Eval config written to ${evalConfigPath}`);
        console.log(`[CodePassKEval] Spawning Python evaluation process...`);

        try {
            const result = await this.runEvalScript(evalConfigPath);
            console.log(`[CodePassKEval] Evaluation complete. Pass@1: ${result.passAt1}%`);
            if (result.errorStats) {
                console.log(`[CodePassKEval] Error rates - Syntax: ${result.errorStats.syntaxErrorRate}%, Runtime: ${result.errorStats.runtimeErrorRate}%, Timeout: ${result.errorStats.timeoutRate}%`);
            }
            if (result.timeStats) {
                console.log(`[CodePassKEval] Time stats - Mean: ${result.timeStats.meanRuntimeMs}ms, P95: ${result.timeStats.p95RuntimeMs}ms`);
            }
            return result;
        } catch (error: any) {
            console.error(`[CodePassKEval] Evaluation failed:`, error);
            console.log(`[CodePassKEval] Falling back to placeholder metrics`);
            return this.getPlaceholderResult();
        }
    }

    /**
     * Streaming evaluation that yields events as they happen in real-time
     */
    async *evaluateStream(evalConfig: EvalConfig): AsyncGenerator<EvalEvent, EvalResult, unknown> {
        const startTime = Date.now();

        yield {
            type: 'log',
            timestamp: new Date(),
            data: { level: 'info', message: `Starting evaluation for run ${evalConfig.runId}` }
        };

        // 检查评估脚本是否存在
        if (!fs.existsSync(EVAL_SCRIPT)) {
            yield {
                type: 'log',
                timestamp: new Date(),
                data: { level: 'warning', message: `Eval script not found: ${EVAL_SCRIPT}` }
            };
            yield {
                type: 'error',
                timestamp: new Date(),
                data: { message: 'Evaluation script not available' }
            };
            return this.getPlaceholderResult();
        }

        // 检查评估数据集
        if (!evalConfig.datasetPath || !fs.existsSync(evalConfig.datasetPath)) {
            yield {
                type: 'log',
                timestamp: new Date(),
                data: { level: 'warning', message: `Eval dataset not found: ${evalConfig.datasetPath}` }
            };
            yield {
                type: 'error',
                timestamp: new Date(),
                data: { message: 'Evaluation dataset not available' }
            };
            return this.getPlaceholderResult();
        }

        // 创建评估配置文件
        const evalConfigPath = path.join(`./storage/runs/${evalConfig.runId}`, 'eval_config.json');
        const pythonConfig = this.buildPythonConfig(evalConfig);

        // 确保目录存在
        const outputDir = path.dirname(evalConfigPath);
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }

        fs.writeFileSync(evalConfigPath, JSON.stringify(pythonConfig, null, 2));

        yield {
            type: 'log',
            timestamp: new Date(),
            data: { level: 'info', message: `Eval config written to ${evalConfigPath}` }
        };

        yield {
            type: 'log',
            timestamp: new Date(),
            data: { level: 'info', message: 'Spawning Python evaluation process...' }
        };

        // Use the real-time streaming generator
        let evalResult: EvalResult | null = null;
        try {
            for await (const event of this.streamEvalProcess(evalConfigPath)) {
                if (event.type === 'result') {
                    evalResult = event.data as EvalResult;
                } else {
                    yield event as EvalEvent;
                }
            }

            if (!evalResult) {
                evalResult = this.getPlaceholderResult();
            }

            const duration = Date.now() - startTime;
            yield {
                type: 'log',
                timestamp: new Date(),
                data: { level: 'info', message: `Evaluation complete in ${(duration / 1000).toFixed(1)}s. Pass@1: ${evalResult.passAt1}%` }
            };

            yield {
                type: 'complete',
                timestamp: new Date(),
                data: { duration, result: evalResult }
            };

            return evalResult;
        } catch (error: any) {
            yield {
                type: 'error',
                timestamp: new Date(),
                data: { message: error.message || String(error) }
            };
            return this.getPlaceholderResult();
        }
    }

    // 注意：评估进程没有超时限制，会一直运行直到完成或出错

    private buildPythonConfig(evalConfig: EvalConfig): any {
        // 使用 evalConfig.config 中的 eval 设置（来自用户 UI 输入），回退到 this.config 默认值
        const evalSettings = evalConfig.config?.eval ?? this.config.eval;

        return {
            runId: evalConfig.runId,
            modelPath: evalConfig.modelPath,
            adapterPath: evalConfig.adapterPath,
            datasetPath: evalConfig.datasetPath,
            outputDir: `./storage/runs/${evalConfig.runId}`,
            eval: {
                k: evalSettings.k ?? this.config.eval.k,
                // 用户设置的每个问题的采样数量，回退到 samples 或默认配置中的 samples
                numSamples: evalSettings.numSamples ?? evalSettings.samples ?? this.config.eval.numSamples ?? this.config.eval.samples ?? 10,
                maxTokens: evalSettings.maxTokens ?? this.config.eval.maxTokens ?? 256,
                temperature: evalSettings.temperature ?? this.config.eval.temperature ?? 0.2,
                timeout: evalSettings.timeout ?? this.config.eval.timeout ?? 10,
                memoryLimit: evalSettings.memoryLimit,
                enableFuzzing: evalSettings.enableFuzzing ?? this.config.eval.enableFuzzing ?? false,
                fuzzingRuns: evalSettings.fuzzingRuns ?? this.config.eval.fuzzingRuns ?? 50,
                enableConsistency: evalSettings.enableConsistency ?? this.config.eval.enableConsistency ?? false,
                consistencyRuns: evalSettings.consistencyRuns ?? this.config.eval.consistencyRuns ?? 5,
                enableCodeQuality: evalSettings.enableCodeQuality ?? this.config.eval.enableCodeQuality ?? true,
                generateReport: evalSettings.generateReport,
                saveFailureCases: evalSettings.saveFailureCases,
                // 每个问题的最大测试用例数（限制超长测试集，加速评估）
                maxTestsPerProblem: evalSettings.maxTestsPerProblem ?? 10,
            },
            lora: {
                quantization: evalConfig.config?.lora?.quantization ?? this.config.lora.quantization,
            },
        };
    }

    private runEvalScript(configPath: string): Promise<EvalResult> {
        return new Promise((resolve, reject) => {
            const pythonCmd = getPython();
            const process = spawn(pythonCmd, [EVAL_SCRIPT, '--config', configPath], {
                stdio: ['pipe', 'pipe', 'pipe'],
            });

            let stdout = '';
            let stderr = '';

            process.stdout?.on('data', (data) => {
                stdout += data.toString();
            });

            process.stderr?.on('data', (data) => {
                stderr += data.toString();
                // Log stderr for debugging
                const lines = data.toString().split('\n');
                for (const line of lines) {
                    if (line.trim()) {
                        console.log(`[Python] ${line}`);
                    }
                }
            });

            process.on('close', (code) => {
                if (code === 0) {
                    try {
                        // Parse the last line as JSON (stdout may have multiple lines)
                        const lines = stdout.trim().split('\n');
                        const resultLine = lines[lines.length - 1];
                        const result = JSON.parse(resultLine);

                        resolve(this.parseEvalResult(result));
                    } catch (e) {
                        console.error('[CodePassKEval] Failed to parse eval output:', e);
                        console.error('[CodePassKEval] stdout:', stdout);
                        reject(new Error('Failed to parse evaluation output'));
                    }
                } else {
                    console.error(`[CodePassKEval] Process exited with code ${code}`);
                    console.error('[CodePassKEval] stderr:', stderr);
                    reject(new Error(`Evaluation process exited with code ${code}`));
                }
            });

            process.on('error', (err) => {
                reject(err);
            });

            // 注意：没有超时限制，评估会一直运行直到完成
        });
    }

    /**
     * Run eval script and collect events for streaming
     */
    private runEvalScriptStreaming(configPath: string): Promise<{ events: EvalEvent[], result: EvalResult }> {
        return new Promise((resolve, reject) => {
            const events: EvalEvent[] = [];
            const pythonCmd = getPython();
            const process = spawn(pythonCmd, [EVAL_SCRIPT, '--config', configPath], {
                stdio: ['pipe', 'pipe', 'pipe'],
            });

            let stdout = '';
            let stderr = '';
            let problemCount = 0;
            let completedCount = 0;

            process.stdout?.on('data', (data) => {
                const text = data.toString();
                stdout += text;

                // Parse structured JSON events from stdout
                const lines = text.split('\n');
                for (const line of lines) {
                    if (line.trim()) {
                        try {
                            const parsed = JSON.parse(line);
                            if (parsed.type === 'progress') {
                                completedCount = parsed.completed || completedCount;
                                problemCount = parsed.total || problemCount;
                                events.push({
                                    type: 'progress',
                                    timestamp: new Date(),
                                    data: { completed: completedCount, total: problemCount, percent: problemCount > 0 ? (completedCount / problemCount * 100) : 0 }
                                });
                            } else if (parsed.type === 'log') {
                                events.push({
                                    type: 'log',
                                    timestamp: new Date(),
                                    data: { level: parsed.level || 'info', message: parsed.message }
                                });
                            }
                        } catch {
                            // Not JSON, ignore
                        }
                    }
                }
            });

            process.stderr?.on('data', (data) => {
                const text = data.toString();
                stderr += text;

                // Parse each line as a log event
                const lines = text.split('\n');
                for (const line of lines) {
                    if (line.trim()) {
                        // Determine log level from content
                        let level = 'info';
                        if (line.toLowerCase().includes('error') || line.toLowerCase().includes('exception')) {
                            level = 'error';
                        } else if (line.toLowerCase().includes('warning') || line.toLowerCase().includes('warn')) {
                            level = 'warning';
                        }

                        events.push({
                            type: 'log',
                            timestamp: new Date(),
                            data: { level, message: line }
                        });
                    }
                }
            });

            process.on('close', (code) => {
                if (code === 0) {
                    try {
                        // Parse the last line as JSON (stdout may have multiple lines)
                        const lines = stdout.trim().split('\n');
                        const resultLine = lines[lines.length - 1];
                        const result = JSON.parse(resultLine);

                        resolve({ events, result: this.parseEvalResult(result) });
                    } catch (e) {
                        console.error('[CodePassKEval] Failed to parse eval output:', e);
                        reject(new Error('Failed to parse evaluation output'));
                    }
                } else {
                    events.push({
                        type: 'error',
                        timestamp: new Date(),
                        data: { message: `Process exited with code ${code}` }
                    });
                    reject(new Error(`Evaluation process exited with code ${code}`));
                }
            });

            process.on('error', (err) => {
                reject(err);
            });

            // 注意：没有超时限制，评估会一直运行直到完成
        });
    }

    /**
     * Real-time streaming generator for eval process
     * This yields events as they arrive from the Python process
     */
    private async *streamEvalProcess(configPath: string): AsyncGenerator<EvalEvent | { type: 'result', data: EvalResult }> {
        const pythonCmd = getPython();
        const evalProcess = spawn(pythonCmd, [EVAL_SCRIPT, '--config', configPath], {
            stdio: ['pipe', 'pipe', 'pipe'],
        });

        // 保存进程引用以便可以停止
        this.process = evalProcess;

        let stdout = '';
        let stdoutBuffer = '';
        let stderrBuffer = '';

        // Create a queue to handle events asynchronously
        const eventQueue: Array<EvalEvent | { type: 'result', data: EvalResult } | { type: 'done' } | { type: 'error_exit', error: Error }> = [];
        let resolveNext: (() => void) | null = null;

        const pushEvent = (event: typeof eventQueue[0]) => {
            eventQueue.push(event);
            if (resolveNext) {
                resolveNext();
                resolveNext = null;
            }
        };

        evalProcess.stdout?.on('data', (data) => {
            const text = data.toString();
            stdout += text;
            stdoutBuffer += text;

            // Process complete lines
            const lines = stdoutBuffer.split('\n');
            stdoutBuffer = lines.pop() || ''; // Keep incomplete line in buffer

            for (const line of lines) {
                if (line.trim()) {
                    try {
                        const parsed = JSON.parse(line);
                        if (parsed.type === 'progress') {
                            const total = parsed.total || 0;
                            const completed = parsed.completed || 0;
                            pushEvent({
                                type: 'progress',
                                timestamp: new Date(),
                                data: { completed, total, percent: total > 0 ? (completed / total * 100) : 0 }
                            });
                        } else if (parsed.type === 'log') {
                            pushEvent({
                                type: 'log',
                                timestamp: new Date(),
                                data: { level: parsed.level || 'info', message: parsed.message }
                            });
                        } else if (parsed.type === 'metric' && parsed.data) {
                            // P1: Forward real-time eval metrics to run-executor
                            pushEvent({
                                type: 'metric',
                                timestamp: new Date(),
                                data: parsed.data
                            });
                        }
                        // Other JSON types (like final result) are not pushed here
                    } catch {
                        // Not JSON, ignore
                    }
                }
            }
        });

        evalProcess.stderr?.on('data', (data) => {
            const text = data.toString();
            stderrBuffer += text;

            // Process complete lines
            const lines = stderrBuffer.split('\n');
            stderrBuffer = lines.pop() || '';

            for (const line of lines) {
                if (line.trim()) {
                    // Determine log level from content (stderr typically contains Python logs)
                    let level = 'info';
                    if (line.toLowerCase().includes('error') || line.toLowerCase().includes('exception') || line.toLowerCase().includes('traceback')) {
                        level = 'error';
                    } else if (line.toLowerCase().includes('warning') || line.toLowerCase().includes('warn')) {
                        level = 'warning';
                    }

                    pushEvent({
                        type: 'log',
                        timestamp: new Date(),
                        data: { level, message: line }
                    });
                }
            }
        });

        evalProcess.on('close', (code) => {
            // Process any remaining buffered content
            if (stderrBuffer.trim()) {
                pushEvent({
                    type: 'log',
                    timestamp: new Date(),
                    data: { level: 'info', message: stderrBuffer.trim() }
                });
            }

            if (code === 0) {
                try {
                    // Parse the last JSON line as result
                    const lines = stdout.trim().split('\n');
                    const resultLine = lines[lines.length - 1];
                    const result = JSON.parse(resultLine);
                    pushEvent({ type: 'result', data: this.parseEvalResult(result) });
                } catch (e) {
                    console.error('[CodePassKEval] Failed to parse eval output:', e);
                    pushEvent({ type: 'error_exit', error: new Error('Failed to parse evaluation output') });
                }
            } else {
                pushEvent({ type: 'error_exit', error: new Error(`Process exited with code ${code}`) });
            }
            pushEvent({ type: 'done' });
        });

        evalProcess.on('error', (err) => {
            pushEvent({ type: 'error_exit', error: err });
            pushEvent({ type: 'done' });
        });

        // 注意：没有超时限制，评估会一直运行直到完成

        // Yield events as they arrive
        while (true) {
            if (eventQueue.length === 0) {
                await new Promise<void>((resolve) => {
                    resolveNext = resolve;
                });
            }

            const event = eventQueue.shift();
            if (!event) continue;

            if (event.type === 'done') {
                break;
            } else if (event.type === 'error_exit') {
                throw (event as any).error;
            } else {
                yield event as EvalEvent | { type: 'result', data: EvalResult };
            }
        }
    }

    private runEvalScriptWithLogs(configPath: string, onLog: (line: string) => void): Promise<EvalResult> {
        // Placeholder - same as runEvalScript but with log callback
        return this.runEvalScript(configPath);
    }

    /**
     * Parse raw Python output to TypeScript EvalResult
     */
    private parseEvalResult(raw: any): EvalResult {
        const failures: FailureCase[] = (raw.failures ?? []).map((f: any) => ({
            taskId: f.taskId ?? 'unknown',
            prompt: f.prompt ?? '',
            output: f.output ?? '',
            errorType: f.errorType ?? 'unknown',
            error: f.error ?? '',
            executionTimeMs: f.executionTimeMs,
        }));

        return {
            passAt1: raw.passAt1 ?? 0,
            compileRate: raw.compileRate ?? 0,
            passAtK: raw.passAtK ?? {},

            errorStats: raw.errorStats ? {
                syntaxErrorRate: raw.errorStats.syntaxErrorRate ?? 0,
                runtimeErrorRate: raw.errorStats.runtimeErrorRate ?? 0,
                timeoutRate: raw.errorStats.timeoutRate ?? 0,
                invalidOutputRate: raw.errorStats.invalidOutputRate ?? 0,
                assertionErrorRate: raw.errorStats.assertionErrorRate ?? 0,
                importErrorRate: raw.errorStats.importErrorRate ?? 0,
                memoryErrorRate: raw.errorStats.memoryErrorRate ?? 0,
            } : undefined,

            timeStats: raw.timeStats ? {
                meanRuntimeMs: raw.timeStats.meanRuntimeMs ?? 0,
                p50RuntimeMs: raw.timeStats.p50RuntimeMs ?? 0,
                p95RuntimeMs: raw.timeStats.p95RuntimeMs ?? 0,
                maxRuntimeMs: raw.timeStats.maxRuntimeMs ?? 0,
                tleRate: raw.timeStats.tleRate ?? 0,
            } : undefined,

            segmentStats: raw.segmentStats,
            codeQuality: raw.codeQuality,
            robustness: raw.robustness,
            consistency: raw.consistency,

            failures,

            totalProblems: raw.totalProblems,
            totalSamples: raw.totalSamples,
            totalPassed: raw.totalPassed,
            totalCompiled: raw.totalCompiled,
        };
    }

    /**
     * Returns placeholder metrics when real evaluation cannot be performed.
     */
    private getPlaceholderResult(): EvalResult {
        console.log('[CodePassKEval] Returning placeholder metrics (no real evaluation performed)');

        return {
            passAt1: 0,
            compileRate: 0,
            passAtK: { '1': 0 },

            errorStats: {
                syntaxErrorRate: 0,
                runtimeErrorRate: 0,
                timeoutRate: 0,
                invalidOutputRate: 0,
                assertionErrorRate: 0,
                importErrorRate: 0,
                memoryErrorRate: 0,
            },

            timeStats: {
                meanRuntimeMs: 0,
                p50RuntimeMs: 0,
                p95RuntimeMs: 0,
                maxRuntimeMs: 0,
                tleRate: 0,
            },

            failures: [{
                taskId: 'system',
                prompt: 'No evaluation performed',
                output: 'N/A',
                errorType: 'System',
                error: 'Evaluation script or dataset not available. Please ensure eval.py exists and an evaluation dataset is configured.',
            }],

            totalProblems: 0,
            totalSamples: 0,
        };
    }
}
