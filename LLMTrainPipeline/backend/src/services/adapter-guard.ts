/**
 * Adapter Safety Guard
 * 
 * 提供以下保护功能:
 * 1. 训练完成后自动备份 adapter 到安全目录
 * 2. 启动时验证 adapter 文件完整性
 * 3. 定期检查 adapter 健康状态
 */

import fs from 'fs';
import path from 'path';
import { prisma } from '../db/prisma-client.js';

// 备份目录 - 这个目录不会被 git 忽略
const BACKUP_DIR = './storage/adapter_backups';

// 必需的 adapter 文件列表
const REQUIRED_ADAPTER_FILES = [
    'adapter_config.json',
    'adapter_model.safetensors',
];

const OPTIONAL_ADAPTER_FILES = [
    'tokenizer_config.json',
    'tokenizer.json',
    'special_tokens_map.json',
];

export interface AdapterHealthStatus {
    adapterId: string;
    name: string;
    path: string;
    exists: boolean;
    isComplete: boolean;
    missingFiles: string[];
    hasBackup: boolean;
    backupPath?: string;
}

/**
 * 检查单个 adapter 的健康状态
 */
export function checkAdapterHealth(adapterPath: string, adapterName: string, adapterId: string): AdapterHealthStatus {
    const status: AdapterHealthStatus = {
        adapterId,
        name: adapterName,
        path: adapterPath,
        exists: false,
        isComplete: false,
        missingFiles: [],
        hasBackup: false,
    };

    // 检查目录是否存在
    if (!fs.existsSync(adapterPath)) {
        status.missingFiles = [...REQUIRED_ADAPTER_FILES];
        return status;
    }

    status.exists = true;

    // 检查必需文件
    for (const file of REQUIRED_ADAPTER_FILES) {
        const filePath = path.join(adapterPath, file);
        if (!fs.existsSync(filePath)) {
            status.missingFiles.push(file);
        }
    }

    status.isComplete = status.missingFiles.length === 0;

    // 检查是否有备份
    const backupPath = path.join(BACKUP_DIR, adapterName);
    if (fs.existsSync(backupPath)) {
        status.hasBackup = true;
        status.backupPath = backupPath;
    }

    return status;
}

/**
 * 检查所有 adapters 的健康状态
 */
export async function checkAllAdaptersHealth(): Promise<AdapterHealthStatus[]> {
    const adapters = await prisma.adapter.findMany();
    const results: AdapterHealthStatus[] = [];

    for (const adapter of adapters) {
        if (adapter.path) {
            const status = checkAdapterHealth(adapter.path, adapter.name, adapter.id);
            results.push(status);
        }
    }

    return results;
}

/**
 * 备份 adapter 到安全目录
 */
export function backupAdapter(sourcePath: string, adapterName: string): { success: boolean; backupPath?: string; error?: string } {
    try {
        // 确保备份目录存在
        if (!fs.existsSync(BACKUP_DIR)) {
            fs.mkdirSync(BACKUP_DIR, { recursive: true });
        }

        // 创建备份目录
        const timestamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        const backupName = `${adapterName}_${timestamp}`;
        const backupPath = path.join(BACKUP_DIR, backupName);

        // 如果备份已存在，添加序号
        let finalBackupPath = backupPath;
        let counter = 1;
        while (fs.existsSync(finalBackupPath)) {
            finalBackupPath = `${backupPath}_${counter}`;
            counter++;
        }

        // 复制所有文件
        if (!fs.existsSync(sourcePath)) {
            return { success: false, error: `Source path does not exist: ${sourcePath}` };
        }

        fs.mkdirSync(finalBackupPath, { recursive: true });

        const files = fs.readdirSync(sourcePath);
        for (const file of files) {
            const srcFile = path.join(sourcePath, file);
            const destFile = path.join(finalBackupPath, file);
            const stat = fs.statSync(srcFile);

            if (stat.isFile()) {
                fs.copyFileSync(srcFile, destFile);
            } else if (stat.isDirectory() && !file.startsWith('checkpoint-')) {
                // 不备份 checkpoints（太大了）
                fs.cpSync(srcFile, destFile, { recursive: true });
            }
        }

        console.log(`[AdapterGuard] Backed up adapter to: ${finalBackupPath}`);
        return { success: true, backupPath: finalBackupPath };

    } catch (error: any) {
        console.error(`[AdapterGuard] Backup failed:`, error);
        return { success: false, error: error.message };
    }
}

