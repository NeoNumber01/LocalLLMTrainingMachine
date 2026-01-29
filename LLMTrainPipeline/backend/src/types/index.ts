// === Run Types ===
export type RunType = 'finetune' | 'pretrain' | 'lora';
export type RunStatus = 'queued' | 'running' | 'success' | 'failed' | 'stopped' | 'warning';

export interface RunConfig {
    lr: string;
    epochs: number;
    batchSize: number;
    useLora?: boolean;
    loraRank?: number;
    loraAlpha?: number;
    loraTargetModules?: string[];
    optimizer?: string;
    scheduler?: string;
    warmupRatio?: number;
    weightDecay?: number;
    maxSeqLen?: number;
    gradAccum?: number;
    precision?: string;
    quantization?: string;
    evaluator?: string;
    evalK?: string;
    evalTemp?: number;
    evalSamples?: number;
    evalTimeout?: number;
}

export interface CreateRunDto {
    name: string;
    type: RunType;
    modelId: string;
    datasetId: string;
    evalDatasetId?: string;
    adapterId?: string;  // 用于评测时指定使用的 adapter
    sourceRunId?: string;  // ID of the training run this eval is based on
    profileName?: string;
    config: Partial<RunConfig>;
}

export interface RunMetrics {
    loss: number;
    passAt1: number;
    compileRate: number;
}

export interface RunResponse {
    id: string;
    name: string;
    type: string;
    status: RunStatus;
    duration: string | null;
    startedAt: string | null;
    createdAt: string;
    baseModel: string;
    dataset: string;
    metrics: RunMetrics;
    config: RunConfig;
    artifacts: string[];
    evalResult?: EvalResultResponse;
}

// Comprehensive evaluation result
export interface EvalResultResponse {
    passAt1: number;
    compileRate: number;
    passAtK: Record<string, number>;

    errorStats?: {
        syntaxErrorRate: number;
        runtimeErrorRate: number;
        timeoutRate: number;
        invalidOutputRate: number;
        assertionErrorRate: number;
        importErrorRate: number;
        memoryErrorRate: number;
    };

    timeStats?: {
        meanRuntimeMs: number;
        p50RuntimeMs: number;
        p95RuntimeMs: number;
        maxRuntimeMs: number;
        tleRate: number;
    };

    segmentStats?: {
        byDifficulty: Record<string, { count: number; pass_at_1: number; compile_rate: number }>;
        byCategory: Record<string, { count: number; pass_at_1: number; compile_rate: number }>;
    };

    codeQuality?: {
        avgCodeLength: number;
        avgLineCount: number;
        extraIORate: number;
        interfaceComplianceRate: number;
    };

    failures: Array<{
        taskId: string;
        prompt: string;
        output: string;
        errorType: string;
        error: string;
        executionTimeMs?: number;
    }>;

    totalProblems?: number;
    totalSamples?: number;
    totalPassed?: number;
    totalCompiled?: number;
}

// === Model Types ===
export type ModelBackend = 'transformers' | 'vllm';
export type ModelSource = 'HuggingFace' | 'Local';
export type ModelQuantization = 'None' | '4-bit' | '8-bit';
export type ModelStatus = 'Valid' | 'Scanning' | 'Error';

export interface ModelResponse {
    id: string;
    name: string;
    backend: ModelBackend;
    source: ModelSource;
    quantization: ModelQuantization;
    params: string;
    path: string;
    status: ModelStatus;
    lastModified: string;
}

// === Dataset Types ===
export type DatasetType = 'Train' | 'Eval';
export type DatasetStatus = 'Active' | 'Ready' | 'Corrupt' | 'Processing';
export type DatasetFormat = 'JSONL' | 'Parquet';

export interface DatasetResponse {
    id: string;
    name: string;
    version: string;
    type: DatasetType;
    status: DatasetStatus;
    samples: number;
    format: DatasetFormat;
    size: string;
    path: string;
    hash: string;
}

export interface DatasetPreview {
    schema: { field: string; valid: boolean }[];
    stats: {
        totalTokens: string;
        avgLength: number;
        duplicates: string;
        emptyRows: number;
    };
    samples: Array<{ prompt: string; completion: string }>;
}

