// API 客户端 - 连接后端服务
export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001/api';

// 通用 fetch 封装
async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options?.headers,
        },
    });

    if (!res.ok) {
        const error = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(error.error || 'API Error');
    }

    return res.json();
}

// ============== Dashboard ==============
export async function fetchDashboard() {
    return fetchApi<{
        systemHealth: string;
        activeRuns: number;
        queuedRuns: number;
        gpuUsage: string;
        storage: { used: string; free: string };
        recentRuns: any[];
    }>('/dashboard/overview');
}

// ============== Runs ==============
export async function fetchRuns(status?: string, limit?: number) {
    const params = new URLSearchParams();
    if (status && status !== 'All') params.append('status', status.toLowerCase());
    if (limit) params.append('limit', limit.toString());

    return fetchApi<any[]>(`/runs?${params.toString()}`);
}

export async function fetchRun(id: string) {
    return fetchApi<any>(`/runs/${id}`);
}

export async function createRun(data: {
    name: string;
    type: string;
    modelId: string;
    datasetId: string;
    evalDatasetId?: string;
    profileName?: string;
    config: any;
}) {
    return fetchApi<{ id: string }>('/runs', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function stopRun(id: string) {
    return fetchApi<{ success: boolean }>(`/runs/${id}/stop`, { method: 'POST' });
}

// ============== Queue Management ==============
export interface QueuedRunItem {
    id: string;
    name: string;
    type: string;
    queuePosition: number;
    createdAt: string;
    baseModel: string;
    dataset: string;
    config?: any;
}

export interface QueueResponse {
    activeRun: { id: string; name: string } | null;
    queue: QueuedRunItem[];
}

export async function fetchQueue() {
    return fetchApi<QueueResponse>('/runs/queue');
}

export async function reorderQueuedRun(id: string, position: number) {
    return fetchApi<{ success: boolean }>(`/runs/${id}/reorder`, {
        method: 'POST',
        body: JSON.stringify({ position }),
    });
}

export async function cancelQueuedRun(id: string) {
    return fetchApi<{ success: boolean; message: string }>(`/runs/${id}/cancel-queue`, {
        method: 'POST',
    });
}

export async function cloneRun(id: string) {
    return fetchApi<{ id: string; name: string }>(`/runs/${id}/clone`, { method: 'POST' });
}

export async function deleteRun(id: string) {
    return fetchApi<{ success: boolean }>(`/runs/${id}`, { method: 'DELETE' });
}

export async function createEvalRun(data: {
    name?: string;  // 可选的自定义名称
    modelId: string;
    adapterId?: string;
    datasetId: string;
    config: {
        evaluator: string;
        k: string;
        temperature: number;
        numSamples: number;
        timeout: number;
        maxTokens?: number;
        memoryLimit?: number;
        generateReport?: boolean;
        saveFailureCases?: boolean;
    };
}) {
    return fetchApi<{ id: string }>('/runs', {
        method: 'POST',
        body: JSON.stringify({
            name: data.name || `eval-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}`,
            type: 'evaluation',
            modelId: data.modelId,
            adapterId: data.adapterId,
            datasetId: data.datasetId,
            config: data.config,
        }),
    });
}

export async function fetchRunMetrics(id: string) {
    return fetchApi<any[]>(`/runs/${id}/metrics`);
}

export async function fetchRunEval(id: string) {
    return fetchApi<any>(`/runs/${id}/eval`);
}

export async function fetchRunArtifacts(id: string) {
    return fetchApi<any[]>(`/runs/${id}/artifacts`);
}

// SSE 日志流
export function connectRunLogs(id: string, onEvent: (event: any) => void): EventSource {
    const eventSource = new EventSource(`${API_BASE}/runs/${id}/logs/stream`);

    eventSource.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            onEvent(data);
        } catch { }
    };

    return eventSource;
}

// ============== Models ==============
export async function fetchModels() {
    return fetchApi<any[]>('/models');
}

export async function rescanModels() {
    return fetchApi<{ success: boolean; added: number; updated: number }>('/models/rescan', { method: 'POST' });
}

export async function deleteModel(id: string) {
    return fetchApi<{ success: boolean }>(`/models/${id}`, { method: 'DELETE' });
}

// ============== Datasets ==============
export async function fetchDatasets() {
    return fetchApi<any[]>('/datasets');
}

