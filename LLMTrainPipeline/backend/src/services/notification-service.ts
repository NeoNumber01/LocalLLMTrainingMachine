import { prisma } from '../db/prisma-client.js';

// 通知类型
export type NotificationType = 'run_completed' | 'run_failed' | 'resource_alert';

/**
 * 创建新通知
 */
export async function createNotification(
    type: NotificationType,
    title: string,
    message: string,
    runId?: string
) {
    // P0-FIX: 从正确的 key 'notifications' 读取设置
    // settings.ts 保存时使用分别的 key: 'notifications', 'compute' 等
    const setting = await prisma.setting.findUnique({
        where: { key: 'notifications' }
    });

    if (setting) {
        try {
            const notifications = JSON.parse(setting.valueJson);

            // 如果任务完成通知被禁用
            if ((type === 'run_completed' || type === 'run_failed') &&
                notifications?.runCompletion === false) {
                console.log(`[Notification] Skipped: runCompletion notifications disabled`);
                return null;
            }

            // 如果资源警告通知被禁用
            if (type === 'resource_alert' && notifications?.resourceAlerts === false) {
                console.log(`[Notification] Skipped: resourceAlerts notifications disabled`);
                return null;
            }
        } catch (e) {
            // 解析失败则继续创建通知
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
 * 获取未读通知数量
 */
export async function getUnreadCount(): Promise<number> {
    return prisma.notification.count({
        where: { isRead: false }
    });
}

/**
 * 获取通知列表
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
 * 标记通知为已读
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
 * 标记所有通知为已读
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
 * 删除通知
 */
export async function deleteNotification(id: string) {
    return prisma.notification.delete({
        where: { id }
    });
}
