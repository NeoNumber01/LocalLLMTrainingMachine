import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchRun, fetchRunMetrics, fetchRunArtifacts, stopRun, cloneRun, connectRunLogs, API_BASE } from '../lib/api';
import { Status } from '../types';

interface MetricPoint {
   step: number;
   loss: number;
   timestamp: string;
   extra?: { lr?: number; grad_norm?: number };
}

interface LogEntry {
   timestamp: string;
   level: string;
   message: string;
}

const RunDetail: React.FC = () => {
   const { id } = useParams();
   const navigate = useNavigate();
   const [run, setRun] = useState<any>(null);
   const [loading, setLoading] = useState(true);
   const [error, setError] = useState<string | null>(null);
   const [activeTab, setActiveTab] = useState('Overview');
   const [logSearch, setLogSearch] = useState('');

   // Real data states
   const [metrics, setMetrics] = useState<MetricPoint[]>([]);
   const [logs, setLogs] = useState<LogEntry[]>([]);
   const [artifacts, setArtifacts] = useState<any[]>([]);
   const logsEndRef = useRef<HTMLDivElement>(null);

   // Performance: Buffer logs to avoid too many re-renders
   const logBuffer = useRef<LogEntry[]>([]);
   const lastLogUpdate = useRef(0);

   // Performance: Downsample metrics for chart rendering
   const sampledMetrics = React.useMemo(() => {
      if (metrics.length <= 500) return metrics;
      const factor = Math.ceil(metrics.length / 500);
      return metrics.filter((_, i) => i % factor === 0);
   }, [metrics]);

   useEffect(() => {
      const flushLogs = () => {
         if (logBuffer.current.length === 0) return;

         const newLogs = [...logBuffer.current];
         logBuffer.current = [];

         setLogs(prev => {
            // Keep last 1000 logs, prevents memory issues
            const updated = [...prev, ...newLogs];
            return updated.slice(-1000);
         });
      };

      const interval = setInterval(flushLogs, 200); // Update UI every 200ms max
      return () => clearInterval(interval);
   }, []);

   useEffect(() => {
      if (!id) return;

      // Load run details
      fetchRun(id)
         .then(setRun)
         .catch(e => setError(e.message))
         .finally(() => setLoading(false));

      // Load metrics
      fetchRunMetrics(id)
         .then(setMetrics)
         .catch(console.error);

      // Load artifacts
      fetchRunArtifacts(id)
         .then(setArtifacts)
         .catch(console.error);

      // Connect to SSE logs
      const eventSource = connectRunLogs(id, (event) => {
         if (event.type === 'log') {
            logBuffer.current.push({
               timestamp: event.timestamp,
               level: event.level,
               message: event.message,
            });
         } else if (event.type === 'metric') {
            setMetrics(prev => {
               // Avoid duplicates
               if (prev.some(m => m.step === event.step)) return prev;
               return [...prev, {
                  step: event.step,
                  loss: event.loss,
                  timestamp: event.timestamp,
                  extra: event.extra
               }];
            });
         } else if (event.type === 'status') {
            setRun((prev: any) => prev ? { ...prev, status: event.status } : prev);
         } else if (event.type === 'artifact') {
            setArtifacts(prev => {
               // Avoid duplicates
               if (prev.some(a => a.path === event.artifact.path)) return prev;
               return [...prev, event.artifact];
            });
         }
      });

      return () => eventSource.close();
   }, [id]);

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

   const handleClone = async () => {
      if (!id) return;
      try {
         const result = await cloneRun(id);
         navigate(`/runs/${result.id}`);
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
               <p className="text-sm text-gray-400 mt-1">{error || 'Run not found'}</p>
               <button onClick={() => navigate('/runs')} className="mt-4 px-4 py-2 bg-primary rounded-lg text-sm">Back to List</button>
            </div>
         </div>
      );
   }

   const runStatus = run.status || 'unknown';

   return (
      <div className="flex flex-col h-full bg-background">
         {/* Header */}
         <div className="px-6 py-4 border-b border-border bg-surface shrink-0">
            <div className="flex items-center justify-between mb-4">
               <div className="flex items-center gap-3">
                  <button onClick={() => navigate('/runs')} className="text-gray-500 hover:text-white">
                     <span className="material-symbols-outlined">arrow_back</span>
                  </button>
                  <div>
                     <h1 className="text-xl font-bold text-white">{run.name}</h1>
                     <div className="text-[10px] text-gray-500 font-mono mt-0.5">ID: {run.id}</div>
                  </div>
                  <div className={`ml-2 px-2 py-0.5 rounded text-xs font-bold uppercase border flex items-center gap-1.5 ${runStatus === 'running' ? 'bg-primary/10 text-primary border-primary/20' :
                     runStatus === 'success' ? 'bg-success/10 text-success border-success/20' :
                        'bg-gray-800 text-gray-400 border-gray-700'
                     }`}>
                     {runStatus === 'running' && <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>}
                     {runStatus}
                  </div>
               </div>
               <div className="flex gap-2">
                  <button
                     onClick={() => {
                        const cmd = `python train.py --model ${run.baseModel} --dataset ${run.dataset} --config '${JSON.stringify(run.config)}'`;
                        navigator.clipboard.writeText(cmd);
                        alert('CLI command copied to clipboard!');
                     }}
                     className="px-3 py-1.5 rounded-md border border-border text-gray-300 text-xs font-medium hover:bg-white/5 flex items-center gap-2"
                  >
                     <span className="material-symbols-outlined text-[16px]">terminal</span> Copy CLI
                  </button>
                  <button
                     onClick={handleClone}
                     className="px-3 py-1.5 rounded-md border border-border text-gray-300 text-xs font-medium hover:bg-white/5"
                  >
                     Clone Config
                  </button>
                  {runStatus === 'running' ? (
                     <button
                        onClick={handleStop}
                        className="px-3 py-1.5 rounded-md bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium hover:bg-red-500/20 flex items-center gap-1"
                     >
                        <span className="material-symbols-outlined text-[14px]">stop</span> Stop
                     </button>
                  ) : (
                     <button
                        onClick={() => navigate(`/reports?runId=${run.id}`)}
                        className="px-3 py-1.5 rounded-md bg-primary/10 border border-primary/20 text-primary text-xs font-medium hover:bg-primary/20 flex items-center gap-1"
                     >
                        <span className="material-symbols-outlined text-[14px]">download</span> Report
                     </button>
                  )}
               </div>
            </div>

            {/* Key Metrics / Repro Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 text-xs text-gray-400 font-mono mt-2 mb-4 bg-black/20 p-3 rounded-lg border border-border">
               <div><span className="text-gray-600 block mb-0.5 uppercase font-bold text-[10px]">Model</span>{run.baseModel}</div>
               <div><span className="text-gray-600 block mb-0.5 uppercase font-bold text-[10px]">Dataset</span>{run.dataset}</div>
               <div><span className="text-gray-600 block mb-0.5 uppercase font-bold text-[10px]">Duration</span>{run.duration}</div>
               <div><span className="text-gray-600 block mb-0.5 uppercase font-bold text-[10px]">Loss</span>{run.metrics.loss}</div>
               <div><span className="text-gray-600 block mb-0.5 uppercase font-bold text-[10px]">Pass@1</span>{run.metrics.passAt1}%</div>
               <div><span className="text-gray-600 block mb-0.5 uppercase font-bold text-[10px]">Git/Env</span><span className="flex items-center gap-1 text-primary cursor-pointer hover:underline"><span className="material-symbols-outlined text-[10px]">commit</span> {run.config?.gitCommit || 'N/A'}</span></div>
            </div>

            {/* Tabs */}
            <div className="flex gap-6 mt-2 border-b border-border -mb-[17px]">
               {['Overview', 'Checkpoints', 'Evaluation', 'Artifacts'].map(tab => (
                  <button
                     key={tab}
                     onClick={() => setActiveTab(tab)}
                     className={`pb-3 text-sm font-medium transition-colors border-b-2 ${activeTab === tab ? 'text-primary border-primary' : 'text-gray-400 border-transparent hover:text-white'
                        }`}
                  >
                     {tab}
                  </button>
               ))}
            </div>
         </div>

         {/* Content Area */}
         <div className="flex-1 overflow-y-auto p-6">
            {activeTab === 'Overview' && (
               <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  <div className="lg:col-span-2 flex flex-col gap-6">
                     {/* Main Loss Chart - Real Data */}
                     <div className="bg-surface border border-border rounded-xl p-4 h-[300px] flex flex-col">
                        <h3 className="text-white font-semibold mb-4 text-sm flex items-center gap-2">
                           <span className="w-2 h-2 rounded-full bg-primary"></span> Training Loss
                           {metrics.length > 0 && <span className="text-xs text-gray-500 font-normal ml-2">({metrics.length} points)</span>}
                        </h3>
                        <div className="flex-1 flex items-end justify-between gap-1 px-4 relative border-l border-b border-border/50">
                           {metrics.length > 0 ? (
                              <svg className="w-full h-full overflow-visible" viewBox="0 0 400 100" preserveAspectRatio="none">
                                 {/* Generate path from real metrics */}
                                 <path
                                    d={metrics.map((m, i) => {
                                       const x = (i / Math.max(metrics.length - 1, 1)) * 400;
                                       const maxLoss = Math.max(...metrics.map(p => p.loss), 1);
                                       const y = 100 - (m.loss / maxLoss) * 90;
                                       return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                                    }).join(' ')}
                                    fill="none" stroke="#137fec" strokeWidth="2" vectorEffect="non-scaling-stroke"
                                 />
                                 <line x1="0" y1="100" x2="400" y2="100" stroke="#333" strokeDasharray="4" />
                              </svg>
                           ) : (
                              <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">No data yet</div>
                           )}
                        </div>
                     </div>

                     {/* Secondary Metrics - Real Data */}
                     <div className="grid grid-cols-2 gap-6">
                        <div className="bg-surface border border-border rounded-xl p-4 h-48 flex flex-col">
                           <h3 className="text-gray-400 font-semibold mb-2 text-xs uppercase">Learning Rate</h3>
                           <div className="flex-1 border-l border-b border-border/50 relative">
                              {sampledMetrics.length > 0 && sampledMetrics.some(m => m.extra?.lr) ? (
                                 <svg className="w-full h-full overflow-visible" viewBox="0 0 300 100" preserveAspectRatio="none">
                                    <path
                                       d={sampledMetrics.filter(m => m.extra?.lr).map((m, i, arr) => {
                                          const x = (i / Math.max(arr.length - 1, 1)) * 300;
                                          const maxLr = Math.max(...arr.map(p => p.extra?.lr || 0));
                                          const y = 100 - ((m.extra?.lr || 0) / maxLr) * 90;
                                          return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                                       }).join(' ')}
                                       fill="none" stroke="#eab308" strokeWidth="2" vectorEffect="non-scaling-stroke"
                                    />
                                 </svg>
                              ) : (
                                 <div className="flex-1 flex items-center justify-center text-gray-500 text-xs">No LR data</div>
                              )}
                           </div>
                        </div>
                        <div className="bg-surface border border-border rounded-xl p-4 h-48 flex flex-col">
                           <h3 className="text-gray-400 font-semibold mb-2 text-xs uppercase">Grad Norm</h3>
                           <div className="flex-1 border-l border-b border-border/50 relative">
                              {sampledMetrics.length > 0 && sampledMetrics.some(m => m.extra?.grad_norm) ? (
                                 <svg className="w-full h-full overflow-visible" viewBox="0 0 300 100" preserveAspectRatio="none">
                                    <path
                                       d={sampledMetrics.filter(m => m.extra?.grad_norm).map((m, i, arr) => {
                                          const x = (i / Math.max(arr.length - 1, 1)) * 300;
                                          const maxGrad = Math.max(...arr.map(p => p.extra?.grad_norm || 0));
                                          const y = 100 - ((m.extra?.grad_norm || 0) / maxGrad) * 90;
                                          return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                                       }).join(' ')}
                                       fill="none" stroke="#ef4444" strokeWidth="2" vectorEffect="non-scaling-stroke"
                                    />
                                 </svg>
                              ) : (
                                 <div className="flex-1 flex items-center justify-center text-gray-500 text-xs">No grad data</div>
                              )}
                           </div>
                        </div>
                     </div>
                  </div>

                  <div className="flex flex-col gap-4 max-h-[600px]">
                     <div className="bg-surface border border-border rounded-xl p-4 flex-1 flex flex-col overflow-hidden min-h-0">
                        <div className="flex justify-between items-center mb-2">
                           <h3 className="text-white font-semibold text-sm">Live Logs</h3>
                           <div className="flex gap-2">
                              <span className="text-xs text-gray-500">{logs.length} entries</span>
                              <button
                                 onClick={() => {
                                    const blob = new Blob([logs.map(l => `[${l.timestamp}] [${l.level}] ${l.message}`).join('\n')], { type: 'text/plain' });
                                    const url = URL.createObjectURL(blob);
                                    const a = document.createElement('a');
                                    a.href = url;
                                    a.download = `run-${id}-logs.txt`;
                                    a.click();
                                    URL.revokeObjectURL(url);
                                 }}
                                 className="text-xs text-primary cursor-pointer hover:underline"
                              >Download</button>
                           </div>
                        </div>
                        {/* Log Search */}
                        <div className="mb-2 relative">
                           <input
                              type="text"
                              placeholder="Filter logs..."
                              className="w-full bg-black/30 border border-border rounded px-2 py-1 text-xs text-white focus:border-primary focus:outline-none"
                              value={logSearch}
                              onChange={(e) => setLogSearch(e.target.value)}
                           />
                        </div>
                        <div className="flex-1 bg-black/40 rounded border border-border p-3 overflow-y-auto font-mono text-xs text-gray-300 space-y-1">
                           {logs.length > 0 ? (
                              logs
                                 .filter(l => !logSearch || l.message.toLowerCase().includes(logSearch.toLowerCase()))
                                 .map((log, i) => (
                                    <div key={i} className={log.level === 'warn' ? 'text-yellow-500' : log.level === 'error' ? 'text-red-400' : ''}>
                                       [{new Date(log.timestamp).toLocaleTimeString()}] {log.message}
                                    </div>
                                 ))
                           ) : (
                              <div className="text-gray-500">Waiting for logs...</div>
                           )}
                           {run.status === 'running' && <div className="animate-pulse">_</div>}
                           <div ref={logsEndRef} />
                        </div>
                     </div>
                  </div>
               </div>
            )}

            {activeTab === 'Checkpoints' && (
               <div className="max-w-4xl mx-auto space-y-4">
                  <div className="flex justify-between items-center mb-2">
                     <h2 className="text-lg font-bold text-white">Saved Checkpoints</h2>
                     <span className="text-xs text-gray-400">
                        {artifacts.filter(a => a.kind === 'checkpoint').length} checkpoint(s)
                     </span>
                  </div>
                  <div className="bg-surface border border-border rounded-xl overflow-hidden">
                     <table className="w-full text-left text-sm">
                        <thead className="bg-black/20 text-xs uppercase text-gray-500 font-medium">
                           <tr>
                              <th className="px-6 py-3">Name</th>
                              <th className="px-6 py-3">Size</th>
                              <th className="px-6 py-3">Created</th>
                              <th className="px-6 py-3 text-right">Actions</th>
                           </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                           {artifacts.filter(a => a.kind === 'checkpoint').length > 0 ? (
                              artifacts.filter(a => a.kind === 'checkpoint').map((cp, i) => (
                                 <tr key={i} className="hover:bg-white/[0.02]">
                                    <td className="px-6 py-4">
                                       <div className="text-white font-medium">{cp.name || cp.path}</div>
                                    </td>
                                    <td className="px-6 py-4 text-gray-400 font-mono">{cp.size}</td>
                                    <td className="px-6 py-4 text-gray-400 text-xs">
                                       {new Date(cp.createdAt).toLocaleString()}
                                    </td>
                                    <td className="px-6 py-4 text-right flex justify-end gap-2">
                                       <a
                                          href={`${API_BASE}/runs/${id}/artifacts/${cp.id}/download`}
                                          download
                                          className="px-3 py-1.5 border border-border text-gray-400 rounded text-xs hover:text-white inline-block"
                                       >Download</a>
                                    </td>
                                 </tr>
                              ))
                           ) : (
                              <tr>
                                 <td colSpan={4} className="px-6 py-8 text-center text-gray-500">
                                    No checkpoints saved yet.
                                 </td>
                              </tr>
                           )}
                        </tbody>
                     </table>
                  </div>
               </div>
            )}


            {activeTab === 'Evaluation' && (
               <div className="max-w-6xl mx-auto space-y-6">
                  {/* Main Metrics Header */}
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 bg-surface p-4 rounded-xl border border-border">
                     <div className="text-center">
                        <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Pass@1</div>
                        <div className="text-2xl font-mono text-primary font-bold">{run.metrics?.passAt1 ?? 0}%</div>
                     </div>
                     <div className="text-center">
                        <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Pass@5</div>
                        <div className="text-2xl font-mono text-white font-bold">{run.evalResult?.passAtK?.['5'] ?? '-'}%</div>
                     </div>
                     <div className="text-center">
                        <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Pass@10</div>
                        <div className="text-2xl font-mono text-white font-bold">{run.evalResult?.passAtK?.['10'] ?? '-'}%</div>
                     </div>
                     <div className="text-center">
                        <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Compile Rate</div>
                        <div className="text-2xl font-mono text-success font-bold">{run.metrics?.compileRate ?? 0}%</div>
                     </div>
                     <div className="text-center">
                        <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Problems</div>
                        <div className="text-2xl font-mono text-white font-bold">{run.evalResult?.totalProblems ?? '-'}</div>
                     </div>
                     <div className="text-center">
                        <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Samples</div>
                        <div className="text-2xl font-mono text-white font-bold">{run.evalResult?.totalSamples ?? '-'}</div>
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
                              const rate = run.evalResult?.errorStats?.[key] ?? 0;
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
                              <div className="text-xl font-mono text-white">{run.evalResult?.timeStats?.meanRuntimeMs?.toFixed(1) ?? '-'} <span className="text-xs text-gray-500">ms</span></div>
                           </div>
                           <div className="bg-black/20 rounded-lg p-3 text-center">
                              <div className="text-xs text-gray-500 uppercase mb-1">P50 Runtime</div>
                              <div className="text-xl font-mono text-white">{run.evalResult?.timeStats?.p50RuntimeMs?.toFixed(1) ?? '-'} <span className="text-xs text-gray-500">ms</span></div>
                           </div>
                           <div className="bg-black/20 rounded-lg p-3 text-center">
                              <div className="text-xs text-gray-500 uppercase mb-1">P95 Runtime</div>
                              <div className="text-xl font-mono text-yellow-400">{run.evalResult?.timeStats?.p95RuntimeMs?.toFixed(1) ?? '-'} <span className="text-xs text-gray-500">ms</span></div>
                           </div>
                           <div className="bg-black/20 rounded-lg p-3 text-center">
                              <div className="text-xs text-gray-500 uppercase mb-1">Max Runtime</div>
                              <div className="text-xl font-mono text-red-400">{run.evalResult?.timeStats?.maxRuntimeMs?.toFixed(1) ?? '-'} <span className="text-xs text-gray-500">ms</span></div>
                           </div>
                        </div>
                        <div className="mt-4 flex items-center justify-between bg-black/20 rounded-lg p-3">
                           <span className="text-xs text-gray-400">TLE Rate (Timeout)</span>
                           <span className="text-lg font-mono text-orange-400">{run.evalResult?.timeStats?.tleRate?.toFixed(1) ?? 0}%</span>
                        </div>
                     </div>
                  </div>

                  {/* Code Quality & Segments */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                     {/* Code Quality */}
                     <div className="bg-surface border border-border rounded-xl p-4">
                        <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                           <span className="w-2 h-2 rounded-full bg-green-400"></span>
                           Code Quality
                        </h3>
                        <div className="grid grid-cols-2 gap-4">
                           <div className="bg-black/20 rounded-lg p-3">
                              <div className="text-xs text-gray-500 uppercase mb-1">Avg Code Length</div>
                              <div className="text-lg font-mono text-white">{run.evalResult?.codeQuality?.avgCodeLength?.toFixed(0) ?? '-'} <span className="text-xs text-gray-500">chars</span></div>
                           </div>
                           <div className="bg-black/20 rounded-lg p-3">
                              <div className="text-xs text-gray-500 uppercase mb-1">Avg Line Count</div>
                              <div className="text-lg font-mono text-white">{run.evalResult?.codeQuality?.avgLineCount?.toFixed(1) ?? '-'} <span className="text-xs text-gray-500">lines</span></div>
                           </div>
                           <div className="bg-black/20 rounded-lg p-3">
                              <div className="text-xs text-gray-500 uppercase mb-1">Extra I/O Rate</div>
                              <div className={`text-lg font-mono ${(run.evalResult?.codeQuality?.extraIORate ?? 0) > 10 ? 'text-red-400' : 'text-green-400'}`}>
                                 {run.evalResult?.codeQuality?.extraIORate?.toFixed(1) ?? 0}%
                              </div>
                           </div>
                           <div className="bg-black/20 rounded-lg p-3">
                              <div className="text-xs text-gray-500 uppercase mb-1">Interface Compliance</div>
                              <div className="text-lg font-mono text-green-400">{run.evalResult?.codeQuality?.interfaceComplianceRate?.toFixed(1) ?? '-'}%</div>
                           </div>
                        </div>
                     </div>

                     {/* Difficulty Breakdown */}
                     <div className="bg-surface border border-border rounded-xl p-4">
                        <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                           <span className="w-2 h-2 rounded-full bg-purple-400"></span>
                           Difficulty Breakdown
                        </h3>
                        {run.evalResult?.segmentStats?.byDifficulty ? (
                           <div className="space-y-3">
                              {Object.entries(run.evalResult.segmentStats.byDifficulty).map(([diff, stats]: [string, any]) => (
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
                        ) : (
                           <div className="text-center text-gray-500 text-sm py-4">No difficulty data available</div>
                        )}
                     </div>
                  </div>

                  {/* Failure Analysis */}
                  <div className="space-y-4">
                     <div className="flex justify-between items-end">
                        <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Failure Analysis</h3>
                        <div className="flex gap-2 text-xs">
                           {run.evalResult?.errorStats && (
                              <>
                                 <span className="text-red-400 cursor-pointer underline">Runtime ({run.evalResult.errorStats.runtimeErrorRate?.toFixed(0)}%)</span>
                                 <span className="text-orange-400 cursor-pointer hover:underline">Timeout ({run.evalResult.errorStats.timeoutRate?.toFixed(0)}%)</span>
                                 <span className="text-purple-400 cursor-pointer hover:underline">Assertion ({run.evalResult.errorStats.assertionErrorRate?.toFixed(0)}%)</span>
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
                        {run.evalResult?.failures && run.evalResult.failures.length > 0 ? (
                           run.evalResult.failures.slice(0, 10).map((failure: any, i: number) => (
                              <div key={i} className="p-4 border-b border-border/50 hover:bg-white/[0.02] transition-colors group">
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
                              {run.evalResult ? 'No failures recorded - all tests passed!' : 'No evaluation results available yet.'}
                           </div>
                        )}
                        {run.evalResult?.failures && run.evalResult.failures.length > 10 && (
                           <div className="px-6 py-3 bg-black/20 text-center text-xs text-gray-500">
                              Showing 10 of {run.evalResult.failures.length} failures
                           </div>
                        )}
                     </div>
                  </div>
               </div>
            )
            }

            {
               activeTab === 'Artifacts' && (
                  <div className="max-w-4xl mx-auto space-y-6">
                     <div className="bg-surface border border-border rounded-xl overflow-hidden">
                        <div className="px-6 py-4 border-b border-border bg-white/5 flex justify-between">
                           <h3 className="font-semibold text-white">Generated Artifacts</h3>
                           <span className="text-xs text-gray-400">{artifacts.length} file(s)</span>
                        </div>
                        <div className="divide-y divide-border">
                           {artifacts.length > 0 ? artifacts.map((artifact, i) => (
                              <div key={i} className="px-6 py-4 flex items-center justify-between hover:bg-white/[0.02]">
                                 <div className="flex items-center gap-3">
                                    <span className="material-symbols-outlined text-gray-500">
                                       {artifact.kind === 'checkpoint' ? 'save' :
                                          artifact.kind === 'adapter' ? 'tune' :
                                             artifact.kind === 'log' ? 'article' :
                                                artifact.kind === 'eval' ? 'assessment' : 'description'}
                                    </span>
                                    <div>
                                       <div className="text-sm text-gray-200 font-mono">{artifact.path}</div>
                                       <div className="text-xs text-gray-500">{artifact.kind}</div>
                                    </div>
                                 </div>
                                 <div className="flex gap-4 items-center">
                                    <span className="text-xs text-gray-600">{artifact.size}</span>
                                    <a
                                       href={`${API_BASE}/runs/${id}/artifacts/${artifact.id}/download`}
                                       download
                                       className="text-gray-400 hover:text-white"
                                    >
                                       <span className="material-symbols-outlined text-[18px]">download</span>
                                    </a>
                                    {artifact.kind === 'adapter' && (
                                       <button
                                          onClick={() => {
                                             alert('Adapter will be registered. Navigate to Models page and rescan to see it.');
                                             window.open('/models', '_blank');
                                          }}
                                          className="text-xs bg-white/10 hover:bg-white/20 px-2 py-1 rounded text-gray-300"
                                       >Register as Model</button>
                                    )}
                                 </div>
                              </div>
                           )) : (
                              <div className="p-8 text-center text-gray-500 text-sm">No artifacts available yet.</div>
                           )}
                        </div>
                     </div>

                     <div className="bg-surface border border-border rounded-xl p-6">
                        <h3 className="font-semibold text-white mb-4">Reproducibility Config</h3>
                        <pre className="text-xs font-mono text-gray-300 overflow-auto bg-black/30 p-4 rounded border border-border max-h-64">{JSON.stringify(run.config, null, 2)}</pre>
                     </div>
                  </div>
               )
            }
         </div >
      </div >
   );
};

export default RunDetail;
