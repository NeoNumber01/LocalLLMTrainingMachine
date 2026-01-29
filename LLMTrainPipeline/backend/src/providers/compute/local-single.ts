import { ComputeProvider } from '../interfaces.js';

export class LocalSingleCompute implements ComputeProvider {
    name = 'local_single';

    async prepare(): Promise<void> {
        console.log('[LocalSingleCompute] Preparing single GPU environment...');
        // In actual implementation would check GPU availability etc.
    }

    async execute(runId: string): Promise<void> {
        console.log(`[LocalSingleCompute] Executing run ${runId} on single GPU...`);
        // In actual implementation would start training process
    }

    async cleanup(): Promise<void> {
        console.log('[LocalSingleCompute] Cleaning up resources...');
        // In actual implementation would release GPU resources etc.
    }
}
