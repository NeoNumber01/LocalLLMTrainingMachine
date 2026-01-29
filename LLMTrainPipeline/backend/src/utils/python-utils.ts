/**
 * Python 命令跨平台兼容工具
 * Windows 上通常是 python，Linux/Mac 上通常是 python3
 */

import { spawnSync } from 'child_process';

/**
 * 获取可用的 Python 命令（跨平台兼容）
 * @returns 可用的 Python 命令 ('python' 或 'python3')
 */
function getPythonCommand(): string {
    const candidates = process.platform === 'win32'
        ? ['python', 'python3']
        : ['python3', 'python'];

    for (const cmd of candidates) {
        try {
            const result = spawnSync(cmd, ['--version'], { encoding: 'utf-8', timeout: 5000 });
            if (result.status === 0) {
                console.log(`[PythonUtils] Using Python command: ${cmd}`);
                return cmd;
            }
        } catch { /* continue to next candidate */ }
    }
    console.warn('[PythonUtils] No Python found, falling back to "python"');
    return 'python'; // fallback
}

// 缓存探测结果，避免重复检测
let cachedPythonCmd: string | null = null;

/**
 * 获取 Python 命令（带缓存）
 * @returns 可用的 Python 命令
 */
export function getPython(): string {
    if (!cachedPythonCmd) {
        cachedPythonCmd = getPythonCommand();
    }
    return cachedPythonCmd;
}

/**
 * 重置 Python 命令缓存（用于测试或环境变更时）
 */
export function resetPythonCache(): void {
    cachedPythonCmd = null;
}
