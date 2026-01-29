import fs from 'fs';
import path from 'path';
import { PrismaClient } from '@prisma/client';
import { Scanner, ScanResult } from '../interfaces.js';

const prisma = new PrismaClient();

export class FileScanner implements Scanner {

    async scanModels(directory: string): Promise<ScanResult> {
        const result: ScanResult = { added: 0, updated: 0, removed: 0, errors: [] };

        if (!fs.existsSync(directory)) {
            result.errors.push(`Directory not found: ${directory}`);
            return result;
        }

        try {
            const entries = fs.readdirSync(directory, { withFileTypes: true });
            const existingModels = await prisma.model.findMany();
            const existingPaths = new Set(existingModels.map(m => m.path));
            const scannedPaths = new Set<string>();

            for (const entry of entries) {
                if (!entry.isDirectory()) continue;

                const modelPath = path.join(directory, entry.name);
                scannedPaths.add(modelPath);

                // 检查是否是有效的模型目录（包含 config.json 或 *.safetensors）
                const files = fs.readdirSync(modelPath);
                const hasConfig = files.some(f => f === 'config.json');
                const hasWeights = files.some(f => f.endsWith('.safetensors') || f.endsWith('.bin'));

                if (!hasConfig && !hasWeights) {
                    continue; // 不是有效的模型目录
                }

                const stats = fs.statSync(modelPath);
                const existing = existingModels.find(m => m.path === modelPath);

                if (existing) {
                    // 更新现有记录
                    await prisma.model.update({
                        where: { id: existing.id },
                        data: {
                            status: 'valid',
                            updatedAt: new Date(),
                        },
                    });
                    result.updated++;
                } else {
                    // 创建新记录
                    await prisma.model.create({
                        data: {
                            name: entry.name,
                            path: modelPath,
                            backend: 'transformers',
                            source: 'Local',
                            quantization: 'None',
                            params: 'Unknown',
                            status: 'valid',
                        },
                    });
                    result.added++;
                }
            }

            // 标记不存在的模型为 error
            for (const existing of existingModels) {
                if (!scannedPaths.has(existing.path)) {
                    await prisma.model.update({
                        where: { id: existing.id },
                        data: { status: 'error' },
                    });
                    result.removed++;
                }
            }
        } catch (error) {
            result.errors.push(`Scan error: ${error}`);
        }

        return result;
    }

    async scanDatasets(directory: string, datasetType: 'Train' | 'Eval' = 'Train'): Promise<ScanResult> {
        const result: ScanResult = { added: 0, updated: 0, removed: 0, errors: [] };

        if (!fs.existsSync(directory)) {
            // 目录不存在时创建它而不是报错
            try {
                fs.mkdirSync(directory, { recursive: true });
            } catch (e) {
                result.errors.push(`Could not create directory: ${directory}`);
            }
            return result;
        }

        try {
            const files = fs.readdirSync(directory);
            const existingDatasets = await prisma.dataset.findMany({ where: { type: datasetType } });
            const existingPaths = new Set(existingDatasets.map(d => d.path));
            const scannedPaths = new Set<string>();

            for (const file of files) {
                const filePath = path.join(directory, file);
                const stats = fs.statSync(filePath);

                if (!stats.isFile()) continue;
                if (!file.endsWith('.jsonl') && !file.endsWith('.parquet')) continue;

                const name = path.parse(file).name;
                scannedPaths.add(filePath);

                const format = file.endsWith('.parquet') ? 'Parquet' : 'JSONL';
                const size = this.formatSize(stats.size);

                // 尝试计算样本数量（仅针对 JSONL）
                let samples = 0;
                if (format === 'JSONL') {
                    try {
                        const content = fs.readFileSync(filePath, 'utf-8');
                        samples = content.split('\n').filter(line => line.trim()).length;
                    } catch { }
                }

                const existing = existingDatasets.find(d => d.path === filePath);

                if (existing) {
                    await prisma.dataset.update({
                        where: { id: existing.id },
                        data: {
                            status: 'ready',
                            size,
                            samples,
                            updatedAt: new Date(),
                        },
                    });
                    result.updated++;
                } else {
                    await prisma.dataset.create({
                        data: {
                            name,
                            path: filePath,
                            version: 'v1.0.0',
                            type: datasetType,
                            status: 'ready',
                            samples,
                            format,
                            size,
                            hash: 'pending',
                        },
                    });
                    result.added++;
                }
            }

            // 标记不存在的数据集
            for (const existing of existingDatasets) {
                if (!scannedPaths.has(existing.path)) {
                    // 检查文件是否确实不存在
                    if (!fs.existsSync(existing.path)) {
                        await prisma.dataset.update({
                            where: { id: existing.id },
                            data: { status: 'corrupt' },
                        });
                        result.removed++;
                    }
                }
            }
        } catch (error) {
            result.errors.push(`Scan error: ${error}`);
        }

        return result;
    }

    async scanAdapters(directory: string): Promise<ScanResult> {
        const result: ScanResult = { added: 0, updated: 0, removed: 0, errors: [] };

        if (!fs.existsSync(directory)) {
            result.errors.push(`Directory not found: ${directory}`);
            return result;
        }

        try {
            const entries = fs.readdirSync(directory, { withFileTypes: true });
            const existingAdapters = await prisma.adapter.findMany();
            const existingPaths = new Set(existingAdapters.map(a => a.path));
            const scannedPaths = new Set<string>();

            for (const entry of entries) {
                if (!entry.isDirectory()) continue;

                const adapterPath = path.join(directory, entry.name);
                scannedPaths.add(adapterPath);

                // 检查是否包含 adapter_config.json 或 adapter_model.bin
                const files = fs.readdirSync(adapterPath);
                const hasAdapterConfig = files.some(f => f === 'adapter_config.json');

                if (!hasAdapterConfig) continue;

                const existing = existingAdapters.find(a => a.path === adapterPath);

                if (existing) {
                    await prisma.adapter.update({
                        where: { id: existing.id },
                        data: { status: 'success' },
                    });
                    result.updated++;
                } else {
                    await prisma.adapter.create({
                        data: {
                            name: entry.name,
                            path: adapterPath,
                            baseModel: 'Unknown',
                            trainDataset: 'Unknown',
                            rank: 16,
                            alpha: 32,
                            status: 'success',
                        },
                    });
                    result.added++;
                }
            }

            // 标记不存在的适配器
            for (const existing of existingAdapters) {
                if (existing.path && !scannedPaths.has(existing.path)) {
                    await prisma.adapter.update({
                        where: { id: existing.id },
                        data: { status: 'warning' },
                    });
                    result.removed++;
                }
            }
        } catch (error) {
            result.errors.push(`Scan error: ${error}`);
        }

        return result;
    }

    private formatSize(bytes: number): string {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
        return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
    }
}
