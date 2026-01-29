import { CacheProvider } from '../interfaces.js';

interface CacheEntry<T> {
    value: T;
    expireAt: number;
}

export class MemoryTtlCache implements CacheProvider {
    name = 'memory_ttl';
    private cache: Map<string, CacheEntry<any>> = new Map();
    private defaultTtl: number;

    constructor(defaultTtlSeconds: number = 300) {
        this.defaultTtl = defaultTtlSeconds * 1000;

        // Periodically cleanup expired entries
        setInterval(() => this.cleanup(), 60000);
    }

    async get<T>(key: string): Promise<T | null> {
        const entry = this.cache.get(key);
        if (!entry) return null;

        if (Date.now() > entry.expireAt) {
            this.cache.delete(key);
            return null;
        }

        return entry.value as T;
    }

    async set<T>(key: string, value: T, ttlSeconds?: number): Promise<void> {
        const ttl = ttlSeconds ? ttlSeconds * 1000 : this.defaultTtl;
        this.cache.set(key, {
            value,
            expireAt: Date.now() + ttl,
        });
    }

    async delete(key: string): Promise<void> {
        this.cache.delete(key);
    }

    async clear(): Promise<void> {
        this.cache.clear();
    }

    private cleanup(): void {
        const now = Date.now();
        for (const [key, entry] of this.cache.entries()) {
            if (now > entry.expireAt) {
                this.cache.delete(key);
            }
        }
    }
}
