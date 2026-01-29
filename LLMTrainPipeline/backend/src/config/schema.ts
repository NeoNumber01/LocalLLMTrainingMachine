import { z } from 'zod';

// Training config Schema
export const TrainingConfigSchema = z.object({
    // Basic training parameters
    lr: z.string().default('2e-4'),
    epochs: z.number().int().min(1).default(3),
    batchSize: z.number().int().min(1).default(1),
    optimizer: z.enum(['adamw_torch', 'adamw_bnb_8bit', 'paged_adamw_8bit', 'sgd']).default('paged_adamw_8bit'),
    scheduler: z.enum(['cosine', 'linear', 'constant', 'cosine_with_restarts', 'polynomial']).default('cosine'),
    warmupRatio: z.number().min(0).max(1).default(0.03),
    weightDecay: z.number().min(0).default(0.01),
    maxSeqLen: z.number().int().min(128).default(512),
    gradAccum: z.number().int().min(1).default(8),
    precision: z.enum(['bf16', 'fp16', 'fp32', 'none']).default('none'),

    // Core training parameters (new)
    seed: z.number().int().default(42),
    loggingSteps: z.number().int().min(1).default(10),
    saveSteps: z.number().int().min(1).default(100),
    saveTotalLimit: z.number().int().min(1).default(3),
    gradientClipping: z.number().min(0).default(1.0),

    // Warmup configuration (new)
    warmupType: z.enum(['ratio', 'steps']).default('ratio'),
    warmupSteps: z.number().int().min(0).default(0),

    // Validation configuration (new)
    evalStrategy: z.enum(['no', 'steps', 'epoch']).default('epoch'),
    evalSteps: z.number().int().min(1).default(200),

    // Advanced training options (new)
    earlyStoppingEnabled: z.boolean().default(false),
    earlyStoppingPatience: z.number().int().min(1).default(3),
    earlyStoppingThreshold: z.number().min(0).default(0.0),
    loadBestModelAtEnd: z.boolean().default(true),
    metricForBestModel: z.string().default('loss'),
});

// LoRA config Schema
export const LoraConfigSchema = z.object({
    enabled: z.boolean().default(true),
    rank: z.number().int().min(1).default(16),
    alpha: z.number().int().min(1).default(32),
    targetModules: z.array(z.string()).default(['q_proj', 'v_proj']),
    quantization: z.enum(['4bit', '8bit', 'none']).default('4bit'),
    // LoRA extended parameters (new)
    dropout: z.number().min(0).max(1).default(0.05),
    bias: z.enum(['none', 'all', 'lora_only']).default('none'),
});

// Eval config Schema
export const EvalConfigSchema = z.object({
    evaluator: z.enum(['pass_at_k', 'perplexity', 'accuracy']).default('pass_at_k'),
    k: z.string().default('1,5,10'),
    temperature: z.number().min(0).max(2).default(0.2),
    samples: z.number().int().min(1).default(20),
    numSamples: z.number().int().min(1).optional(),  // User-configured sample count
    timeout: z.number().int().min(1).default(10),
    maxTokens: z.number().int().min(64).default(256),
    memoryLimit: z.number().int().min(256).optional(),  // Memory limit (MB)
    generateReport: z.boolean().optional(),  // Whether to generate academic report
    saveFailureCases: z.boolean().optional(),  // Whether to save failure cases

    // Feature flags for extended evaluation
    enableFuzzing: z.boolean().default(false),
    fuzzingRuns: z.number().int().min(10).default(50),
    enableConsistency: z.boolean().default(false),
    consistencyRuns: z.number().int().min(3).default(5),
    enableComplexityTest: z.boolean().default(false),
    complexityScales: z.array(z.number()).default([100, 1000, 10000]),
    enableCodeQuality: z.boolean().default(true),
    // Max test cases per problem (limit long test sets, speed up evaluation)
    maxTestsPerProblem: z.number().int().min(1).default(10),
});

// Provider config Schema
export const ProvidersConfigSchema = z.object({
    compute: z.enum(['local_single', 'local_multi_fsdp']).default('local_single'),
    trainer: z.enum(['lora', 'full_finetune']).default('lora'),
    eval: z.enum(['code_passk']).default('code_passk'),
    artifactStore: z.enum(['filesystem', 's3']).default('filesystem'),
    cache: z.enum(['memory_ttl', 'sqlite_cache']).default('memory_ttl'),
});

// Storage config Schema
export const StorageConfigSchema = z.object({
    baseDir: z.string().default('./storage'),
    modelsDir: z.string().default('./storage/models'),
    datasetsDir: z.string().default('./storage/datasets'),
    trainDatasetsDir: z.string().default('./storage/train_datasets'),
    evalDatasetsDir: z.string().default('./storage/eval_datasets'),
    adaptersDir: z.string().default('./storage/adapters'),
    artifactsDir: z.string().default('./storage/artifacts'),
    reportsDir: z.string().default('./storage/reports'),
});

// Cache config Schema
export const CacheConfigSchema = z.object({
    ttlSeconds: z.number().int().min(0).default(300),
});

// Complete config Schema
export const ConfigSchema = z.object({
    training: TrainingConfigSchema.default({}),
    lora: LoraConfigSchema.default({}),
    eval: EvalConfigSchema.default({}),
    providers: ProvidersConfigSchema.default({}),
    storage: StorageConfigSchema.default({}),
    cache: CacheConfigSchema.default({}),
});

// Type exports
export type TrainingConfig = z.infer<typeof TrainingConfigSchema>;
export type LoraConfig = z.infer<typeof LoraConfigSchema>;
export type EvalConfig = z.infer<typeof EvalConfigSchema>;
export type ProvidersConfig = z.infer<typeof ProvidersConfigSchema>;
export type StorageConfig = z.infer<typeof StorageConfigSchema>;
export type CacheConfig = z.infer<typeof CacheConfigSchema>;
export type Config = z.infer<typeof ConfigSchema>;