/**
 * 从备份恢复 adapter
 */
export function restoreAdapterFromBackup(backupPath: string, targetPath: string): { success: boolean; error?: string } {
    try {
        if (!fs.existsSync(backupPath)) {
            return { success: false, error: `Backup path does not exist: ${backupPath}` };
        }

        // 创建目标目录
        if (!fs.existsSync(targetPath)) {
            fs.mkdirSync(targetPath, { recursive: true });
        }

        // 复制文件
        const files = fs.readdirSync(backupPath);
        for (const file of files) {
            const srcFile = path.join(backupPath, file);
            const destFile = path.join(targetPath, file);
            const stat = fs.statSync(srcFile);

            if (stat.isFile()) {
                fs.copyFileSync(srcFile, destFile);
            } else if (stat.isDirectory()) {
                fs.cpSync(srcFile, destFile, { recursive: true });
            }
        }

        console.log(`[AdapterGuard] Restored adapter from ${backupPath} to ${targetPath}`);
        return { success: true };

    } catch (error: any) {
        console.error(`[AdapterGuard] Restore failed:`, error);
        return { success: false, error: error.message };
    }
}

/**
 * 启动时验证所有 adapters
 */
export async function validateAdaptersOnStartup(): Promise<void> {
    console.log('[AdapterGuard] Validating adapters on startup...');

    const healthStatuses = await checkAllAdaptersHealth();
    let invalidCount = 0;

    for (const status of healthStatuses) {
        if (!status.exists) {
            console.warn(`[AdapterGuard] ⚠️ Adapter "${status.name}" path does not exist!`);
            console.warn(`[AdapterGuard]    Path: ${status.path}`);

            if (status.hasBackup) {
                console.log(`[AdapterGuard]    ✅ Backup available: ${status.backupPath}`);
            } else {
                console.warn(`[AdapterGuard]    ❌ No backup available`);
            }
            invalidCount++;
        } else if (!status.isComplete) {
            console.warn(`[AdapterGuard] ⚠️ Adapter "${status.name}" is incomplete!`);
            console.warn(`[AdapterGuard]    Missing files: ${status.missingFiles.join(', ')}`);
            invalidCount++;
        } else {
            console.log(`[AdapterGuard] ✅ Adapter "${status.name}" is valid`);
        }
    }

    if (invalidCount > 0) {
        console.warn(`[AdapterGuard] Found ${invalidCount} invalid adapter(s). Consider cleaning up or restoring from backup.`);
    } else {
        console.log('[AdapterGuard] All adapters validated successfully');
    }
}

/**
 * 自动备份新训练的 adapter
 */
export async function autoBackupNewAdapter(runId: string, adapterPath: string, adapterName: string): Promise<void> {
    console.log(`[AdapterGuard] Auto-backing up new adapter: ${adapterName}`);

    // 验证 adapter 完整性
    const status = checkAdapterHealth(adapterPath, adapterName, runId);

    if (!status.isComplete) {
        console.warn(`[AdapterGuard] New adapter is incomplete, skipping backup. Missing: ${status.missingFiles.join(', ')}`);
        return;
    }

    // 执行备份
    const result = backupAdapter(adapterPath, adapterName);

    if (result.success) {
        console.log(`[AdapterGuard] ✅ Auto-backup completed: ${result.backupPath}`);
    } else {
        console.error(`[AdapterGuard] ❌ Auto-backup failed: ${result.error}`);
    }
}
