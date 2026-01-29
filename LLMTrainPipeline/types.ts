export enum Status {
  Running = 'Running',
  Success = 'Success',
  Failed = 'Failed',
  Queued = 'Queued',
  Warning = 'Warning',
}

export interface Run {
  id: string;
  name: string;
  type: 'Fine-tuning' | 'Pre-training' | 'LoRA Adapter';
  status: Status;
  duration: string;
  startedAt: string;
  baseModel: string;
  dataset: string;
  metrics: {
    loss: number;
    passAt1: number;
    compileRate: number;
  };
  config: {
    lr: string;
    epochs: number;
    batchSize: number;
    loraRank?: number;
    loraAlpha?: number;
  };
  artifacts: string[];
}

export interface Model {
  id: string;
  name: string;
  backend: 'transformers' | 'vllm';
  source: 'HuggingFace' | 'Local';
  quantization: 'None' | '4-bit' | '8-bit';
  params: string;
  path: string;
  status: 'Valid' | 'Scanning' | 'Error';
  lastModified: string;
}

export interface Dataset {
  id: string;
  name: string;
  version: string;
  type: 'Train' | 'Eval';
  status: 'Active' | 'Ready' | 'Corrupt' | 'Processing';
  samples: number;
  format: 'JSONL' | 'Parquet';
  size: string;
  path: string;
  hash: string;
}

export interface Adapter {
  id: string;
  name: string;
  baseModel: string;
  trainDataset: string;
  rank: number;
  alpha: number;
  status: Status;
  created: string;
  metrics: {
    passAt1: number;
    compileRate: number;
  };
}

export interface FileScanEvent {
  id: string;
  path: string;
  status: 'Idle' | 'Scanning' | 'Error';
  message?: string;
  timestamp: string;
}

export interface Report {
  id: string;
  title: string;
  type: 'Run' | 'Comparison';
  date: string;
  format: 'HTML' | 'PDF';
  size: string;
}
