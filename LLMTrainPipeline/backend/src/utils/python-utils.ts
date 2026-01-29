/**
 * Python command cross-platform compatibility utility
 * On Windows it's usually 'python', on Linux/Mac it's usually 'python3'
 */

import { spawnSync } from 'child_process';

/**
 * Get available Python command (cross-platform compatible)
 * @returns Available Python command ('python' or 'python3')
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

// Cache detection result to avoid repeated checks
let cachedPythonCmd: string | null = null;

/**
 * Get Python command (with cache)
 * @returns Available Python command
 */
export function getPython(): string {
    if (!cachedPythonCmd) {
        cachedPythonCmd = getPythonCommand();
    }
    return cachedPythonCmd;
}

/**
 * Reset Python command cache (for testing or environment changes)
 */
export function resetPythonCache(): void {
    cachedPythonCmd = null;
}