export async function rescanDatasets() {
    return fetchApi<{ success: boolean; added: number; updated: number }>('/datasets/rescan', { method: 'POST' });
}

export async function fetchDatasetPreview(id: string) {
    return fetchApi<any>(`/datasets/${id}/preview`);
}

export async function deleteDataset(id: string) {
    return fetchApi<{ success: boolean }>(`/datasets/${id}`, { method: 'DELETE' });
}

// ============== Adapters ==============
export async function fetchAdapters() {
    return fetchApi<any[]>('/adapters');
}

export async function rescanAdapters() {
    return fetchApi<{ success: boolean; added: number; updated: number }>('/adapters/rescan', { method: 'POST' });
}

export async function deleteAdapter(id: string) {
    return fetchApi<{ success: boolean }>(`/adapters/${id}`, { method: 'DELETE' });
}

export function mergeAdapter(id: string, outputName?: string): EventSource {
    const params = new URLSearchParams();
    if (outputName) params.append('outputName', outputName);

    // Use EventSource for SSE but we need POST, so use fetch with streaming
    const eventSource = {
        onmessage: null as ((event: { data: string }) => void) | null,
        onerror: null as ((error: any) => void) | null,
        close: () => { },
        readyState: 0,
    };

    const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001/api';

    fetch(`${API_BASE}/adapters/${id}/merge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ outputName }),
    }).then(async response => {
        const reader = response.body?.getReader();
        if (!reader) return;

        const decoder = new TextDecoder();
        let buffer = '';

        eventSource.readyState = 1;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (eventSource.onmessage) {
                        eventSource.onmessage({ data });
                    }
                }
            }
        }
        eventSource.readyState = 2;
    }).catch(error => {
        if (eventSource.onerror) {
            eventSource.onerror(error);
        }
    });

    return eventSource as unknown as EventSource;
}

// ============== Compare ==============
export async function compareRuns(baseRunId: string, candidateRunId: string) {
    return fetchApi<{
        metrics: any;
        configDiff: any[];
        regressions: any[];
    }>('/compare', {
        method: 'POST',
        body: JSON.stringify({ baseRunId, candidateRunId }),
    });
}

// ============== Reports ==============
export async function fetchReports() {
    return fetchApi<any[]>('/reports');
}

export async function fetchReport(id: string) {
    return fetchApi<any>(`/reports/${id}`);
}

export async function fetchReportPreview(id: string) {
    return fetchApi<any>(`/reports/${id}/preview`);
}

export async function generateReport(data: { runId?: string; title?: string; format?: string }) {
    return fetchApi<{ id: string }>('/reports/generate', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function updateReport(id: string, data: { title?: string }) {
    return fetchApi<{ success: boolean }>(`/reports/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    });
}

export async function deleteReport(id: string) {
    return fetchApi<{ success: boolean }>(`/reports/${id}`, {
        method: 'DELETE',
    });
}

export function getReportDownloadUrl(id: string) {
    return `${API_BASE}/reports/${id}/download`;
}

// ============== Academic Reports ==============
export interface AcademicReport {
    runId: string;
    runName: string;
    startTime: string;
    endTime: string;
    duration: string;
    seed: number | null;
    gitCommit: string | null;
    environment: {
        os: string | null;
        python: string | null;
        pytorch: string | null;
        transformers: string | null;
        trl: string | null;
        cuda: string | null;
    };
    hardware: {
        gpu: string | null;
        gpuMemory: string | null;
        cpu: string | null;
        ram: string | null;
    };
    model: {
        name: string;
        params: string;
        quantization: string;
    };
    training: {
        batchSize: number;
        effectiveBatchSize: number;
        learningRate: string;
        epochs: number;
    };
    lora: {
        enabled: boolean;
        rank: number | null;
        alpha: number | null;
        trainableParams: string | null;
        trainablePercent: string | null;
    };
    trainingStats: {
        totalSteps: number | null;
        totalTokens: number | null;
        tokensPerSecond: number | null;
        gpuHours: number | null;
    };
    evaluation: {
        passAt1: number | null;
        passAt5: number | null;
        passAt10: number | null;
        compileRate: number | null;
        errorStats: {
            syntaxErrorRate: number | null;
            runtimeErrorRate: number | null;
            timeoutRate: number | null;
        };
    };
}

export async function fetchAcademicReport(runId: string) {
    return fetchApi<AcademicReport>(`/reports/academic/${runId}`);
}

