import { FastifyInstance } from 'fastify';
import fs from 'fs';
import path from 'path';
import os from 'os';

export async function filesRoutes(fastify: FastifyInstance) {

    // GET /api/files/browse - Browse folder contents
    fastify.get<{
        Querystring: { path?: string; filter?: string }
    }>('/browse', {
        schema: {
            tags: ['Files'],
            summary: 'Browse local folder',
            querystring: {
                type: 'object',
                properties: {
                    path: { type: 'string', description: 'Path to browse' },
                    filter: { type: 'string', description: 'File filter, e.g. .jsonl,.json' },
                },
            },
        },
    }, async (request, reply) => {
        // Default to start from user directory
        let targetPath = request.query.path || os.homedir();
        const filter = request.query.filter?.split(',').map(f => f.trim().toLowerCase()) || [];

        // Handle special paths
        if (targetPath === '~') {
            targetPath = os.homedir();
        }

        // Security check: ensure path exists
        if (!fs.existsSync(targetPath)) {
            return reply.status(404).send({ error: `Path not found: ${targetPath}` });
        }

        // Ensure it's a directory
        const stats = fs.statSync(targetPath);
        if (!stats.isDirectory()) {
            return reply.status(400).send({ error: 'Path is not a directory' });
        }

        try {
            const entries = fs.readdirSync(targetPath, { withFileTypes: true });

            const items = entries
                .filter(entry => {
                    // Filter hidden files
                    if (entry.name.startsWith('.')) return false;

                    // If directory, always show
                    if (entry.isDirectory()) return true;

                    // If filter exists, only show matching files
                    if (filter.length > 0) {
                        const ext = path.extname(entry.name).toLowerCase();
                        return filter.includes(ext);
                    }

                    return true;
                })
                .map(entry => {
                    const fullPath = path.join(targetPath, entry.name);
                    let size = 0;

                    try {
                        if (entry.isFile()) {
                            size = fs.statSync(fullPath).size;
                        }
                    } catch { }

                    return {
                        name: entry.name,
                        path: fullPath,
                        isDirectory: entry.isDirectory(),
                        size: entry.isDirectory() ? null : formatSize(size),
                        ext: entry.isFile() ? path.extname(entry.name) : null,
                    };
                })
                // Directories sort first
                .sort((a, b) => {
                    if (a.isDirectory && !b.isDirectory) return -1;
                    if (!a.isDirectory && b.isDirectory) return 1;
                    return a.name.localeCompare(b.name);
                });

            // Get parent directory
            const parentPath = path.dirname(targetPath);
            const hasParent = parentPath !== targetPath;

            return {
                currentPath: targetPath,
                parent: hasParent ? parentPath : null,
                items,
            };
        } catch (err: any) {
            return reply.status(500).send({ error: `Failed to read directory: ${err.message}` });
        }
    });

    // GET /api/files/drives - Get available drives (Windows)
    fastify.get('/drives', {
        schema: {
            tags: ['Files'],
            summary: 'Get available drives list',
        },
    }, async (request, reply) => {
        if (process.platform !== 'win32') {
            return { drives: ['/'] };
        }

        // Windows: scan available drives
        const drives: string[] = [];
        for (let i = 65; i <= 90; i++) {
            const drive = String.fromCharCode(i) + ':\\';
            if (fs.existsSync(drive)) {
                drives.push(drive);
            }
        }

        return { drives };
    });

    // GET /api/files/quickPaths - Get quick access paths
    fastify.get('/quickPaths', {
        schema: {
            tags: ['Files'],
            summary: 'Get quick access paths',
        },
    }, async (request, reply) => {
        const home = os.homedir();
        const cwd = process.cwd();

        const paths = [
            { name: 'Home', path: home },
            { name: 'Project', path: cwd },
            { name: 'Storage', path: path.join(cwd, 'storage') },
            { name: 'Datasets', path: path.join(cwd, 'storage', 'train_datasets') },
            { name: 'Desktop', path: path.join(home, 'Desktop') },
            { name: 'Downloads', path: path.join(home, 'Downloads') },
        ].filter(p => fs.existsSync(p.path));

        return { paths };
    });

    // POST /api/files/openNativeDialog - Open system native file selection dialog
    fastify.post<{
        Body: { mode: 'file' | 'folder'; filter?: string; title?: string }
    }>('/openNativeDialog', {
        schema: {
            tags: ['Files'],
            summary: 'Open system native file selection dialog',
            body: {
                type: 'object',
                properties: {
                    mode: { type: 'string', enum: ['file', 'folder'] },
                    filter: { type: 'string' },
                    title: { type: 'string' },
                },
            },
        },
    }, async (request, reply) => {
        const { mode, filter, title } = request.body;
        const { spawn } = await import('child_process');

        // Escape special characters for PowerShell strings to prevent injection
        const escapePowerShellString = (str: string): string => {
            return str.replace(/`/g, '``').replace(/"/g, '`"').replace(/\$/g, '`$');
        };

        const safeTitle = title ? escapePowerShellString(title) : '';
        const safeFilter = filter ? escapePowerShellString(filter) : '';

        return new Promise((resolve) => {
            if (process.platform === 'win32') {
                let script: string;
                if (mode === 'folder') {
                    script = `
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "${safeTitle || 'Select Folder'}"
$dialog.ShowNewFolderButton = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.SelectedPath
}`;
                } else {
                    const filterStr = safeFilter || 'All Files|*.*';
                    script = `
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = "${safeTitle || 'Select File'}"
$dialog.Filter = "${filterStr}"
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.FileName
}`;
                }

                const ps = spawn('powershell', ['-NoProfile', '-Command', script], {
                    stdio: ['pipe', 'pipe', 'pipe'],
                });

                let stdout = '';
                ps.stdout.on('data', (data) => { stdout += data.toString(); });
                ps.on('close', () => {
                    const selectedPath = stdout.trim();
                    if (selectedPath && fs.existsSync(selectedPath)) {
                        resolve({
                            selected: true,
                            path: selectedPath,
                            name: path.basename(selectedPath),
                            isDirectory: fs.statSync(selectedPath).isDirectory(),
                        });
                    } else {
                        resolve({ selected: false, path: null, cancelled: true });
                    }
                });
                ps.on('error', () => {
                    resolve({ selected: false, path: null, error: 'Failed to open dialog' });
                });
            } else if (process.platform === 'darwin') {
                // Mac: use osascript (AppleScript) to open native dialog
                let script: string;
                if (mode === 'folder') {
                    script = `POSIX path of (choose folder with prompt "${safeTitle || 'Select Folder'}")`;
                } else {
                    script = `POSIX path of (choose file with prompt "${safeTitle || 'Select File'}")`;
                }

                const osa = spawn('osascript', ['-e', script], {
                    stdio: ['pipe', 'pipe', 'pipe'],
                });

                let stdout = '';
                let stderr = '';
                osa.stdout.on('data', (data) => { stdout += data.toString(); });
                osa.stderr.on('data', (data) => { stderr += data.toString(); });
                osa.on('close', (code) => {
                    const selectedPath = stdout.trim();
                    if (code === 0 && selectedPath && fs.existsSync(selectedPath)) {
                        resolve({
                            selected: true,
                            path: selectedPath,
                            name: path.basename(selectedPath),
                            isDirectory: fs.statSync(selectedPath).isDirectory(),
                        });
                    } else if (stderr.includes('User canceled')) {
                        resolve({ selected: false, path: null, cancelled: true });
                    } else {
                        resolve({ selected: false, path: null, cancelled: true });
                    }
                });
                osa.on('error', () => {
                    resolve({ selected: false, path: null, error: 'Failed to open dialog' });
                });
            } else {
                // Linux: try to use zenity (GTK) or return not supported
                const zenityCmd = mode === 'folder'
                    ? ['--file-selection', '--directory', `--title=${safeTitle || 'Select Folder'}`]
                    : ['--file-selection', `--title=${safeTitle || 'Select File'}`];

                const zenity = spawn('zenity', zenityCmd, {
                    stdio: ['pipe', 'pipe', 'pipe'],
                });

                let stdout = '';
                zenity.stdout.on('data', (data) => { stdout += data.toString(); });
                zenity.on('close', (code) => {
                    const selectedPath = stdout.trim();
                    if (code === 0 && selectedPath && fs.existsSync(selectedPath)) {
                        resolve({
                            selected: true,
                            path: selectedPath,
                            name: path.basename(selectedPath),
                            isDirectory: fs.statSync(selectedPath).isDirectory(),
                        });
                    } else {
                        resolve({ selected: false, path: null, cancelled: true });
                    }
                });
                zenity.on('error', () => {
                    // zenity not available, return not supported
                    resolve({ selected: false, path: null, error: 'Native dialog requires zenity on Linux. Please use the file browser instead.' });
                });
            }
        });
    });
}

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}
