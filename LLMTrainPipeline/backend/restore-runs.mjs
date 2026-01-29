/**
 * Restore historical run records from storage/runs directory
 * Read experiment_log.json, train_config.json, eval_config.json etc. to rebuild database records
 */

import { PrismaClient } from '@prisma/client';
import fs from 'fs';
import path from 'path';

const prisma = new PrismaClient();
const RUNS_DIR = './storage/runs';

// Helper function: Read JSON file
function readJson(filePath) {
    try {
        const content = fs.readFileSync(filePath, 'utf-8');
        return JSON.parse(content);
    } catch (error) {
        return null;
    }
}

// Calculate duration
function calculateDuration(startTime, endTime) {
    if (!startTime || !endTime) return null;
    const start = new Date(startTime);
    const end = new Date(endTime);
    const diffMs = end - start;
    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
}

// Restore training run
async function restoreTrainingRun(runId, runDir) {
    const experimentLog = readJson(path.join(runDir, 'experiment_log.json'));
    const trainConfig = readJson(path.join(runDir, 'train_config.json'));

    if (!experimentLog && !trainConfig) {
        console.log(`  Skip ${runId}: No training config file`);
        return null;
    }

    // Find model ID
    let modelName = 'Unknown Model';
    if (trainConfig?.modelPath) {
        modelName = path.basename(trainConfig.modelPath);
    }

    const model = await prisma.model.findFirst({
        where: { name: { contains: modelName.split('-')[0] } }
    });

    if (!model) {
        console.log(`  Warning: Model ${modelName} not found`);
        return null;
    }

    // Find dataset ID
    const dataset = await prisma.dataset.findFirst();
    if (!dataset) {
        console.log(`  Warning: Dataset not found`);
        return null;
    }

    // Create run record
    const run = await prisma.run.create({
        data: {
            id: runId,
            name: `Training: ${modelName}`,
            type: 'train',
            status: 'completed',
            createdAt: experimentLog?.start_time ? new Date(experimentLog.start_time) : new Date(),
            startedAt: experimentLog?.start_time ? new Date(experimentLog.start_time) : null,
            completedAt: experimentLog?.end_time ? new Date(experimentLog.end_time) : null,
            duration: calculateDuration(experimentLog?.start_time, experimentLog?.end_time),
            modelId: model.id,
            datasetId: dataset.id,
            profileName: 'single_gpu',
            configJson: JSON.stringify(trainConfig || {}),
            metricsJson: experimentLog?.training_config ? JSON.stringify(experimentLog.training_config) : null,
            seed: experimentLog?.seed || 42,
            gitCommit: experimentLog?.git_commit || null,
            totalTokens: experimentLog?.total_tokens || null,
            totalSteps: experimentLog?.total_steps || null,
            gpuHours: experimentLog?.gpu_hours || null,
            tokensPerSecond: experimentLog?.tokens_per_second || null,
        }
    });

    // Create LoRA statistics
    if (experimentLog?.lora_stats) {
        const loraStats = experimentLog.lora_stats;
        await prisma.loraStats.create({
            data: {
                runId: run.id,
                rank: loraStats.rank || null,
                alpha: loraStats.alpha || null,
                dropout: loraStats.dropout || null,
                targetModules: loraStats.target_modules ? JSON.stringify(loraStats.target_modules) : null,
                trainableParams: loraStats.trainable_params ? BigInt(loraStats.trainable_params) : null,
                totalParams: loraStats.total_params ? BigInt(loraStats.total_params) : null,
                trainablePercent: loraStats.trainable_percent || null,
            }
        });
    }

    // Create experiment metadata
    if (experimentLog?.environment || experimentLog?.hardware) {
        const env = experimentLog.environment || {};
        const hw = experimentLog.hardware || {};
        await prisma.experimentMeta.create({
            data: {
                runId: run.id,
                osVersion: env.os_version || null,
                pythonVersion: env.python_version || null,
                pytorchVersion: env.pytorch_version || null,
                transformersVersion: env.transformers_version || null,
                trlVersion: env.trl_version || null,
                peftVersion: env.peft_version || null,
                cudaVersion: env.cuda_version || null,
                cudnnVersion: env.cudnn_version || null,
                bitsandbytesVersion: env.bitsandbytes_version || null,
                gpuModel: hw.gpu_model || null,
                gpuMemoryGB: hw.gpu_memory_gb || null,
                cpuModel: hw.cpu_model || null,
                ramGB: hw.ram_gb || null,
                startTime: experimentLog.start_time ? new Date(experimentLog.start_time) : null,
                endTime: experimentLog.end_time ? new Date(experimentLog.end_time) : null,
            }
        });
    }

    // Create dataset metadata
    if (experimentLog?.dataset_info) {
        const di = experimentLog.dataset_info;
        await prisma.datasetMeta.create({
            data: {
                runId: run.id,
                source: di.source || null,
                trainSamples: di.train_samples || null,
                valSamples: di.val_samples || null,
                testSamples: di.test_samples || null,
                totalProblems: di.total_problems || null,
                totalTokens: di.total_tokens || null,
                promptTemplate: di.prompt_template || null,
                outputFormat: di.output_format || null,
                dedupeMethod: di.dedupe_method || null,
                lengthFilter: di.length_filter || null,
                cleaningFlags: di.cleaning_flags || null,
                splitMethod: di.split_method || null,
                splitRatios: di.split_ratios || null,
                statisticsJson: experimentLog.data_quality_stats_json || null,
            }
        });
    }

    return run;
}

