import { getConfig, Config } from '../config/index.js';
import {
    ComputeProvider,
    TrainerProvider,
    EvalProvider,
    ArtifactStore,
    CacheProvider,
    Scanner,
} from './interfaces.js';

// Provider 实现导入
import { LocalSingleCompute } from './compute/local-single.js';
import { LoraTrainer } from './trainer/lora.js';
import { FullFinetuneTrainer } from './trainer/full-finetune.js';
import { CodePassKEval } from './eval/code-passk.js';
import { FilesystemStore } from './artifact-store/filesystem.js';
import { MemoryTtlCache } from './cache/memory-ttl.js';
import { SqliteCacheProvider } from './cache/sqlite-cache.js';
import { FileScanner } from './scanner/index.js';

export class ProviderFactory {
    private config: Config;

    constructor(config?: Config) {
        this.config = config || getConfig();
    }

    getComputeProvider(): ComputeProvider {
        switch (this.config.providers.compute) {
            case 'local_single':
                return new LocalSingleCompute();
            case 'local_multi_fsdp':
                // 占位实现，暂时返回单 GPU
                console.warn('local_multi_fsdp not implemented, falling back to local_single');
                return new LocalSingleCompute();
            default:
                throw new Error(`Unknown compute provider: ${this.config.providers.compute}`);
        }
    }

    getTrainerProvider(): TrainerProvider {
        switch (this.config.providers.trainer) {
            case 'lora':
                return new LoraTrainer(this.config);
            case 'full_finetune':
                return new FullFinetuneTrainer(this.config);
            default:
                throw new Error(`Unknown trainer provider: ${this.config.providers.trainer}`);
        }
    }

    getEvalProvider(): EvalProvider {
        switch (this.config.providers.eval) {
            case 'code_passk':
                return new CodePassKEval(this.config);
            default:
                throw new Error(`Unknown eval provider: ${this.config.providers.eval}`);
        }
    }

    getArtifactStore(): ArtifactStore {
        switch (this.config.providers.artifactStore) {
            case 'filesystem':
                return new FilesystemStore(this.config.storage.artifactsDir);
            case 's3':
                // 占位实现
                console.warn('S3 store not implemented, falling back to filesystem');
                return new FilesystemStore(this.config.storage.artifactsDir);
            default:
                throw new Error(`Unknown artifact store: ${this.config.providers.artifactStore}`);
        }
    }

    getCacheProvider(): CacheProvider {
        switch (this.config.providers.cache) {
            case 'memory_ttl':
                return new MemoryTtlCache(this.config.cache.ttlSeconds);
            case 'sqlite_cache':
                return new SqliteCacheProvider();
            default:
                throw new Error(`Unknown cache provider: ${this.config.providers.cache}`);
        }
    }

    getScanner(): Scanner {
        return new FileScanner();
    }
}

// 导出便捷函数
let defaultFactory: ProviderFactory | null = null;

export function getProviderFactory(config?: Config): ProviderFactory {
    if (!defaultFactory || config) {
        defaultFactory = new ProviderFactory(config);
    }
    return defaultFactory;
}

export * from './interfaces.js';
