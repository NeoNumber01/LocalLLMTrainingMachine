
import { FastifyInstance } from 'fastify';
import { InferRequest } from '../types/index.js';
import { modelServer } from '../services/model-server.js';
import { prisma } from '../db/prisma-client.js';

export async function playgroundRoutes(fastify: FastifyInstance) {

    // POST /api/playground/infer - Inference request (Streaming)
    fastify.post('/infer', {
        schema: {
            tags: ['Playground'],
            summary: 'Use local model for inference (SSE Stream)',
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

        // 1. Get model information
        const model = await prisma.model.findUnique({
            where: { id: body.modelId },
        });

        if (!model) {
            return reply.status(400).send({ error: 'Model not found' });
        }

        // 2. Get adapter information (if any)
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

        // 3. Set SSE response headers
        reply.raw.setHeader('Content-Type', 'text/event-stream');
        reply.raw.setHeader('Cache-Control', 'no-cache');
        reply.raw.setHeader('Connection', 'keep-alive');

        // CORS handling
        const origin = request.headers.origin || '*';
        reply.raw.setHeader('Access-Control-Allow-Origin', origin);
        reply.raw.setHeader('Access-Control-Allow-Credentials', 'true');

        // Send initialization headers
        reply.raw.flushHeaders();
        reply.raw.write(': keeping connection alive\n\n');

        try {
            // 4. Load model (if needed)
            // This may take some time, so we sent keep-alive first
            // Model service handles locking and duplicate load checking
            await modelServer.loadModel(model.path, adapterPath, body.quantization);


            // 5. Prepare conversation messages
            const messages = [
                { role: 'system', content: body.systemPrompt },
                ...body.messages
            ];

            // 6. Initiate streaming request
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

            // Wait for stream to end
            await new Promise((resolve, reject) => {
                stream.on('end', resolve);
                stream.on('error', (err: Error) => {
                    console.error('Stream error:', err);
                    resolve(err); // Resolve anyway to not leave hanging
                });
            });

            // Critical fix: properly close SSE connection to let frontend know stream has ended
            reply.raw.end();

        } catch (e: any) {
            console.error('Inference Error:', e);
            reply.raw.write(`data: ${JSON.stringify({ error: e.message || 'Inference failed' })}\n\n`);
            reply.raw.end();
        }

        return reply;
    });

    // POST /api/playground/unload - Unload model
    fastify.post('/unload', {
        schema: {
            tags: ['Playground'],
            summary: 'Unload model to free GPU memory',
        },
    }, async (request, reply) => {
        await modelServer.unloadModel();
        return { status: 'unloaded' };
    });

    // GET /api/playground/status - Check inference service status and loaded model
    fastify.get('/status', {
        schema: {
            tags: ['Playground'],
            summary: 'Check inference service status and loaded model info',
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

    // POST /api/playground/load - Actively load model
    fastify.post('/load', {
        schema: {
            tags: ['Playground'],
            summary: 'Load specified model to GPU memory',
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

        // Get model information
        const model = await prisma.model.findUnique({
            where: { id: body.modelId },
        });

        if (!model) {
            return reply.status(400).send({ error: 'Model not found' });
        }

        // Get adapter information (if any)
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
