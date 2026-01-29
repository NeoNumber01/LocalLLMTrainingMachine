import { FastifyInstance } from 'fastify';
import { resolveConfig } from '../config/index.js';
import { prisma } from '../db/prisma-client.js';

export async function configRoutes(fastify: FastifyInstance) {

    // GET /api/config/resolved - Get merged configuration
    fastify.get('/resolved', {
        schema: {
            tags: ['Config'],
            summary: 'Get merged effective configuration',
            querystring: {
                type: 'object',
                properties: {
                    runId: { type: 'string' },
                    profileName: { type: 'string' },
                },
            },
        },
    }, async (request, reply) => {
        const query = request.query as { runId?: string; profileName?: string };

        let profileName = query.profileName || 'single_gpu';
        let runOverride = {};

        // If runId is provided, load run configuration from database
        if (query.runId) {
            const run = await prisma.run.findUnique({
                where: { id: query.runId },
            });

            if (run) {
                profileName = run.profileName;
                runOverride = JSON.parse(run.configJson);
            }
        }

        // Merge three-layer configuration
        const config = resolveConfig(profileName, runOverride);

        return {
            profileName,
            resolved: config,
            layers: {
                defaults: 'src/config/defaults.yaml',
                profile: `src/config/profiles/${profileName}.yaml`,
                runOverride: query.runId ? `Run ${query.runId} config` : 'none',
            },
        };
    });

    // GET /api/config/profiles - List available configuration profiles
    fastify.get('/profiles', {
        schema: {
            tags: ['Config'],
            summary: 'List available configuration profiles',
        },
    }, async (request, reply) => {
        return {
            profiles: [
                { name: 'single_gpu', description: 'Single GPU configuration' },
                { name: 'multi_gpu_fsdp', description: 'Multi GPU FSDP configuration' },
            ],
        };
    });
}
