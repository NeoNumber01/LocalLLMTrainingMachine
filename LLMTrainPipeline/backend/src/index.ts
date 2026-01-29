import Fastify from 'fastify';
import cors from '@fastify/cors';
import swagger from '@fastify/swagger';
import swaggerUi from '@fastify/swagger-ui';

// 路由导入
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

// 安全守护
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

    // Swagger 文档
    await fastify.register(swagger, {
        openapi: {
            info: {
                title: 'Nexus AI Backend API',
                description: 'LLM 训练流水线后端 API',
                version: '1.0.0',
            },
            servers: [{ url: `http://localhost:${PORT}` }],
            tags: [
                { name: 'Dashboard', description: '仪表盘' },
                { name: 'Runs', description: '训练运行' },
                { name: 'Models', description: '模型管理' },
                { name: 'Datasets', description: '数据集管理' },
                { name: 'Adapters', description: '适配器管理' },
                { name: 'Compare', description: '运行对比' },
                { name: 'Reports', description: '报告' },
                { name: 'Settings', description: '设置' },
                { name: 'Config', description: '配置' },
                { name: 'Playground', description: '推理测试' },
                { name: 'Search', description: '全局搜索' },
                { name: 'Files', description: '文件浏览' },
                { name: 'Notifications', description: '通知' },
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

    // 健康检查
    fastify.get('/health', async () => {
        return { status: 'ok', timestamp: new Date().toISOString() };
    });

    // 注册 API 路由
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

    // 启动服务器
    try {
        await fastify.listen({ port: PORT, host: HOST });
        console.log(`
🚀 Nexus AI Backend 已启动
   
   API: http://localhost:${PORT}/api
   Swagger: http://localhost:${PORT}/docs
   Health: http://localhost:${PORT}/health
    `);

        // P0-SAFETY: 启动时验证所有 adapters
        await validateAdaptersOnStartup();

        // P0-SAFETY: 恢复队列状态 (重启后恢复排队任务)
        await restoreQueue();
    } catch (err) {
        fastify.log.error(err);
        process.exit(1);
    }
}

main();
