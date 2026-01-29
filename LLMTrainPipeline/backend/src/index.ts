import Fastify from 'fastify';
import cors from '@fastify/cors';
import swagger from '@fastify/swagger';
import swaggerUi from '@fastify/swagger-ui';

// Route imports
import { dashboardRoutes } from './routes/dashboard.js';
import { runsRoutes } from './routes/runs.js';
import { modelsRoutes } from './routes/models.js';
import { datasetsRoutes } from './routes/datasets.js';
import { adaptersRoutes } from './routes/adapters.js';
import { compareRoutes } from './routes/compare.js';
import { reportsRoutes } from './routes/reports.js';
import { settingsRoutes } from './routes/settings.js';
import { configRoutes } from './routes/config.js';
import { playgroundRoutes } from './routes/playground.js';
import { searchRoutes } from './routes/search.js';
import { filesRoutes } from './routes/files.js';
import { notificationsRoutes } from './routes/notifications.js';

// Safety guards
import { validateAdaptersOnStartup } from './services/adapter-guard.js';
import { restoreQueue } from './services/run-executor.js';

// P0-FIX: Handle BigInt serialization globally
(BigInt.prototype as any).toJSON = function () {
    return this.toString();
};

const PORT = parseInt(process.env.PORT || '3001');
const HOST = process.env.HOST || '127.0.0.1';

async function main() {
    const fastify = Fastify({
        logger: true,
    });

    // CORS
    await fastify.register(cors, {
        origin: true,
        credentials: true,
    });

    // Swagger documentation
    await fastify.register(swagger, {
        openapi: {
            info: {
                title: 'Nexus AI Backend API',
                description: 'LLM Training Pipeline Backend API',
                version: '1.0.0',
            },
            servers: [{ url: `http://localhost:${PORT}` }],
            tags: [
                { name: 'Dashboard', description: 'Dashboard' },
                { name: 'Runs', description: 'Training Runs' },
                { name: 'Models', description: 'Model Management' },
                { name: 'Datasets', description: 'Dataset Management' },
                { name: 'Adapters', description: 'Adapter Management' },
                { name: 'Compare', description: 'Run Comparison' },
                { name: 'Reports', description: 'Reports' },
                { name: 'Settings', description: 'Settings' },
                { name: 'Config', description: 'Configuration' },
                { name: 'Playground', description: 'Inference Testing' },
                { name: 'Search', description: 'Global Search' },
                { name: 'Files', description: 'File Browser' },
                { name: 'Notifications', description: 'Notifications' },
            ],
        },
    });

    await fastify.register(swaggerUi, {
        routePrefix: '/docs',
        uiConfig: {
            docExpansion: 'list',
            deepLinking: false,
        },
    });

    // Health check
    fastify.get('/health', async () => {
        return { status: 'ok', timestamp: new Date().toISOString() };
    });

    // Register API routes
    await fastify.register(dashboardRoutes, { prefix: '/api/dashboard' });
    await fastify.register(runsRoutes, { prefix: '/api/runs' });
    await fastify.register(modelsRoutes, { prefix: '/api/models' });
    await fastify.register(datasetsRoutes, { prefix: '/api/datasets' });
    await fastify.register(adaptersRoutes, { prefix: '/api/adapters' });
    await fastify.register(compareRoutes, { prefix: '/api/compare' });
    await fastify.register(reportsRoutes, { prefix: '/api/reports' });
    await fastify.register(settingsRoutes, { prefix: '/api/settings' });
    await fastify.register(configRoutes, { prefix: '/api/config' });
    await fastify.register(playgroundRoutes, { prefix: '/api/playground' });
    await fastify.register(searchRoutes, { prefix: '/api/search' });
    await fastify.register(filesRoutes, { prefix: '/api/files' });
    await fastify.register(notificationsRoutes, { prefix: '/api/notifications' });

    // Start server
    try {
        await fastify.listen({ port: PORT, host: HOST });
        console.log(`
🚀 Nexus AI Backend Started
   
   API: http://localhost:${PORT}/api
   Swagger: http://localhost:${PORT}/docs
   Health: http://localhost:${PORT}/health
    `);

        // P0-SAFETY: Validate all adapters on startup
        await validateAdaptersOnStartup();

        // P0-SAFETY: Restore queue state (resume queued tasks after restart)
        await restoreQueue();
    } catch (err) {
        fastify.log.error(err);
        process.exit(1);
    }
}

main();
