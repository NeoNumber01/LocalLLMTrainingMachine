import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchRun, fetchRunArtifacts, stopRun, connectRunLogs } from '../lib/api';

interface LogEntry {
    timestamp: string;
    level: string;
    message: string;
}

interface ProgressData {
    completed: number;
    total: number;
    percent: number;
}

const EvalDetail: React.FC = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [run, setRun] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [progress, setProgress] = useState<ProgressData | null>(null);
    const [artifacts, setArtifacts] = useState<any[]>([]);
    const [activeTab, setActiveTab] = useState<'logs' | 'results' | 'failures'>('logs');
    const logsEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!id) return;

        // Load run details
        fetchRun(id)
            .then(data => {
                setRun(data);
                // If run is already complete, show results tab by default
                if (data.status === 'success' || data.status === 'failed') {
                    setActiveTab('results');
                }
            })
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));

        // Load artifacts
        fetchRunArtifacts(id)
            .then(setArtifacts)
            .catch(console.error);

        // Connect to SSE logs
        const eventSource = connectRunLogs(id, (event) => {
            if (event.type === 'log') {
                setLogs(prev => [...prev.slice(-500), {
                    timestamp: event.timestamp,
                    level: event.level,
                    message: event.message,
                }]);
            } else if (event.type === 'progress') {
                setProgress({
                    completed: event.completed,
                    total: event.total,
                    percent: event.percent,
                });
            } else if (event.type === 'status') {
                // Refresh run data when status changes
                fetchRun(id).then(setRun).catch(console.error);
            }
        });

        return () => eventSource.close();
    }, [id]);

    // Auto-scroll logs
    useEffect(() => {
        if (logsEndRef.current) {
            logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [logs]);

    // Refresh run data periodically while running
    useEffect(() => {
        if (!id || run?.status !== 'running') return;

        const interval = setInterval(() => {
            fetchRun(id).then(setRun).catch(console.error);
        }, 5000);

        return () => clearInterval(interval);
    }, [id, run?.status]);

    const handleStop = async () => {
        if (!id) return;
        try {
            await stopRun(id);
            const updated = await fetchRun(id);
            setRun(updated);
        } catch (e) {
            console.error(e);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
        );
    }

    if (error || !run) {
        return (
            <div className="flex items-center justify-center h-full text-error">
                <div className="text-center">
                    <p className="text-lg font-semibold">Loading Failed</p>
                    <p className="text-sm text-gray-400 mt-1">{error || 'Evaluation not found'}</p>
                    <button onClick={() => navigate('/evaluation')} className="mt-4 px-4 py-2 bg-primary rounded-lg text-sm">Back</button>
                </div>
            </div>
        );
    }

    const runStatus = run.status || 'unknown';
    const evalResult = run.evalResult;

    return (
        <div className="flex flex-col h-full bg-background">
            {/* Header */}
            <div className="px-6 py-4 border-b border-border bg-surface shrink-0">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                        <button onClick={() => navigate('/evaluation')} className="text-gray-500 hover:text-white">
                            <span className="material-symbols-outlined">arrow_back</span>
                        </button>
                        <div>
                            <h1 className="text-xl font-bold text-white flex items-center gap-2">
                                <span className="material-symbols-outlined text-purple-400">science</span>
                                {run.name}
                            </h1>
                            <div className="text-[10px] text-gray-500 font-mono mt-0.5">ID: {run.id}</div>
                        </div>
                        <div className={`ml-2 px-2 py-0.5 rounded text-xs font-bold uppercase border flex items-center gap-1.5 ${runStatus === 'running' ? 'bg-primary/10 text-primary border-primary/20' :
                            runStatus === 'success' ? 'bg-success/10 text-success border-success/20' :
                                runStatus === 'failed' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                                    'bg-gray-800 text-gray-400 border-gray-700'
                            }`}>
                            {runStatus === 'running' && <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>}
                            {runStatus}
                        </div>
                    </div>
                    <div className="flex gap-2">
                        {runStatus === 'running' && (
                            <button
                                onClick={handleStop}
                                className="px-3 py-1.5 rounded-md bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium hover:bg-red-500/20 flex items-center gap-1"
                            >
                                <span className="material-symbols-outlined text-[14px]">stop</span> Stop
                            </button>
                        )}
                        {runStatus === 'success' && (
                            <button
                                onClick={() => navigate(`/reports?runId=${run.id}`)}
                                className="px-3 py-1.5 rounded-md bg-primary/10 border border-primary/20 text-primary text-xs font-medium hover:bg-primary/20 flex items-center gap-1"
                            >
                                <span className="material-symbols-outlined text-[14px]">download</span> Report
                            </button>
                        )}
                    </div>
                </div>

                {/* Progress Bar (when running) */}
                {runStatus === 'running' && progress && (
                    <div className="mb-4">
                        <div className="flex justify-between text-xs text-gray-400 mb-1">
                            <span>Evaluating problems...</span>
                            <span>{progress.completed} / {progress.total} ({progress.percent.toFixed(1)}%)</span>
                        </div>
                        <div className="w-full bg-black/30 rounded-full h-2 overflow-hidden">
                            <div
                                className="h-full bg-primary transition-all duration-300"
                                style={{ width: `${progress.percent}%` }}
                            ></div>
                        </div>
                    </div>
                )}

                {/* Key Metrics Summary */}
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 text-xs text-gray-400 font-mono bg-black/20 p-3 rounded-lg border border-border">
                    <div><span className="text-gray-600 block mb-0.5 uppercase font-bold text-[10px]">Model</span>{run.baseModel}</div>
                    <div><span className="text-gray-600 block mb-0.5 uppercase font-bold text-[10px]">Dataset</span>{run.dataset}</div>
                    <div><span className="text-gray-600 block mb-0.5 uppercase font-bold text-[10px]">Duration</span>{run.duration || '-'}</div>
                    <div><span className="text-gray-600 block mb-0.5 uppercase font-bold text-[10px]">Pass@1</span><span className="text-primary font-bold">{run.metrics?.passAt1 || 0}%</span></div>
                    <div><span className="text-gray-600 block mb-0.5 uppercase font-bold text-[10px]">Compile Rate</span><span className="text-success">{run.metrics?.compileRate || 0}%</span></div>
                    <div><span className="text-gray-600 block mb-0.5 uppercase font-bold text-[10px]">Problems</span>{evalResult?.totalProblems || '-'}</div>
                </div>

                {/* Tabs */}
                <div className="flex gap-6 mt-4 border-b border-border -mb-[17px]">
                    {(['logs', 'results', 'failures'] as const).map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`pb-3 text-sm font-medium transition-colors border-b-2 capitalize ${activeTab === tab ? 'text-primary border-primary' : 'text-gray-400 border-transparent hover:text-white'
                                }`}
                        >
                            {tab === 'logs' ? 'Live Logs' : tab === 'results' ? 'Results' : 'Failure Analysis'}
                        </button>
                    ))}
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-6">
                {/* Logs Tab */}
                {activeTab === 'logs' && (
                    <div className="h-full flex flex-col">
                        <div className="flex justify-between items-center mb-2">
                            <h3 className="text-white font-semibold text-sm">Evaluation Logs</h3>
                            <div className="flex gap-2">
                                <span className="text-xs text-gray-500">{logs.length} entries</span>
                                <button
                                    onClick={() => {
                                        const blob = new Blob([logs.map(l => `[${l.timestamp}] [${l.level}] ${l.message}`).join('\n')], { type: 'text/plain' });
                                        const url = URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = `eval-${id}-logs.txt`;
                                        a.click();
                                        URL.revokeObjectURL(url);
                                    }}
                                    className="text-xs text-primary cursor-pointer hover:underline"
                                >Download</button>
                            </div>
                        </div>
                        <div className="flex-1 bg-black/40 rounded border border-border p-4 overflow-y-auto font-mono text-xs text-gray-300 space-y-1 min-h-[400px]">
                            {logs.length > 0 ? (
                                logs.map((log, i) => (
                                    <div key={i} className={`${log.level === 'warning' ? 'text-yellow-500' : log.level === 'error' ? 'text-red-400' : ''}`}>
                                        <span className="text-gray-600">[{new Date(log.timestamp).toLocaleTimeString()}]</span> {log.message}
                                    </div>
                                ))
                            ) : (
                                <div className="text-gray-500">
                                    {runStatus === 'running' ? 'Waiting for logs...' : 'No logs available'}
                                </div>
                            )}
                            {runStatus === 'running' && <div className="animate-pulse text-primary">_</div>}
                            <div ref={logsEndRef} />
                        </div>
                    </div>
                )}

                {/* Results Tab */}
                {activeTab === 'results' && (
                    <div className="space-y-6">
                        {/* Main Metrics */}
                        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 bg-surface p-4 rounded-xl border border-border">
                            <div className="text-center">
                                <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Pass@1</div>
                                <div className="text-2xl font-mono text-primary font-bold">{run.metrics?.passAt1 ?? 0}%</div>
                            </div>
                            <div className="text-center">
                                <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Pass@5</div>
                                <div className="text-2xl font-mono text-white font-bold">{evalResult?.passAtK?.['5'] ?? '-'}%</div>
                            </div>
                            <div className="text-center">
                                <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Pass@10</div>
                                <div className="text-2xl font-mono text-white font-bold">{evalResult?.passAtK?.['10'] ?? '-'}%</div>
                            </div>
                            <div className="text-center">
                                <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Compile Rate</div>
                                <div className="text-2xl font-mono text-success font-bold">{run.metrics?.compileRate ?? 0}%</div>
                            </div>
                            <div className="text-center">
                                <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Problems</div>
                                <div className="text-2xl font-mono text-white font-bold">{evalResult?.totalProblems ?? '-'}</div>
                            </div>
                            <div className="text-center">
                                <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Samples</div>
                                <div className="text-2xl font-mono text-white font-bold">{evalResult?.totalSamples ?? '-'}</div>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            {/* Error Classification */}
                            <div className="bg-surface border border-border rounded-xl p-4">
                                <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-red-400"></span>
                                    Error Classification
                                </h3>
                                <div className="space-y-3">
                                    {[
                                        { key: 'syntaxErrorRate', label: 'Syntax Error', color: 'bg-red-500' },
                                        { key: 'runtimeErrorRate', label: 'Runtime Error', color: 'bg-orange-500' },
                                        { key: 'timeoutRate', label: 'Timeout (TLE)', color: 'bg-yellow-500' },
                                        { key: 'assertionErrorRate', label: 'Assertion Error', color: 'bg-purple-500' },
                                        { key: 'importErrorRate', label: 'Import Error', color: 'bg-blue-500' },
                                        { key: 'memoryErrorRate', label: 'Memory Error', color: 'bg-pink-500' },
                                    ].map(({ key, label, color }) => {
                                        const rate = evalResult?.errorStats?.[key] ?? 0;
                                        return (
                                            <div key={key} className="flex items-center gap-3">
                                                <div className="w-28 text-xs text-gray-400">{label}</div>
                                                <div className="flex-1 bg-black/30 rounded-full h-2 overflow-hidden">
                                                    <div className={`h-full ${color} transition-all`} style={{ width: `${Math.min(rate, 100)}%` }}></div>
                                                </div>
                                                <div className="w-12 text-xs text-gray-300 text-right font-mono">{rate.toFixed(1)}%</div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Time Statistics */}
                            <div className="bg-surface border border-border rounded-xl p-4">
                                <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-blue-400"></span>
                                    Execution Time Statistics
                                </h3>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="bg-black/20 rounded-lg p-3 text-center">
                                        <div className="text-xs text-gray-500 uppercase mb-1">Mean Runtime</div>
                                        <div className="text-xl font-mono text-white">{evalResult?.timeStats?.meanRuntimeMs?.toFixed(1) ?? '-'} <span className="text-xs text-gray-500">ms</span></div>
                                    </div>
                                    <div className="bg-black/20 rounded-lg p-3 text-center">
                                        <div className="text-xs text-gray-500 uppercase mb-1">P50 Runtime</div>
                                        <div className="text-xl font-mono text-white">{evalResult?.timeStats?.p50RuntimeMs?.toFixed(1) ?? '-'} <span className="text-xs text-gray-500">ms</span></div>
                                    </div>
                                    <div className="bg-black/20 rounded-lg p-3 text-center">
                                        <div className="text-xs text-gray-500 uppercase mb-1">P95 Runtime</div>
                                        <div className="text-xl font-mono text-yellow-400">{evalResult?.timeStats?.p95RuntimeMs?.toFixed(1) ?? '-'} <span className="text-xs text-gray-500">ms</span></div>
                                    </div>
                                    <div className="bg-black/20 rounded-lg p-3 text-center">
                                        <div className="text-xs text-gray-500 uppercase mb-1">Max Runtime</div>
                                        <div className="text-xl font-mono text-red-400">{evalResult?.timeStats?.maxRuntimeMs?.toFixed(1) ?? '-'} <span className="text-xs text-gray-500">ms</span></div>
                                    </div>
                                </div>
                                <div className="mt-4 flex items-center justify-between bg-black/20 rounded-lg p-3">
                                    <span className="text-xs text-gray-400">TLE Rate (Timeout)</span>
                                    <span className="text-lg font-mono text-orange-400">{evalResult?.timeStats?.tleRate?.toFixed(1) ?? 0}%</span>
                                </div>
                            </div>
                        </div>

                        {/* Difficulty Breakdown */}
                        {evalResult?.segmentStats?.byDifficulty && (
                            <div className="bg-surface border border-border rounded-xl p-4">
                                <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-purple-400"></span>
                                    Difficulty Breakdown
                                </h3>
                                <div className="space-y-3">
                                    {Object.entries(evalResult.segmentStats.byDifficulty).map(([diff, stats]: [string, any]) => (
                                        <div key={diff} className="flex items-center gap-3">
                                            <div className={`w-20 text-xs font-medium px-2 py-0.5 rounded ${diff === 'easy' ? 'bg-green-500/20 text-green-400' :
                                                diff === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                                                    diff === 'hard' ? 'bg-red-500/20 text-red-400' :
                                                        'bg-gray-500/20 text-gray-400'
                                                }`}>{diff}</div>
                                            <div className="flex-1 bg-black/30 rounded-full h-2 overflow-hidden">
                                                <div className="h-full bg-primary transition-all" style={{ width: `${stats.pass_at_1}%` }}></div>
                                            </div>
                                            <div className="w-16 text-xs text-gray-300 text-right font-mono">{stats.pass_at_1?.toFixed(1)}%</div>
                                            <div className="w-12 text-xs text-gray-500">({stats.count})</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* No Results Message */}
                        {!evalResult && runStatus !== 'running' && (
                            <div className="bg-surface border border-border rounded-xl p-8 text-center">
                                <span className="material-symbols-outlined text-4xl text-gray-600 mb-2">assessment</span>
                                <p className="text-gray-400">No evaluation results available yet.</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Failures Tab */}
                {activeTab === 'failures' && (
                    <div className="space-y-4">
                        <div className="flex justify-between items-end">
                            <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Failure Analysis</h3>
                            <div className="flex gap-2 text-xs">
                                {evalResult?.errorStats && (
                                    <>
                                        <span className="text-red-400">Runtime ({evalResult.errorStats.runtimeErrorRate?.toFixed(0) ?? 0}%)</span>
                                        <span className="text-orange-400">Timeout ({evalResult.errorStats.timeoutRate?.toFixed(0) ?? 0}%)</span>
                                        <span className="text-purple-400">Assertion ({evalResult.errorStats.assertionErrorRate?.toFixed(0) ?? 0}%)</span>
                                    </>
                                )}
                            </div>
                        </div>

                        <div className="bg-surface border border-border rounded-xl overflow-hidden">
                            <div className="grid grid-cols-12 gap-4 px-6 py-3 bg-black/20 border-b border-border text-xs font-bold text-gray-400 uppercase">
                                <div className="col-span-1">ID</div>
                                <div className="col-span-3">Prompt</div>
                                <div className="col-span-4">Output / Error</div>
                                <div className="col-span-2">Error Type</div>
                                <div className="col-span-2 text-right">Time</div>
                            </div>
                            {evalResult?.failures && evalResult.failures.length > 0 ? (
                                evalResult.failures.slice(0, 20).map((failure: any, i: number) => (
                                    <div key={i} className="p-4 border-b border-border/50 hover:bg-white/[0.02] transition-colors">
                                        <div className="grid grid-cols-12 gap-4 items-start">
                                            <div className="col-span-1 text-xs text-gray-500 font-mono">{failure.taskId}</div>
                                            <div className="col-span-3">
                                                <code className="text-xs text-gray-300 block bg-black/20 p-2 rounded border border-border/50 line-clamp-2 overflow-hidden">{failure.prompt?.slice(0, 100)}...</code>
                                            </div>
                                            <div className="col-span-4">
                                                <code className="text-xs text-red-300 block font-mono line-clamp-2">{failure.error || failure.output?.slice(0, 100)}</code>
                                            </div>
                                            <div className="col-span-2">
                                                <span className={`text-[10px] font-bold px-2 py-1 rounded ${failure.errorType === 'runtime_error' ? 'text-orange-400 bg-orange-500/10' :
                                                    failure.errorType === 'timeout' ? 'text-yellow-400 bg-yellow-500/10' :
                                                        failure.errorType === 'syntax_error' ? 'text-red-400 bg-red-500/10' :
                                                            failure.errorType === 'assertion_error' ? 'text-purple-400 bg-purple-500/10' :
                                                                'text-gray-400 bg-gray-500/10'
                                                    }`}>{failure.errorType}</span>
                                            </div>
                                            <div className="col-span-2 text-right text-xs text-gray-400 font-mono">
                                                {failure.executionTimeMs ? `${failure.executionTimeMs.toFixed(0)}ms` : '-'}
                                            </div>
                                        </div>
                                    </div>
                                ))
                            ) : (
                                <div className="p-8 text-center text-gray-500 text-sm">
                                    {evalResult ? 'No failures recorded - all tests passed!' : 'No evaluation results available yet.'}
                                </div>
                            )}
                            {evalResult?.failures && evalResult.failures.length > 20 && (
                                <div className="px-6 py-3 bg-black/20 text-center text-xs text-gray-500">
                                    Showing 20 of {evalResult.failures.length} failures
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default EvalDetail;
