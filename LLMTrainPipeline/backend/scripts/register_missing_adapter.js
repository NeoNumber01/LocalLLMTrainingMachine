// Quick fix script to register missing LoRA adapter for run_12949
import { PrismaClient } from '@prisma/client';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const prisma = new PrismaClient();

async function main() {
    const adapterName = 'train efficient split 6.7B-adapter';
    const adapterDir = path.resolve(__dirname, '../storage/runs/run_12949');

    console.log('Registering missing adapter:', adapterName);
    console.log('Path:', adapterDir);

    try {
        const result = await prisma.adapter.upsert({
            where: { name: adapterName },
            create: {
                name: adapterName,
                path: adapterDir,
                baseModel: 'deepseek-coder-6.7b-instruct',
                trainDataset: 'train_split',
                rank: 16,
                alpha: 32,
                status: 'success',
            },
            update: {
                status: 'success',
                path: adapterDir,
            },
        });

        console.log('✅ Adapter registered successfully!');
        console.log('ID:', result.id);
        console.log('Name:', result.name);
        console.log('Base Model:', result.baseModel);
    } catch (error) {
        console.error('❌ Error registering adapter:', error);
    } finally {
        await prisma.$disconnect();
    }
}

main();
