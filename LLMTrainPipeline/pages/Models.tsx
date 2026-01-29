import React, { useState, useEffect } from 'react';
import { fetchModels, importModel, deleteModel, openNativeDialog } from '../lib/api';
import { Link } from 'react-router-dom';

const Models: React.FC = () => {
   const [models, setModels] = useState<any[]>([]);
   const [loading, setLoading] = useState(true);
   const [selectedModel, setSelectedModel] = useState<string | null>(null);
   const [importing, setImporting] = useState(false);

   const loadModels = () => {
      setLoading(true);
      fetchModels()
         .then(setModels)
         .catch(console.error)
         .finally(() => setLoading(false));
   };

   useEffect(() => {
      loadModels();
   }, []);

   const handleImportClick = async () => {
      setImporting(true);
      try {
         const result = await openNativeDialog('folder', {
            title: 'Select Model Folder',
         });

         if (result.selected && result.path && result.name) {
            await importModel(result.path, result.name);
            loadModels();
         }
      } catch (e) {
         console.error(e);
      } finally {
         setImporting(false);
      }
   };

   const handleDelete = async (id: string, name: string) => {
      if (!confirm(`Remove "${name}" from list? (Local files will NOT be deleted)`)) return;
      try {
         await deleteModel(id);
         loadModels();
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
                  <h1 className="text-lg font-bold text-white">Models Registry</h1>
                  <p className="text-xs text-gray-500 mt-1">Manage local base models and fine-tuned checkpoints.</p>
               </div>
               <div className="flex gap-2">
                  <button
                     onClick={handleImportClick}
                     disabled={importing}
                     className="bg-surface border border-border hover:bg-white/5 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                  >
                     <span className="material-symbols-outlined text-[18px]">folder_open</span>
                     {importing ? 'Importing...' : 'Import Local'}
                  </button>
               </div>
            </div>

            <div className="flex-1 overflow-auto bg-background p-6">
               <div className="bg-surface border border-border rounded-xl overflow-hidden">
                  <table className="w-full text-left text-sm">
                     <thead className="bg-black/20 text-xs uppercase text-gray-500 font-medium border-b border-border">
                        <tr>
                           <th className="px-6 py-3">Model Name</th>
                           <th className="px-6 py-3">Architecture</th>
                           <th className="px-6 py-3">Quantization</th>
                           <th className="px-6 py-3">Source</th>
                           <th className="px-6 py-3">Status</th>
                           <th className="px-6 py-3 text-right">Actions</th>
                        </tr>
                     </thead>
                     <tbody className="divide-y divide-border">
                        {models.map((model) => (
                           <React.Fragment key={model.id}>
                              <tr
                                 className={`hover:bg-white/[0.02] transition-colors cursor-pointer ${selectedModel === model.id ? 'bg-white/[0.04]' : ''}`}
                                 onClick={() => setSelectedModel(selectedModel === model.id ? null : model.id)}
                              >
                                 <td className="px-6 py-4">
                                    <div className="flex items-center gap-3">
                                       <div className="w-8 h-8 rounded bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-xs">
                                          {model.name.substring(0, 2).toUpperCase()}
                                       </div>
                                       <div className="flex flex-col">
                                          <span className="text-white font-medium">{model.name}</span>
                                          <span className="text-[10px] text-gray-500 font-mono break-all">{model.path}</span>
                                       </div>
                                    </div>
                                 </td>
                                 <td className="px-6 py-4 text-gray-300 font-mono text-xs">{model.params} Params</td>
                                 <td className="px-6 py-4">
                                    <span className={`px-2 py-0.5 rounded text-xs border ${model.quantization === 'None' ? 'bg-gray-800 border-gray-700 text-gray-400' :
                                       'bg-purple-500/10 border-purple-500/20 text-purple-400'
                                       }`}>{model.quantization}</span>
                                 </td>
                                 <td className="px-6 py-4 text-gray-400 text-xs">{model.source}</td>
                                 <td className="px-6 py-4">
                                    <div className="flex items-center gap-2">
                                       <span className={`w-1.5 h-1.5 rounded-full ${model.status === 'Valid' ? 'bg-success' : 'bg-error'}`}></span>
                                       <span className={model.status === 'Valid' ? 'text-success' : 'text-error'}>{model.status}</span>
                                    </div>
                                 </td>
                                 <td className="px-6 py-4 text-right">
                                    <div className="flex items-center justify-end gap-2">
                                       <button
                                          onClick={(e) => { e.stopPropagation(); handleDelete(model.id, model.name); }}
                                          className="text-gray-500 hover:text-red-400 transition-colors"
                                          title="Remove from list"
                                       >
                                          <span className="material-symbols-outlined text-[18px]">delete</span>
                                       </button>
                                       <button className="text-gray-500 hover:text-white transition-colors">
                                          <span className="material-symbols-outlined">{selectedModel === model.id ? 'expand_less' : 'expand_more'}</span>
                                       </button>
                                    </div>
                                 </td>
                              </tr>
                              {selectedModel === model.id && (
                                 <tr className="bg-black/20">
                                    <td colSpan={6} className="px-6 py-4">
                                       <div className="grid grid-cols-3 gap-6 text-xs">
                                          <div className="space-y-2">
                                             <h4 className="font-bold text-gray-500 uppercase">Model Info</h4>
                                             <div className="grid grid-cols-2 gap-y-1 text-gray-400">
                                                <span>Backend:</span> <span className="text-white">{model.backend || 'transformers'}</span>
                                                <span>Source:</span> <span className="text-white">{model.source}</span>
                                                <span>Last Modified:</span> <span className="text-white">{model.lastModified || 'Unknown'}</span>
                                             </div>
                                          </div>
                                          <div className="space-y-2">
                                             <h4 className="font-bold text-gray-500 uppercase">Path</h4>
                                             <div className="text-gray-300 font-mono text-[10px] break-all bg-black/30 rounded p-2">
                                                {model.path}
                                             </div>
                                          </div>
                                          <div className="space-y-2">
                                             <h4 className="font-bold text-gray-500 uppercase">Actions</h4>
                                             <div className="flex flex-col gap-2">
                                                <Link to="/runs/new" className="text-primary hover:underline">Create Run with this Model</Link>
                                                <Link to="/playground" className="text-primary hover:underline">Test in Playground</Link>
                                             </div>
                                          </div>
                                       </div>
                                    </td>
                                 </tr>
                              )}
                           </React.Fragment>
                        ))}
                        {models.length === 0 && (
                           <tr>
                              <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                                 No models found. Click "Import Local" to add models.
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

export default Models;
