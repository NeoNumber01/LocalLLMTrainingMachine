// System monitoring service - Get real GPU and disk usage information
import { exec } from 'child_process';
import { promisify } from 'util';
import * as os from 'os';
import * as fs from 'fs';
import * as path from 'path';

const execAsync = promisify(exec);

interface GpuInfo {
    available: boolean;
    usage: string;
    memory: string;
    devices: GpuDevice[];
}

interface GpuDevice {
    name: string;
    index: number;
    utilization: number;
    memoryUsed: number;
    memoryTotal: number;
    temperature: number;
}

interface StorageInfo {
    used: string;
    free: string;
    total: string;
    usedBytes: number;
    freeBytes: number;
    totalBytes: number;
    percent: number;
}

interface SystemInfo {
    health: 'Healthy' | 'Warning' | 'Error';
    gpu: GpuInfo;
    storage: StorageInfo;
    cpu: {
        usage: string;
        cores: number;
    };
    memory: {
        used: string;
        total: string;
        percent: number;
    };
}

// Format bytes to human-readable format
function formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + sizes[i];
}

// Get GPU information (via nvidia-smi)
async function getGpuInfo(): Promise<GpuInfo> {
    try {
        // Try calling nvidia-smi (use full path to ensure availability in subprocess)
        const nvidiaSmiPath = process.platform === 'win32'
            ? 'C:\\Windows\\System32\\nvidia-smi.exe'
            : 'nvidia-smi';

        const { stdout } = await execAsync(
            'nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits',
            { timeout: 10000, shell: process.platform === 'win32' ? 'cmd.exe' : '/bin/sh' }
        );

        const lines = stdout.trim().split('\n');
        const devices: GpuDevice[] = [];
        let totalUtilization = 0;

        for (const line of lines) {
            const [index, name, utilization, memUsed, memTotal, temp] = line.split(',').map(s => s.trim());
            const device: GpuDevice = {
                index: parseInt(index),
                name,
                utilization: parseInt(utilization),
                memoryUsed: parseInt(memUsed),
                memoryTotal: parseInt(memTotal),
                temperature: parseInt(temp),
            };
            devices.push(device);
            totalUtilization += device.utilization;
        }

        const avgUtilization = devices.length > 0 ? Math.round(totalUtilization / devices.length) : 0;

        return {
            available: true,
            usage: `${avgUtilization}%`,
            memory: devices.length > 0
                ? `${devices.reduce((sum, d) => sum + d.memoryUsed, 0)}/${devices.reduce((sum, d) => sum + d.memoryTotal, 0)} MB`
                : 'N/A',
            devices,
        };
    } catch (error) {
        // nvidia-smi not available (no NVIDIA GPU or driver not installed)
        return {
            available: false,
            usage: 'N/A',
            memory: 'N/A',
            devices: [],
        };
    }
}

// Get disk storage information (aggregate all drives)
async function getStorageInfo(targetPath?: string): Promise<StorageInfo> {
    try {
        if (process.platform === 'win32') {
            // Windows: Get total storage space from all file system drives
            const { stdout } = await execAsync(
                `powershell -Command "Get-PSDrive -PSProvider FileSystem | Select-Object Name,Used,Free | ConvertTo-Json"`,
                { timeout: 5000 }
            );

            try {
                const rawData = JSON.parse(stdout.trim());
                // Ensure it's an array (single drive may return object)
                const drives = Array.isArray(rawData) ? rawData : [rawData];

                let totalUsedBytes = 0;
                let totalFreeBytes = 0;

                for (const drive of drives) {
                    // Filter out invalid drives (Used and Free are both null or 0)
                    if (drive.Used || drive.Free) {
                        totalUsedBytes += drive.Used || 0;
                        totalFreeBytes += drive.Free || 0;
                    }
                }

                const totalBytes = totalUsedBytes + totalFreeBytes;
                const percent = totalBytes > 0 ? Math.round((totalUsedBytes / totalBytes) * 100) : 0;

                return {
                    used: formatBytes(totalUsedBytes),
                    free: formatBytes(totalFreeBytes),
                    total: formatBytes(totalBytes),
                    usedBytes: totalUsedBytes,
                    freeBytes: totalFreeBytes,
                    totalBytes,
                    percent,
                };
            } catch (parseError) {
                console.error('Failed to parse PowerShell output:', parseError);
            }
        } else {
            // Linux/Mac: Get total storage space from all mount points
            const { stdout } = await execAsync(`df -B1 --total 2>/dev/null | grep '^total' || df -B1 / | tail -1`, { timeout: 5000 });
            const parts = stdout.trim().split(/\s+/);
            if (parts.length >= 4) {
                const totalBytes = parseInt(parts[1]) || 0;
                const usedBytes = parseInt(parts[2]) || 0;
                const freeBytes = parseInt(parts[3]) || 0;
                const percent = totalBytes > 0 ? Math.round((usedBytes / totalBytes) * 100) : 0;

                return {
                    used: formatBytes(usedBytes),
                    free: formatBytes(freeBytes),
                    total: formatBytes(totalBytes),
                    usedBytes,
                    freeBytes,
                    totalBytes,
                    percent,
                };
            }
        }
    } catch (error) {
        console.error('Failed to get storage info:', error);
    }

    // Fallback: return N/A
    return {
        used: 'N/A',
        free: 'N/A',
        total: 'N/A',
        usedBytes: 0,
        freeBytes: 0,
        totalBytes: 0,
        percent: 0,
    };
}

