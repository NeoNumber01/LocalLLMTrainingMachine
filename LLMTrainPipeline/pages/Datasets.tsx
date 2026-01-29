import React, { useState, useEffect } from 'react';
import { fetchDatasets, fetchDatasetPreview, importDataset, deleteDataset, openNativeDialog } from '../lib/api';

const Datasets: React.FC = () => {
   const [datasets, setDatasets] = useState<any[]>([]);
   const [loading, setLoading] = useState(true);
   const [selectedDataset, setSelectedDataset] = useState<string | null>(null);
   const [preview, setPreview] = useState<any>(null);
   const [importing, setImporting] = useState(false);

   const loadDatasets = () => {
      setLoading(true);
      fetchDatasets()
         .then(setDatasets)
         .catch(console.error)
         .finally(() => setLoading(false));
   };

   useEffect(() => {
      loadDatasets();
   }, []);

   const handlePreview = async (id: string) => {
      if (selectedDataset === id) {
         setSelectedDataset(null);
         setPreview(null);
      } else {
         setSelectedDataset(id);
         try {
            const data = await fetchDatasetPreview(id);
            setPreview(data);
         } catch (e) {
            console.error(e);
         }
      }
   };

   const handleImportClick = async () => {
      setImporting(true);
      try {
         const result = await openNativeDialog('file', {
            title: 'Select Dataset File',
            filter: 'Dataset Files|*.jsonl;*.json;*.parquet|All Files|*.*',
         });

         if (result.selected && result.path && result.name) {
            const isEval = result.name.toLowerCase().includes('eval') || result.name.toLowerCase().includes('test');
            await importDataset(result.path, result.name.replace(/\.(jsonl|json|parquet)$/i, ''), isEval ? 'Eval' : 'Train');
            loadDatasets();
         }
      } catch (e) {
         console.error(e);
      } finally {
         setImporting(false);
      }
   };

   const handleImportFolderClick = async () => {
      setImporting(true);
      try {
         const result = await openNativeDialog('folder', {
            title: 'Select Dataset Folder',
         });

         if (result.selected && result.path && result.name) {
            const isEval = result.name.toLowerCase().includes('eval') || result.name.toLowerCase().includes('test');
            await importDataset(result.path, result.name, isEval ? 'Eval' : 'Train');
            loadDatasets();
         }
      } catch (e) {
         console.error(e);
      } finally {
         setImporting(false);
      }
   };

   const handleDelete = async (id: string, name: string) => {
      if (!confirm(`Remove "${name}" from list? (Local file will NOT be deleted)`)) return;
      try {
         await deleteDataset(id);
         loadDatasets();
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
                  <h1 className="text-lg font-bold text-white">Datasets</h1>
                  <p className="text-xs text-gray-500 mt-1">Manage training and evaluation datasets.</p>
               </div>
               <div className="flex gap-2">
                  <button
                     onClick={handleImportClick}
                     disabled={importing}
                     className="bg-surface border border-border hover:bg-white/5 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                  >
                     <span className="material-symbols-outlined text-[18px]">upload_file</span>
                     {importing ? 'Importing...' : 'Import File'}
                  </button>
                  <button
                     onClick={handleImportFolderClick}
                     disabled={importing}
                     className="bg-surface border border-border hover:bg-white/5 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                  >
                     <span className="material-symbols-outlined text-[18px]">folder_open</span>
                     {importing ? 'Importing...' : 'Import Folder'}
                  </button>
               </div>
            </div>

            <div className="flex-1 overflow-auto bg-background p-6">
               <div className="bg-surface border border-border rounded-xl overflow-hidden">
                  <table className="w-full text-left text-sm">
                     <thead className="bg-black/20 text-xs uppercase text-gray-500 font-medium border-b border-border">
                        <tr>
                           <th className="px-6 py-3">Dataset Name</th>
                           <th className="px-6 py-3">Type</th>
                           <th className="px-6 py-3">Samples</th>
                           <th className="px-6 py-3">Format</th>
                           <th className="px-6 py-3">Size</th>
                           <th className="px-6 py-3">Status</th>
                           <th className="px-6 py-3 text-right">Actions</th>
                        </tr>
                     </thead>
                     <tbody className="divide-y divide-border">
                        {datasets.map((ds) => (
                           <React.Fragment key={ds.id}>
                              <tr
                                 className={`hover:bg-white/[0.02] transition-colors cursor-pointer ${selectedDataset === ds.id ? 'bg-white/[0.04]' : ''}`}
                                 onClick={() => handlePreview(ds.id)}
                              >
                                 <td className="px-6 py-4">
                                    <div className="flex items-center gap-3">
                                       <div className={`w-8 h-8 rounded flex items-center justify-center font-bold text-xs ${ds.type === 'Train' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'
                                          }`}>
                                          {ds.type === 'Train' ? 'TR' : 'EV'}
                                       </div>
                                       <div className="flex flex-col">
                                          <span className="text-white font-medium">{ds.name}</span>
                                          <span className="text-[10px] text-gray-500">v{ds.version}</span>
                                       </div>
                                    </div>
                                 </td>
                                 <td className="px-6 py-4">
                                    <span className={`px-2 py-0.5 rounded text-xs ${ds.type === 'Train' ? 'bg-green-500/10 text-green-400' : 'bg-blue-500/10 text-blue-400'
                                       }`}>{ds.type}</span>
                                 </td>
                                 <td className="px-6 py-4 font-mono text-gray-300">{ds.samples?.toLocaleString() || 0}</td>
                                 <td className="px-6 py-4 text-gray-400">{ds.format}</td>
                                 <td className="px-6 py-4 text-gray-400">{ds.size}</td>
                                 <td className="px-6 py-4">
                                    <div className="flex items-center gap-2">
                                       <span className={`w-1.5 h-1.5 rounded-full ${ds.status === 'Active' || ds.status === 'Ready' ? 'bg-success' :
                                          ds.status === 'Processing' ? 'bg-warning animate-pulse' : 'bg-error'
                                          }`}></span>
                                       <span className={`text-xs ${ds.status === 'Active' || ds.status === 'Ready' ? 'text-success' :
                                          ds.status === 'Processing' ? 'text-warning' : 'text-error'
                                          }`}>{ds.status}</span>
                                    </div>
                                 </td>
                                 <td className="px-6 py-4 text-right">
                                    <div className="flex items-center justify-end gap-2">
                                       <button
                                          onClick={(e) => { e.stopPropagation(); handleDelete(ds.id, ds.name); }}
                                          className="text-gray-500 hover:text-red-400 transition-colors"
                                          title="Remove from list"
                                       >
                                          <span className="material-symbols-outlined text-[18px]">delete</span>
                                       </button>
                                       <button className="text-gray-500 hover:text-white transition-colors">
                                          <span className="material-symbols-outlined">{selectedDataset === ds.id ? 'expand_less' : 'expand_more'}</span>
                                       </button>
                                    </div>
                                 </td>
                              </tr>
                              {selectedDataset === ds.id && preview && (
                                 <tr className="bg-black/20">
                                    <td colSpan={7} className="px-6 py-4">
                                       <div className="grid grid-cols-3 gap-6">
                                          <div className="space-y-2">
                                             <h4 className="font-bold text-gray-500 uppercase text-xs">Schema</h4>
                                             <div className="space-y-1">
                                                {preview.schema?.map((field: any, i: number) => (
                                                   <div key={i} className="flex items-center gap-2 text-xs">
                                                      <span className={`w-2 h-2 rounded-full ${field.valid ? 'bg-success' : 'bg-error'}`}></span>
                                                      <span className="text-gray-300">{field.field}</span>
                                                   </div>
                                                ))}
                                             </div>
                                          </div>
                                          <div className="space-y-2">
                                             <h4 className="font-bold text-gray-500 uppercase text-xs">Quality Stats</h4>
                                             <div className="grid grid-cols-2 gap-y-1 text-xs text-gray-400">
                                                <span>Total Tokens:</span> <span className="text-white">{preview.stats?.totalTokens}</span>
                                                <span>Avg Length:</span> <span className="text-white">{preview.stats?.avgLength}</span>
                                                <span>Duplicates:</span> <span className="text-white">{preview.stats?.duplicates}</span>
                                                <span>Empty Rows:</span> <span className="text-white">{preview.stats?.emptyRows}</span>
                                             </div>
                                          </div>
                                          <div className="space-y-2">
                                             <h4 className="font-bold text-gray-500 uppercase text-xs">Sample Preview</h4>
                                             <div className="bg-black/30 rounded p-2 text-xs">
                                                {preview.samples?.[0] && (
                                                   <div className="space-y-1">
                                                      <div className="text-gray-500">Prompt:</div>
                                                      <div className="text-gray-300 truncate">{preview.samples[0].prompt}</div>
                                                   </div>
                                                )}
                                             </div>
                                          </div>
                                       </div>
                                    </td>
                                 </tr>
                              )}
                           </React.Fragment>
                        ))}
                        {datasets.length === 0 && (
                           <tr>
                              <td colSpan={7} className="px-6 py-8 text-center text-gray-500">
                                 No datasets found. Click "Import File" or "Import Folder" to add datasets.
                              </td>
                           </tr>
                        )}
                     </tbody>
                  </table>
               </div>
            </div>
         </div>
      </div>
   );
};

export default Datasets;
