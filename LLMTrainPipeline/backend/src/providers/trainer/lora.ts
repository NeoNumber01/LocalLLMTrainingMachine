import { TrainerProvider, TrainConfig, TrainEvent } from '../interfaces.js';
import { Config } from '../../config/index.js';
import { spawn, ChildProcess } from 'child_process';
import { createInterface } from 'readline';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { getPython } from '../../utils/python-utils.js';

// ES Module dirname fix
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Path to train.py script
const TRAIN_SCRIPT = path.resolve(__dirname, '../../../scripts/train.py');

export class LoraTrainer implements TrainerProvider {
    name = 'lora';
    private config: Config;
    private process: ChildProcess | null = null;

    constructor(config: Config) {
        this.config = config;
    }

    async *train(trainConfig: TrainConfig): AsyncGenerator<TrainEvent> {
        const startTime = Date.now();

        // 初始化日志
        yield {
            type: 'log',
            timestamp: new Date(),
            data: {
                level: 'info',
                message: `[LoraTrainer] Starting real LoRA training for run ${trainConfig.runId}`,
            },
        };

        yield {
            type: 'log',
            timestamp: new Date(),
            data: {
                level: 'info',
                message: `[LoraTrainer] Config: rank=${this.config.lora.rank}, alpha=${this.config.lora.alpha}, quantization=${this.config.lora.quantization}`,
            },
        };

        // 创建训练配置文件
        const trainingConfigPath = path.join(trainConfig.outputDir, 'train_config.json');

        // 使用 trainConfig.config 中的用户设置
        const userTrainingConfig = trainConfig.config.training;
        const userLoraConfig = trainConfig.config.lora;

        const pythonConfig = {
            runId: trainConfig.runId,
            modelPath: trainConfig.modelPath,
            datasetPath: trainConfig.datasetPath,
            evalDatasetPath: trainConfig.evalDatasetPath,
            outputDir: trainConfig.outputDir,
            seed: userTrainingConfig.seed ?? 42,  // 新增: 随机种子
            training: {
                // 基础训练参数
                epochs: userTrainingConfig.epochs,
                batchSize: userTrainingConfig.batchSize,
                lr: userTrainingConfig.lr,
                gradientAccumulation: userTrainingConfig.gradAccum,
                warmupRatio: userTrainingConfig.warmupRatio,
                maxLength: userTrainingConfig.maxSeqLen,
                optimizer: userTrainingConfig.optimizer,
                scheduler: userTrainingConfig.scheduler,
                weightDecay: userTrainingConfig.weightDecay,
                precision: userTrainingConfig.precision,

                // 核心训练参数 (新增)
                loggingSteps: userTrainingConfig.loggingSteps ?? 10,
                saveSteps: userTrainingConfig.saveSteps ?? 100,
                saveTotalLimit: userTrainingConfig.saveTotalLimit ?? 3,
                gradientClipping: userTrainingConfig.gradientClipping ?? 1.0,

                // Warmup 配置 (新增)
                warmupType: userTrainingConfig.warmupType ?? 'ratio',
                warmupSteps: userTrainingConfig.warmupSteps ?? 0,

                // 验证配置 (新增)
                evalStrategy: userTrainingConfig.evalStrategy ?? 'epoch',
                evalSteps: userTrainingConfig.evalSteps ?? 200,

                // 高级训练选项 (新增)
                earlyStoppingEnabled: userTrainingConfig.earlyStoppingEnabled ?? false,
                earlyStoppingPatience: userTrainingConfig.earlyStoppingPatience ?? 3,
                earlyStoppingThreshold: userTrainingConfig.earlyStoppingThreshold ?? 0.0,
                loadBestModelAtEnd: userTrainingConfig.loadBestModelAtEnd ?? true,
                metricForBestModel: userTrainingConfig.metricForBestModel ?? 'loss',
            },
            lora: {
                rank: userLoraConfig.rank,
                alpha: userLoraConfig.alpha,
                dropout: userLoraConfig.dropout ?? 0.05,  // 新增: LoRA dropout
                bias: userLoraConfig.bias ?? 'none',      // 新增: LoRA bias
                quantization: userLoraConfig.quantization,
                targetModules: userLoraConfig.targetModules,
                enabled: userLoraConfig.enabled,
            },
        };

        // 确保输出目录存在
        if (!fs.existsSync(trainConfig.outputDir)) {
            fs.mkdirSync(trainConfig.outputDir, { recursive: true });
        }

        fs.writeFileSync(trainingConfigPath, JSON.stringify(pythonConfig, null, 2));

        yield {
            type: 'log',
            timestamp: new Date(),
            data: {
                level: 'info',
                message: `[LoraTrainer] Training config written to ${trainingConfigPath}`,
            },
        };

        // 检查训练脚本是否存在
        if (!fs.existsSync(TRAIN_SCRIPT)) {
            yield {
                type: 'error',
                timestamp: new Date(),
                data: {
                    error: `Training script not found: ${TRAIN_SCRIPT}`,
                },
            };
            return;
        }

        // 启动 Python 训练进程
        yield {
            type: 'log',
            timestamp: new Date(),
            data: {
                level: 'info',
                message: `[LoraTrainer] Spawning Python training process...`,
            },
        };

        try {
            // 使用 AsyncGenerator 来处理进程输出
            const events = this.spawnTrainingProcess(trainingConfigPath, startTime);

            for await (const event of events) {
                yield event;
            }

        } catch (error: any) {
            yield {
                type: 'error',
                timestamp: new Date(),
                data: {
                    error: error.message || 'Training process failed',
                },
            };
        }
    }

