import { PrismaClient } from '@prisma/client';

// Global singleton pattern for PrismaClient
// This prevents multiple instances causing SQLite locking issues
declare global {
    var __prisma: PrismaClient | undefined;
}

export const prisma = global.__prisma || new PrismaClient();

if (process.env.NODE_ENV !== 'production') {
    global.__prisma = prisma;
}
