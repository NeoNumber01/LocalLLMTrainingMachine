import { prisma } from '../db/prisma-client.js';

// Notification types
export type NotificationType = 'run_completed' | 'run_failed' | 'resource_alert';

/**
 * Create a new notification
 */
export async function createNotification(
    type: NotificationType,
    title: string,
    message: string,
    runId?: string
) {
    // P0-FIX: Read settings from correct key 'notifications'
    // settings.ts saves using separate keys: 'notifications', 'compute' etc.
    const setting = await prisma.setting.findUnique({
        where: { key: 'notifications' }
    });

    if (setting) {
        try {
            const notifications = JSON.parse(setting.valueJson);

            // If run completion notification is disabled
            if ((type === 'run_completed' || type === 'run_failed') &&
                notifications?.runCompletion === false) {
                console.log(`[Notification] Skipped: runCompletion notifications disabled`);
                return null;
            }

            // If resource alert notification is disabled
            if (type === 'resource_alert' && notifications?.resourceAlerts === false) {
                console.log(`[Notification] Skipped: resourceAlerts notifications disabled`);
                return null;
            }
        } catch (e) {
            // Continue creating notification on parse failure
        }
    }

    const notification = await prisma.notification.create({
        data: {
            type,
            title,
            message,
            runId,
        }
    });

    console.log(`[Notification] Created: ${type} - ${title}`);
    return notification;
}

/**
 * Get unread notification count
 */
export async function getUnreadCount(): Promise<number> {
    return prisma.notification.count({
        where: { isRead: false }
    });
}

/**
 * Get notification list
 */
export async function getNotifications(options: {
    limit?: number;
    offset?: number;
    unreadOnly?: boolean;
} = {}) {
    const { limit = 50, offset = 0, unreadOnly = false } = options;

    return prisma.notification.findMany({
        where: unreadOnly ? { isRead: false } : undefined,
        orderBy: { createdAt: 'desc' },
        take: limit,
        skip: offset,
    });
}

/**
 * Mark notification as read
 */
export async function markAsRead(id: string) {
    return prisma.notification.update({
        where: { id },
        data: {
            isRead: true,
            readAt: new Date(),
        }
    });
}

/**
 * Mark all notifications as read
 */
export async function markAllAsRead() {
    return prisma.notification.updateMany({
        where: { isRead: false },
        data: {
            isRead: true,
            readAt: new Date(),
        }
    });
}

/**
 * Delete notification
 */
export async function deleteNotification(id: string) {
    return prisma.notification.delete({
        where: { id }
    });
}