    private async *spawnTrainingProcess(configPath: string, startTime: number): AsyncGenerator<TrainEvent> {
        // 使用事件队列实现实时流式传输
        const eventQueue: TrainEvent[] = [];
        let resolveNext: (() => void) | null = null;
        let processComplete = false;
        let processError: Error | null = null;

        // P0-FIX: 跟踪已发送的 step，防止重复发送
        const processedSteps = new Set<number>();

        const pythonCmd = getPython();
        this.process = spawn(pythonCmd, [TRAIN_SCRIPT, '--config', configPath], {
            stdio: ['pipe', 'pipe', 'pipe'],
        });

        const stdout = createInterface({ input: this.process.stdout! });
        const stderr = createInterface({ input: this.process.stderr! });
        let currentStep = 0;

        const pushEvent = (event: TrainEvent) => {
            eventQueue.push(event);
            if (resolveNext) {
                resolveNext();
                resolveNext = null;
            }
        };

        // 解析标准输出
        stdout.on('line', (line) => {
            const trimmedLine = line.trim();
            if (!trimmedLine) return;

            // Debug log for raw output
            console.log(`[LoraTrainer RAW] ${trimmedLine}`);

            // 首先尝试解析 JSON 格式的事件 (来自 TrainingEventCallback)
            if (trimmedLine.startsWith('{') && trimmedLine.endsWith('}')) {
                try {
                    const jsonEvent = JSON.parse(trimmedLine);

                    // 处理 metric 事件
                    if (jsonEvent.type === 'metric' && jsonEvent.data) {
                        currentStep = jsonEvent.data.step || currentStep + 1;
                        // P0-FIX: 检查是否已处理过该 step
                        if (processedSteps.has(currentStep)) {
                            return; // 跳过重复的 step
                        }
                        processedSteps.add(currentStep);
                        // console.log(`[LoraTrainer] Parsed metric event: step=${currentStep}, loss=${jsonEvent.data.loss}`);
                        pushEvent({
                            type: 'metric',
                            timestamp: new Date(),
                            data: {
                                step: currentStep,
                                loss: jsonEvent.data.loss,
                                lr: jsonEvent.data.lr,
                                epoch: jsonEvent.data.epoch,
                                gradNorm: jsonEvent.data.grad_norm,
                            },
                        });
                        return;
                    }

                    // 处理 checkpoint 事件
                    if (jsonEvent.type === 'checkpoint' && jsonEvent.data) {
                        console.log(`[LoraTrainer] Parsed checkpoint event: ${jsonEvent.data.path}`);
                        pushEvent({
                            type: 'checkpoint',
                            timestamp: new Date(),
                            data: {
                                path: jsonEvent.data.path,
                                step: jsonEvent.data.step,
                            },
                        });
                        return;
                    }

                    // 处理 experiment_log 事件
                    if (jsonEvent.type === 'experiment_log' && jsonEvent.data) {
                        console.log(`[LoraTrainer] Parsed experiment_log event`);
                        pushEvent({
                            type: 'experiment_log',
                            timestamp: new Date(),
                            data: jsonEvent.data,
                        });
                        return;
                    }

                    // 处理 data_quality 事件 (P2: 数据质量统计)
                    if (jsonEvent.type === 'data_quality' && jsonEvent.data) {
                        console.log(`[LoraTrainer] Parsed data_quality event`);
                        pushEvent({
                            type: 'data_quality',
                            timestamp: new Date(),
                            data: jsonEvent.data,
                        });
                        return;
                    }

                    // 处理 training_summary 事件
                    if (jsonEvent.type === 'training_summary' && jsonEvent.data) {
                        console.log(`[LoraTrainer] Parsed training_summary event`);
                        pushEvent({
                            type: 'training_summary',
                            timestamp: new Date(),
                            data: jsonEvent.data,
                        });
                        return;
                    }
                } catch (e) {
                    // 不是有效JSON，继续使用正则表达式解析
                    // console.warn(`[LoraTrainer] Failed to parse JSON line: ${trimmedLine}`, e);
                }
            } else if (line.includes('"type":')) {
                // Fallback for lines that might contain JSON but rely on previous looser check
                try {
                    const jsonEvent = JSON.parse(line);
                    // ... (logic would be duplicated, but the strict check above covers most)
                    // meaningful fallback logic if needed, otherwise let it fall through
                } catch (e) { }
            }

            // 后备：尝试解析训练指标 (HuggingFace Trainer 格式)
            // 格式: {'loss': 3.5068, 'grad_norm': 6.55, 'learning_rate': 9.4e-05, 'epoch': 1.6}
            // P0-FIX: 仅匹配 'loss'，不匹配 'train_loss'（epoch 平均值）
            // train_loss 是训练结束时的平均 loss，会导致异常跳跃
            const lossMatch = line.match(/'loss':\s*([\d.]+)/);
            const lrMatch = line.match(/'learning_rate':\s*([\d.e+-]+)/);
            const epochMatch = line.match(/'epoch':\s*([\d.]+)/);
            const gradNormMatch = line.match(/'grad_norm':\s*([\d.]+)/);

            if (lossMatch && epochMatch) {
                currentStep++;
                // P0-FIX: 检查是否已处理过该 step（防止 JSON 和 regex 双重解析）
                if (processedSteps.has(currentStep)) {
                    return; // 跳过重复的 step
                }
                processedSteps.add(currentStep);
                // console.log(`[LoraTrainer] Regex parsed stride: step=${currentStep}, loss=${lossMatch[1]}`);
                pushEvent({
                    type: 'metric',
                    timestamp: new Date(),
                    data: {
                        step: currentStep,
                        loss: parseFloat(lossMatch[1]),
                        lr: lrMatch ? parseFloat(lrMatch[1]) : undefined,
                        epoch: parseFloat(epochMatch[1]),
                        gradNorm: gradNormMatch ? parseFloat(gradNormMatch[1]) : undefined,
                    },
                });
            } else if (line.trim()) {
                pushEvent({
                    type: 'log',
                    timestamp: new Date(),
                    data: {
                        level: 'info',
                        message: `[Python] ${line}`,
                    },
                });
            }
        });

        // 解析标准错误（包含进度和日志）
        stderr.on('line', (line) => {
            if (!line.trim()) return;

            // 检查进度条 (tqdm 格式)
            const progressMatch = line.match(/(\d+)%\|/);
            if (progressMatch) {
                pushEvent({
                    type: 'log',
                    timestamp: new Date(),
                    data: {
                        level: 'info',
                        message: `[Progress] ${progressMatch[1]}%`,
                    },
                });
                return;
            }

            // 检查常见日志格式
            const logMatch = line.match(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.*?) - (.*?) - (INFO|WARNING|ERROR|DEBUG) - (.*)/);
            if (logMatch) {
                const level = logMatch[3].toLowerCase() as 'info' | 'warning' | 'error';
                pushEvent({
                    type: 'log',
                    timestamp: new Date(),
                    data: {
                        level,
                        message: `[${logMatch[2]}] ${logMatch[4]}`,
                    },
                });
                return;
            }

            // 错误和警告检测
            const lowerLine = line.toLowerCase();
            if (lowerLine.includes('error') || lowerLine.includes('exception') || lowerLine.includes('traceback')) {
                pushEvent({
                    type: 'log',
                    timestamp: new Date(),
                    data: {
                        level: 'error',
                        message: `[Python] ${line}`,
                    },
                });
            } else if (lowerLine.includes('warning')) {
                pushEvent({
                    type: 'log',
                    timestamp: new Date(),
                    data: {
                        level: 'warning',
                        message: `[Python] ${line}`,
                    },
                });
            } else {
                pushEvent({
                    type: 'log',
                    timestamp: new Date(),
                    data: {
                        level: 'info',
                        message: `[Python] ${line}`,
                    },
                });
            }
        });

