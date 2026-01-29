import React, { useState, useEffect } from 'react';
import ScannerPanel from '../components/ScannerPanel';
import { fetchAdapters, rescanAdapters, mergeAdapter, deleteAdapter } from '../lib/api';
import { Link } from 'react-router-dom';

const Adapters: React.FC = () => {
   const [adapters, setAdapters] = useState<any[]>([]);
   const [loading, setLoading] = useState(true);
   const [scanning, setScanning] = useState(false);

   // Merge modal state
   const [mergeModal, setMergeModal] = useState<{ adapter: any; show: boolean }>({ adapter: null, show: false });
   const [mergeProgress, setMergeProgress] = useState(0);
   const [mergeStatus, setMergeStatus] = useState<'idle' | 'running' | 'success' | 'error'>('idle');
   const [mergeMessage, setMergeMessage] = useState('');
   const [outputName, setOutputName] = useState('');

   const loadAdapters = () => {
      setLoading(true);
      fetchAdapters()
         .then(setAdapters)
         .catch(console.error)
         .finally(() => setLoading(false));
   };

   useEffect(() => {
      loadAdapters();
   }, []);

   const handleRescan = async () => {
      setScanning(true);
      try {
         await rescanAdapters();
         loadAdapters();
      } catch (e) {
         console.error(e);
      } finally {
         setScanning(false);
      }
   };

   const openMergeModal = (adapter: any) => {
      setMergeModal({ adapter, show: true });
      setOutputName(`${adapter.name}-merged`);
      setMergeStatus('idle');
      setMergeProgress(0);
      setMergeMessage('');
   };

   const closeMergeModal = () => {
      if (mergeStatus === 'running') return; // Prevent closing running merge
      setMergeModal({ adapter: null, show: false });
   };

   const handleMerge = () => {
      if (!mergeModal.adapter) return;

      setMergeStatus('running');
      setMergeProgress(0);
      setMergeMessage('Starting merge process...');

      const eventSource = mergeAdapter(mergeModal.adapter.id, outputName);

      eventSource.onmessage = (event) => {
         try {
            const data = JSON.parse(event.data);
            setMergeMessage(data.message || '');
            if (data.progress !== undefined) {
               setMergeProgress(data.progress);
            }
            if (data.status === 'success') {
               setMergeStatus('success');
            } else if (data.status === 'error') {
               setMergeStatus('error');
            }
         } catch {
            // ignore
         }
      };

      eventSource.onerror = () => {
         setMergeStatus('error');
         setMergeMessage('Connection lost');
      };
   };

   const handleDelete = async (adapter: any) => {
      if (!confirm(`Remove "${adapter.name}" from list? (Local files will NOT be deleted)`)) return;
      try {
         await deleteAdapter(adapter.id);
         loadAdapters();
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

   return (
      <div className="flex h-full">
         <div className="flex-1 flex flex-col min-w-0">
            <div className="px-6 py-4 border-b border-border bg-surface flex justify-between items-center">
               <div>
                  <h1 className="text-lg font-bold text-white">LoRA Adapters</h1>
                  <p className="text-xs text-gray-500 mt-1">Manage trained LoRA adapters.</p>
               </div>
               <div className="flex gap-2">
                  <button
                     onClick={handleRescan}
                     disabled={scanning}
                     className="bg-primary hover:bg-blue-600 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                  >
                     <span className={`material-symbols-outlined text-[18px] ${scanning ? 'animate-spin' : ''}`}>refresh</span>
                     {scanning ? 'Scanning...' : 'Rescan'}
                  </button>
               </div>
            </div>

            <div className="flex-1 overflow-auto bg-background p-6">
               <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {adapters.map((adapter) => (
                     <div key={adapter.id} className="bg-surface border border-border rounded-xl p-5 flex flex-col gap-4 hover:border-primary/50 transition-colors">
                        <div className="flex justify-between items-start">
                           <div>
                              <h3 className="font-bold text-white">{adapter.name}</h3>
                              <p className="text-xs text-gray-500 mt-1">Base: {adapter.baseModel}</p>
                           </div>
                           <span className={`px-2 py-0.5 rounded text-xs ${adapter.status === 'success' ? 'bg-success/10 text-success' :
                              adapter.status === 'warning' ? 'bg-warning/10 text-warning' : 'bg-error/10 text-error'
                              }`}>{adapter.status}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                           <div className="bg-black/20 rounded p-2">
                              <div className="text-gray-500">Rank</div>
                              <div className="text-white font-mono">{adapter.rank}</div>
                           </div>
                           <div className="bg-black/20 rounded p-2">
                              <div className="text-gray-500">Alpha</div>
                              <div className="text-white font-mono">{adapter.alpha}</div>
                           </div>
                           <div className="bg-black/20 rounded p-2">
                              <div className="text-gray-500">Pass@1</div>
                              <div className="text-white font-mono">{adapter.metrics?.passAt1 || 0}%</div>
                           </div>
                           <div className="bg-black/20 rounded p-2">
                              <div className="text-gray-500">Compile</div>
                              <div className="text-white font-mono">{adapter.metrics?.compileRate || 0}%</div>
                           </div>
                        </div>
                        <div className="flex gap-2 mt-auto">
                           <button
                              onClick={() => openMergeModal(adapter)}
                              className="flex-1 bg-white/5 hover:bg-white/10 text-white py-2 rounded-lg text-xs font-medium transition-colors"
                           >
                              Merge to Base
                           </button>
                           <Link to="/playground" className="flex-1 bg-primary/10 hover:bg-primary/20 text-primary py-2 rounded-lg text-xs font-medium transition-colors text-center">
                              Test in Playground
                           </Link>
                           <button
                              onClick={() => handleDelete(adapter)}
                              className="p-2 bg-white/5 hover:bg-red-500/20 text-gray-400 hover:text-red-400 rounded-lg transition-colors"
                              title="Delete adapter"
                           >
                              <span className="material-symbols-outlined text-[16px]">delete</span>
                           </button>
                        </div>
                     </div>
                  ))}
                  {adapters.length === 0 && (
                     <div className="col-span-full text-center text-gray-500 py-12">
                        No adapters found. Train a model with LoRA to create adapters.
                     </div>
                  )}
               </div>
            </div>
         </div>

         <ScannerPanel entityType="Adapters" />

         {/* Merge Modal */}
         {mergeModal.show && (
            <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={closeMergeModal}>
               <div className="bg-surface border border-border rounded-2xl w-full max-w-md" onClick={e => e.stopPropagation()}>
                  <div className="px-6 py-4 border-b border-border flex justify-between items-center">
                     <h2 className="text-lg font-bold text-white">Merge Adapter to Base Model</h2>
                     {mergeStatus !== 'running' && (
                        <button onClick={closeMergeModal} className="text-gray-400 hover:text-white">
                           <span className="material-symbols-outlined">close</span>
                        </button>
                     )}
                  </div>
                  <div className="p-6 space-y-4">
                     <div>
                        <label className="block text-sm text-gray-400 mb-1">Adapter</label>
                        <div className="text-white font-medium">{mergeModal.adapter?.name}</div>
                        <div className="text-xs text-gray-500">Base: {mergeModal.adapter?.baseModel}</div>
                     </div>

                     <div>
                        <label className="block text-sm text-gray-400 mb-1">Output Model Name</label>
                        <input
                           type="text"
                           value={outputName}
                           onChange={e => setOutputName(e.target.value)}
                           disabled={mergeStatus === 'running'}
                           className="w-full bg-black/30 border border-border rounded-lg px-3 py-2 text-white text-sm disabled:opacity-50"
                           placeholder="merged-model-name"
                        />
                     </div>

                     {mergeStatus !== 'idle' && (
                        <div className="space-y-2">
                           <div className="flex justify-between text-xs">
                              <span className={
                                 mergeStatus === 'success' ? 'text-success' :
                                    mergeStatus === 'error' ? 'text-error' : 'text-primary'
                              }>
                                 {mergeStatus === 'success' ? '✓ Complete' :
                                    mergeStatus === 'error' ? '✗ Failed' : 'Merging...'}
                              </span>
                              <span className="text-gray-500">{mergeProgress}%</span>
                           </div>
                           <div className="w-full bg-black/30 rounded-full h-2">
                              <div
                                 className={`h-2 rounded-full transition-all ${mergeStatus === 'success' ? 'bg-success' :
                                    mergeStatus === 'error' ? 'bg-error' : 'bg-primary'
                                    }`}
                                 style={{ width: `${mergeProgress}%` }}
                              ></div>
                           </div>
                           <div className="text-xs text-gray-400 truncate">{mergeMessage}</div>
                        </div>
                     )}

                     <div className="text-xs text-gray-500 bg-black/20 rounded p-3">
                        <strong>Note:</strong> This will create a standalone merged model. The process requires significant GPU memory and disk space.
                     </div>
                  </div>
                  <div className="px-6 py-4 border-t border-border flex justify-end gap-2">
                     {mergeStatus !== 'running' && (
                        <button onClick={closeMergeModal} className="px-4 py-2 rounded-lg text-gray-400 hover:text-white">
                           {mergeStatus === 'success' ? 'Done' : 'Cancel'}
                        </button>
                     )}
                     {mergeStatus !== 'success' && (
                        <button
                           onClick={handleMerge}
                           disabled={mergeStatus === 'running' || !outputName.trim()}
                           className="px-4 py-2 bg-primary hover:bg-blue-600 disabled:opacity-50 text-white rounded-lg text-sm font-medium flex items-center gap-2"
                        >
                           {mergeStatus === 'running' && <span className="material-symbols-outlined text-[16px] animate-spin">sync</span>}
                           {mergeStatus === 'running' ? 'Merging...' : mergeStatus === 'error' ? 'Retry' : 'Start Merge'}
                        </button>
                     )}
                  </div>
               </div>
            </div>
         )}
      </div>
   );
};

export default Adapters;
