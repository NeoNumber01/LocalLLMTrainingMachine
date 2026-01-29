import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

async function main() {
    console.log('=== 验证恢复结果 ===\n');

    const runs = await prisma.run.findMany({
        include: {
            model: { select: { name: true } },
            loraStats: true,
            experimentMeta: true,
            datasetMeta: true,
        },
        orderBy: { createdAt: 'desc' }
    });

    console.log(`总共 ${runs.length} 个运行记录:\n`);

    for (const run of runs) {
        console.log(`📌 ${run.id}`);
        console.log(`   类型: ${run.type}`);
        console.log(`   名称: ${run.name}`);
        console.log(`   状态: ${run.status}`);
        console.log(`   模型: ${run.model?.name || 'N/A'}`);
        console.log(`   时长: ${run.duration || 'N/A'}`);

        if (run.type === 'train' && run.loraStats) {
            console.log(`   LoRA: rank=${run.loraStats.rank}, alpha=${run.loraStats.alpha}`);
            console.log(`   可训练参数: ${(Number(run.loraStats.trainableParams) / 1e6).toFixed(1)}M`);
        }

        if (run.type === 'eval' && run.metricsJson) {
            const metrics = JSON.parse(run.metricsJson);
            console.log(`   Pass@1: ${metrics.passAt1}%`);
            console.log(`   Compile Rate: ${metrics.compileRate}%`);
        }

        console.log('');
    }

    // 统计
    const models = await prisma.model.count();
    const datasets = await prisma.dataset.count();
    const adapters = await prisma.adapter.count();

    console.log('=== 数据库统计 ===');
    console.log(`模型: ${models}`);
    console.log(`数据集: ${datasets}`);
    console.log(`运行记录: ${runs.length}`);
    console.log(`适配器: ${adapters}`);
}

main().catch(console.error).finally(() => prisma.$disconnect());