        this.process.on('close', (code) => {
            const duration = ((Date.now() - startTime) / 1000).toFixed(1);

            if (code === 0) {
                pushEvent({
                    type: 'log',
                    timestamp: new Date(),
                    data: {
                        level: 'info',
                        message: `[LoraTrainer] Training complete in ${duration}s`,
                    },
                });
                pushEvent({
                    type: 'complete',
                    timestamp: new Date(),
                    data: {
                        duration: `${duration}s`,
                        exitCode: code,
                    },
                });
            } else {
                pushEvent({
                    type: 'error',
                    timestamp: new Date(),
                    data: {
                        error: `Training process exited with code ${code}`,
                    },
                });
                processError = new Error(`Training process exited with code ${code}`);
            }
            processComplete = true;
            if (resolveNext) resolveNext();
        });

        this.process.on('error', (err) => {
            pushEvent({
                type: 'error',
                timestamp: new Date(),
                data: {
                    error: err.message,
                },
            });
            processError = err;
            processComplete = true;
            if (resolveNext) resolveNext();
        });

        // 异步迭代器：持续 yield 事件直到进程完成
        while (!processComplete || eventQueue.length > 0) {
            if (eventQueue.length > 0) {
                yield eventQueue.shift()!;
            } else if (!processComplete) {
                // 等待新事件
                await new Promise<void>((resolve) => {
                    resolveNext = resolve;
                });
            }
        }

        if (processError) {
            throw processError;
        }
    }

    stop() {
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
}
