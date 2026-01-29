import { FastifyInstance } from 'fastify';
import { prisma } from '../db/prisma-client.js';

interface SearchResult {
    id: string;
    type: 'run' | 'model' | 'dataset' | 'adapter';
    name: string;
    description?: string;
    path: string;
}

export async function searchRoutes(fastify: FastifyInstance) {

    // GET /api/search - Global search across all resources
    fastify.get<{ Querystring: { q: string } }>('/', {
        schema: {
            tags: ['Search'],
            summary: 'Search across all resources',
            querystring: {
                type: 'object',
                properties: {
                    q: { type: 'string' },
                },
            },
        },
    }, async (request, reply) => {
        const query = request.query.q?.toLowerCase()?.trim() || '';

        if (!query) {
            return { results: [] };
        }

        const results: SearchResult[] = [];

        // Search Runs
        const runs = await prisma.run.findMany({
            where: {
                OR: [
                    { name: { contains: query } },
                    { type: { contains: query } },
                ],
            },
            take: 5,
            orderBy: { createdAt: 'desc' },
        });

        for (const run of runs) {
            results.push({
                id: run.id,
                type: 'run',
                name: run.name,
                description: `${run.type} • ${run.status}`,
                path: `/runs/${run.id}`,
            });
        }

        // Search Models
        const models = await prisma.model.findMany({
            where: {
                OR: [
                    { name: { contains: query } },
                    { path: { contains: query } },
                ],
            },
            take: 5,
            orderBy: { updatedAt: 'desc' },
        });

        for (const model of models) {
            results.push({
                id: model.id,
                type: 'model',
                name: model.name,
                description: model.params || model.path,
                path: `/models`,
            });
        }

        // Search Datasets
        const datasets = await prisma.dataset.findMany({
            where: {
                OR: [
                    { name: { contains: query } },
                    { path: { contains: query } },
                ],
            },
            take: 5,
            orderBy: { updatedAt: 'desc' },
        });

        for (const dataset of datasets) {
            results.push({
                id: dataset.id,
                type: 'dataset',
                name: dataset.name,
                description: `${dataset.samples} samples • ${dataset.type}`,
                path: `/datasets`,
            });
        }

        // Search Adapters
        const adapters = await prisma.adapter.findMany({
            where: {
                OR: [
                    { name: { contains: query } },
                    { path: { contains: query } },
                ],
            },
            take: 5,
            orderBy: { createdAt: 'desc' },
        });

        for (const adapter of adapters) {
            results.push({
                id: adapter.id,
                type: 'adapter',
                name: adapter.name,
                description: `Rank ${adapter.rank}`,
                path: `/adapters`,
            });
        }

        // Sort by relevance (exact name match first)
        results.sort((a, b) => {
            const aExact = a.name.toLowerCase() === query;
            const bExact = b.name.toLowerCase() === query;
            if (aExact && !bExact) return -1;
            if (!aExact && bExact) return 1;
            return 0;
        });

        return { results: results.slice(0, 10) };
    });
}
