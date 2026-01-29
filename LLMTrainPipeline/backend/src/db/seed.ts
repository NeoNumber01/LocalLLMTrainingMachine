import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
    console.log('🌱 Seeding database...');

    // 清理现有数据
    await prisma.runMetric.deleteMany();
    await prisma.runEvent.deleteMany();
    await prisma.artifact.deleteMany();
    await prisma.run.deleteMany();
    await prisma.adapter.deleteMany();
    await prisma.dataset.deleteMany();
    await prisma.model.deleteMany();
    await prisma.report.deleteMany();
    await prisma.setting.deleteMany();
    await prisma.kvCache.deleteMany();

    console.log('  ✓ Cleared existing data');

    // 创建模型
    const models = await Promise.all([
        prisma.model.create({
            data: {
                id: 'm1',
                name: 'llama-2-7b-chat-hf',
                backend: 'transformers',
                source: 'HuggingFace',
                quantization: '4-bit',
                params: '6.74B',
                path: '/workspace/models/llama-2-7b',
                status: 'valid',
            },
        }),
        prisma.model.create({
            data: {
                id: 'm2',
                name: 'mistral-7b-instruct-v0.2',
                backend: 'vllm',
                source: 'Local',
                quantization: '8-bit',
                params: '7.2B',
                path: '/workspace/models/mistral-7b',
                status: 'valid',
            },
        }),
        prisma.model.create({
            data: {
                id: 'm3',
                name: 'falcon-40b-instruct',
                backend: 'transformers',
                source: 'HuggingFace',
                quantization: 'None',
                params: '40B',
                path: '/workspace/models/falcon-40b',
                status: 'error',
            },
        }),
    ]);
    console.log(`  ✓ Created ${models.length} models`);

    // 创建数据集
    const datasets = await Promise.all([
        prisma.dataset.create({
            data: {
                id: 'd1',
                name: 'custom_instruct_mix',
                version: 'v3.1.0',
                type: 'Train',
                status: 'active',
                samples: 154200,
                format: 'JSONL',
                size: '128.5 MB',
                path: '/data/raw_ingest',
                hash: 'a1b2c3d4',
            },
        }),
        prisma.dataset.create({
            data: {
                id: 'd2',
                name: 'alpaca_cleaned_en',
                version: 'v2.4.0',
                type: 'Train',
                status: 'ready',
                samples: 52002,
                format: 'JSONL',
                size: '44.2 MB',
                path: '/data/processed',
                hash: 'e5f6g7h8',
            },
        }),
        prisma.dataset.create({
            data: {
                id: 'd3',
                name: 'toxic_comments_v1',
                version: 'v0.9.0',
                type: 'Eval',
                status: 'corrupt',
                samples: 0,
                format: 'JSONL',
                size: '0 B',
                path: '/data/raw_ingest',
                hash: '00000000',
            },
        }),
        prisma.dataset.create({
            data: {
                id: 'd4',
                name: 'humaneval_python',
                version: 'v1.0.0',
                type: 'Eval',
                status: 'ready',
                samples: 164,
                format: 'JSONL',
                size: '1.2 MB',
                path: '/data/eval',
                hash: 'i9j0k1l2',
            },
        }),
    ]);
    console.log(`  ✓ Created ${datasets.length} datasets`);

    // 创建适配器
    const adapters = await Promise.all([
        prisma.adapter.create({
            data: {
                id: 'a1',
                name: 'adapter-llama3-ft-v4',
                baseModel: 'Llama-3-8B',
                trainDataset: 'finance-alpaca-10k',
                rank: 16,
                alpha: 32,
                status: 'success',
                passAt1: 42.5,
                compileRate: 100,
                path: '/workspace/adapters/adapter-llama3-ft-v4',
            },
        }),
        prisma.adapter.create({
            data: {
                id: 'a2',
                name: 'adapter-mistral-mix',
                baseModel: 'Mistral-7B',
                trainDataset: 'open-orca-sample',
                rank: 8,
                alpha: 16,
                status: 'warning',
                passAt1: 30.1,
                compileRate: 85,
                path: '/workspace/adapters/adapter-mistral-mix',
            },
        }),
        prisma.adapter.create({
            data: {
                id: 'a3',
                name: 'adapter-code-wizard',
                baseModel: 'Llama-3-8B',
                trainDataset: 'python-evol-instruct',
                rank: 64,
                alpha: 128,
                status: 'success',
                passAt1: 68.4,
                compileRate: 99.2,
                path: '/workspace/adapters/adapter-code-wizard',
            },
        }),
    ]);
    console.log(`  ✓ Created ${adapters.length} adapters`);

    // 创建运行记录
    const runs = await Promise.all([
        prisma.run.create({
            data: {
                id: 'run_8329x',
                name: 'Llama-3-8B-FineTune-v2',
                type: 'lora',
                status: 'running',
                modelId: 'm1',
                datasetId: 'd1',
                profileName: 'single_gpu',
                duration: '2h 15m',
                startedAt: new Date(Date.now() - 2 * 60 * 60 * 1000),
                configJson: JSON.stringify({
                    lr: '2e-5',
                    epochs: 3,
                    batchSize: 32,
                    useLora: true,
                    loraRank: 16,
                    loraAlpha: 32,
                }),
                metricsJson: JSON.stringify({
                    loss: 0.245,
                    passAt1: 42.5,
                    compileRate: 88.0,
                }),
            },
        }),
        prisma.run.create({
            data: {
                id: 'run_1029y',
                name: 'GPT-J-Re-train-Batch-4',
                type: 'pretrain',
                status: 'queued',
                modelId: 'm2',
                datasetId: 'd2',
                profileName: 'single_gpu',
                configJson: JSON.stringify({
                    lr: '1e-4',
                    epochs: 1,
                    batchSize: 64,
                }),
                metricsJson: JSON.stringify({
                    loss: 0,
                    passAt1: 0,
                    compileRate: 0,
                }),
            },
        }),
        prisma.run.create({
            data: {
                id: 'run_7712a',
                name: 'Mistral-7B-LoRA-Adapter',
                type: 'lora',
                status: 'success',
                modelId: 'm2',
                datasetId: 'd1',
                profileName: 'single_gpu',
                duration: '45m 12s',
                startedAt: new Date(Date.now() - 24 * 60 * 60 * 1000),
                completedAt: new Date(Date.now() - 23 * 60 * 60 * 1000),
                configJson: JSON.stringify({
                    lr: '3e-4',
                    epochs: 5,
                    batchSize: 16,
                    useLora: true,
                    loraRank: 64,
                    loraAlpha: 128,
                }),
                metricsJson: JSON.stringify({
                    loss: 0.112,
                    passAt1: 56.2,
                    compileRate: 94.5,
                }),
            },
        }),
        prisma.run.create({
            data: {
                id: 'run_3301q',
                name: 'Bert-Large-Classification',
                type: 'finetune',
                status: 'failed',
                modelId: 'm3',
                datasetId: 'd2',
                profileName: 'single_gpu',
                duration: '12m 04s',
                startedAt: new Date(Date.now() - 48 * 60 * 60 * 1000),
                completedAt: new Date(Date.now() - 47.8 * 60 * 60 * 1000),
                configJson: JSON.stringify({
                    lr: '5e-5',
                    epochs: 3,
                    batchSize: 32,
                }),
                metricsJson: JSON.stringify({
                    loss: 2.4,
                    passAt1: 12.0,
                    compileRate: 45.0,
                }),
            },
        }),
    ]);
    console.log(`  ✓ Created ${runs.length} runs`);

    // 为运行添加产物
    await Promise.all([
        prisma.artifact.create({
            data: {
                runId: 'run_8329x',
                kind: 'adapter',
                path: 'adapter_model.bin',
                size: 13107200,
            },
        }),
        prisma.artifact.create({
            data: {
                runId: 'run_8329x',
                kind: 'log',
                path: 'training_log.json',
                size: 524288,
            },
        }),
        prisma.artifact.create({
            data: {
                runId: 'run_8329x',
                kind: 'eval',
                path: 'eval_results.csv',
                size: 102400,
            },
        }),
        prisma.artifact.create({
            data: {
                runId: 'run_7712a',
                kind: 'adapter',
                path: 'adapter_model.bin',
                size: 26214400,
            },
        }),
        prisma.artifact.create({
            data: {
                runId: 'run_7712a',
                kind: 'log',
                path: 'adapter_config.json',
                size: 2048,
            },
        }),
        prisma.artifact.create({
            data: {
                runId: 'run_3301q',
                kind: 'log',
                path: 'error_log.txt',
                size: 8192,
            },
        }),
    ]);
    console.log('  ✓ Created artifacts');

    // 为运行添加一些事件
    await Promise.all([
        prisma.runEvent.create({
            data: {
                runId: 'run_8329x',
                level: 'info',
                message: 'Initializing distributed process group...',
            },
        }),
        prisma.runEvent.create({
            data: {
                runId: 'run_8329x',
                level: 'info',
                message: 'Loaded model weights from llama-2-7b-chat-hf',
            },
        }),
        prisma.runEvent.create({
            data: {
                runId: 'run_8329x',
                level: 'info',
                message: 'Epoch 1/3 started. Batch size: 32',
            },
        }),
        prisma.runEvent.create({
            data: {
                runId: 'run_8329x',
                level: 'warning',
                message: 'Gradient norm exceeds threshold (2.1)',
            },
        }),
    ]);
    console.log('  ✓ Created run events');

    // 创建报告
    await Promise.all([
        prisma.report.create({
            data: {
                id: 'r1',
                title: 'Llama-3 Fine-tune Regression Analysis',
                type: 'Run',
                format: 'HTML',
                size: '2.4 MB',
                path: '/storage/reports/r1.html',
            },
        }),
        prisma.report.create({
            data: {
                id: 'r2',
                title: 'Mistral vs Llama Code Perf',
                type: 'Comparison',
                format: 'PDF',
                size: '1.1 MB',
                path: '/storage/reports/r2.pdf',
            },
        }),
    ]);
    console.log('  ✓ Created reports');

    console.log('\n✅ Database seeded successfully!');
}

main()
    .catch((e) => {
        console.error('Seed error:', e);
        process.exit(1);
    })
    .finally(async () => {
        await prisma.$disconnect();
    });
