// Cleanup duplicate data in RunMetric table
// Keep only the latest record for each (runId, step) combination

import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function cleanupDuplicateMetrics() {
    console.log('Starting cleanup of duplicate RunMetric data...');

    // Find all duplicate (runId, step) combinations
    const duplicates = await prisma.$queryRaw<Array<{ runId: string; step: number; count: bigint }>>`
        SELECT runId, step, COUNT(*) as count 
        FROM RunMetric 
        GROUP BY runId, step 
        HAVING COUNT(*) > 1
    `;

    console.log(`Found ${duplicates.length} duplicate (runId, step) combinations`);

    let totalDeleted = 0;

    for (const dup of duplicates) {
        // Get all records for this combination, sorted by timestamp descending
        const metrics = await prisma.runMetric.findMany({
            where: {
                runId: dup.runId,
                step: dup.step
            },
            orderBy: {
                timestamp: 'desc'
            }
        });

        // Keep the first one (newest), delete the rest
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
            console.log(`  Deleted ${toDelete.length} duplicate records (runId=${dup.runId}, step=${dup.step})`);
        }
    }

    console.log(`\nCleanup complete! Deleted ${totalDeleted} duplicate records`);

    // Verify
    const remaining = await prisma.$queryRaw<Array<{ runId: string; step: number; count: bigint }>>`
        SELECT runId, step, COUNT(*) as count 
        FROM RunMetric 
        GROUP BY runId, step 
        HAVING COUNT(*) > 1
    `;

    if (remaining.length === 0) {
        console.log('✅ Verification passed: No remaining duplicate records');
    } else {
        console.log(`❌ Warning: Still have ${remaining.length} duplicate combinations`);
    }

    await prisma.$disconnect();
}

cleanupDuplicateMetrics().catch(console.error);
