import fs from 'fs';
import path from 'path';
import { ArtifactStore, ArtifactInfo } from '../interfaces.js';

export class FilesystemStore implements ArtifactStore {
    name = 'filesystem';
    private baseDir: string;

    constructor(baseDir: string) {
        this.baseDir = path.resolve(baseDir);
        // 确保目录存在
        if (!fs.existsSync(this.baseDir)) {
            fs.mkdirSync(this.baseDir, { recursive: true });
        }
    }

    async save(runId: string, kind: string, filename: string, data: Buffer): Promise<string> {
        const runDir = path.join(this.baseDir, runId);
        if (!fs.existsSync(runDir)) {
            fs.mkdirSync(runDir, { recursive: true });
        }

        const filePath = path.join(runDir, filename);
        fs.writeFileSync(filePath, data);

        return filePath;
    }

    async get(filePath: string): Promise<Buffer> {
        if (!fs.existsSync(filePath)) {
            throw new Error(`Artifact not found: ${filePath}`);
        }
        return fs.readFileSync(filePath);
    }

    async delete(filePath: string): Promise<void> {
        if (fs.existsSync(filePath)) {
            fs.unlinkSync(filePath);
        }
    }

    async list(runId: string): Promise<ArtifactInfo[]> {
        const runDir = path.join(this.baseDir, runId);
        if (!fs.existsSync(runDir)) {
            return [];
        }

        const files = fs.readdirSync(runDir);
        return files.map(filename => {
            const filePath = path.join(runDir, filename);
            const stats = fs.statSync(filePath);

            // 根据文件扩展名确定 kind
            let kind: string = 'log';
            if (filename.includes('checkpoint')) kind = 'checkpoint';
            else if (filename.endsWith('.bin')) kind = 'adapter';
            else if (filename.includes('eval')) kind = 'eval';
            else if (filename.includes('report')) kind = 'report';

            return {
                id: filename,
                kind: kind as any,
                name: filename,
                size: this.formatSize(stats.size),
                createdAt: stats.mtime.toISOString(),
            };
        });
    }

    getDownloadPath(filePath: string): string {
        return filePath;
    }

    private formatSize(bytes: number): string {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
        return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
    }
}
