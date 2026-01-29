// Query RunEvents for run_12949 to understand execution flow
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
    // 获取 run_12949 的所有事件
    const events = await prisma.runEvent.findMany({
        where: { runId: 'run_12949' },
        orderBy: { timestamp: 'asc' },
    });

    console.log('========== Run Events ==========');
    console.log(`Total events: ${events.length}`);
    console.log('');

    for (const event of events) {
        const time = new Date(event.timestamp).toLocaleTimeString();
        console.log(`[${time}] [${event.level.toUpperCase()}] ${event.message}`);
    }

    console.log('');
    console.log('========== Run Status ==========');

    // 获取 Run 状态
    const run = await prisma.run.findUnique({
        where: { id: 'run_12949' },
        include: { artifacts: true },
    });

    if (run) {
        console.log(`Status: ${run.status}`);
        console.log(`Created: ${run.createdAt}`);
        console.log(`Started: ${run.startedAt}`);
        console.log(`Completed: ${run.completedAt}`);
        console.log(`Duration: ${run.duration}`);
        console.log(`Artifacts: ${run.artifacts.length}`);
        for (const artifact of run.artifacts) {
            console.log(`  - [${artifact.kind}] ${artifact.path}`);
        }
    }

    console.log('');
    console.log('========== Adapter Check ==========');

    // 检查是否有 adapter 记录
    const adapters = await prisma.adapter.findMany({
        where: {
            OR: [
                { name: { contains: '6.7B' } },
                { name: { contains: 'run_12949' } },
                { path: { contains: 'run_12949' } },
            ]
        }
    });

    console.log(`Matching adapters: ${adapters.length}`);
    for (const adapter of adapters) {
        console.log(`  - ${adapter.name} (${adapter.baseModel})`);
    }

    await prisma.$disconnect();
}

main().catch(console.error);
