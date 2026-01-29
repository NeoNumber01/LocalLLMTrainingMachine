import React, { useState, useEffect } from 'react';
import { fetchReports, generateReport, fetchReportPreview, updateReport, deleteReport, getReportDownloadUrl, fetchRuns } from '../lib/api';

interface Report {
   id: string;
   title: string;
   type: string;
   format: string;
   date: string;
   size: string;
}

interface ReportPreview {
   id: string;
   title: string;
   type: string;
   format: string;
   date: string;
   hasTrainingData?: boolean;
   message?: string;
   summary: { status: string };
   metrics: { finalLoss: number; passAt1: number; compileRate: number } | null;
   config: { learningRate: string; epochs: number; batchSize: number } | null;

   // Extended fields from AcademicReport
   runInfo?: {
      runName: string;
      duration: string;
      seed: number | null;
      gitCommit: string | null;
   };
   model?: {
      name: string;
      path: string;
      params: string;
      quantization: string;
   };
   dataset?: {
      name: string;
      source: string | null;
      trainSamples: number | null;
      valSamples: number | null;
      testSamples: number | null;
      totalTokens: number | null;
   };
   training?: {
      batchSize: number;
      gradientAccumulationSteps: number;
      effectiveBatchSize: number;
      learningRate: string;
      scheduler: string;
      warmupRatio: number;
      epochs: number;
      maxSeqLength: number;
      optimizer: string;
      weightDecay: number;
      precision: string;
   };
   lora?: {
      enabled: boolean;
      rank: number | null;
      alpha: number | null;
      dropout: number | null;
      targetModules: string[];
      trainableParams: string | null;
      trainablePercent: string | null;
   };
   trainingStats?: {
      totalSteps: number | null;
      totalTokens: number | null;
      tokensPerSecond: number | null;
      gpuHours: number | null;
   };
   evaluation?: {
      passAt1: number | null;
      passAt5: number | null;
      passAt10: number | null;
      compileRate: number | null;
      errorStats: {
         syntaxErrorRate: number | null;
         runtimeErrorRate: number | null;
         timeoutRate: number | null;
         assertionErrorRate: number | null;
         importErrorRate: number | null;
         memoryErrorRate: number | null;
      };
      timeStats: {
         meanRuntimeMs: number | null;
         p50RuntimeMs: number | null;
         p95RuntimeMs: number | null;
         maxRuntimeMs: number | null;
      };
   };
   hardware?: {
      gpu: string | null;
      gpuMemory: string | null;
      cpu: string | null;
      ram: string | null;
   };
   environment?: {
      os: string | null;
      python: string | null;
      pytorch: string | null;
      transformers: string | null;
      trl: string | null;
      peft: string | null;
      cuda: string | null;
      cudnn: string | null;
      bitsandbytes: string | null;
   };
}