// === Adapter Types ===
export interface AdapterResponse {
    id: string;
    name: string;
    baseModel: string;
    trainDataset: string;
    rank: number;
    alpha: number;
    status: string;
    created: string;
    metrics: {
        passAt1: number;
        compileRate: number;
    };
}

// === Compare Types ===
export interface CompareRequest {
    baseRunId: string;
    candidateRunId: string;
}

export interface MetricDelta {
    base: number | null;
    candidate: number | null;
    delta: number | null;
}

export interface ConfigDiffItem {
    param: string;
    base: string | number | null;
    candidate: string | number | null;
}

export interface RegressionItem {
    prompt: string;
    baseOutput: string;
    baseResult: 'pass' | 'fail';
    candidateOutput: string;
    candidateResult: 'pass' | 'fail';
}

export interface CompareResponse {
    metrics: Record<string, MetricDelta>;
    configDiff: ConfigDiffItem[];
    regressions: RegressionItem[];
    history?: {
        base: MetricEvent[];
        candidate: MetricEvent[];
    };
}

// === Dashboard Types ===
export type SystemHealth = 'Healthy' | 'Warning' | 'Error';

export interface DashboardOverview {
    systemHealth: SystemHealth;
    activeRuns: number;
    queuedRuns: number;
    gpuUsage: string;
    storage: {
        used: string;
        free: string;
    };
    recentRuns: RunResponse[];
}

// === Report Types ===
export type ReportType = 'Run' | 'Comparison';
export type ReportFormat = 'HTML' | 'PDF';

export interface ReportResponse {
    id: string;
    title: string;
    type: ReportType;
    date: string;
    format: ReportFormat;
    size: string;
}

export interface GenerateReportRequest {
    runId?: string;
    compareRequest?: CompareRequest;
    format: ReportFormat;
}

// === Settings Types ===
export interface WatchFolders {
    models: string;
    datasets: string;
    adapters: string;
}

export interface ComputeSettings {
    maxSimultaneousRuns: number;
    gpuStrategy: 'DDP' | 'FSDP' | 'DeepSpeed';
}

export interface NotificationSettings {
    runCompletion: boolean;
    resourceAlerts: boolean;
}

export interface StorageSettings {
    checkpointRetention: number;  // 0 = keep all, N = keep last N
}

export interface SettingsResponse {
    watchFolders: WatchFolders;
    compute: ComputeSettings;
    notifications: NotificationSettings;
    storage: StorageSettings;
}

export interface UpdateSettingsDto {
    watchFolders?: Partial<WatchFolders>;
    compute?: Partial<ComputeSettings>;
    notifications?: Partial<NotificationSettings>;
    storage?: Partial<StorageSettings>;
}

// === Artifact Types ===
export type ArtifactKind = 'checkpoint' | 'log' | 'eval' | 'adapter' | 'report';

export interface ArtifactInfo {
    id: string;
    kind: ArtifactKind;
    name: string;
    size: string;
    createdAt: string;
}

// === SSE Event Types ===
export interface LogEvent {
    type: 'log';
    timestamp: string;
    level: 'info' | 'warning' | 'error';
    message: string;
}

export interface MetricEvent {
    type: 'metric';
    timestamp: string;
    step: number;
    loss?: number;
    lr?: number;
    gradNorm?: number;
}

export interface StatusEvent {
    type: 'status';
    status: RunStatus;
}

export interface ProgressEvent {
    type: 'progress';
    timestamp: string;
    completed: number;
    total: number;
    percent: number;
}

export type SSEEvent = LogEvent | MetricEvent | StatusEvent | ProgressEvent;

// === Playground Types ===
export interface InferRequest {
    modelId: string;
    adapterId?: string;
    systemPrompt: string;
    messages: Array<{ role: 'user' | 'assistant'; content: string }>;
    temperature?: number;
    maxTokens?: number;
    quantization?: '4bit' | '8bit' | 'none';
}

export interface InferResponse {
    content: string;
    tokensUsed: number;
}
