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

        // Initialize logging
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

        // Create training config file
        const trainingConfigPath = path.join(trainConfig.outputDir, 'train_config.json');

        // Use user settings from trainConfig.config
        const userTrainingConfig = trainConfig.config.training;
        const userLoraConfig = trainConfig.config.lora;

        const pythonConfig = {
            runId: trainConfig.runId,
            modelPath: trainConfig.modelPath,
            datasetPath: trainConfig.datasetPath,
            evalDatasetPath: trainConfig.evalDatasetPath,
            outputDir: trainConfig.outputDir,
            seed: userTrainingConfig.seed ?? 42,  // New: random seed
            training: {
                // Basic training parameters
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

                // Core training parameters (new)
                loggingSteps: userTrainingConfig.loggingSteps ?? 10,
                saveSteps: userTrainingConfig.saveSteps ?? 100,
                saveTotalLimit: userTrainingConfig.saveTotalLimit ?? 3,
                gradientClipping: userTrainingConfig.gradientClipping ?? 1.0,

                // Warmup configuration (new)
                warmupType: userTrainingConfig.warmupType ?? 'ratio',
                warmupSteps: userTrainingConfig.warmupSteps ?? 0,

                // Validation configuration (new)
                evalStrategy: userTrainingConfig.evalStrategy ?? 'epoch',
                evalSteps: userTrainingConfig.evalSteps ?? 200,

                // Advanced training options (new)
                earlyStoppingEnabled: userTrainingConfig.earlyStoppingEnabled ?? false,
                earlyStoppingPatience: userTrainingConfig.earlyStoppingPatience ?? 3,
                earlyStoppingThreshold: userTrainingConfig.earlyStoppingThreshold ?? 0.0,
                loadBestModelAtEnd: userTrainingConfig.loadBestModelAtEnd ?? true,
                metricForBestModel: userTrainingConfig.metricForBestModel ?? 'loss',
            },
            lora: {
                rank: userLoraConfig.rank,
                alpha: userLoraConfig.alpha,
                dropout: userLoraConfig.dropout ?? 0.05,  // New: LoRA dropout
                bias: userLoraConfig.bias ?? 'none',      // New: LoRA bias
                quantization: userLoraConfig.quantization,
                targetModules: userLoraConfig.targetModules,
                enabled: userLoraConfig.enabled,
            },
        };

        // Ensure output directory exists
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

        // Check if training script exists
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

        // Start Python training process
        yield {
            type: 'log',
            timestamp: new Date(),
            data: {
                level: 'info',
                message: `[LoraTrainer] Spawning Python training process...`,
            },
        };

        try {
            // Use AsyncGenerator to handle process output
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
        // Use event queue for real-time streaming
        const eventQueue: TrainEvent[] = [];
        let resolveNext: (() => void) | null = null;
        let processComplete = false;
        let processError: Error | null = null;

        // P0-FIX: Track sent steps to prevent duplicate sending
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

        // Parse standard output
        stdout.on('line', (line) => {
            const trimmedLine = line.trim();
            if (!trimmedLine) return;

            // Debug log for raw output
            console.log(`[LoraTrainer RAW] ${trimmedLine}`);

            // First try to parse JSON format events (from TrainingEventCallback)
            if (trimmedLine.startsWith('{') && trimmedLine.endsWith('}')) {
                try {
                    const jsonEvent = JSON.parse(trimmedLine);

                    // Handle metric event
                    if (jsonEvent.type === 'metric' && jsonEvent.data) {
                        currentStep = jsonEvent.data.step || currentStep + 1;
                        // P0-FIX: Check if this step has already been processed
                        if (processedSteps.has(currentStep)) {
                            return; // Skip duplicate step
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

                    // Handle checkpoint event
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

                    // Handle experiment_log event
                    if (jsonEvent.type === 'experiment_log' && jsonEvent.data) {
                        console.log(`[LoraTrainer] Parsed experiment_log event`);
                        pushEvent({
                            type: 'experiment_log',
                            timestamp: new Date(),
                            data: jsonEvent.data,
                        });
                        return;
                    }

                    // Handle data_quality event (P2: Data quality statistics)
                    if (jsonEvent.type === 'data_quality' && jsonEvent.data) {
                        console.log(`[LoraTrainer] Parsed data_quality event`);
                        pushEvent({
                            type: 'data_quality',
                            timestamp: new Date(),
                            data: jsonEvent.data,
                        });
                        return;
                    }

                    // Handle training_summary event
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
                    // Not valid JSON, continue with regex parsing
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

            // Fallback: try to parse training metrics (HuggingFace Trainer format)
            // Format: {'loss': 3.5068, 'grad_norm': 6.55, 'learning_rate': 9.4e-05, 'epoch': 1.6}
            // P0-FIX: Only match 'loss', not 'train_loss' (epoch average)
            // train_loss is average loss at training end, causes abnormal jumps
            const lossMatch = line.match(/'loss':\s*([\d.]+)/);
            const lrMatch = line.match(/'learning_rate':\s*([\d.e+-]+)/);
            const epochMatch = line.match(/'epoch':\s*([\d.]+)/);
            const gradNormMatch = line.match(/'grad_norm':\s*([\d.]+)/);

            if (lossMatch && epochMatch) {
                currentStep++;
                // P0-FIX: Check if this step has been processed (prevent JSON and regex double parsing)
                if (processedSteps.has(currentStep)) {
                    return; // Skip duplicate step
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

        // Parse standard error (contains progress and logs)
        stderr.on('line', (line) => {
            if (!line.trim()) return;

            // Check progress bar (tqdm format)
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

            // Check common log format
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

            // Error and warning detection
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

        // Async iterator: keep yielding events until process completes
        while (!processComplete || eventQueue.length > 0) {
            if (eventQueue.length > 0) {
                yield eventQueue.shift()!;
            } else if (!processComplete) {
                // Wait for new events
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
