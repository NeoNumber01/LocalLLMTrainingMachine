import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

async function main() {
    console.log('=== Verify Restore Results ===\n');

    const runs = await prisma.run.findMany({
        include: {
            model: { select: { name: true } },
            loraStats: true,
            experimentMeta: true,
            datasetMeta: true,
        },
        orderBy: { createdAt: 'desc' }
    });

    console.log(`Total ${runs.length} run records:\n`);

    for (const run of runs) {
        console.log(`📌 ${run.id}`);
        console.log(`   Type: ${run.type}`);
        console.log(`   Name: ${run.name}`);
        console.log(`   Status: ${run.status}`);
        console.log(`   Model: ${run.model?.name || 'N/A'}`);
        console.log(`   Duration: ${run.duration || 'N/A'}`);

        if (run.type === 'train' && run.loraStats) {
            console.log(`   LoRA: rank=${run.loraStats.rank}, alpha=${run.loraStats.alpha}`);
            console.log(`   Trainable Params: ${(Number(run.loraStats.trainableParams) / 1e6).toFixed(1)}M`);
        }

        if (run.type === 'eval' && run.metricsJson) {
            const metrics = JSON.parse(run.metricsJson);
            console.log(`   Pass@1: ${metrics.passAt1}%`);
            console.log(`   Compile Rate: ${metrics.compileRate}%`);
        }

        console.log('');
    }

    // Statistics
    const models = await prisma.model.count();
    const datasets = await prisma.dataset.count();
    const adapters = await prisma.adapter.count();

    console.log('=== Database Statistics ===');
    console.log(`Models: ${models}`);
    console.log(`Datasets: ${datasets}`);
    console.log(`Run Records: ${runs.length}`);
    console.log(`Adapters: ${adapters}`);
}

main().catch(console.error).finally(() => prisma.$disconnect());
