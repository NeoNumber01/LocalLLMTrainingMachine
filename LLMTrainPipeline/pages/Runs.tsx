import React, { useState, useEffect } from 'react';
import { fetchRuns, fetchQueue, reorderQueuedRun, cancelQueuedRun, QueuedRunItem } from '../lib/api';
import { Link } from 'react-router-dom';

const Runs: React.FC = () => {
   const [runs, setRuns] = useState<any[]>([]);
   const [loading, setLoading] = useState(true);
   const [selectedRuns, setSelectedRuns] = useState<string[]>([]);
   const [filterStatus, setFilterStatus] = useState<string>('All');
   const [viewMode, setViewMode] = useState<'List' | 'Queue'>('List');
   const [queueData, setQueueData] = useState<{ activeRun: { id: string; name: string } | null; queue: QueuedRunItem[] }>({ activeRun: null, queue: [] });
   const [queueLoading, setQueueLoading] = useState(false);

   const loadRuns = () => {
      setLoading(true);
      fetchRuns()
         .then(setRuns)
         .catch(console.error)
         .finally(() => setLoading(false));
   };

   const loadQueue = async () => {
      setQueueLoading(true);
      try {
         const data = await fetchQueue();
         setQueueData(data);
      } catch (e) {
         console.error('Failed to load queue:', e);
      } finally {
         setQueueLoading(false);
      }
   };

   useEffect(() => {
      loadRuns();
   }, []);

   // Load queue when switching to Queue view
   useEffect(() => {
      if (viewMode === 'Queue') {
         loadQueue();
         // Auto-refresh every 3 seconds
         const interval = setInterval(loadQueue, 3000);
         return () => clearInterval(interval);
      }
   }, [viewMode]);

   const handleMoveUp = async (runId: string, currentPosition: number) => {
      if (currentPosition <= 1) return;
      try {
         await reorderQueuedRun(runId, currentPosition - 1);
         await loadQueue();
      } catch (e) {
         console.error('Failed to reorder:', e);
      }
   };

   const handleMoveDown = async (runId: string, currentPosition: number, maxPosition: number) => {
      if (currentPosition >= maxPosition) return;
      try {
         await reorderQueuedRun(runId, currentPosition + 1);
         await loadQueue();
      } catch (e) {
         console.error('Failed to reorder:', e);
      }
   };

   const handleCancelQueue = async (runId: string) => {
      if (!confirm('Are you sure you want to cancel this queued task?')) return;
      try {
         await cancelQueuedRun(runId);
         await loadQueue();
         loadRuns(); // Also refresh runs list
      } catch (e) {
         console.error('Failed to cancel:', e);
      }
   };

   const toggleRun = (id: string) => {
      if (selectedRuns.includes(id)) {
         setSelectedRuns(selectedRuns.filter(r => r !== id));
      } else {
         setSelectedRuns([...selectedRuns, id]);
      }
   };

   const handleBulkDelete = async () => {
      if (!window.confirm(`Are you sure you want to delete the selected ${selectedRuns.length} run(s)?`)) return;

      try {
         const { deleteRun } = await import('../lib/api');
         for (const id of selectedRuns) {
            await deleteRun(id);
         }
         setSelectedRuns([]);
         loadRuns();
      } catch (e) {
         console.error('Failed to delete runs:', e);
         alert('Delete failed');
      }
   };

   const handleBulkStop = async () => {
      try {
         const { stopRun } = await import('../lib/api');
         for (const id of selectedRuns) {
            const run = runs.find(r => r.id === id);
            if (run?.status === 'running' || run?.status === 'queued') {
               await stopRun(id);
            }
         }
         loadRuns();
      } catch (e) {
         console.error('Failed to stop runs:', e);
      }
   };

   const handleBulkExport = () => {
      // Export selected run configs and metrics as JSON
      const exportData = selectedRuns.map(id => {
         const run = runs.find(r => r.id === id);
         return {
            id: run?.id,
            name: run?.name,
            status: run?.status,
            config: run?.config,
            metrics: run?.metrics,
            createdAt: run?.createdAt,
         };
      });

      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `runs_export_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
   };

   const filteredRuns = filterStatus === 'All' ? runs : runs.filter(r => r.status.toLowerCase() === filterStatus.toLowerCase());
   const queuedRuns = runs.filter(r => r.status === 'queued');

   if (loading) {
      return (
         <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
         </div>
      );
   }

   return (
      <div className="flex h-full">
         <div className="flex-1 flex flex-col min-w-0">
            <div className="px-6 py-4 border-b border-border bg-surface flex flex-col gap-4">
               <div className="flex justify-between items-center">
                  <h1 className="text-lg font-bold text-white">Runs</h1>
                  <div className="flex gap-2">
                     <button onClick={loadRuns} className="bg-surface border border-border hover:bg-white/5 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
                        <span className="material-symbols-outlined text-[18px]">refresh</span> Refresh
                     </button>
                     <Link to="/runs/new" className="bg-primary hover:bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
                        <span className="material-symbols-outlined text-[18px]">add</span> New Run
                     </Link>
                  </div>
               </div>

               <div className="flex justify-between items-center">
                  <div className="flex gap-4">
                     {/* View Toggle */}
                     <div className="flex bg-black/20 p-1 rounded-lg border border-border">
                        <button
                           onClick={() => setViewMode('List')}
                           className={`px-3 py-1 text-xs font-medium rounded ${viewMode === 'List' ? 'bg-surface text-white shadow' : 'text-gray-500 hover:text-gray-300'}`}
                        >
                           All Runs
                        </button>
                        <button
                           onClick={() => setViewMode('Queue')}
                           className={`px-3 py-1 text-xs font-medium rounded flex items-center gap-2 ${viewMode === 'Queue' ? 'bg-surface text-white shadow' : 'text-gray-500 hover:text-gray-300'}`}
                        >
                           Queue <span className="bg-white/10 px-1.5 rounded-full text-[10px]">{queuedRuns.length}</span>
                        </button>
                     </div>

                     {viewMode === 'List' && (
                        <div className="flex gap-2">
                           {['All', 'Running', 'Success', 'Failed'].map(status => (
                              <button
                                 key={status}
                                 onClick={() => setFilterStatus(status)}
                                 className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${filterStatus === status
                                    ? 'bg-white text-black border-white'
                                    : 'bg-transparent text-gray-400 border-border hover:border-gray-500'
                                    }`}
                              >
                                 {status}
                              </button>
                           ))}
                        </div>
                     )}
                  </div>

                  <div className="flex gap-2">
                     {selectedRuns.length > 0 && (
                        <div className="flex items-center gap-2 animate-in fade-in slide-in-from-right-4 mr-4 border-r border-border pr-4 bg-primary/5 px-3 py-1 rounded-lg border border-primary/20">
                           <span className="text-xs text-primary font-medium">{selectedRuns.length} selected</span>
                           <button onClick={handleBulkDelete} className="p-1 hover:bg-red-500/20 rounded text-red-400" title="Delete"><span className="material-symbols-outlined text-[16px]">delete</span></button>
                           <button onClick={handleBulkExport} className="p-1 hover:bg-white/10 rounded text-gray-300" title="Export"><span className="material-symbols-outlined text-[16px]">download</span></button>
                           <button onClick={handleBulkStop} className="p-1 hover:bg-white/10 rounded text-gray-300" title="Stop"><span className="material-symbols-outlined text-[16px]">stop_circle</span></button>
                           {selectedRuns.length === 2 && (
                              <Link to={`/compare?base=${selectedRuns[0]}&candidate=${selectedRuns[1]}`} className="text-xs text-primary hover:text-blue-300 font-bold ml-2">
                                 Compare
                              </Link>
                           )}
                        </div>
                     )}
                     {viewMode === 'List' && (
                        <div className="relative">
                           <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 text-[18px]">search</span>
                           <input className="bg-black/20 border border-border rounded-lg pl-9 pr-3 py-1.5 text-sm text-white focus:border-primary w-48" placeholder="Filter runs..." />
                        </div>
                     )}
                  </div>
               </div>
            </div>

            <div className="flex-1 overflow-auto bg-background">
               {viewMode === 'List' ? (
                  <table className="w-full text-left text-sm border-collapse">
                     <thead className="bg-surface sticky top-0 z-10 text-xs uppercase text-gray-500 font-medium shadow-sm">
                        <tr>
                           <th className="px-4 py-3 w-10"></th>
                           <th className="px-4 py-3">Run Name</th>
                           <th className="px-4 py-3">Status</th>
                           <th className="px-4 py-3">Model / Data</th>
                           <th className="px-4 py-3">Loss</th>
                           <th className="px-4 py-3">Pass@1</th>
                           <th className="px-4 py-3 text-right">Created</th>
                        </tr>
                     </thead>
                     <tbody className="divide-y divide-border">
                        {filteredRuns.map((run) => (
                           <tr key={run.id} className={`hover:bg-white/[0.02] transition-colors ${selectedRuns.includes(run.id) ? 'bg-primary/5' : ''}`}>
                              <td className="px-4 py-4">
                                 <input
                                    type="checkbox"
                                    className="rounded border-gray-600 bg-transparent text-primary focus:ring-offset-0 focus:ring-primary cursor-pointer"
                                    checked={selectedRuns.includes(run.id)}
                                    onChange={() => toggleRun(run.id)}
                                 />
                              </td>
                              <td className="px-4 py-4">
                                 <Link to={run.type === 'evaluation' ? `/evaluation/${run.id}` : `/runs/${run.id}`} className="flex flex-col group">
                                    <span className="text-white font-medium group-hover:text-primary transition-colors">{run.name}</span>
                                    <div className="flex gap-2 mt-1">
                                       <span className="text-[10px] bg-white/10 text-gray-400 px-1.5 py-0.5 rounded">{run.type}</span>
                                       <span className="text-[10px] text-gray-600 font-mono">{run.id}</span>
                                    </div>
                                 </Link>
                              </td>
                              <td className="px-4 py-4">
                                 <div className="flex items-center gap-2">
                                    <span className={`w-1.5 h-1.5 rounded-full ${run.status === 'running' ? 'bg-primary animate-pulse' :
                                       run.status === 'success' ? 'bg-success' :
                                          run.status === 'failed' ? 'bg-error' :
                                             run.status === 'stopped' ? 'bg-orange-500' : 'bg-gray-500'
                                       }`}></span>
                                    <span className={`text-xs font-bold uppercase ${run.status === 'running' ? 'text-primary' :
                                       run.status === 'success' ? 'text-success' :
                                          run.status === 'failed' ? 'text-error' :
                                             run.status === 'stopped' ? 'text-orange-500' : 'text-gray-500'
                                       }`}>{run.status}</span>
                                 </div>
                              </td>
                              <td className="px-4 py-4">
                                 <div className="text-xs text-gray-300">{run.baseModel}</div>
                                 <div className="text-[10px] text-gray-500 mt-0.5">{run.dataset}</div>
                              </td>
                              <td className="px-4 py-4 font-mono text-gray-400">{run.metrics?.loss?.toFixed(4) || '-'}</td>
                              <td className="px-4 py-4 font-mono text-white font-bold">{run.metrics?.passAt1 > 0 ? `${run.metrics.passAt1}%` : '-'}</td>
                              <td className="px-4 py-4 text-right text-gray-500 text-xs">{run.startedAt || run.createdAt}</td>
                           </tr>
                        ))}
                        {filteredRuns.length === 0 && (
                           <tr>
                              <td colSpan={7} className="px-6 py-8 text-center text-gray-500">
                                 No runs found.
                              </td>
                           </tr>
                        )}
                     </tbody>
                  </table>
               ) : (
                  <div className="p-6 space-y-4">
                     {/* Currently Running Task */}
                     {queueData.activeRun && (
                        <div className="bg-surface border border-primary/50 rounded-xl p-4 mb-4">
                           <div className="flex items-center gap-3">
                              <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                              <div>
                                 <div className="text-[10px] font-bold text-primary uppercase">Currently Running</div>
                                 <Link to={`/runs/${queueData.activeRun.id}`} className="font-bold text-white hover:text-primary">
                                    {queueData.activeRun.name}
                                 </Link>
                              </div>
                           </div>
                        </div>
                     )}

                     {/* Waiting Queue */}
                     <div className="text-xs font-bold text-gray-400 uppercase mb-2">Waiting Queue ({queueData.queue.length})</div>
                     {queueLoading && queueData.queue.length === 0 ? (
                        <div className="text-center text-gray-500 py-8">
                           <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto"></div>
                        </div>
                     ) : queueData.queue.length === 0 ? (
                        <div className="text-center text-gray-500 py-12">No runs currently queued.</div>
                     ) : (
                        queueData.queue.map((run, index) => (
                           <div key={run.id} className="bg-surface border border-border rounded-xl p-4 flex items-center justify-between hover:border-gray-600 transition-colors">
                              <div className="flex items-center gap-4">
                                 <div className="text-2xl font-bold text-gray-600 w-8 text-center">#{run.queuePosition}</div>
                                 <div>
                                    <div className="font-bold text-white">{run.name}</div>
                                    <div className="flex gap-2 mt-1">
                                       <span className="text-[10px] bg-white/10 text-gray-400 px-1.5 py-0.5 rounded">{run.type}</span>
                                       <span className="text-[10px] text-gray-600 font-mono">{run.id}</span>
                                    </div>
                                    <div className="text-xs text-gray-500 mt-1">
                                       {run.baseModel} • {run.dataset}
                                    </div>
                                 </div>
                              </div>
                              <div className="flex items-center gap-4">
                                 <div className="text-right">
                                    <div className="text-[10px] font-bold text-gray-500 uppercase">Created</div>
                                    <div className="text-xs text-gray-300">{new Date(run.createdAt).toLocaleString()}</div>
                                 </div>
                                 <div className="flex gap-1">
                                    <button
                                       onClick={() => handleMoveUp(run.id, run.queuePosition)}
                                       disabled={run.queuePosition <= 1}
                                       className={`p-2 rounded transition-colors ${run.queuePosition <= 1 ? 'text-gray-700 cursor-not-allowed' : 'hover:bg-white/10 text-gray-400 hover:text-white'}`}
                                       title="Move Up"
                                    ><span className="material-symbols-outlined text-[20px]">arrow_upward</span></button>
                                    <button
                                       onClick={() => handleMoveDown(run.id, run.queuePosition, queueData.queue.length)}
                                       disabled={run.queuePosition >= queueData.queue.length}
                                       className={`p-2 rounded transition-colors ${run.queuePosition >= queueData.queue.length ? 'text-gray-700 cursor-not-allowed' : 'hover:bg-white/10 text-gray-400 hover:text-white'}`}
                                       title="Move Down"
                                    ><span className="material-symbols-outlined text-[20px]">arrow_downward</span></button>
                                    <button
                                       onClick={() => handleCancelQueue(run.id)}
                                       className="p-2 hover:bg-red-500/20 rounded text-red-400 hover:text-red-300 transition-colors"
                                       title="Cancel Queue"
                                    ><span className="material-symbols-outlined text-[20px]">close</span></button>
                                 </div>
                              </div>
                           </div>
                        ))
                     )}
                  </div>
               )}
            </div>
         </div>

         {/* Preview Drawer */}
         <div className="w-80 border-l border-border bg-surface hidden xl:flex flex-col">
            <div className="p-4 border-b border-border bg-surface/50">
               <h3 className="text-gray-400 text-xs uppercase font-bold">Run Preview</h3>
            </div>
            {selectedRuns.length > 0 ? (
               <div className="p-6 space-y-6">
                  {selectedRuns.slice(0, 2).map(runId => {
                     const r = runs.find(mr => mr.id === runId);
                     if (!r) return null;
                     return (
                        <div key={r.id} className="bg-black/20 rounded-xl p-4 border border-border">
                           <h4 className="font-bold text-white text-sm mb-2">{r.name}</h4>
                           <div className="space-y-2 text-xs text-gray-400">
                              <div className="flex justify-between">
                                 <span>Loss</span>
                                 <span className="text-white font-mono">{r.metrics?.loss || '-'}</span>
                              </div>
                              <div className="flex justify-between">
                                 <span>Pass@1</span>
                                 <span className="text-white font-mono">{r.metrics?.passAt1 ? `${r.metrics.passAt1}%` : '-'}</span>
                              </div>
                              <div className="flex justify-between">
                                 <span>Config</span>
                                 <span className="text-gray-500 font-mono">lr={r.config?.lr || '-'}</span>
                              </div>
                           </div>
                        </div>
                     );
                  })}
                  {selectedRuns.length === 2 && (
                     <Link to={`/compare?base=${selectedRuns[0]}&candidate=${selectedRuns[1]}`} className="block w-full py-2 bg-primary text-center text-white text-sm font-bold rounded-lg hover:bg-blue-600">
                        Compare 2 Runs
                     </Link>
                  )}
               </div>
            ) : (
               <div className="p-8 text-center text-gray-500 text-sm italic">
                  Select runs to compare or preview details.
               </div>
            )}
         </div>
      </div>
   );
};

export default Runs;