// Restore evaluation run
async function restoreEvalRun(runId, runDir) {
    const evalConfig = readJson(path.join(runDir, 'eval_config.json'));
    const evalSummary = readJson(path.join(runDir, 'eval_summary.json'));

    if (!evalConfig && !evalSummary) {
        console.log(`  Skip ${runId}: No evaluation config file`);
        return null;
    }

    // Find model
    let modelName = 'Unknown Model';
    if (evalConfig?.modelPath) {
        modelName = path.basename(evalConfig.modelPath);
    } else if (evalSummary?.base_model_name) {
        modelName = evalSummary.base_model_name;
    }

    const model = await prisma.model.findFirst({
        where: { name: { contains: modelName.split('-')[0] } }
    });

    if (!model) {
        console.log(`  Warning: Model ${modelName} not found`);
        return null;
    }

    // Find dataset
    const dataset = await prisma.dataset.findFirst();
    if (!dataset) {
        console.log(`  Warning: Dataset not found`);
        return null;
    }

    // Get source training run ID
    let sourceRunId = null;
    if (evalConfig?.adapterPath) {
        const match = evalConfig.adapterPath.match(/run_([a-f0-9]+)/);
        if (match) {
            sourceRunId = `run_${match[1]}`;
        }
    }

    // Extract metrics
    const metrics = evalSummary?.metrics_overall || {};

    const run = await prisma.run.create({
        data: {
            id: runId,
            name: `Evaluation: ${modelName}`,
            type: 'eval',
            status: 'completed',
            createdAt: evalSummary?.eval_time ? new Date(evalSummary.eval_time) : new Date(),
            startedAt: evalSummary?.eval_time ? new Date(evalSummary.eval_time) : null,
            completedAt: evalSummary?.eval_time ? new Date(evalSummary.eval_time) : null,
            modelId: model.id,
            datasetId: dataset.id,
            evalDatasetId: dataset.id,
            profileName: 'single_gpu',
            configJson: JSON.stringify(evalConfig || {}),
            metricsJson: JSON.stringify({
                passAt1: metrics.pass_at_1,
                passAt5: metrics.pass_at_5,
                passAt10: metrics.pass_at_10,
                compileRate: metrics.compile_rate,
            }),
            evalResultJson: JSON.stringify(evalSummary || {}),
            sourceRunId: sourceRunId,
            seed: evalSummary?.reproducibility_info?.python_seed || 42,
            gitCommit: evalSummary?.git_commit || null,
        }
    });

    // Create experiment metadata
    if (evalSummary?.environment) {
        const env = evalSummary.environment;
        await prisma.experimentMeta.create({
            data: {
                runId: run.id,
                osVersion: env.os_version || null,
                pythonVersion: env.python_version || null,
                pytorchVersion: env.pytorch_version || null,
                transformersVersion: env.transformers_version || null,
                peftVersion: env.peft_version || null,
                gpuModel: env.gpu_model || null,
                gpuMemoryGB: env.gpu_memory_gb || null,
                cpuModel: env.cpu_model || null,
                ramGB: env.ram_gb || null,
            }
        });
    }

    return run;
}

async function main() {
    console.log('=== Start Restoring Historical Run Records ===\n');

    // Read runs directory
    if (!fs.existsSync(RUNS_DIR)) {
        console.log('Error: storage/runs directory does not exist');
        return;
    }

    const runDirs = fs.readdirSync(RUNS_DIR).filter(d => d.startsWith('run_'));
    console.log(`Found ${runDirs.length} run directories\n`);

    let restoredCount = 0;
    let skippedCount = 0;

    for (const runId of runDirs) {
        const runDir = path.join(RUNS_DIR, runId);

        // Check if already exists
        const existing = await prisma.run.findUnique({ where: { id: runId } });
        if (existing) {
            console.log(`[Skip] ${runId}: Already exists`);
            skippedCount++;
            continue;
        }

        // Determine if training or evaluation
        const hasExperimentLog = fs.existsSync(path.join(runDir, 'experiment_log.json'));
        const hasEvalSummary = fs.existsSync(path.join(runDir, 'eval_summary.json'));
        const hasEvalConfig = fs.existsSync(path.join(runDir, 'eval_config.json'));

        let result = null;
        if (hasExperimentLog) {
            console.log(`[Restore] ${runId}: Training record`);
            result = await restoreTrainingRun(runId, runDir);
        } else if (hasEvalSummary || hasEvalConfig) {
            console.log(`[Restore] ${runId}: Evaluation record`);
            result = await restoreEvalRun(runId, runDir);
        } else {
            console.log(`[Skip] ${runId}: No recognizable config file`);
            skippedCount++;
            continue;
        }

        if (result) {
            restoredCount++;
        }
    }

    console.log(`\n=== Restore Complete ===`);
    console.log(`Successfully restored: ${restoredCount}`);
    console.log(`Skipped: ${skippedCount}`);
}

main()
    .catch(console.error)
    .finally(() => prisma.$disconnect());
