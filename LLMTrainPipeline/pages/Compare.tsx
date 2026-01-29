import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { compareRuns, fetchRuns, fetchRun } from '../lib/api';
import {
   LineChart,
   Line,
   XAxis,
   YAxis,
   CartesianGrid,
   Tooltip,
   Legend,
   ResponsiveContainer
} from 'recharts';

interface Run {
   id: string;
   name: string;
   type: string;
   status: string;
   createdAt: string;
}

const Compare: React.FC = () => {
   const [searchParams, setSearchParams] = useSearchParams();
   const navigate = useNavigate();

   const [loading, setLoading] = useState(true);
   const [comparing, setComparing] = useState(false);
   const [allRuns, setAllRuns] = useState<Run[]>([]);
   const [compareData, setCompareData] = useState<any>(null);
   const [baseRun, setBaseRun] = useState<Run | null>(null);
   const [candidateRun, setCandidateRun] = useState<Run | null>(null);

   // User selected IDs
   const [selectedBaseId, setSelectedBaseId] = useState<string>('');
   const [selectedCandidateId, setSelectedCandidateId] = useState<string>('');

   // UI state
   const [typeFilter, setTypeFilter] = useState<'all' | 'training' | 'evaluation'>('all');
   const [searchQuery, setSearchQuery] = useState('');
   const [showOnlyDiff, setShowOnlyDiff] = useState(true);
   const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());
   const [baseDropdownOpen, setBaseDropdownOpen] = useState(false);
   const [candidateDropdownOpen, setCandidateDropdownOpen] = useState(false);

   const baseId = searchParams.get('base');
   const candidateId = searchParams.get('candidate');

   // Load all runs list
   useEffect(() => {
      const loadRuns = async () => {
         try {
            const runs = await fetchRuns(undefined, 100);
            setAllRuns(runs);
         } catch (e) {
            console.error('Failed to load runs:', e);
         }
      };
      loadRuns();
   }, []);

   // Initialize selection state
   useEffect(() => {
      const initializeSelection = async () => {
         setLoading(true);
         try {
            let base: Run | null = null;
            let candidate: Run | null = null;

            if (baseId && candidateId) {
               try {
                  [base, candidate] = await Promise.all([
                     fetchRun(baseId),
                     fetchRun(candidateId)
                  ]);
               } catch (e) {
                  console.error("Failed to fetch specific runs", e);
               }
            }

            // Fallback: if not specified or fetch failed, take the most recent two runs
            if (!base || !candidate) {
               const recentRuns = await fetchRuns(undefined, 2);
               if (recentRuns.length > 0) {
                  candidate = recentRuns[0];
                  base = recentRuns[1] || recentRuns[0];
               }
            }

            if (base) {
               setBaseRun(base);
               setSelectedBaseId(base.id);
            }
            if (candidate) {
               setCandidateRun(candidate);
               setSelectedCandidateId(candidate.id);
            }

            if (base && candidate) {
               const data = await compareRuns(base.id, candidate.id);
               setCompareData(data);
            }
         } catch (e) {
            console.error(e);
         } finally {
            setLoading(false);
         }
      };

      initializeSelection();
   }, [baseId, candidateId]);

   // Execute comparison
   const doCompare = async (newBaseId: string, newCandidateId: string) => {
      if (!newBaseId || !newCandidateId) return;
      if (newBaseId === newCandidateId) return;

      setComparing(true);
      try {
         const [base, candidate] = await Promise.all([
            fetchRun(newBaseId),
            fetchRun(newCandidateId)
         ]);
         setBaseRun(base);
         setCandidateRun(candidate);

         const data = await compareRuns(newBaseId, newCandidateId);
         setCompareData(data);

         // Update URL
         setSearchParams({ base: newBaseId, candidate: newCandidateId });
      } catch (e) {
         console.error('Compare failed:', e);
      } finally {
         setComparing(false);
      }
   };

   // Filter runs list
   const filteredRuns = useMemo(() => {
      return allRuns.filter(run => {
         if (typeFilter !== 'all' && run.type !== typeFilter) return false;
         if (searchQuery && !run.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
         return true;
      });
   }, [allRuns, typeFilter, searchQuery]);

   // Swap base and candidate
   const handleSwap = () => {
      const tempId = selectedBaseId;
      setSelectedBaseId(selectedCandidateId);
      setSelectedCandidateId(tempId);
      doCompare(selectedCandidateId, selectedBaseId);
   };

   // Select baseline
   const handleSelectBase = (id: string) => {
      setSelectedBaseId(id);
      setBaseDropdownOpen(false);
      if (selectedCandidateId && id !== selectedCandidateId) {
         doCompare(id, selectedCandidateId);
      }
   };

   // Select candidate
   const handleSelectCandidate = (id: string) => {
      setSelectedCandidateId(id);
      setCandidateDropdownOpen(false);
      if (selectedBaseId && id !== selectedBaseId) {
         doCompare(selectedBaseId, id);
      }
   };

   // Toggle category collapse
   const toggleCategory = (category: string) => {
      setCollapsedCategories(prev => {
         const next = new Set(prev);
         if (next.has(category)) {
            next.delete(category);
         } else {
            next.add(category);
         }
         return next;
      });
   };

   // Export as JSON
   const exportAsJson = () => {
      const exportData = {
         base: { id: baseRun?.id, name: baseRun?.name, type: baseRun?.type },
         candidate: { id: candidateRun?.id, name: candidateRun?.name, type: candidateRun?.type },
         metrics: compareData?.metrics,
         configDiff: compareData?.configDiff,
         regressions: compareData?.regressions,
         exportedAt: new Date().toISOString(),
      };
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `compare-${baseRun?.name}-vs-${candidateRun?.name}.json`;
      a.click();
      URL.revokeObjectURL(url);
   };

   // Export as CSV
   const exportAsCsv = () => {
      const rows: string[][] = [];
      rows.push(['Parameter', 'Baseline', 'Candidate', 'Category']);

      const diffs = compareData?.configDiff || [];
      diffs.forEach((diff: any) => {
         rows.push([
            diff.param,
            diff.base === null ? 'N/A' : JSON.stringify(diff.base),
            diff.candidate === null ? 'N/A' : JSON.stringify(diff.candidate),
            diff.category || 'other'
         ]);
      });

      // Add metrics
      rows.push(['']);
      rows.push(['Metric', 'Baseline', 'Candidate', 'Delta']);
      const metrics = compareData?.metrics || {};
      Object.entries(metrics).forEach(([key, value]: [string, any]) => {
         rows.push([
            key,
            String(value.base ?? 'N/A'),
            String(value.candidate ?? 'N/A'),
            String(value.delta ?? 'N/A')
         ]);
      });

      const csvContent = rows.map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `compare-${baseRun?.name}-vs-${candidateRun?.name}.csv`;
      a.click();
      URL.revokeObjectURL(url);
   };

   // Run selector dropdown component
   const RunSelector: React.FC<{
      label: string;
      selectedId: string;
      onSelect: (id: string) => void;
      isOpen: boolean;
      setIsOpen: (open: boolean) => void;
      excludeId?: string;
      variant: 'base' | 'candidate';
   }> = ({ label, selectedId, onSelect, isOpen, setIsOpen, excludeId, variant }) => {
      const selectedRun = allRuns.find(r => r.id === selectedId);
      const availableRuns = filteredRuns.filter(r => r.id !== excludeId);

      return (
         <div className="relative">
            <label className="text-xs text-gray-500 uppercase font-bold mb-1 block">{label}</label>
            <button
               onClick={() => setIsOpen(!isOpen)}
               className={`w-full px-4 py-3 rounded-lg border text-left flex items-center justify-between gap-2 transition-all ${variant === 'base'
                  ? 'bg-black/30 border-border hover:border-gray-600'
                  : 'bg-primary/5 border-primary/30 hover:border-primary/50'
                  }`}
            >
               <div className="flex items-center gap-2 min-w-0">
                  {selectedRun ? (
                     <>
                        <span className="text-white font-medium truncate">{selectedRun.name}</span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold whitespace-nowrap ${selectedRun.type === 'evaluation' ? 'bg-purple-500/20 text-purple-400' : 'bg-primary/20 text-primary'
                           }`}>
                           {selectedRun.type === 'evaluation' ? 'Eval' : 'Train'}
                        </span>
                     </>
                  ) : (
                     <span className="text-gray-500">Select a run...</span>
                  )}
               </div>
               <span className="material-symbols-outlined text-gray-400 text-[18px] shrink-0">
                  {isOpen ? 'expand_less' : 'expand_more'}
               </span>
            </button>

            {isOpen && (
               <div className="absolute z-50 w-full mt-2 bg-surface border border-border rounded-xl shadow-2xl overflow-hidden">
                  {/* Search and filter */}
                  <div className="p-3 border-b border-border space-y-2">
                     <input
                        type="text"
                        placeholder="Search runs..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full px-3 py-2 bg-black/30 border border-border rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary/50"
                     />
                     <div className="flex gap-1">
                        {(['all', 'training', 'evaluation'] as const).map(type => (
                           <button
                              key={type}
                              onClick={() => setTypeFilter(type)}
                              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${typeFilter === type
                                 ? 'bg-primary text-black'
                                 : 'bg-black/20 text-gray-400 hover:bg-black/30'
                                 }`}
                           >
                              {type === 'all' ? 'All' : type === 'training' ? 'Train' : 'Eval'}
                           </button>
                        ))}
                     </div>
                  </div>

                  {/* Runs list */}
                  <div className="max-h-64 overflow-y-auto">
                     {availableRuns.length === 0 ? (
                        <div className="px-4 py-6 text-center text-gray-500 text-sm">
                           No runs found
                        </div>
                     ) : (
                        availableRuns.map(run => (
                           <button
                              key={run.id}
                              onClick={() => onSelect(run.id)}
                              className={`w-full px-4 py-3 text-left hover:bg-white/5 flex items-center justify-between border-b border-border/50 last:border-0 ${run.id === selectedId ? 'bg-primary/10' : ''
                                 }`}
                           >
                              <div className="flex items-center gap-2 min-w-0">
                                 <span className="text-white truncate">{run.name}</span>
                                 <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold whitespace-nowrap ${run.type === 'evaluation' ? 'bg-purple-500/20 text-purple-400' : 'bg-primary/20 text-primary'
                                    }`}>
                                    {run.type === 'evaluation' ? 'Eval' : 'Train'}
                                 </span>
                              </div>
                              <span className={`text-[10px] px-2 py-0.5 rounded uppercase font-bold ${run.status === 'success' ? 'bg-success/20 text-success' :
                                 run.status === 'failed' ? 'bg-error/20 text-error' :
                                    run.status === 'running' ? 'bg-yellow-500/20 text-yellow-400' :
                                       'bg-gray-500/20 text-gray-400'
                                 }`}>
                                 {run.status}
                              </span>
                           </button>
                        ))
                     )}
                  </div>
               </div>
            )}
         </div>
      );
   };

   // Prepare chart data - must be called before early return to keep Hooks order consistent
   const chartData = useMemo(() => {
      if (!compareData?.history) return null;

      const { base, candidate } = compareData.history;
      if (!base?.length && !candidate?.length) return null;

      // Merge time steps to create a unified X axis
      const steps = new Set<number>();
      base.forEach((m: any) => steps.add(m.step));
      candidate.forEach((m: any) => steps.add(m.step));
      const sortedSteps = Array.from(steps).sort((a, b) => a - b);

      return sortedSteps.map(step => {
         const basePoint = base.find((m: any) => m.step === step);
         const candidatePoint = candidate.find((m: any) => m.step === step);

         return {
            step,
            baseLoss: basePoint?.loss,
            candidateLoss: candidatePoint?.loss,
            basePassAt1: basePoint?.passAt1,
            candidatePassAt1: candidatePoint?.passAt1
         };
      });
   }, [compareData]);

   if (loading) {
      return (
         <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
         </div>
      );
   }

   const metrics = compareData?.metrics || {};

   return (
      <div className="flex flex-col h-full bg-background overflow-hidden" onClick={() => {
         setBaseDropdownOpen(false);
         setCandidateDropdownOpen(false);
      }}>
         {/* Header */}
         <div className="px-6 py-4 border-b border-border bg-surface shrink-0">
            <div className="flex justify-between items-start mb-4">
               <div>
                  <h1 className="text-lg font-bold text-white">Compare Runs</h1>
                  <p className="text-xs text-gray-500 mt-1">Select two runs to compare their configurations and metrics</p>
               </div>
               <div className="flex gap-2">
                  <button
                     onClick={exportAsCsv}
                     disabled={!compareData}
                     className="px-3 py-2 rounded-lg bg-surface border border-border hover:bg-white/5 text-white text-sm font-medium flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                     <span className="material-symbols-outlined text-[16px]">table_chart</span>
                     CSV
                  </button>
                  <button
                     onClick={exportAsJson}
                     disabled={!compareData}
                     className="px-3 py-2 rounded-lg bg-surface border border-border hover:bg-white/5 text-white text-sm font-medium flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                     <span className="material-symbols-outlined text-[16px]">download</span>
                     JSON
                  </button>
               </div>
            </div>

            {/* Run Selectors */}
            <div className="flex items-end gap-4">
               <div className="flex-1" onClick={(e) => e.stopPropagation()}>
                  <RunSelector
                     label="Baseline"
                     selectedId={selectedBaseId}
                     onSelect={handleSelectBase}
                     isOpen={baseDropdownOpen}
                     setIsOpen={setBaseDropdownOpen}
                     excludeId={selectedCandidateId}
                     variant="base"
                  />
               </div>

               <button
                  onClick={handleSwap}
                  disabled={!selectedBaseId || !selectedCandidateId || comparing}
                  className="h-[52px] w-12 flex items-center justify-center rounded-lg bg-surface border border-border hover:bg-white/5 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title="Swap Base and Candidate"
               >
                  <span className="material-symbols-outlined">swap_horiz</span>
               </button>

               <div className="flex-1" onClick={(e) => e.stopPropagation()}>
                  <RunSelector
                     label="Candidate"
                     selectedId={selectedCandidateId}
                     onSelect={handleSelectCandidate}
                     isOpen={candidateDropdownOpen}
                     setIsOpen={setCandidateDropdownOpen}
                     excludeId={selectedBaseId}
                     variant="candidate"
                  />
               </div>
            </div>

            {/* Same run warning */}
            {selectedBaseId && selectedBaseId === selectedCandidateId && (
               <div className="mt-3 px-3 py-2 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-yellow-400 text-sm flex items-center gap-2">
                  <span className="material-symbols-outlined text-[18px]">warning</span>
                  Please select different runs for comparison
               </div>
            )}
         </div>

         {/* Content */}
         <div className="flex-1 overflow-y-auto p-6 scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent">
            {comparing ? (
               <div className="flex items-center justify-center h-64">
                  <div className="flex items-center gap-3 text-gray-400">
                     <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                     <span>Comparing runs...</span>
                  </div>
               </div>
            ) : !baseRun || !candidateRun || !compareData ? (
               <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                  <span className="material-symbols-outlined text-[64px] mb-4 opacity-50">difference</span>
                  <h2 className="text-lg font-bold text-white mb-2">Select Runs to Compare</h2>
                  <p className="text-sm max-w-md text-center">
                     Use the dropdowns above to select a baseline and candidate run for comparison.
                  </p>
               </div>
            ) : (
               <div className="max-w-7xl mx-auto space-y-8 pb-10">

                  {/* Charts Section */}
                  {chartData && chartData.length > 0 && (
                     <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Training Loss Chart */}
                        <div className="bg-surface border border-border rounded-xl p-5 shadow-sm">
                           <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                              <span className="material-symbols-outlined text-primary text-sm">show_chart</span>
                              Training Loss
                           </h3>
                           <div className="h-64">
                              <ResponsiveContainer width="100%" height="100%">
                                 <LineChart data={chartData}>
                                    <CartesianGrid strokeDasharray="3 3" opacity={0.1} vertical={false} />
                                    <XAxis
                                       dataKey="step"
                                       tick={{ fill: '#6b7280', fontSize: 10 }}
                                       tickLine={false}
                                       axisLine={false}
                                    />
                                    <YAxis
                                       tick={{ fill: '#6b7280', fontSize: 10 }}
                                       tickLine={false}
                                       axisLine={false}
                                       width={30}
                                    />
                                    <Tooltip
                                       contentStyle={{ backgroundColor: '#1a1b1e', borderColor: '#2c2e33', borderRadius: '8px' }}
                                       itemStyle={{ fontSize: '12px' }}
                                       labelStyle={{ color: '#9ca3af', fontSize: '10px', marginBottom: '4px' }}
                                    />
                                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                                    <Line
                                       type="monotone"
                                       dataKey="baseLoss"
                                       name={`Base: ${baseRun.name}`}
                                       stroke="#6b7280"
                                       strokeWidth={2}
                                       dot={false}
                                    />
                                    <Line
                                       type="monotone"
                                       dataKey="candidateLoss"
                                       name={`Candidate: ${candidateRun.name}`}
                                       stroke="#10b981"
                                       strokeWidth={2}
                                       dot={false}
                                    />
                                 </LineChart>
                              </ResponsiveContainer>
                           </div>
                        </div>

                        {/* Eval Metric Chart (if available) */}
                        {(chartData.some(d => d.basePassAt1 !== undefined || d.candidatePassAt1 !== undefined)) && (
                           <div className="bg-surface border border-border rounded-xl p-5 shadow-sm">
                              <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                                 <span className="material-symbols-outlined text-primary text-sm">code</span>
                                 Pass@1 Rate
                              </h3>
                              <div className="h-64">
                                 <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartData}>
                                       <CartesianGrid strokeDasharray="3 3" opacity={0.1} vertical={false} />
                                       <XAxis
                                          dataKey="step"
                                          tick={{ fill: '#6b7280', fontSize: 10 }}
                                          tickLine={false}
                                          axisLine={false}
                                       />
                                       <YAxis
                                          tick={{ fill: '#6b7280', fontSize: 10 }}
                                          tickLine={false}
                                          axisLine={false}
                                          width={30}
                                       />
                                       <Tooltip
                                          contentStyle={{ backgroundColor: '#1a1b1e', borderColor: '#2c2e33', borderRadius: '8px' }}
                                          itemStyle={{ fontSize: '12px' }}
                                          labelStyle={{ color: '#9ca3af', fontSize: '10px', marginBottom: '4px' }}
                                       />
                                       <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                                       <Line
                                          type="monotone"
                                          dataKey="basePassAt1"
                                          name={`Base: ${baseRun.name}`}
                                          stroke="#6b7280"
                                          strokeWidth={2}
                                          strokeDasharray="5 5"
                                          dot={true}
                                       />
                                       <Line
                                          type="monotone"
                                          dataKey="candidatePassAt1"
                                          name={`Candidate: ${candidateRun.name}`}
                                          stroke="#10b981"
                                          strokeWidth={2}
                                          strokeDasharray="5 5"
                                          dot={true}
                                       />
                                    </LineChart>
                                 </ResponsiveContainer>
                              </div>
                           </div>
                        )}
                     </div>
                  )}

                  {/* Metrics Delta */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                     {Object.entries(metrics).length === 0 ? (
                        <div className="col-span-3 text-center py-8 bg-surface border border-border rounded-xl">
                           <p className="text-gray-500">No common numeric metrics found to compare.</p>
                        </div>
                     ) : (
                        Object.entries(metrics).map(([key, value]: [string, any]) => {
                           const formatMetricName = (key: string) => {
                              return key
                                 .replace(/([A-Z])/g, ' $1')
                                 .replace(/^./, (str) => str.toUpperCase())
                                 .replace(/_/g, ' ')
                                 .replace('Pass At', 'Pass@');
                           };

                           return (
                              <div key={key} className="bg-surface border border-border rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden group">
                                 {/* Accent blob */}
                                 <div className="absolute top-0 right-0 w-16 h-16 bg-gradient-to-br from-primary/10 to-transparent rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-150"></div>

                                 <h3 className="text-gray-400 text-xs uppercase font-bold mb-4 relative z-10">{formatMetricName(key)}</h3>
                                 <div className="flex items-end gap-2 relative z-10">
                                    <span className="text-3xl font-mono font-bold text-white">
                                       {value.candidate !== null ? Number(value.candidate).toLocaleString(undefined, { maximumFractionDigits: 4 }) : 'N/A'}
                                    </span>
                                    {value.delta !== null && (
                                       <span className={`font-mono text-xs mb-1 ml-2 px-1.5 py-0.5 rounded-full ${value.delta > 0 ? 'bg-success/20 text-success' : value.delta < 0 ? 'bg-error/20 text-error' : 'bg-gray-500/20 text-gray-400'
                                          }`}>
                                          {value.delta > 0 ? '+' : ''}{Number(value.delta).toLocaleString(undefined, { maximumFractionDigits: 4 })}
                                       </span>
                                    )}
                                 </div>
                                 <div className="text-xs text-gray-500 mt-2 relative z-10 font-mono">
                                    Baseline: {value.base !== null ? Number(value.base).toLocaleString(undefined, { maximumFractionDigits: 4 }) : 'N/A'}
                                 </div>
                              </div>
                           );
                        })
                     )}
                  </div>

                  {/* Config Diff */}
                  <div className="bg-surface border border-border rounded-xl overflow-hidden shadow-sm">
                     <div className="px-6 py-4 border-b border-border bg-white/5 flex justify-between items-center">
                        <div>
                           <h3 className="font-semibold text-white text-sm">Configuration Differences</h3>
                           {baseRun.type !== candidateRun.type && (
                              <p className="text-xs text-gray-500 mt-1">
                                 Comparing different run types: {baseRun.type} vs {candidateRun.type}
                              </p>
                           )}
                        </div>
                        <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer hover:text-white transition-colors">
                           <div className={`w-4 h-4 rounded border ${showOnlyDiff ? 'bg-primary border-primary' : 'border-gray-600'} flex items-center justify-center transition-colors`}>
                              {showOnlyDiff && <span className="material-symbols-outlined text-[12px] text-black font-bold">check</span>}
                           </div>
                           <input
                              type="checkbox"
                              checked={showOnlyDiff}
                              onChange={(e) => setShowOnlyDiff(e.target.checked)}
                              className="hidden"
                           />
                           Show only differences
                        </label>
                     </div>
                     <table className="w-full text-left text-sm">
                        <thead className="text-xs uppercase text-gray-500 font-medium">
                           <tr>
                              <th className="px-6 py-3 w-1/4">Parameter</th>
                              <th className="px-6 py-3 w-1/3 bg-black/10">Base: <span className="text-gray-400 normal-case">{baseRun.name}</span></th>
                              <th className="px-6 py-3 w-1/3 bg-primary/5 text-primary">Candidate: <span className="text-primary/80 normal-case">{candidateRun.name}</span></th>
                           </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                           {(() => {
                              const diffs = compareData?.configDiff || [];

                              // Group by category
                              const groupedDiffs: { [key: string]: any[] } = { training: [], evaluation: [], other: [] };
                              diffs.forEach((diff: any) => {
                                 const cat = diff.category || 'other';
                                 if (!groupedDiffs[cat]) groupedDiffs[cat] = [];
                                 groupedDiffs[cat].push(diff);
                              });

                              const categoryLabels: { [key: string]: string } = {
                                 training: '🔧 Training',
                                 evaluation: '🧪 Evaluation',
                                 other: '📋 Other'
                              };

                              const elements: React.ReactNode[] = [];

                              Object.entries(groupedDiffs).forEach(([category, items]) => {
                                 if (items.length === 0) return;

                                 const isCollapsed = collapsedCategories.has(category);

                                 elements.push(
                                    <tr
                                       key={`cat-${category}`}
                                       className="bg-white/[0.02] cursor-pointer hover:bg-white/[0.04] transition-colors"
                                       onClick={() => toggleCategory(category)}
                                    >
                                       <td colSpan={3} className="px-6 py-2 text-xs font-bold text-gray-400 uppercase flex items-center gap-2">
                                          <span className="material-symbols-outlined text-[16px] transition-transform duration-200" style={{ transform: isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}>
                                             expand_more
                                          </span>
                                          {categoryLabels[category]} ({items.length})
                                       </td>
                                    </tr>
                                 );

                                 if (!isCollapsed) {
                                    items.forEach((diff: any, idx: number) => {
                                       const isDifferent = JSON.stringify(diff.base) !== JSON.stringify(diff.candidate);

                                       elements.push(
                                          <tr key={`${category}-${idx}`} className={`${isDifferent ? 'bg-primary/[0.02]' : ''} hover:bg-white/[0.02] transition-colors`}>
                                             <td className="px-6 py-3 text-gray-300 font-medium pl-10 border-r border-border/10">{diff.param}</td>
                                             <td className="px-6 py-3 bg-black/10 font-mono text-xs border-r border-border/10">
                                                {diff.base === null ? (
                                                   <span className="text-gray-600 italic">N/A</span>
                                                ) : (
                                                   <span className="text-gray-400 break-all">{JSON.stringify(diff.base)}</span>
                                                )}
                                             </td>
                                             <td className="px-6 py-3 bg-primary/5 font-mono text-xs">
                                                {diff.candidate === null ? (
                                                   <span className="text-gray-600 italic">N/A</span>
                                                ) : (
                                                   <span className={`${isDifferent ? 'text-primary font-semibold' : 'text-white'} break-all`}>
                                                      {JSON.stringify(diff.candidate)}
                                                   </span>
                                                )}
                                             </td>
                                          </tr>
                                       );
                                    });
                                 }
                              });

                              return elements.length > 0 ? elements : (
                                 <tr>
                                    <td colSpan={3} className="px-6 py-8 text-center text-gray-500 italic">
                                       No configuration differences found.
                                    </td>
                                 </tr>
                              );
                           })()}
                        </tbody>
                     </table>
                  </div>

                  {/* Regressions */}
                  {(compareData?.regressions || []).length > 0 && (
                     <div className="bg-surface border border-border rounded-xl overflow-hidden shadow-sm">
                        <div className="px-6 py-3 border-b border-border bg-error/10">
                           <h3 className="font-semibold text-error text-sm flex items-center gap-2">
                              <span className="material-symbols-outlined text-[18px]">warning</span>
                              Regressions Detected ({compareData.regressions.length})
                           </h3>
                        </div>
                        <div className="p-6 space-y-4">
                           {compareData.regressions.map((reg: any, idx: number) => (
                              <div key={idx} className="bg-black/20 rounded-lg p-4 border border-border">
                                 <div className="text-xs text-gray-400 mb-2">Prompt:</div>
                                 <div className="text-sm text-gray-300 mb-4">{reg.prompt}</div>
                                 <div className="grid grid-cols-2 gap-4">
                                    <div>
                                       <div className="text-xs text-success mb-1">Baseline ({reg.baseResult})</div>
                                       <pre className="text-xs text-gray-400 bg-black/30 p-2 rounded overflow-x-auto">{reg.baseOutput}</pre>
                                    </div>
                                    <div>
                                       <div className="text-xs text-error mb-1">Candidate ({reg.candidateResult})</div>
                                       <pre className="text-xs text-gray-400 bg-black/30 p-2 rounded overflow-x-auto">{reg.candidateOutput}</pre>
                                    </div>
                                 </div>
                              </div>
                           ))}
                        </div>
                     </div>
                  )}
               </div>
            )}
         </div>
      </div>
   );
};

export default Compare;