const Reports: React.FC = () => {
   const [reports, setReports] = useState<Report[]>([]);
   const [loading, setLoading] = useState(true);
   const [generating, setGenerating] = useState(false);

   // Modal states
   const [selectedReport, setSelectedReport] = useState<Report | null>(null);
   const [previewData, setPreviewData] = useState<ReportPreview | null>(null);
   const [showPreview, setShowPreview] = useState(false);
   const [showEditModal, setShowEditModal] = useState(false);
   const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
   const [showCreateModal, setShowCreateModal] = useState(false);

   // Form states
   const [editTitle, setEditTitle] = useState('');
   const [newReportTitle, setNewReportTitle] = useState('');
   const [newReportFormat, setNewReportFormat] = useState<'HTML' | 'MARKDOWN'>('HTML');
   const [actionLoading, setActionLoading] = useState(false);

   // Run selection for report generation
   const [runs, setRuns] = useState<any[]>([]);
   const [selectedRunId, setSelectedRunId] = useState<string>('');
   const [runsLoading, setRunsLoading] = useState(false);

   const loadReports = () => {
      setLoading(true);
      fetchReports()
         .then(setReports)
         .catch(console.error)
         .finally(() => setLoading(false));
   };

   useEffect(() => {
      loadReports();
   }, []);

   const handleViewReport = async (report: Report) => {
      setSelectedReport(report);
      setShowPreview(true);
      try {
         const preview = await fetchReportPreview(report.id);
         setPreviewData(preview);
      } catch (e) {
         console.error(e);
      }
   };

   const handleEditClick = (report: Report) => {
      setSelectedReport(report);
      setEditTitle(report.title);
      setShowEditModal(true);
   };

   const handleEditSubmit = async () => {
      if (!selectedReport) return;
      setActionLoading(true);
      try {
         await updateReport(selectedReport.id, { title: editTitle });
         loadReports();
         setShowEditModal(false);
      } catch (e) {
         console.error(e);
      } finally {
         setActionLoading(false);
      }
   };

   const handleDeleteClick = (report: Report) => {
      setSelectedReport(report);
      setShowDeleteConfirm(true);
   };

   const handleDeleteConfirm = async () => {
      if (!selectedReport) return;
      setActionLoading(true);
      try {
         await deleteReport(selectedReport.id);
         loadReports();
         setShowDeleteConfirm(false);
      } catch (e) {
         console.error(e);
      } finally {
         setActionLoading(false);
      }
   };

   const handleDownload = (report: Report) => {
      window.open(getReportDownloadUrl(report.id), '_blank');
   };

   const handleOpenCreateModal = async () => {
      setShowCreateModal(true);
      setRunsLoading(true);
      try {
         const runList = await fetchRuns('success', 20);
         setRuns(runList);
         if (runList.length > 0) {
            setSelectedRunId(runList[0].id);
         }
      } catch (e) {
         console.error(e);
      } finally {
         setRunsLoading(false);
      }
   };

   const handleGenerateReport = async () => {
      if (!selectedRunId) {
         alert('Please select a completed training run first');
         return;
      }
      setActionLoading(true);
      try {
         await generateReport({
            runId: selectedRunId,
            title: newReportTitle || `Report ${new Date().toLocaleDateString()}`,
            format: newReportFormat,
         });
         loadReports();
         setShowCreateModal(false);
         setNewReportTitle('');
         setSelectedRunId('');
      } catch (e) {
         console.error(e);
      } finally {
         setActionLoading(false);
      }
   };

   const closeAllModals = () => {
      setShowPreview(false);
      setShowEditModal(false);
      setShowDeleteConfirm(false);
      setShowCreateModal(false);
      setSelectedReport(null);
      setPreviewData(null);
   };

   if (loading) {
      return (
         <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
         </div>
      );
   }

   return (
      <div className="flex h-full p-6 lg:p-8 overflow-y-auto">
         <div className="max-w-5xl mx-auto w-full space-y-6">
            <div className="flex justify-between items-center">
               <h1 className="text-2xl font-bold text-white">Reports</h1>
               <div className="flex gap-2">
                  <button
                     onClick={handleOpenCreateModal}
                     className="px-4 py-2 rounded-lg bg-primary hover:bg-blue-600 text-white text-sm font-medium flex items-center gap-2"
                  >
                     <span className="material-symbols-outlined text-[18px]">add</span>
                     New Report
                  </button>
               </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
               {reports.map(report => (
                  <div
                     key={report.id}
                     className="bg-surface border border-border rounded-xl p-5 hover:border-gray-500 transition-colors group flex flex-col h-full"
                  >
                     <div className="flex justify-between items-start mb-4">
                        <div className={`w-10 h-10 rounded flex items-center justify-center ${report.type === 'Comparison' ? 'bg-purple-500/10 text-purple-400' : 'bg-blue-500/10 text-blue-400'}`}>
                           <span className="material-symbols-outlined">{report.type === 'Comparison' ? 'compare_arrows' : 'analytics'}</span>
                        </div>
                        <span className="text-[10px] font-bold text-gray-500 bg-black/20 px-2 py-1 rounded uppercase">{report.format}</span>
                     </div>
                     <h3 className="text-white font-bold mb-2">{report.title}</h3>
                     <div className="text-xs text-gray-500 pt-4 border-t border-border/50 flex justify-between">
                        <span>{new Date(report.date).toLocaleDateString()}</span>
                        <span>{report.size}</span>
                     </div>

                     {/* Action buttons */}
                     <div className="flex gap-2 mt-4 pt-4 border-t border-border/50">
                        <button
                           onClick={() => handleViewReport(report)}
                           className="flex-1 py-1.5 rounded text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors flex items-center justify-center gap-1"
                        >
                           <span className="material-symbols-outlined text-[14px]">visibility</span>
                           View
                        </button>
                        <button
                           onClick={() => handleDownload(report)}
                           className="flex-1 py-1.5 rounded text-xs font-medium bg-success/10 text-success hover:bg-success/20 transition-colors flex items-center justify-center gap-1"
                        >
                           <span className="material-symbols-outlined text-[14px]">download</span>
                           Download
                        </button>
                        <button
                           onClick={() => handleEditClick(report)}
                           className="py-1.5 px-2 rounded text-xs font-medium bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white transition-colors"
                        >
                           <span className="material-symbols-outlined text-[14px]">edit</span>
                        </button>
                        <button
                           onClick={() => handleDeleteClick(report)}
                           className="py-1.5 px-2 rounded text-xs font-medium bg-error/10 text-error hover:bg-error/20 transition-colors"
                        >
                           <span className="material-symbols-outlined text-[14px]">delete</span>
                        </button>
                     </div>
                  </div>
               ))}

               {reports.length === 0 && (
                  <div className="col-span-full text-center py-12 text-gray-500">
                     <span className="material-symbols-outlined text-[48px] mb-4">description</span>
                     <p>No reports yet. Generate your first report!</p>
                  </div>
               )}
            </div>
         </div>

         {/* Preview Modal */}
         {showPreview && selectedReport && (
            <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={closeAllModals}>
               <div className="bg-surface border border-border rounded-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
                  <div className="px-6 py-4 border-b border-border flex justify-between items-center">
                     <h2 className="text-lg font-bold text-white">{selectedReport.title}</h2>
                     <button onClick={closeAllModals} className="text-gray-400 hover:text-white">
                        <span className="material-symbols-outlined">close</span>
                     </button>
                  </div>
                  <div className="p-6 overflow-y-auto max-h-[60vh]">
                     {previewData ? (
                        <div className="space-y-4">
                           {/* Basic Information */}
                           <div className="grid grid-cols-2 gap-4 text-sm">
                              <div className="bg-black/20 rounded-lg p-4">
                                 <div className="text-gray-400 text-xs uppercase mb-1">Type</div>
                                 <div className="text-white font-medium">{previewData.type}</div>
                              </div>
                              <div className="bg-black/20 rounded-lg p-4">
                                 <div className="text-gray-400 text-xs uppercase mb-1">Format</div>
                                 <div className="text-white font-medium">{previewData.format}</div>
                              </div>
                           </div>

                           {previewData.hasTrainingData && previewData.runInfo ? (
                              <>
                                 {/* Run Information */}
                                 <div className="bg-black/20 rounded-lg p-4">
                                    <h3 className="text-xs font-bold text-gray-400 uppercase mb-3">Run Information</h3>
                                    <div className="grid grid-cols-2 gap-2 text-sm">
                                       <div className="flex justify-between">
                                          <span className="text-gray-400">Run Name</span>
                                          <span className="text-white font-mono truncate ml-2">{previewData.runInfo.runName}</span>
                                       </div>
                                       {previewData.runInfo.duration && (
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">Duration</span>
                                             <span className="text-white font-mono">{previewData.runInfo.duration}</span>
                                          </div>
                                       )}
                                       {previewData.runInfo.seed && (
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">Seed</span>
                                             <span className="text-white font-mono">{previewData.runInfo.seed}</span>
                                          </div>
                                       )}
                                    </div>
                                 </div>

                                 {/* Model and Dataset */}
                                 {(previewData.model || previewData.dataset) && (
                                    <div className="grid grid-cols-2 gap-4">
                                       {previewData.model && (
                                          <div className="bg-black/20 rounded-lg p-4">
                                             <h3 className="text-xs font-bold text-gray-400 uppercase mb-3">Model</h3>
                                             <div className="text-white font-medium text-sm truncate">{previewData.model.name}</div>
                                             <div className="text-xs text-gray-500 mt-1">{previewData.model.params} • {previewData.model.quantization}</div>
                                          </div>
                                       )}
                                       {previewData.dataset && (
                                          <div className="bg-black/20 rounded-lg p-4">
                                             <h3 className="text-xs font-bold text-gray-400 uppercase mb-3">Dataset</h3>
                                             <div className="text-white font-medium text-sm truncate">{previewData.dataset.name}</div>
                                             <div className="text-xs text-gray-500 mt-1">{previewData.dataset.trainSamples?.toLocaleString() || 'N/A'} samples</div>
                                          </div>
                                       )}
                                    </div>
                                 )}

                                 {/* Key Metrics */}
                                 {previewData.evaluation && (
                                    <div className="bg-black/20 rounded-lg p-4">
                                       <h3 className="text-xs font-bold text-gray-400 uppercase mb-3">Evaluation Results</h3>
                                       <div className="grid grid-cols-4 gap-4">
                                          <div className="text-center">
                                             <div className="text-xl font-bold text-success">{previewData.evaluation.passAt1?.toFixed(1) ?? 'N/A'}%</div>
                                             <div className="text-xs text-gray-500">Pass@1</div>
                                          </div>
                                          <div className="text-center">
                                             <div className="text-xl font-bold text-white">{previewData.evaluation.passAt5?.toFixed(1) ?? 'N/A'}%</div>
                                             <div className="text-xs text-gray-500">Pass@5</div>
                                          </div>
                                          <div className="text-center">
                                             <div className="text-xl font-bold text-white">{previewData.evaluation.passAt10?.toFixed(1) ?? 'N/A'}%</div>
                                             <div className="text-xs text-gray-500">Pass@10</div>
                                          </div>
                                          <div className="text-center">
                                             <div className="text-xl font-bold text-primary">{previewData.evaluation.compileRate?.toFixed(1) ?? 'N/A'}%</div>
                                             <div className="text-xs text-gray-500">Compile Rate</div>
                                          </div>
                                       </div>
                                    </div>
                                 )}

                                 {/* Training Configuration (only shown for training reports, hidden for evaluation reports) */}
                                 {previewData.training && previewData.type !== 'Evaluation' && (
                                    <div className="bg-black/20 rounded-lg p-4">
                                       <h3 className="text-xs font-bold text-gray-400 uppercase mb-3">Training Configuration</h3>
                                       <div className="grid grid-cols-2 gap-2 text-sm">
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">Learning Rate</span>
                                             <span className="text-white font-mono">{previewData.training.learningRate}</span>
                                          </div>
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">Epochs</span>
                                             <span className="text-white font-mono">{previewData.training.epochs}</span>
                                          </div>
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">Batch Size</span>
                                             <span className="text-white font-mono">{previewData.training.batchSize}</span>
                                          </div>
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">Max Seq Length</span>
                                             <span className="text-white font-mono">{previewData.training.maxSeqLength || 'N/A'}</span>
                                          </div>
                                       </div>
                                    </div>
                                 )}

                                 {/* LoRA Configuration (only shown for training reports) */}
                                 {previewData.lora?.enabled && previewData.type !== 'Evaluation' && (
                                    <div className="bg-black/20 rounded-lg p-4">
                                       <h3 className="text-xs font-bold text-gray-400 uppercase mb-3">LoRA Configuration</h3>
                                       <div className="grid grid-cols-3 gap-2 text-sm">
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">Rank</span>
                                             <span className="text-white font-mono">{previewData.lora.rank ?? 'N/A'}</span>
                                          </div>
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">Alpha</span>
                                             <span className="text-white font-mono">{previewData.lora.alpha ?? 'N/A'}</span>
                                          </div>
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">Trainable</span>
                                             <span className="text-white font-mono">{previewData.lora.trainablePercent ?? 'N/A'}</span>
                                          </div>
                                       </div>
                                    </div>
                                 )}

                                 {/* Training Statistics (only shown for training reports) */}
                                 {previewData.trainingStats && previewData.type !== 'Evaluation' && (
                                    <div className="bg-black/20 rounded-lg p-4">
                                       <h3 className="text-xs font-bold text-gray-400 uppercase mb-3">Training Statistics</h3>
                                       <div className="grid grid-cols-2 gap-2 text-sm">
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">Total Steps</span>
                                             <span className="text-white font-mono">{previewData.trainingStats.totalSteps?.toLocaleString() ?? 'N/A'}</span>
                                          </div>
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">Tokens/sec</span>
                                             <span className="text-white font-mono">{previewData.trainingStats.tokensPerSecond?.toFixed(1) ?? 'N/A'}</span>
                                          </div>
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">GPU Hours</span>
                                             <span className="text-white font-mono">{previewData.trainingStats.gpuHours?.toFixed(4) ?? 'N/A'}</span>
                                          </div>
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">Total Tokens</span>
                                             <span className="text-white font-mono">{previewData.trainingStats.totalTokens?.toLocaleString() ?? 'N/A'}</span>
                                          </div>
                                       </div>
                                    </div>
                                 )}

                                 {/* Hardware Information */}
                                 {previewData.hardware && (
                                    <div className="bg-black/20 rounded-lg p-4">
                                       <h3 className="text-xs font-bold text-gray-400 uppercase mb-3">Hardware</h3>
                                       <div className="grid grid-cols-2 gap-2 text-sm">
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">GPU</span>
                                             <span className="text-white font-mono truncate ml-2">{previewData.hardware.gpu || 'N/A'}</span>
                                          </div>
                                          <div className="flex justify-between">
                                             <span className="text-gray-400">VRAM</span>
                                             <span className="text-white font-mono">{previewData.hardware.gpuMemory || 'N/A'}</span>
                                          </div>
                                       </div>
                                    </div>
                                 )}

                                 <div className="text-xs text-gray-500 text-center pt-2">
                                    Download the full report for more details
                                 </div>
                              </>
                           ) : (
                              <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-6 text-center">
                                 <span className="material-symbols-outlined text-[48px] text-yellow-500 mb-3">info</span>
                                 <h3 className="text-white font-bold mb-2">No Training Data Available</h3>
                                 <p className="text-gray-400 text-sm">
                                    {previewData.message || 'This report is currently a template. After completing a training run, the report will contain actual training data.'}
                                 </p>
                              </div>
                           )}
                        </div>
                     ) : (
                        <div className="flex items-center justify-center py-12">
                           <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                        </div>
                     )}
                  </div>
                  <div className="px-6 py-4 border-t border-border flex justify-end gap-3">
                     <button
                        onClick={() => handleDownload(selectedReport)}
                        className="px-4 py-2 rounded-lg bg-primary hover:bg-blue-600 text-white text-sm font-medium flex items-center gap-2"
                     >
                        <span className="material-symbols-outlined text-[18px]">download</span>
                        Download Full Report
                     </button>
                  </div>
               </div>
            </div>
         )}

         {/* Edit Modal */}
         {showEditModal && selectedReport && (
            <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={closeAllModals}>
               <div className="bg-surface border border-border rounded-2xl w-full max-w-md" onClick={e => e.stopPropagation()}>
                  <div className="px-6 py-4 border-b border-border">
                     <h2 className="text-lg font-bold text-white">Edit Report</h2>
                  </div>
                  <div className="p-6 space-y-4">
                     <div className="space-y-2">
                        <label className="text-xs font-bold text-gray-400 uppercase">Title</label>
                        <input
                           type="text"
                           value={editTitle}
                           onChange={e => setEditTitle(e.target.value)}
                           className="w-full bg-black/20 border border-border rounded-lg p-3 text-white focus:border-primary focus:outline-none"
                        />
                     </div>
                  </div>
                  <div className="px-6 py-4 border-t border-border flex justify-end gap-3">
                     <button onClick={closeAllModals} className="px-4 py-2 rounded-lg text-gray-400 hover:text-white">
                        Cancel
                     </button>
                     <button
                        onClick={handleEditSubmit}
                        disabled={actionLoading}
                        className="px-4 py-2 rounded-lg bg-primary hover:bg-blue-600 text-white font-medium disabled:opacity-50"
                     >
                        {actionLoading ? 'Saving...' : 'Save Changes'}
                     </button>
                  </div>
               </div>
            </div>
         )}

         {/* Delete Confirmation Modal */}
         {showDeleteConfirm && selectedReport && (
            <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={closeAllModals}>
               <div className="bg-surface border border-border rounded-2xl w-full max-w-md" onClick={e => e.stopPropagation()}>
                  <div className="px-6 py-4 border-b border-border">
                     <h2 className="text-lg font-bold text-error">Delete Report</h2>
                  </div>
                  <div className="p-6">
                     <p className="text-gray-300">
                        Are you sure you want to delete <span className="font-bold text-white">"{selectedReport.title}"</span>?
                        This action cannot be undone.
                     </p>
                  </div>
                  <div className="px-6 py-4 border-t border-border flex justify-end gap-3">
                     <button onClick={closeAllModals} className="px-4 py-2 rounded-lg text-gray-400 hover:text-white">
                        Cancel
                     </button>
                     <button
                        onClick={handleDeleteConfirm}
                        disabled={actionLoading}
                        className="px-4 py-2 rounded-lg bg-error hover:bg-red-600 text-white font-medium disabled:opacity-50"
                     >
                        {actionLoading ? 'Deleting...' : 'Delete'}
                     </button>
                  </div>
               </div>
            </div>
         )}

         {/* Create Report Modal */}
         {showCreateModal && (
            <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={closeAllModals}>
               <div className="bg-surface border border-border rounded-2xl w-full max-w-md" onClick={e => e.stopPropagation()}>
                  <div className="px-6 py-4 border-b border-border">
                     <h2 className="text-lg font-bold text-white">Generate New Report</h2>
                  </div>
                  <div className="p-6 space-y-4">
                     {/* Run Selection */}
                     <div className="space-y-2">
                        <label className="text-xs font-bold text-gray-400 uppercase">Select Training Run *</label>
                        {runsLoading ? (
                           <div className="flex items-center justify-center py-4">
                              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                           </div>
                        ) : runs.length === 0 ? (
                           <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4 text-center">
                              <span className="material-symbols-outlined text-yellow-500 text-[24px] mb-2">warning</span>
                              <p className="text-sm text-yellow-400">No completed runs available. Complete a training run first to generate a report.</p>
                           </div>
                        ) : (
                           <select
                              value={selectedRunId}
                              onChange={e => setSelectedRunId(e.target.value)}
                              className="w-full bg-black/20 border border-border rounded-lg p-3 text-white focus:border-primary focus:outline-none"
                           >
                              {runs.map(run => (
                                 <option key={run.id} value={run.id}>
                                    {run.name} ({new Date(run.createdAt).toLocaleDateString()})
                                 </option>
                              ))}
                           </select>
                        )}
                     </div>

                     <div className="space-y-2">
                        <label className="text-xs font-bold text-gray-400 uppercase">Title</label>
                        <input
                           type="text"
                           value={newReportTitle}
                           onChange={e => setNewReportTitle(e.target.value)}
                           placeholder="e.g. Training Report - Jan 2026"
                           className="w-full bg-black/20 border border-border rounded-lg p-3 text-white focus:border-primary focus:outline-none"
                        />
                     </div>
                     <div className="space-y-2">
                        <label className="text-xs font-bold text-gray-400 uppercase">Format</label>
                        <div className="grid grid-cols-2 gap-3">
                           <button
                              onClick={() => setNewReportFormat('HTML')}
                              className={`p-3 rounded-lg border text-sm font-medium flex items-center justify-center gap-2 ${newReportFormat === 'HTML'
                                 ? 'bg-primary/10 border-primary text-primary'
                                 : 'bg-black/20 border-border text-gray-400 hover:border-gray-500'
                                 }`}
                           >
                              <span className="material-symbols-outlined text-[18px]">code</span>
                              HTML
                           </button>
                           <button
                              onClick={() => setNewReportFormat('MARKDOWN')}
                              className={`p-3 rounded-lg border text-sm font-medium flex items-center justify-center gap-2 ${newReportFormat === 'MARKDOWN'
                                 ? 'bg-primary/10 border-primary text-primary'
                                 : 'bg-black/20 border-border text-gray-400 hover:border-gray-500'
                                 }`}
                           >
                              <span className="material-symbols-outlined text-[18px]">description</span>
                              Markdown
                           </button>
                        </div>
                     </div>
                  </div>
                  <div className="px-6 py-4 border-t border-border flex justify-end gap-3">
                     <button onClick={closeAllModals} className="px-4 py-2 rounded-lg text-gray-400 hover:text-white">
                        Cancel
                     </button>
                     <button
                        onClick={handleGenerateReport}
                        disabled={actionLoading}
                        className="px-4 py-2 rounded-lg bg-primary hover:bg-blue-600 text-white font-medium disabled:opacity-50 flex items-center gap-2"
                     >
                        {actionLoading ? (
                           <>
                              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                              Generating...
                           </>
                        ) : (
                           <>
                              <span className="material-symbols-outlined text-[18px]">add</span>
                              Generate
                           </>
                        )}
                     </button>
                  </div>
               </div>
            </div>
         )}
      </div>
   );
};

export default Reports;
