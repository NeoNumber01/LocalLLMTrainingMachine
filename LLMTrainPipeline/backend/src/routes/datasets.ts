import { FastifyInstance } from 'fastify';
import { getProviderFactory } from '../providers/factory.js';
import { getConfig } from '../config/index.js';
import { DatasetResponse, DatasetPreview } from '../types/index.js';
import { prisma } from '../db/prisma-client.js';

export async function datasetsRoutes(fastify: FastifyInstance) {

    // GET /api/datasets - Get all datasets
    fastify.get('/', {
        schema: {
            tags: ['Datasets'],
            summary: 'Get all datasets',
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

    // GET /api/datasets/:id - Get dataset details
    fastify.get<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Datasets'],
            summary: 'Get dataset details',
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

    // GET /api/datasets/:id/preview - Preview dataset samples
    fastify.get<{ Params: { id: string } }>('/:id/preview', {
        schema: {
            tags: ['Datasets'],
            summary: 'Preview dataset samples',
        },
    }, async (request, reply) => {
        const dataset = await prisma.dataset.findUnique({
            where: { id: request.params.id },
        });

        if (!dataset) {
            return reply.status(404).send({ error: 'Dataset not found' });
        }

        // Read actual dataset file
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

            // Read first 1000 lines of JSONL file for analysis
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

                    // Collect schema fields
                    Object.keys(obj).forEach(key => schemaFields.add(key));

                    // Collect samples (max 5)
                    if (samples.length < maxSamplesToShow) {
                        // Support multiple formats - extended field list
                        let prompt = '';
                        let completion = '';
                        let detectedFormat = 'unknown';

                        // === Conversation format ===
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
                        // === Instruction format ===
                        else if (obj.instruction !== undefined) {
                            detectedFormat = 'alpaca/instruction';
                            const input = obj.input ? `\n\nInput: ${obj.input}` : '';
                            prompt = String(obj.instruction) + input;
                            // Try multiple output fields
                            completion = String(obj.output || obj.response || obj.answer || obj.reference || '');
                        }
                        // === Code generation format ===
                        else if (obj.prompt !== undefined) {
                            // TACO/HumanEval/CodeContests and other code datasets
                            detectedFormat = 'code/prompt';
                            prompt = String(obj.prompt);
                            if (obj.starter_code) {
                                prompt += `\n\nStarter code:\n${obj.starter_code}`;
                            }
                            // Try multiple code fields
                            completion = String(obj.code || obj.reference || obj.solution ||
                                obj.canonical_solution || obj.completion || '');
                            // If solutions is an array
                            if (!completion && Array.isArray(obj.solutions) && obj.solutions.length > 0) {
                                completion = String(obj.solutions[0]);
                            }
                        }
                        // === Q&A format ===
                        else if (obj.question !== undefined) {
                            detectedFormat = 'qa';
                            if (obj.context) {
                                prompt = `Context: ${obj.context}\n\nQuestion: ${obj.question}`;
                            } else {
                                prompt = String(obj.question);
                            }
                            // Handle answers which may be an array
                            if (Array.isArray(obj.answers) && obj.answers.length > 0) {
                                const ans = obj.answers[0];
                                completion = String(typeof ans === 'object' ? ans.text : ans);
                            } else {
                                completion = String(obj.answer || obj.response || '');
                            }
                        }
                        // === Summarization format ===
                        else if (obj.document !== undefined || obj.article !== undefined) {
                            detectedFormat = 'summarization';
                            prompt = String(obj.document || obj.article || obj.text || '');
                            completion = String(obj.summary || obj.highlights || obj.abstract || '');
                        }
                        // === Translation format ===
                        else if (obj.source !== undefined && obj.target !== undefined) {
                            detectedFormat = 'translation';
                            prompt = String(obj.source);
                            completion = String(obj.target);
                        }
                        // === Plain text format (fallback) ===
                        else if (obj.text !== undefined) {
                            detectedFormat = 'text';
                            prompt = '[Text sample]';
                            completion = String(obj.text);
                        }
                        // === ChatML individual fields format ===
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

                    // Accumulate length
                    totalLength += trimmed.length;
                    lineCount++;
                } catch (parseErr) {
                    // Skip lines that fail to parse
                    emptyRows++;
                }
            }

            // Calculate statistics
            const avgLength = lineCount > 0 ? Math.round(totalLength / lineCount) : 0;

            // Generate schema
            const schema = Array.from(schemaFields).map(field => ({
                field,
                valid: true,
            }));

            const preview: DatasetPreview = {
                schema,
                stats: {
                    totalTokens: `~${Math.round(totalLength / 4)}`, // Rough token count estimate
                    avgLength,
                    duplicates: '0%', // Requires more complex logic to detect
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

    // POST /api/datasets/import - Import dataset
    fastify.post('/import', {
        schema: {
            tags: ['Datasets'],
            summary: 'Import dataset',
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

        // Calculate file size and sample count
        const fs = await import('fs');
        const pathModule = await import('path');
        let samples = 0;
        let size = '0 B';

        if (fs.existsSync(body.path)) {
            const stats = fs.statSync(body.path);
            // Calculate size
            const bytes = stats.size;
            if (bytes < 1024) size = `${bytes} B`;
            else if (bytes < 1024 * 1024) size = `${(bytes / 1024).toFixed(1)} KB`;
            else if (bytes < 1024 * 1024 * 1024) size = `${(bytes / 1024 / 1024).toFixed(1)} MB`;
            else size = `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;

            // Calculate sample count
            try {
                if (body.path.endsWith('.jsonl')) {
                    // JSONL: Use streaming read to count lines, avoiding memory overflow for large files
                    const fileStream = fs.createReadStream(body.path);
                    const rl = (await import('readline')).createInterface({
                        input: fileStream,
                        crlfDelay: Infinity,
                    });

                    for await (const line of rl) {
                        if (line.trim()) samples++;
                    }
                } else if (body.path.endsWith('.json')) {
                    // JSON: Try to parse as array
                    // If file is too large, cannot directly JSON.parse, here we make a simple attempt
                    // For very large JSON array files, it's usually recommended to convert to JSONL
                    if (bytes < 50 * 1024 * 1024) { // < 50MB
                        const content = fs.readFileSync(body.path, 'utf-8');
                        const json = JSON.parse(content);
                        if (Array.isArray(json)) {
                            samples = json.length;
                        }
                    } else {
                        // Large file, try streaming parse or assume it's a JSONL format .json file
                        // Here we do a simple fallback: count by lines (assuming well-formatted JSON array with one item per line, or it's actually JSONL)
                        const fileStream = fs.createReadStream(body.path);
                        const rl = (await import('readline')).createInterface({
                            input: fileStream,
                            crlfDelay: Infinity,
                        });

                        let lineCount = 0;
                        for await (const line of rl) {
                            if (line.trim()) lineCount++;
                        }
                        // Rough estimate: if it's a formatted JSON array `[\n  {...},\n  {...}\n]`
                        // Line count will be much more than sample count. Here we are conservative, if not JSONL, don't set samples or set to 0
                        // Let user know it might be inaccurate. But if it's a .json mislabeled as JSONL, then line count is correct.
                        // For simplicity, we assume large .json files are mostly mislabeled JSONL, or we cannot efficiently count here
                        samples = lineCount;
                    }
                } else if (body.path.endsWith('.parquet')) {
                    // Parquet does not support reading row count yet
                    samples = 0;
                }
            } catch (e) {
                console.error('Failed to count samples:', e);
                // Don't interrupt import on failure, samples defaults to 0
            }
        }

        // Create dataset record
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

    // POST /api/datasets/rescan - Rescan datasets directory
    fastify.post('/rescan', {
        schema: {
            tags: ['Datasets'],
            summary: 'Rescan datasets directory',
        },
    }, async (request, reply) => {
        const config = getConfig();
        const factory = getProviderFactory(config);
        const scanner = factory.getScanner();

        // P2-FIX: Read dynamic path from Settings, fallback to default config
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

        // Scan both training datasets and evaluation datasets directories
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

    // DELETE /api/datasets/:id - Delete dataset record (does not delete local files)
    fastify.delete<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Datasets'],
            summary: 'Delete dataset record (does not delete local files)',
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
