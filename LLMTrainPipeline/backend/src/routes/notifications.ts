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

    // GET /api/notifications - Get notification list
    fastify.get('/', {
        schema: {
            tags: ['Notifications'],
            summary: 'Get notification list',
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

    // GET /api/notifications/unread-count - Get unread notification count
    fastify.get('/unread-count', {
        schema: {
            tags: ['Notifications'],
            summary: 'Get unread notification count',
        },
    }, async (request, reply) => {
        const count = await getUnreadCount();
        return { count };
    });

    // POST /api/notifications/:id/read - Mark single notification as read
    fastify.post<{ Params: { id: string } }>('/:id/read', {
        schema: {
            tags: ['Notifications'],
            summary: 'Mark notification as read',
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

    // POST /api/notifications/read-all - Mark all notifications as read
    fastify.post('/read-all', {
        schema: {
            tags: ['Notifications'],
            summary: 'Mark all notifications as read',
        },
    }, async (request, reply) => {
        const result = await markAllAsRead();
        return { success: true, count: result.count };
    });

    // DELETE /api/notifications/:id - Delete single notification
    fastify.delete<{ Params: { id: string } }>('/:id', {
        schema: {
            tags: ['Notifications'],
            summary: 'Delete notification',
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
