
import { FastifyInstance } from 'fastify';
import { InferRequest } from '../types/index.js';
import { modelServer } from '../services/model-server.js';
import { prisma } from '../db/prisma-client.js';

export async function playgroundRoutes(fastify: FastifyInstance) {

    // POST /api/playground/infer - 推理请求 (Streaming)
    fastify.post('/infer', {
        schema: {
            tags: ['Playground'],
            summary: '使用本地模型进行推理 (SSE Stream)',
            body: {
                type: 'object',
                required: ['modelId', 'systemPrompt', 'messages'],
                properties: {
                    modelId: { type: 'string' },
                    adapterId: { type: 'string' },
                    systemPrompt: { type: 'string' },
                    messages: {
                        type: 'array',
                        items: {
                            type: 'object',
                            properties: {
                                role: { type: 'string', enum: ['user', 'assistant'] },
                                content: { type: 'string' },
                            },
                        },
                    },
                    temperature: { type: 'number' },
                    maxTokens: { type: 'number' },
                    quantization: { type: 'string', enum: ['4bit', '8bit', 'none'] },
                },
            },
        },
    }, async (request, reply) => {
        const body = request.body as InferRequest;

        // 1. 获取模型信息
        const model = await prisma.model.findUnique({
            where: { id: body.modelId },
        });

        if (!model) {
            return reply.status(400).send({ error: 'Model not found' });
        }

        // 2. 获取 adapter 信息（如果有）
        let adapterPath: string | undefined;
        if (body.adapterId) {
            const adapter = await prisma.adapter.findUnique({
                where: { id: body.adapterId },
            });
            if (adapter?.path) {
                adapterPath = adapter.path;
            }
        }

        console.log(`[Playground] Inference request: ${model.name}`);

        // 3. 设置 SSE 响应头
        reply.raw.setHeader('Content-Type', 'text/event-stream');
        reply.raw.setHeader('Cache-Control', 'no-cache');
        reply.raw.setHeader('Connection', 'keep-alive');

        // CORS 处理
        const origin = request.headers.origin || '*';
        reply.raw.setHeader('Access-Control-Allow-Origin', origin);
        reply.raw.setHeader('Access-Control-Allow-Credentials', 'true');

        // 发送初始化头部
        reply.raw.flushHeaders();
        reply.raw.write(': keeping connection alive\n\n');

        try {
            // 4. 加载模型 (如果需要)
            // 这可能会花费一些时间，所以我们先发送了 keep-alive
            // 模型服务那边会处理锁和重复加载检查
            await modelServer.loadModel(model.path, adapterPath, body.quantization);


            // 5. 准备对话消息
            const messages = [
                { role: 'system', content: body.systemPrompt },
                ...body.messages
            ];

            // 6. 发起流式请求
            const stream = await modelServer.chatStream({
                messages,
                max_tokens: body.maxTokens || 512,
                temperature: body.temperature || 0.7
            });

            // 7. Manually pipe stream to response with immediate flushing
            // This avoids buffering issues with stream.pipe()
            stream.on('data', (chunk: Buffer) => {
                reply.raw.write(chunk);
                // Force flush if available (for Node.js http response)
                if (typeof (reply.raw as any).flush === 'function') {
                    (reply.raw as any).flush();
                }
            });

            // 等待流结束
            await new Promise((resolve, reject) => {
                stream.on('end', resolve);
                stream.on('error', (err: Error) => {
                    console.error('Stream error:', err);
                    resolve(err); // Resolve anyway to not leave hanging
                });
            });

            // 关键修复：正确关闭 SSE 连接，让前端知道流已结束
            reply.raw.end();

        } catch (e: any) {
            console.error('Inference Error:', e);
            reply.raw.write(`data: ${JSON.stringify({ error: e.message || 'Inference failed' })}\n\n`);
            reply.raw.end();
        }

        return reply;
    });

    // POST /api/playground/unload - 卸载模型
    fastify.post('/unload', {
        schema: {
            tags: ['Playground'],
            summary: '卸载模型释放显存',
        },
    }, async (request, reply) => {
        await modelServer.unloadModel();
        return { status: 'unloaded' };
    });

    // GET /api/playground/status - 检查推理服务状态和已加载模型
    fastify.get('/status', {
        schema: {
            tags: ['Playground'],
            summary: '检查推理服务状态和已加载模型信息',
        },
    }, async (request, reply) => {
        try {
            const status = await modelServer.getStatus();
            return {
                available: true,
                message: status.loaded ? 'Model loaded and ready' : 'Inference server is running',
                loaded: status.loaded,
                loadedModel: status.loadedModel || null,
            };
        } catch (e) {
            return {
                available: false,
                message: 'Inference server starting or unavailable',
                loaded: false,
                loadedModel: null,
            };
        }
    });

    // POST /api/playground/load - 主动加载模型
    fastify.post('/load', {
        schema: {
            tags: ['Playground'],
            summary: '加载指定模型到显存',
            body: {
                type: 'object',
                required: ['modelId'],
                properties: {
                    modelId: { type: 'string' },
                    adapterId: { type: 'string' },
                    quantization: { type: 'string', enum: ['4bit', '8bit', 'none'] },
                },
            },
        },
    }, async (request, reply) => {
        const body = request.body as { modelId: string; adapterId?: string; quantization?: string };

        // 获取模型信息
        const model = await prisma.model.findUnique({
            where: { id: body.modelId },
        });

        if (!model) {
            return reply.status(400).send({ error: 'Model not found' });
        }

        // 获取 adapter 信息（如果有）
        let adapterPath: string | undefined;
        let adapterName: string | undefined;
        if (body.adapterId && body.adapterId !== 'none') {
            const adapter = await prisma.adapter.findUnique({
                where: { id: body.adapterId },
            });
            if (adapter?.path) {
                adapterPath = adapter.path;
                adapterName = adapter.name;
            }
        }

        console.log(`[Playground] Load model request: ${model.name}`);

        try {
            await modelServer.loadModel(model.path, adapterPath, body.quantization);
            return {
                status: 'loaded',
                model: {
                    id: body.modelId,
                    name: model.name,
                    path: model.path,
                },
                adapter: adapterPath ? {
                    id: body.adapterId,
                    name: adapterName,
                    path: adapterPath,
                } : null,
                quantization: body.quantization || 'none',
            };
        } catch (e: any) {
            console.error('Load model error:', e);
            return reply.status(500).send({ error: e.message || 'Failed to load model' });
        }
    });
}
