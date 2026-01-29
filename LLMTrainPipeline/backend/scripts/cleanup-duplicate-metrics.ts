// 清理 RunMetric 表中的重复数据
// 保留每个 (runId, step) 组合中最新的一条记录

import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function cleanupDuplicateMetrics() {
    console.log('开始清理重复的 RunMetric 数据...');

    // 查找所有重复的 (runId, step) 组合
    const duplicates = await prisma.$queryRaw<Array<{ runId: string; step: number; count: bigint }>>`
        SELECT runId, step, COUNT(*) as count 
        FROM RunMetric 
        GROUP BY runId, step 
        HAVING COUNT(*) > 1
    `;

    console.log(`找到 ${duplicates.length} 个重复的 (runId, step) 组合`);

    let totalDeleted = 0;

    for (const dup of duplicates) {
        // 获取该组合下的所有记录，按 timestamp 降序排列
        const metrics = await prisma.runMetric.findMany({
            where: {
                runId: dup.runId,
                step: dup.step
            },
            orderBy: {
                timestamp: 'desc'
            }
        });

        // 保留第一条（最新的），删除其余的
        const toDelete = metrics.slice(1).map(m => m.id);

        if (toDelete.length > 0) {
            await prisma.runMetric.deleteMany({
                where: {
                    id: {
                        in: toDelete
                    }
                }
            });
            totalDeleted += toDelete.length;
            console.log(`  删除了 ${toDelete.length} 条重复记录 (runId=${dup.runId}, step=${dup.step})`);
        }
    }

    console.log(`\n清理完成！共删除 ${totalDeleted} 条重复记录`);

    // 验证
    const remaining = await prisma.$queryRaw<Array<{ runId: string; step: number; count: bigint }>>`
        SELECT runId, step, COUNT(*) as count 
        FROM RunMetric 
        GROUP BY runId, step 
        HAVING COUNT(*) > 1
    `;

    if (remaining.length === 0) {
        console.log('✅ 验证通过：没有剩余的重复记录');
    } else {
        console.log(`❌ 警告：仍有 ${remaining.length} 个重复组合`);
    }

    await prisma.$disconnect();
}

cleanupDuplicateMetrics().catch(console.error);
