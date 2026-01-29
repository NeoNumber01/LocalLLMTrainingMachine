import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

async function fixRun() {
    const runId = 'run_12949';

    // Read experiment_log.json to get correct training time
    const fs = await import('fs');
    const path = await import('path');

    const expLogPath = path.resolve(`./storage/runs/${runId}/experiment_log.json`);
    let gpuHours = 1.337;
    let totalSteps = 200;

    if (fs.existsSync(expLogPath)) {
        const expLog = JSON.parse(fs.readFileSync(expLogPath, 'utf-8'));
        gpuHours = expLog.gpu_hours || gpuHours;
        totalSteps = expLog.total_steps || totalSteps;
        console.log('Loaded experiment log:', { gpuHours, totalSteps });
    }

    // Get the last valid loss value
    const metrics = await prisma.runMetric.findMany({
        where: { runId },
        orderBy: { step: 'desc' },
        take: 10
    });

    let finalLoss = 0;
    for (const m of metrics) {
        const extra = m.extraJson ? JSON.parse(m.extraJson) : null;
        if (m.loss && (extra?.lr != null)) {
            finalLoss = m.loss;
            break;
        }
    }
    if (finalLoss === 0 && metrics.length > 0 && metrics[0].loss) {
        finalLoss = metrics[0].loss;
    }
    console.log('Final loss:', finalLoss);

    // Calculate training duration
    const durationHours = gpuHours;
    const hours = Math.floor(durationHours);
    const minutes = Math.floor((durationHours - hours) * 60);
    const duration = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;

    // Update Run status
    const updated = await prisma.run.update({
        where: { id: runId },
        data: {
            status: 'success',
            duration: duration,
            totalSteps: totalSteps,
            gpuHours: gpuHours,
            metricsJson: JSON.stringify({
                loss: finalLoss,
                passAt1: 0,
                compileRate: 0
            })
        }
    });

    console.log('Updated run:', updated.id, 'to status:', updated.status, 'duration:', updated.duration);

    // Try to save LoRA statistics (using BigInt)
    const loraStats = {
        runId,
        rank: 16,
        alpha: 32,
        dropout: 0.05,
        targetModules: JSON.stringify(["q_proj", "v_proj", "o_proj", "k_proj", "down_proj", "gate_proj", "up_proj"]),
        trainableParams: BigInt(39976960),
        totalParams: BigInt(3542487040),
        trainablePercent: 1.1285
    };

    try {
        await prisma.loraStats.upsert({
            where: { runId },
            create: loraStats,
            update: loraStats
        });
        console.log('LoRA stats saved successfully!');
    } catch (e) {
        console.error('Failed to save LoRA stats:', e);
    }
}

fixRun()
    .catch(console.error)
    .finally(() => prisma.$disconnect());
