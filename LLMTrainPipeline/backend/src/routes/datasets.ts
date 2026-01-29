import { FastifyInstance } from 'fastify';
import { getProviderFactory } from '../providers/factory.js';
import { getConfig } from '../config/index.js';
import { DatasetResponse, DatasetPreview } from '../types/index.js';
import { prisma } from '../db/prisma-client.js';

export async function datasetsRoutes(fastify: FastifyInstance) {

    // GET /api/datasets - 获取所有数据集
    fastify.get('/', {
        schema: {
            tags: ['Datasets'],
            summary: '获取所有数据集',
        },
    }, async (request, reply) => {
        const datasets = await prisma.dataset.findMany({
            orderBy: { updatedAt: 'desc' },
        });

        const response: DatasetResponse[] = datasets.map(d => ({
            id: d.id,
            name: d.name,
            version: d.version,
            type: d.type as any,
            status: d.status === 'active' ? 'Active' :
                d.status === 'ready' ? 'Ready' :
                    d.status === 'corrupt' ? 'Corrupt' : 'Processing',
            samples: d.samples,
            format: d.format as any,
            size: d.size,
            path: d.path,
            hash: d.hash,
        }));

        return response;
    });

    // GET /api/datasets/:id - 获取数据集详情
    fastify.get<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Datasets'],
            summary: '获取数据集详情',
        },
    }, async (request, reply) => {
        const dataset = await prisma.dataset.findUnique({
            where: { id: request.params.id },
        });

        if (!dataset) {
            return reply.status(404).send({ error: 'Dataset not found' });
        }

        return {
            id: dataset.id,
            name: dataset.name,
            version: dataset.version,
            type: dataset.type,
            status: dataset.status,
            samples: dataset.samples,
            format: dataset.format,
            size: dataset.size,
            path: dataset.path,
            hash: dataset.hash,
        };
    });

    // GET /api/datasets/:id/preview - 预览数据集样本
    fastify.get<{ Params: { id: string } }>('/:id/preview', {
        schema: {
            tags: ['Datasets'],
            summary: '预览数据集样本',
        },
    }, async (request, reply) => {
        const dataset = await prisma.dataset.findUnique({
            where: { id: request.params.id },
        });

        if (!dataset) {
            return reply.status(404).send({ error: 'Dataset not found' });
        }

        // 读取真实数据集文件
        const fs = await import('fs');
        const path = await import('path');
        const readline = await import('readline');

        const datasetPath = dataset.path;

        if (!fs.existsSync(datasetPath)) {
            return reply.status(404).send({ error: `Dataset file not found: ${datasetPath}` });
        }

        try {
            const samples: Array<{ prompt: string; completion: string }> = [];
            const schemaFields = new Set<string>();
            let totalLength = 0;
            let lineCount = 0;
            let emptyRows = 0;

            // 读取 JSONL 文件前 1000 行进行分析
            const fileStream = fs.createReadStream(datasetPath);
            const rl = readline.createInterface({
                input: fileStream,
                crlfDelay: Infinity,
            });

            const maxLinesToRead = 1000;
            const maxSamplesToShow = 5;

            for await (const line of rl) {
                if (lineCount >= maxLinesToRead) {
                    rl.close();
                    break;
                }

                const trimmed = line.trim();
                if (!trimmed) {
                    emptyRows++;
                    continue;
                }

                try {
                    const obj = JSON.parse(trimmed);

                    // 收集 schema 字段
                    Object.keys(obj).forEach(key => schemaFields.add(key));

                    // 收集样本（最多 5 个）
                    if (samples.length < maxSamplesToShow) {
                        // 支持多种格式 - 拓展的字段列表
                        let prompt = '';
                        let completion = '';
                        let detectedFormat = 'unknown';

                        // === 对话格式 ===
                        if (obj.messages && Array.isArray(obj.messages)) {
                            detectedFormat = 'messages';
                            const userMsg = obj.messages.find((m: any) => m.role === 'user');
                            const assistantMsg = obj.messages.find((m: any) => m.role === 'assistant');
                            if (userMsg) prompt = String(userMsg.content || '');
                            if (assistantMsg) completion = String(assistantMsg.content || '');
                        } else if (obj.conversations && Array.isArray(obj.conversations)) {
                            detectedFormat = 'sharegpt';
                            const humanConv = obj.conversations.find((c: any) =>
                                c.from === 'human' || c.from === 'user' || c.role === 'user');
                            const gptConv = obj.conversations.find((c: any) =>
                                c.from === 'gpt' || c.from === 'assistant' || c.role === 'assistant');
                            if (humanConv) prompt = String(humanConv.value || humanConv.content || '');
                            if (gptConv) completion = String(gptConv.value || gptConv.content || '');
                        }
                        // === 指令格式 ===
                        else if (obj.instruction !== undefined) {
                            detectedFormat = 'alpaca/instruction';
                            const input = obj.input ? `\n\nInput: ${obj.input}` : '';
                            prompt = String(obj.instruction) + input;
                            // 尝试多个输出字段
                            completion = String(obj.output || obj.response || obj.answer || obj.reference || '');
                        }
                        // === 代码生成格式 ===
                        else if (obj.prompt !== undefined) {
                            // TACO/HumanEval/CodeContests 等代码类数据集
                            detectedFormat = 'code/prompt';
                            prompt = String(obj.prompt);
                            if (obj.starter_code) {
                                prompt += `\n\nStarter code:\n${obj.starter_code}`;
                            }
                            // 尝试多个代码字段
                            completion = String(obj.code || obj.reference || obj.solution ||
                                obj.canonical_solution || obj.completion || '');
                            // 如果 solutions 是数组
                            if (!completion && Array.isArray(obj.solutions) && obj.solutions.length > 0) {
                                completion = String(obj.solutions[0]);
                            }
                        }
                        // === 问答格式 ===
                        else if (obj.question !== undefined) {
                            detectedFormat = 'qa';
                            if (obj.context) {
                                prompt = `Context: ${obj.context}\n\nQuestion: ${obj.question}`;
                            } else {
                                prompt = String(obj.question);
                            }
                            // 处理 answers 可能是数组
                            if (Array.isArray(obj.answers) && obj.answers.length > 0) {
                                const ans = obj.answers[0];
                                completion = String(typeof ans === 'object' ? ans.text : ans);
                            } else {
                                completion = String(obj.answer || obj.response || '');
                            }
                        }
                        // === 摘要格式 ===
                        else if (obj.document !== undefined || obj.article !== undefined) {
                            detectedFormat = 'summarization';
                            prompt = String(obj.document || obj.article || obj.text || '');
                            completion = String(obj.summary || obj.highlights || obj.abstract || '');
                        }
                        // === 翻译格式 ===
                        else if (obj.source !== undefined && obj.target !== undefined) {
                            detectedFormat = 'translation';
                            prompt = String(obj.source);
                            completion = String(obj.target);
                        }
                        // === 纯文本格式 (兜底) ===
                        else if (obj.text !== undefined) {
                            detectedFormat = 'text';
                            prompt = '[Text sample]';
                            completion = String(obj.text);
                        }
                        // === ChatML 独立字段格式 ===
                        else if (obj.user !== undefined && obj.assistant !== undefined) {
                            detectedFormat = 'chatml';
                            prompt = String(obj.user);
                            completion = String(obj.assistant);
                        }

                        if (prompt || completion) {
                            samples.push({
                                prompt: prompt.slice(0, 200) + (prompt.length > 200 ? '...' : ''),
                                completion: completion.slice(0, 200) + (completion.length > 200 ? '...' : ''),
                            });
                        }
                    }

                    // 累计长度
                    totalLength += trimmed.length;
                    lineCount++;
                } catch (parseErr) {
                    // 跳过解析失败的行
                    emptyRows++;
                }
            }

            // 计算统计信息
            const avgLength = lineCount > 0 ? Math.round(totalLength / lineCount) : 0;

            // 生成 schema
            const schema = Array.from(schemaFields).map(field => ({
                field,
                valid: true,
            }));

            const preview: DatasetPreview = {
                schema,
                stats: {
                    totalTokens: `~${Math.round(totalLength / 4)}`, // 粗略估计 token 数
                    avgLength,
                    duplicates: '0%', // 需要更复杂的逻辑来检测
                    emptyRows,
                },
                samples,
            };

            return preview;
        } catch (err: any) {
            console.error('Error reading dataset:', err);
            return reply.status(500).send({ error: `Failed to read dataset: ${err.message}` });
        }
    });

    // POST /api/datasets/import - 导入数据集
    fastify.post('/import', {
        schema: {
            tags: ['Datasets'],
            summary: '导入数据集',
            body: {
                type: 'object',
                properties: {
                    path: { type: 'string' },
                    name: { type: 'string' },
                    type: { type: 'string', enum: ['Train', 'Eval'] },
                },
            },
        },
    }, async (request, reply) => {
        const body = request.body as { path: string; name?: string; type?: string };

        // 计算文件大小和样本数量
        const fs = await import('fs');
        const pathModule = await import('path');
        let samples = 0;
        let size = '0 B';

        if (fs.existsSync(body.path)) {
            const stats = fs.statSync(body.path);
            // 计算大小
            const bytes = stats.size;
            if (bytes < 1024) size = `${bytes} B`;
            else if (bytes < 1024 * 1024) size = `${(bytes / 1024).toFixed(1)} KB`;
            else if (bytes < 1024 * 1024 * 1024) size = `${(bytes / 1024 / 1024).toFixed(1)} MB`;
            else size = `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;

            // 计算样本数量
            try {
                if (body.path.endsWith('.jsonl')) {
                    // JSONL: 使用流式读取计算行数，避免大文件内存溢出
                    const fileStream = fs.createReadStream(body.path);
                    const rl = (await import('readline')).createInterface({
                        input: fileStream,
                        crlfDelay: Infinity,
                    });

                    for await (const line of rl) {
                        if (line.trim()) samples++;
                    }
                } else if (body.path.endsWith('.json')) {
                    // JSON: 尝试解析为数组
                    // 如果文件太大，可能无法直接 JSON.parse，这里做一个简单的尝试
                    // 对于非常大的 JSON 数组文件，通常建议转换为 JSONL
                    if (bytes < 50 * 1024 * 1024) { // < 50MB
                        const content = fs.readFileSync(body.path, 'utf-8');
                        const json = JSON.parse(content);
                        if (Array.isArray(json)) {
                            samples = json.length;
                        }
                    } else {
                        // 大文件，尝试流式解析或假设是 JSONL 格式的 .json 文件
                        // 这里做个简单的回退：按行计算 (假设格式化良好的 JSON 数组每项一行，或者它其实是 JSONL)
                        const fileStream = fs.createReadStream(body.path);
                        const rl = (await import('readline')).createInterface({
                            input: fileStream,
                            crlfDelay: Infinity,
                        });

                        let lineCount = 0;
                        for await (const line of rl) {
                            if (line.trim()) lineCount++;
                        }
                        // 粗略估计：如果是格式化的 JSON 数组 `[\n  {...},\n  {...}\n]`
                        // 行数会比样本数多很多。这里保守起见，如果不是 JSONL，不设 samples 或设为 0
                        // 让用户知道可能不准确。但如果是误命名为 .json 的 JSONL，则行数是对的。
                        // 简单起见，我们假设大 .json 文件多半是误命名的 JSONL，或者这里无法高效统计
                        samples = lineCount;
                    }
                } else if (body.path.endsWith('.parquet')) {
                    // Parquet 暂不支持读取行数
                    samples = 0;
                }
            } catch (e) {
                console.error('Failed to count samples:', e);
                // 失败时不中断导入，samples 默认为 0
            }
        }

        // 创建数据集记录
        const dataset = await prisma.dataset.create({
            data: {
                name: body.name || pathModule.basename(body.path) || 'imported',
                path: body.path,
                version: 'v1.0.0',
                type: body.type || 'Train',
                status: 'ready',
                samples,
                format: body.path.endsWith('.parquet') ? 'Parquet' : 'JSONL',
                size,
                hash: 'pending',
            },
        });

        return { id: dataset.id, status: 'ready', samples };
    });

    // POST /api/datasets/rescan - 重新扫描数据集目录
    fastify.post('/rescan', {
        schema: {
            tags: ['Datasets'],
            summary: '重新扫描数据集目录',
        },
    }, async (request, reply) => {
        const config = getConfig();
        const factory = getProviderFactory(config);
        const scanner = factory.getScanner();

        // P2-FIX: 从 Settings 读取动态路径，fallback 到默认配置
        let datasetsDir = config.storage.trainDatasetsDir;
        try {
            const watchFoldersSetting = await prisma.setting.findUnique({
                where: { key: 'watchFolders' }
            });
            if (watchFoldersSetting) {
                const watchFolders = JSON.parse(watchFoldersSetting.valueJson);
                if (watchFolders?.datasets) {
                    datasetsDir = watchFolders.datasets;
                }
            }
        } catch (e) {
            console.warn('[Datasets] Failed to read watchFolders setting:', e);
        }

        // 同时扫描训练数据集和评估数据集目录
        const [trainResult, evalResult] = await Promise.all([
            scanner.scanDatasets(datasetsDir, 'Train'),
            scanner.scanDatasets(config.storage.evalDatasetsDir, 'Eval'),
        ]);

        return {
            success: true,
            added: trainResult.added + evalResult.added,
            updated: trainResult.updated + evalResult.updated,
            removed: trainResult.removed + evalResult.removed,
            errors: [...(trainResult.errors || []), ...(evalResult.errors || [])],
        };
    });

    // DELETE /api/datasets/:id - 删除数据集记录（不删除本地文件）
    fastify.delete<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Datasets'],
            summary: '删除数据集记录（不删除本地文件）',
        },
    }, async (request, reply) => {
        const dataset = await prisma.dataset.findUnique({
            where: { id: request.params.id },
        });

        if (!dataset) {
            return reply.status(404).send({ error: 'Dataset not found' });
        }

        try {
            await prisma.dataset.delete({
                where: { id: request.params.id },
            });

            return { success: true, message: 'Dataset record deleted (local file preserved)' };
        } catch (err: any) {
            // Handle foreign key constraint error
            if (err.code === 'P2003' || err.message?.includes('Foreign key constraint')) {
                return reply.status(400).send({
                    error: 'Cannot delete dataset: it is currently being used by one or more training runs. Please delete those runs first.'
                });
            }
            console.error('Error deleting dataset:', err);
            return reply.status(500).send({ error: 'Failed to delete dataset' });
        }
    });
}
