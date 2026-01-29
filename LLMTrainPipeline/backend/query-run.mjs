import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

async function main() {
    // 查询 run 状态
    const run = await prisma.run.findUnique({
        where: { id: 'run_12949' },
        select: { id: true, status: true, duration: true, metricsJson: true, gpuHours: true, totalSteps: true }
    });
    console.log('Run status:', JSON.stringify(run, null, 2));

    // 查询 LoRA 统计信息
    const loraStats = await prisma.loraStats.findUnique({
        where: { runId: 'run_12949' }
    });
    console.log('\nLoRA Stats:', JSON.stringify(loraStats, (key, value) =>
        typeof value === 'bigint' ? value.toString() : value
        , 2));
}

main().catch(console.error).finally(() => prisma.$disconnect());
