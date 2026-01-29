/**
 * 从 storage/runs 目录恢复历史运行记录
 * 读取 experiment_log.json, train_config.json, eval_config.json 等文件重建数据库记录
 */

import { PrismaClient } from '@prisma/client';
import fs from 'fs';
import path from 'path';

const prisma = new PrismaClient();
const RUNS_DIR = './storage/runs';

// 辅助函数: 读取 JSON 文件
function readJson(filePath) {
    try {
        const content = fs.readFileSync(filePath, 'utf-8');
        return JSON.parse(content);
    } catch (error) {
        return null;
    }
}

// 计算持续时间
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

// 恢复训练记录
async function restoreTrainingRun(runId, runDir) {
    const experimentLog = readJson(path.join(runDir, 'experiment_log.json'));
    const trainConfig = readJson(path.join(runDir, 'train_config.json'));

    if (!experimentLog && !trainConfig) {
        console.log(`  跳过 ${runId}: 无训练配置文件`);
        return null;
    }

    // 查找模型ID
    let modelName = 'Unknown Model';
    if (trainConfig?.modelPath) {
        modelName = path.basename(trainConfig.modelPath);
    }

    const model = await prisma.model.findFirst({
        where: { name: { contains: modelName.split('-')[0] } }
    });

    if (!model) {
        console.log(`  警告: 找不到模型 ${modelName}`);
        return null;
    }

    // 查找数据集ID
    const dataset = await prisma.dataset.findFirst();
    if (!dataset) {
        console.log(`  警告: 找不到数据集`);
        return null;
    }

    // 创建运行记录
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

    // 创建 LoRA 统计
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

    // 创建实验元数据
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

    // 创建数据集元数据
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

// 恢复评估记录
async function restoreEvalRun(runId, runDir) {
    const evalConfig = readJson(path.join(runDir, 'eval_config.json'));
    const evalSummary = readJson(path.join(runDir, 'eval_summary.json'));

    if (!evalConfig && !evalSummary) {
        console.log(`  跳过 ${runId}: 无评估配置文件`);
        return null;
    }

    // 查找模型
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
        console.log(`  警告: 找不到模型 ${modelName}`);
        return null;
    }

    // 查找数据集
    const dataset = await prisma.dataset.findFirst();
    if (!dataset) {
        console.log(`  警告: 找不到数据集`);
        return null;
    }

    // 获取源训练运行ID
    let sourceRunId = null;
    if (evalConfig?.adapterPath) {
        const match = evalConfig.adapterPath.match(/run_([a-f0-9]+)/);
        if (match) {
            sourceRunId = `run_${match[1]}`;
        }
    }

    // 提取指标
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

    // 创建实验元数据
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
    console.log('=== 开始恢复历史运行记录 ===\n');

    // 读取 runs 目录
    if (!fs.existsSync(RUNS_DIR)) {
        console.log('错误: storage/runs 目录不存在');
        return;
    }

    const runDirs = fs.readdirSync(RUNS_DIR).filter(d => d.startsWith('run_'));
    console.log(`找到 ${runDirs.length} 个运行目录\n`);

    let restoredCount = 0;
    let skippedCount = 0;

    for (const runId of runDirs) {
        const runDir = path.join(RUNS_DIR, runId);

        // 检查是否已存在
        const existing = await prisma.run.findUnique({ where: { id: runId } });
        if (existing) {
            console.log(`[跳过] ${runId}: 已存在`);
            skippedCount++;
            continue;
        }

        // 判断是训练还是评估
        const hasExperimentLog = fs.existsSync(path.join(runDir, 'experiment_log.json'));
        const hasEvalSummary = fs.existsSync(path.join(runDir, 'eval_summary.json'));
        const hasEvalConfig = fs.existsSync(path.join(runDir, 'eval_config.json'));

        let result = null;
        if (hasExperimentLog) {
            console.log(`[恢复] ${runId}: 训练记录`);
            result = await restoreTrainingRun(runId, runDir);
        } else if (hasEvalSummary || hasEvalConfig) {
            console.log(`[恢复] ${runId}: 评估记录`);
            result = await restoreEvalRun(runId, runDir);
        } else {
            console.log(`[跳过] ${runId}: 无可识别的配置文件`);
            skippedCount++;
            continue;
        }

        if (result) {
            restoredCount++;
        }
    }

    console.log(`\n=== 恢复完成 ===`);
    console.log(`成功恢复: ${restoredCount} 个`);
    console.log(`跳过: ${skippedCount} 个`);
}

main()
    .catch(console.error)
    .finally(() => prisma.$disconnect());
