import { ComputeProvider } from '../interfaces.js';

export class LocalSingleCompute implements ComputeProvider {
    name = 'local_single';

    async prepare(): Promise<void> {
        console.log('[LocalSingleCompute] Preparing single GPU environment...');
        // 实际实现中会检查 GPU 可用性等
    }

    async execute(runId: string): Promise<void> {
        console.log(`[LocalSingleCompute] Executing run ${runId} on single GPU...`);
        // 实际实现中会启动训练进程
    }

    async cleanup(): Promise<void> {
        console.log('[LocalSingleCompute] Cleaning up resources...');
        // 实际实现中会释放 GPU 资源等
    }
}
