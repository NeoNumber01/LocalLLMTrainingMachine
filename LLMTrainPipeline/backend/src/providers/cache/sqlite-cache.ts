import { PrismaClient } from '@prisma/client';
import { CacheProvider } from '../interfaces.js';

const prisma = new PrismaClient();

export class SqliteCacheProvider implements CacheProvider {
    name = 'sqlite_cache';

    async get<T>(key: string): Promise<T | null> {
        const entry = await prisma.kvCache.findUnique({
            where: { key },
        });

        if (!entry) return null;

        // 检查过期
        if (entry.expireAt && new Date() > entry.expireAt) {
            await this.delete(key);
            return null;
        }

        try {
            return JSON.parse(entry.valueJson) as T;
        } catch {
            return null;
        }
    }

    async set<T>(key: string, value: T, ttlSeconds?: number): Promise<void> {
        const expireAt = ttlSeconds
            ? new Date(Date.now() + ttlSeconds * 1000)
            : null;

        await prisma.kvCache.upsert({
            where: { key },
            update: {
                valueJson: JSON.stringify(value),
                expireAt,
            },
            create: {
                key,
                valueJson: JSON.stringify(value),
                expireAt,
            },
        });
    }

    async delete(key: string): Promise<void> {
        await prisma.kvCache.delete({
            where: { key },
        }).catch(() => { }); // 忽略不存在的 key
    }

    async clear(): Promise<void> {
        await prisma.kvCache.deleteMany();
    }

    // 清理过期条目（可定期调用）
    async cleanup(): Promise<number> {
        const result = await prisma.kvCache.deleteMany({
            where: {
                expireAt: {
                    lt: new Date(),
                },
            },
        });
        return result.count;
    }
}
