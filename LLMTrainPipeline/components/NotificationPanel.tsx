import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    fetchNotifications,
    fetchUnreadCount,
    markNotificationRead,
    markAllNotificationsRead,
    Notification
} from '../lib/api';

interface NotificationPanelProps {
    isOpen: boolean;
    onClose: () => void;
    onUnreadCountChange: (count: number) => void;
}

const NotificationPanel: React.FC<NotificationPanelProps> = ({ isOpen, onClose, onUnreadCountChange }) => {
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [loading, setLoading] = useState(false);
    const panelRef = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();

    useEffect(() => {
        if (isOpen) {
            loadNotifications();
        }
    }, [isOpen]);

    // Click outside to close panel
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
                onClose();
            }
        };

        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isOpen, onClose]);

    const loadNotifications = async () => {
        setLoading(true);
        try {
            const [notifs, { count }] = await Promise.all([
                fetchNotifications(20),
                fetchUnreadCount()
            ]);
            setNotifications(notifs);
            onUnreadCountChange(count);
        } catch (e) {
            console.error('Failed to load notifications:', e);
        } finally {
            setLoading(false);
        }
    };

    const handleNotificationClick = async (notification: Notification) => {
        // Mark as read
        if (!notification.isRead) {
            try {
                await markNotificationRead(notification.id);
                setNotifications(prev =>
                    prev.map(n => n.id === notification.id ? { ...n, isRead: true } : n)
                );
                onUnreadCountChange(notifications.filter(n => !n.isRead && n.id !== notification.id).length);
            } catch (e) {
                console.error('Failed to mark as read:', e);
            }
        }

        // If there's an associated runId, navigate to detail page
        if (notification.runId) {
            onClose();
            // Determine navigation based on notification type (evaluation or training)
            if (notification.title.toLowerCase().includes('evaluation')) {
                navigate(`/evaluation/${notification.runId}`);
            } else {
                navigate(`/runs/${notification.runId}`);
            }
        }
    };

    const handleMarkAllRead = async () => {
        try {
            await markAllNotificationsRead();
            setNotifications(prev => prev.map(n => ({ ...n, isRead: true })));
            onUnreadCountChange(0);
        } catch (e) {
            console.error('Failed to mark all as read:', e);
        }
    };

    const getIconForType = (type: string) => {
        switch (type) {
            case 'run_completed':
                return { icon: 'check_circle', color: 'text-emerald-400' };
            case 'run_failed':
                return { icon: 'error', color: 'text-red-400' };
            case 'resource_alert':
                return { icon: 'warning', color: 'text-yellow-400' };
            default:
                return { icon: 'notifications', color: 'text-gray-400' };
        }
    };

    const formatTimeAgo = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

        if (seconds < 60) return 'Just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        return `${Math.floor(seconds / 86400)}d ago`;
    };

    if (!isOpen) return null;

    return (
        <div
            ref={panelRef}
            className="absolute top-14 right-0 w-96 bg-surface border border-border rounded-xl shadow-2xl z-50 overflow-hidden"
        >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-black/20">
                <h3 className="text-sm font-semibold text-white">Notifications</h3>
                {notifications.some(n => !n.isRead) && (
                    <button
                        onClick={handleMarkAllRead}
                        className="text-xs text-primary hover:text-blue-400 transition-colors"
                    >
                        Mark all read
                    </button>
                )}
            </div>

            {/* Content */}
            <div className="max-h-96 overflow-y-auto">
                {loading ? (
                    <div className="flex items-center justify-center py-8">
                        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                    </div>
                ) : notifications.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                        <span className="material-symbols-outlined text-4xl mb-2">notifications_off</span>
                        <span className="text-sm">No notifications</span>
                    </div>
                ) : (
                    notifications.map((notification) => {
                        const { icon, color } = getIconForType(notification.type);
                        return (
                            <div
                                key={notification.id}
                                onClick={() => handleNotificationClick(notification)}
                                className={`flex items-start gap-3 px-4 py-3 border-b border-border/50 cursor-pointer transition-colors hover:bg-white/5 ${!notification.isRead ? 'bg-primary/5' : ''
                                    }`}
                            >
                                <span className={`material-symbols-outlined text-xl mt-0.5 ${color}`}>
                                    {icon}
                                </span>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span className={`text-sm font-medium truncate ${notification.isRead ? 'text-gray-400' : 'text-white'
                                            }`}>
                                            {notification.title}
                                        </span>
                                        {!notification.isRead && (
                                            <span className="w-2 h-2 rounded-full bg-primary shrink-0"></span>
                                        )}
                                    </div>
                                    <p className="text-xs text-gray-500 truncate mt-0.5">
                                        {notification.message}
                                    </p>
                                    <span className="text-[10px] text-gray-600 mt-1">
                                        {formatTimeAgo(notification.createdAt)}
                                    </span>
                                </div>
                            </div>
                        );
                    })
                )}
            </div>

            {/* Footer */}
            {notifications.length > 0 && (
                <div className="px-4 py-2 border-t border-border bg-black/10">
                    <button
                        onClick={() => {
                            onClose();
                            navigate('/settings');
                        }}
                        className="text-xs text-gray-500 hover:text-gray-400 transition-colors"
                    >
                        Notification Settings
                    </button>
                </div>
            )}
        </div>
    );
};

export default NotificationPanel;