export async function generateAcademicReport(data: {
    runId: string;
    format?: 'html' | 'markdown';
    title?: string;
}) {
    return fetchApi<{ id: string; title: string; format: string; content: string }>('/reports/generate-academic', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export function getAcademicReportDownloadUrl(runId: string, format: 'html' | 'markdown' = 'html') {
    return `${API_BASE}/reports/academic/${runId}/download?format=${format}`;
}

// ============== Settings ==============
export async function fetchSettings() {
    return fetchApi<any>('/settings');
}

export async function updateSettings(data: any) {
    return fetchApi<{ success: boolean }>('/settings', {
        method: 'PUT',
        body: JSON.stringify(data),
    });
}

// ============== Config ==============
export async function fetchResolvedConfig(runId?: string) {
    const query = runId ? `?runId=${runId}` : '';
    return fetchApi<any>(`/config/resolved${query}`);
}

// ============== Playground ==============
export async function inferPlayground(data: {
    modelId: string;
    adapterId?: string;
    systemPrompt: string;
    messages: { role: string; content: string }[];
    temperature?: number;
    maxTokens?: number;
}) {
    // Legacy support or full response if needed
    return fetchApi<{ content: string; tokensUsed: number }>('/playground/infer', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function inferPlaygroundStream(data: {
    modelId: string;
    adapterId?: string;
    systemPrompt: string;
    messages: { role: string; content: string }[];
    temperature?: number;
    maxTokens?: number;
}) {
    const response = await fetch(`${API_BASE}/playground/infer`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: response.statusText }));
        throw new Error(error.error || 'Inference request failed');
    }

    return response;
}

// ============== Files ==============
export interface FileItem {
    name: string;
    path: string;
    isDirectory: boolean;
    size: string | null;
    ext: string | null;
}

export interface BrowseResult {
    currentPath: string;
    parent: string | null;
    items: FileItem[];
}

export async function browseFiles(path?: string, filter?: string) {
    const params = new URLSearchParams();
    if (path) params.append('path', path);
    if (filter) params.append('filter', filter);

    return fetchApi<BrowseResult>(`/files/browse?${params.toString()}`);
}

export async function getDrives() {
    return fetchApi<{ drives: string[] }>('/files/drives');
}

export async function getQuickPaths() {
    return fetchApi<{ paths: { name: string; path: string }[] }>('/files/quickPaths');
}

export async function importDataset(filePath: string, name?: string, type?: 'Train' | 'Eval') {
    return fetchApi<{ id: string; status: string }>('/datasets/import', {
        method: 'POST',
        body: JSON.stringify({ path: filePath, name, type }),
    });
}

export async function importModel(folderPath: string, name?: string) {
    return fetchApi<{ id: string; name: string; status: string }>('/models/import', {
        method: 'POST',
        body: JSON.stringify({ path: folderPath, name }),
    });
}

export interface NativeDialogResult {
    selected: boolean;
    path: string | null;
    name?: string;
    isDirectory?: boolean;
    cancelled?: boolean;
    error?: string;
}

export async function openNativeDialog(mode: 'file' | 'folder', options?: {
    filter?: string;
    title?: string;
}) {
    return fetchApi<NativeDialogResult>('/files/openNativeDialog', {
        method: 'POST',
        body: JSON.stringify({
            mode,
            filter: options?.filter,
            title: options?.title,
        }),
    });
}

// ============== Notifications ==============
export interface Notification {
    id: string;
    type: 'run_completed' | 'run_failed' | 'resource_alert';
    title: string;
    message: string;
    runId: string | null;
    isRead: boolean;
    createdAt: string;
    readAt: string | null;
}

export async function fetchNotifications(limit?: number) {
    const params = new URLSearchParams();
    if (limit) params.append('limit', limit.toString());
    return fetchApi<Notification[]>(`/notifications?${params.toString()}`);
}

export async function fetchUnreadCount() {
    return fetchApi<{ count: number }>('/notifications/unread-count');
}

export async function markNotificationRead(id: string) {
    return fetchApi<{ success: boolean }>(`/notifications/${id}/read`, { method: 'POST' });
}

export async function markAllNotificationsRead() {
    return fetchApi<{ success: boolean; count: number }>('/notifications/read-all', { method: 'POST' });
}

export async function deleteNotification(id: string) {
    return fetchApi<{ success: boolean }>(`/notifications/${id}`, { method: 'DELETE' });
}


