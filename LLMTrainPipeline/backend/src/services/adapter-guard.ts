/**
 * Adapter Safety Guard
 * 
 * Provides the following protection features:
 * 1. Auto backup adapter to safe directory after training completes
 * 2. Validate adapter file integrity on startup
 * 3. Periodically check adapter health status
 */

import fs from 'fs';
import path from 'path';
import { prisma } from '../db/prisma-client.js';

// Backup directory - this directory won't be ignored by git
const BACKUP_DIR = './storage/adapter_backups';

// Required adapter files list
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
 * Check health status of a single adapter
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

    // Check if directory exists
    if (!fs.existsSync(adapterPath)) {
        status.missingFiles = [...REQUIRED_ADAPTER_FILES];
        return status;
    }

    status.exists = true;

    // Check required files
    for (const file of REQUIRED_ADAPTER_FILES) {
        const filePath = path.join(adapterPath, file);
        if (!fs.existsSync(filePath)) {
            status.missingFiles.push(file);
        }
    }

    status.isComplete = status.missingFiles.length === 0;

    // Check if backup exists
    const backupPath = path.join(BACKUP_DIR, adapterName);
    if (fs.existsSync(backupPath)) {
        status.hasBackup = true;
        status.backupPath = backupPath;
    }

    return status;
}

/**
 * Check health status of all adapters
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
 * Backup adapter to safe directory
 */
export function backupAdapter(sourcePath: string, adapterName: string): { success: boolean; backupPath?: string; error?: string } {
    try {
        // Ensure backup directory exists
        if (!fs.existsSync(BACKUP_DIR)) {
            fs.mkdirSync(BACKUP_DIR, { recursive: true });
        }

        // Create backup directory
        const timestamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        const backupName = `${adapterName}_${timestamp}`;
        const backupPath = path.join(BACKUP_DIR, backupName);

        // If backup already exists, add sequence number
        let finalBackupPath = backupPath;
        let counter = 1;
        while (fs.existsSync(finalBackupPath)) {
            finalBackupPath = `${backupPath}_${counter}`;
            counter++;
        }

        // Copy all files
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
                // Don't backup checkpoints (too large)
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
 * Restore adapter from backup
 */
export function restoreAdapterFromBackup(backupPath: string, targetPath: string): { success: boolean; error?: string } {
    try {
        if (!fs.existsSync(backupPath)) {
            return { success: false, error: `Backup path does not exist: ${backupPath}` };
        }

        // Create target directory
        if (!fs.existsSync(targetPath)) {
            fs.mkdirSync(targetPath, { recursive: true });
        }

        // Copy files
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
 * Validate all adapters on startup
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
 * Auto backup newly trained adapter
 */
export async function autoBackupNewAdapter(runId: string, adapterPath: string, adapterName: string): Promise<void> {
    console.log(`[AdapterGuard] Auto-backing up new adapter: ${adapterName}`);

    // Validate adapter integrity
    const status = checkAdapterHealth(adapterPath, adapterName, runId);

    if (!status.isComplete) {
        console.warn(`[AdapterGuard] New adapter is incomplete, skipping backup. Missing: ${status.missingFiles.join(', ')}`);
        return;
    }

    // Execute backup
    const result = backupAdapter(adapterPath, adapterName);

    if (result.success) {
        console.log(`[AdapterGuard] ✅ Auto-backup completed: ${result.backupPath}`);
    } else {
        console.error(`[AdapterGuard] ❌ Auto-backup failed: ${result.error}`);
    }
}
