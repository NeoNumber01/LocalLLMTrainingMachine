import { FastifyInstance } from 'fastify';
import { prisma } from '../db/prisma-client.js';
import {
    getNotifications,
    getUnreadCount,
    markAsRead,
    markAllAsRead,
    deleteNotification
} from '../services/notification-service.js';

interface NotificationRecord {
    id: string;
    type: string;
    title: string;
    message: string;
    runId: string | null;
    isRead: boolean;
    createdAt: Date;
    readAt: Date | null;
}

export async function notificationsRoutes(fastify: FastifyInstance) {

    // GET /api/notifications - 获取通知列表
    fastify.get('/', {
        schema: {
            tags: ['Notifications'],
            summary: '获取通知列表',
            querystring: {
                type: 'object',
                properties: {
                    limit: { type: 'number', default: 50 },
                    offset: { type: 'number', default: 0 },
                    unreadOnly: { type: 'boolean', default: false },
                },
            },
        },
    }, async (request, reply) => {
        const query = request.query as { limit?: number; offset?: number; unreadOnly?: boolean };

        const notifications = await getNotifications({
            limit: query.limit,
            offset: query.offset,
            unreadOnly: query.unreadOnly,
        });

        return notifications.map((n: NotificationRecord) => ({
            id: n.id,
            type: n.type,
            title: n.title,
            message: n.message,
            runId: n.runId,
            isRead: n.isRead,
            createdAt: n.createdAt.toISOString(),
            readAt: n.readAt?.toISOString() || null,
        }));
    });

    // GET /api/notifications/unread-count - 获取未读通知数量
    fastify.get('/unread-count', {
        schema: {
            tags: ['Notifications'],
            summary: '获取未读通知数量',
        },
    }, async (request, reply) => {
        const count = await getUnreadCount();
        return { count };
    });

    // POST /api/notifications/:id/read - 标记单条通知为已读
    fastify.post<{ Params: { id: string } }>('/:id/read', {
        schema: {
            tags: ['Notifications'],
            summary: '标记通知为已读',
            params: {
                type: 'object',
                properties: { id: { type: 'string' } },
            },
        },
    }, async (request, reply) => {
        try {
            await markAsRead(request.params.id);
            return { success: true };
        } catch (error) {
            return reply.status(404).send({ error: 'Notification not found' });
        }
    });

    // POST /api/notifications/read-all - 标记所有通知为已读
    fastify.post('/read-all', {
        schema: {
            tags: ['Notifications'],
            summary: '标记所有通知为已读',
        },
    }, async (request, reply) => {
        const result = await markAllAsRead();
        return { success: true, count: result.count };
    });

    // DELETE /api/notifications/:id - 删除单条通知
    fastify.delete<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Notifications'],
            summary: '删除通知',
            params: {
                type: 'object',
                properties: { id: { type: 'string' } },
            },
        },
    }, async (request, reply) => {
        try {
            await deleteNotification(request.params.id);
            return { success: true };
        } catch (error) {
            return reply.status(404).send({ error: 'Notification not found' });
        }
    });
}
