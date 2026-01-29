import type { Config } from '../config/index.js';
import type { ArtifactInfo } from '../types/index.js';

// Re-export for convenience
export type { ArtifactInfo } from '../types/index.js';

// === Compute Provider ===
export interface ComputeProvider {
    name: string;
    prepare(): Promise<void>;
    execute(runId: string): Promise<void>;
    cleanup(): Promise<void>;
}

// === Trainer Provider ===
export interface TrainConfig {
    runId: string;
    modelPath: string;
    datasetPath: string;
    evalDatasetPath?: string;
    outputDir: string;
    config: Config;
}

export interface TrainEvent {
    type: 'log' | 'metric' | 'checkpoint' | 'complete' | 'error' | 'experiment_log' | 'eval_log' | 'data_quality' | 'training_summary';
    timestamp: Date;
    data: any;
}

export interface TrainerProvider {
    name: string;
    train(config: TrainConfig): AsyncGenerator<TrainEvent>;
    stop?(): void;
}

// === Eval Provider ===
export interface EvalConfig {
    runId: string;
    modelPath: string;
    adapterPath?: string;
    datasetPath: string;
    config: Config;
}

// Error classification statistics
export interface ErrorStats {
    syntaxErrorRate: number;
    runtimeErrorRate: number;
    timeoutRate: number;
    invalidOutputRate: number;
    assertionErrorRate: number;
    importErrorRate: number;
    memoryErrorRate: number;
}

// Execution time statistics
export interface TimeStats {
    meanRuntimeMs: number;
    p50RuntimeMs: number;
    p95RuntimeMs: number;
    maxRuntimeMs: number;
    tleRate: number;
}

// Segment result (for difficulty/category breakdown)
export interface SegmentResult {
    count: number;
    pass_at_1: number;
    compile_rate: number;
}

// Code quality statistics
export interface CodeQualityStats {
    avgCodeLength: number;
    avgLineCount: number;
    extraIORate: number;
    interfaceComplianceRate: number;
}

// Robustness testing statistics
export interface RobustnessStats {
    fuzzPassRate: number;
    boundaryPassRate: number;
}

// Self-consistency statistics
export interface ConsistencyStats {
    selfConsistencyRate: number;
    variance: number;
}

// Failure case details
export interface FailureCase {
    taskId: string;
    prompt: string;
    output: string;
    errorType: string;
    error: string;
    executionTimeMs?: number;
}

export interface EvalResult {
    // Basic metrics
    passAt1: number;
    compileRate: number;
    passAtK: Record<string, number>;

    // Error classification (new)
    errorStats?: ErrorStats;

    // Time statistics (new)
    timeStats?: TimeStats;

    // Segment statistics (new)
    segmentStats?: {
        byDifficulty: Record<string, SegmentResult>;
        byCategory: Record<string, SegmentResult>;
    };

    // Code quality (new)
    codeQuality?: CodeQualityStats;

    // Robustness (new, optional)
    robustness?: RobustnessStats;

    // Consistency (new, optional)
    consistency?: ConsistencyStats;

    // Failures (enhanced)
    failures: FailureCase[];

    // Meta info (new)
    totalProblems?: number;
    totalSamples?: number;
    totalPassed?: number;
    totalCompiled?: number;
}

// Evaluation event types (for real-time progress)
export interface EvalEvent {
    type: 'log' | 'progress' | 'metric' | 'complete' | 'error';
    timestamp: Date;
    data: any;
}

export interface EvalProvider {
    name: string;
    evaluate(config: EvalConfig): Promise<EvalResult>;
    // New streaming evaluation method
    evaluateStream?(config: EvalConfig): AsyncGenerator<EvalEvent, EvalResult, unknown>;
    // Stop method for canceling evaluation
    stop?(): void;
}

// === Artifact Store ===
export interface ArtifactStore {
    name: string;
    save(runId: string, kind: string, filename: string, data: Buffer): Promise<string>;
    get(path: string): Promise<Buffer>;
    delete(path: string): Promise<void>;
    list(runId: string): Promise<ArtifactInfo[]>;
    getDownloadPath(path: string): string;
}

// === Cache Provider ===
export interface CacheProvider {
    name: string;
    get<T>(key: string): Promise<T | null>;
    set<T>(key: string, value: T, ttlSeconds?: number): Promise<void>;
    delete(key: string): Promise<void>;
    clear(): Promise<void>;
}

// === Scanner ===
export interface ScanResult {
    added: number;
    updated: number;
    removed: number;
    errors: string[];
}

export interface Scanner {
    scanModels(directory: string): Promise<ScanResult>;
    scanDatasets(directory: string, datasetType?: 'Train' | 'Eval'): Promise<ScanResult>;
    scanAdapters(directory: string): Promise<ScanResult>;
}
