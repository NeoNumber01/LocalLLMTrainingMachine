import { TrainerProvider, TrainConfig, TrainEvent } from '../interfaces.js';
import { Config } from '../../config/index.js';

export class FullFinetuneTrainer implements TrainerProvider {
    name = 'full_finetune';
    private config: Config;

    constructor(config: Config) {
        this.config = config;
    }

    async *train(trainConfig: TrainConfig): AsyncGenerator<TrainEvent> {
        const totalSteps = trainConfig.config.training.epochs * 100;
        const startTime = Date.now();

        yield {
            type: 'log',
            timestamp: new Date(),
            data: {
                level: 'info',
                message: `[FullFinetuneTrainer] Starting full fine-tune for run ${trainConfig.runId}`,
            },
        };

        yield {
            type: 'log',
            timestamp: new Date(),
            data: {
                level: 'info',
                message: `[FullFinetuneTrainer] Config: epochs=${trainConfig.config.training.epochs}, batch=${trainConfig.config.training.batchSize}, lr=${trainConfig.config.training.lr}`,
            },
        };

        for (let step = 1; step <= totalSteps; step++) {
            await new Promise(resolve => setTimeout(resolve, 80)); // 比 LoRA 慢

            const progress = step / totalSteps;
            const baseLoss = 3.0;
            const finalLoss = 0.08 + Math.random() * 0.1;
            const currentLoss = baseLoss * Math.exp(-4 * progress) + finalLoss * progress;

            if (step % 10 === 0) {
                yield {
                    type: 'metric',
                    timestamp: new Date(),
                    data: {
                        step,
                        loss: Number(currentLoss.toFixed(4)),
                        lr: Number((parseFloat(trainConfig.config.training.lr) * (1 - progress * 0.3)).toExponential(1)),
                        gradNorm: Number((2.0 + Math.random()).toFixed(2)),
                    },
                };
            }

            if (step % 100 === 0) {
                const epoch = Math.floor(step / 100);
                yield {
                    type: 'log',
                    timestamp: new Date(),
                    data: {
                        level: 'info',
                        message: `[FullFinetuneTrainer] Epoch ${epoch}/${trainConfig.config.training.epochs} completed. Loss: ${currentLoss.toFixed(4)}`,
                    },
                };

                yield {
                    type: 'checkpoint',
                    timestamp: new Date(),
                    data: {
                        step,
                        epoch,
                        path: `checkpoint-${step}`,
                    },
                };
            }
        }

        const duration = ((Date.now() - startTime) / 1000).toFixed(1);
        yield {
            type: 'log',
            timestamp: new Date(),
            data: {
                level: 'info',
                message: `[FullFinetuneTrainer] Training complete in ${duration}s`,
            },
        };

        yield {
            type: 'complete',
            timestamp: new Date(),
            data: {
                finalLoss: 0.085,
                duration: `${duration}s`,
            },
        };
    }
}