// Get memory information
function getMemoryInfo(): { used: string; total: string; percent: number } {
    const totalMem = os.totalmem();
    const freeMem = os.freemem();
    const usedMem = totalMem - freeMem;
    const percent = Math.round((usedMem / totalMem) * 100);

    return {
        used: formatBytes(usedMem),
        total: formatBytes(totalMem),
        percent,
    };
}

// Get CPU usage
async function getCpuUsage(): Promise<{ usage: string; cores: number }> {
    const cpus = os.cpus();
    const cores = cpus.length;

    // Calculate average CPU usage
    let totalIdle = 0;
    let totalTick = 0;

    for (const cpu of cpus) {
        for (const type in cpu.times) {
            totalTick += (cpu.times as any)[type];
        }
        totalIdle += cpu.times.idle;
    }

    const usage = Math.round(100 - (totalIdle / totalTick) * 100);

    return {
        usage: `${usage}%`,
        cores,
    };
}

// Get system health status
function determineHealth(gpu: GpuInfo, storage: StorageInfo, memory: { percent: number }): 'Healthy' | 'Warning' | 'Error' {
    // Disk space below 10% is considered an error
    if (storage.percent > 90) return 'Error';
    // Memory usage above 90% is considered a warning
    if (memory.percent > 90) return 'Warning';
    // High GPU temperature is considered a warning
    if (gpu.available && gpu.devices.some(d => d.temperature > 80)) return 'Warning';

    return 'Healthy';
}

// Main function: Get complete system information
export async function getSystemInfo(storagePath?: string): Promise<SystemInfo> {
    const [gpu, storage, cpu] = await Promise.all([
        getGpuInfo(),
        getStorageInfo(storagePath),
        getCpuUsage(),
    ]);

    const memory = getMemoryInfo();
    const health = determineHealth(gpu, storage, memory);

    return {
        health,
        gpu,
        storage,
        cpu,
        memory,
    };
}

// Convenience function: Get format needed for Dashboard
export async function getDashboardSystemInfo(storagePath?: string): Promise<{
    systemHealth: string;
    gpuUsage: string;
    gpuDeviceCount: number;
    gpuName: string;
    storage: { used: string; free: string };
}> {
    const info = await getSystemInfo(storagePath);

    // Get GPU name
    let gpuName = 'No GPU';
    if (info.gpu.available && info.gpu.devices.length > 0) {
        if (info.gpu.devices.length === 1) {
            gpuName = info.gpu.devices[0].name;
        } else {
            gpuName = `${info.gpu.devices.length}x ${info.gpu.devices[0].name}`;
        }
    }

    return {
        systemHealth: info.health,
        gpuUsage: info.gpu.usage,
        gpuDeviceCount: info.gpu.devices.length,
        gpuName,
        storage: {
            used: info.storage.used,
            free: info.storage.free,
        },
    };
}
