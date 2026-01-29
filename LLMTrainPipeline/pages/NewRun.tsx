import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchModels, fetchDatasets, fetchAdapters, createRun } from '../lib/api';

const Steps = ['Model & Setup', 'Data', 'Training', 'Review'];

const NewRun: React.FC = () => {
   const navigate = useNavigate();
   const [currentStep, setCurrentStep] = useState(0);
   const [showAdvanced, setShowAdvanced] = useState(false);

   // Auto-generate run name based on timestamp
   const defaultRunName = `run - ${new Date().toISOString().slice(0, 10).replace(/-/g, '')} -llama3`;

   const [formData, setFormData] = useState({
      // Step 1
      runName: defaultRunName,
      outputDir: '/workspace/runs/',
      modelId: '',

      // Step 2
      trainDatasetId: '',
      valDatasetId: '',
      testDatasetId: '',

      // Step 3 - Basic (P0 Core Parameters)
      lr: '1e-4',
      epochs: 2,
      batchSize: 1,
      maxSeqLen: 512,
      gradAccum: 16,

      // Step 3 - LoRA Config
      useLora: true,
      loraRank: 16,
      loraAlpha: 32,
      loraDropout: 0.05,
      loraTargetModules: ['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],
      loraBias: 'none',
      quantization: '4bit',

      // Step 3 - Advanced (P1 Advanced Parameters)
      warmupRatio: 0.03,
      warmupType: 'ratio',
      warmupSteps: 0,
      scheduler: 'cosine',
      weightDecay: 0.01,
      seed: 42,
      optimizer: 'paged_adamw_8bit',
      precision: 'none',
      gradientClipping: 1.0,

      // Step 3 - Logging & Saving
      loggingSteps: 10,
      saveSteps: 100,
      saveTotalLimit: 3,

      // Step 3 - Evaluation
      evalStrategy: 'epoch',
      evalSteps: 200,

      // Step 3 - Early Stopping
      earlyStoppingEnabled: false,
      earlyStoppingPatience: 3,
      earlyStoppingThreshold: 0.0,
      loadBestModelAtEnd: true,
      metricForBestModel: 'loss',

      // Step 3 - Warm Start
      warmStartAdapterId: 'none',
   });

   const [models, setModels] = useState<any[]>([]);
   const [datasets, setDatasets] = useState<any[]>([]);
   const [adapters, setAdapters] = useState<any[]>([]);
   const [loading, setLoading] = useState(true);
   const [submitting, setSubmitting] = useState(false);

   useEffect(() => {
      const loadData = async () => {
         try {
            const [modelsData, datasetsData, adaptersData] = await Promise.all([
               fetchModels(),
               fetchDatasets(),
               fetchAdapters()
            ]);
            setModels(modelsData);
            setDatasets(datasetsData);
            setAdapters(adaptersData);
         } catch (e) {
            console.error(e);
         } finally {
            setLoading(false);
         }
      };
      loadData();
   }, []);

   const handleSelect = (key: string, value: any) => {
      setFormData(prev => ({ ...prev, [key]: value }));
   };

   const getModel = (id: string) => models.find(m => m.id === id);
   const getDataset = (id: string) => datasets.find(d => d.id === id);

   // Computed fields
   const fullOutputPath = `${formData.outputDir}${formData.runName}`;
   const selectedModel = getModel(formData.modelId);

   // Filtering Logic (P0 Requirement)
   const compatibleAdapters = adapters.filter(a => !selectedModel || a.baseModel === selectedModel.name);
   const trainDatasets = datasets.filter(d => d.type === 'Train');
   const evalDatasets = datasets.filter(d => d.type === 'Eval' || d.type === 'Train');

   const isFormValid = () => {
      if (currentStep === 0 && (!formData.modelId || !formData.runName)) return false;
      if (currentStep === 1 && !formData.trainDatasetId) return false;
      return true;
   };

   // Training time estimation based on heuristics
   const estimateTrainingTime = () => {
      const dataset = getDataset(formData.trainDatasetId);
      const model = selectedModel;

      if (!dataset || !model) return 'Select model & dataset';

      // Parse model params (e.g., "7B" -> 7)
      const paramMatch = model.params?.match(/(\d+(?:\.\d+)?)/);
      const modelSizeB = paramMatch ? parseFloat(paramMatch[1]) : 7;

      // Parameters adjusted based on actual testing
      const samples = dataset.samples || 1000;
      const epochs = formData.epochs;

      // Base speed (samples per minute) - lowered based on actual test data
      // LoRA with 4-bit: ~25 samples/min for 7B model
      // Full fine-tune: ~8 samples/min for 7B model
      const baseSpeed = formData.useLora ? 25 : 8;

      // Model size impact (larger is slower, non-linear relationship)
      const sizeMultiplier = Math.pow(7 / modelSizeB, 1.2);

      // Sequence length impact (512 as baseline, longer sequences are slower)
      const seqLenMultiplier = 512 / formData.maxSeqLen;

      // Quantization impact (4-bit fastest, none slowest)
      const quantMultiplier = formData.quantization === '4bit' ? 1.0
         : formData.quantization === '8bit' ? 0.85
            : 0.6;

      const totalSamples = samples * epochs;
      const effectiveSpeed = baseSpeed * sizeMultiplier * seqLenMultiplier * quantMultiplier;
      const estimatedMins = Math.round(totalSamples / effectiveSpeed);

      if (estimatedMins < 60) return `~${estimatedMins} mins`;
      if (estimatedMins < 1440) return `~${(estimatedMins / 60).toFixed(1)} hrs`;
      return `~${(estimatedMins / 1440).toFixed(1)} days`;
   };

   const estimatedTime = estimateTrainingTime();

   const handleSubmit = async () => {
      setSubmitting(true);
      try {
         const result = await createRun({
            name: formData.runName,
            type: formData.useLora ? 'lora' : 'finetune',
            modelId: formData.modelId,
            datasetId: formData.trainDatasetId,
            evalDatasetId: formData.testDatasetId || undefined,
            profileName: 'single_gpu',
            config: {
               // Basic Training Config (P0)
               lr: formData.lr,
               epochs: formData.epochs,
               batchSize: formData.batchSize,
               maxSeqLen: formData.maxSeqLen,
               gradAccum: formData.gradAccum,

               // Advanced Training Config (P1)
               warmupRatio: formData.warmupRatio,
               warmupType: formData.warmupType,
               warmupSteps: formData.warmupSteps,
               weightDecay: formData.weightDecay,
               seed: formData.seed,
               optimizer: formData.optimizer,
               scheduler: formData.scheduler,
               precision: formData.precision,
               gradientClipping: formData.gradientClipping,

               // Logging & Saving
               loggingSteps: formData.loggingSteps,
               saveSteps: formData.saveSteps,
               saveTotalLimit: formData.saveTotalLimit,

               // Evaluation
               evalStrategy: formData.evalStrategy,
               evalSteps: formData.evalSteps,

               // Early Stopping
               earlyStoppingEnabled: formData.earlyStoppingEnabled,
               earlyStoppingPatience: formData.earlyStoppingPatience,
               earlyStoppingThreshold: formData.earlyStoppingThreshold,
               loadBestModelAtEnd: formData.loadBestModelAtEnd,
               metricForBestModel: formData.metricForBestModel,

               // LoRA config
               useLora: formData.useLora,
               loraRank: formData.loraRank,
               loraAlpha: formData.loraAlpha,
               loraDropout: formData.loraDropout,
               loraBias: formData.loraBias,
               loraTargetModules: formData.loraTargetModules,
               quantization: formData.quantization,
            },
         });
         navigate(`/runs/${result.id}`);
      } catch (e) {
         console.error(e);
      } finally {
         setSubmitting(false);
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
      <div className="flex flex-col h-full bg-background">
         {/* Header */}
         <div className="px-8 py-6 border-b border-border bg-surface shrink-0">
            <div className="max-w-5xl mx-auto">
               <div className="flex items-center justify-between mb-6">
                  <h1 className="text-2xl font-bold text-white">New Training Run</h1>
                  <button className="text-gray-400 hover:text-white" onClick={() => navigate('/')}>
                     <span className="material-symbols-outlined">close</span>
                  </button>
               </div>

               {/* Stepper */}
               <div className="flex items-center justify-between relative px-4">
                  <div className="absolute top-1/2 left-0 w-full h-0.5 bg-border -z-10"></div>
                  {Steps.map((step, idx) => (
                     <div key={step} className={`flex flex-col items-center gap-2 px-4 z-10 cursor-pointer ${idx <= currentStep ? '' : 'opacity-50'}`} onClick={() => idx < currentStep && setCurrentStep(idx)}>
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${idx <= currentStep ? 'bg-primary text-white' : 'bg-surface border-2 border-border text-gray-500'}`}>
                           {idx + 1}
                        </div>
                        <span className={`text-xs font-medium ${idx <= currentStep ? 'text-white' : 'text-gray-600'}`}>{step}</span>
                     </div>
                  ))}
               </div>
            </div>
         </div>

         {/* Content */}
         <div className="flex-1 overflow-y-auto p-8">
            <div className="max-w-4xl mx-auto space-y-8">

               {/* Step 1: Model & Setup */}
               {currentStep === 0 && (
                  <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4">
                     <div className="grid grid-cols-2 gap-6">
                        <div className="space-y-2">
                           <label className="text-xs font-bold text-gray-400 uppercase tracking-wider">Run Name <span className="text-red-500">*</span></label>
                           <input
                              type="text"
                              className="w-full bg-black/20 border border-border rounded-lg p-3 text-sm text-white focus:border-primary focus:outline-none font-mono"
                              value={formData.runName}
                              onChange={e => handleSelect('runName', e.target.value)}
                           />
                           <div className="text-[10px] text-gray-500 font-mono">Output: ./storage/runs/{formData.runName}</div>
                        </div>
                        <div className="space-y-2">
                           <label className="text-xs font-bold text-gray-400 uppercase tracking-wider">Project / Tags</label>
                           <input
                              type="text"
                              placeholder="e.g. experiment, regression-fix"
                              className="w-full bg-black/20 border border-border rounded-lg p-3 text-sm text-white focus:border-primary focus:outline-none"
                           />
                        </div>
                     </div>

                     <div className="space-y-4">
                        <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-border pb-2">Select Base Model <span className="text-red-500">*</span></h2>
                        <div className="grid gap-4">
                           {models.map(model => (
                              <div
                                 key={model.id}
                                 onClick={() => handleSelect('modelId', model.id)}
                                 className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${formData.modelId === model.id
                                    ? 'border-primary bg-primary/5'
                                    : 'border-border bg-surface hover:border-gray-500'}`}
                              >
                                 <div className="flex justify-between items-start">
                                    <div className="flex items-center gap-4">
                                       <div className="w-12 h-12 rounded bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold text-lg border border-indigo-500/20">
                                          {model.name.substring(0, 2).toUpperCase()}
                                       </div>
                                       <div>
                                          <h3 className="text-white font-bold text-base">{model.name}</h3>
                                          <div className="flex items-center gap-3 mt-1.5">
                                             <span className="text-xs text-gray-400 font-mono bg-black/30 px-1.5 py-0.5 rounded border border-border">{model.params}</span>
                                             <span className="text-xs text-gray-400 font-mono bg-black/30 px-1.5 py-0.5 rounded border border-border">{model.quantization}</span>
                                             <span className="text-xs text-gray-400 font-mono bg-black/30 px-1.5 py-0.5 rounded border border-border">{model.backend}</span>
                                          </div>
                                       </div>
                                    </div>
                                    {formData.modelId === model.id && <span className="material-symbols-outlined text-primary text-[28px]">check_circle</span>}
                                 </div>
                              </div>
                           ))}
                        </div>
                     </div>
                  </div>
               )}

               {/* Step 2: Data */}
               {currentStep === 1 && (
                  <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4">
                     {/* Train Data */}
                     <div className="space-y-4">
                        <div className="flex justify-between items-end border-b border-border pb-2">
                           <h2 className="text-sm font-bold text-white uppercase tracking-wider">Training Dataset <span className="text-red-500">*</span></h2>
                           {formData.trainDatasetId && (
                              <button
                                 onClick={() => window.open(`/datasets?preview=${formData.trainDatasetId}`, '_blank')}
                                 className="text-xs text-primary hover:text-blue-400 flex items-center gap-1"
                              >
                                 <span className="material-symbols-outlined text-[14px]">visibility</span> Preview
                              </button>
                           )}
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                           {trainDatasets.map(ds => (
                              <div
                                 key={ds.id}
                                 onClick={() => handleSelect('trainDatasetId', ds.id)}
                                 className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${formData.trainDatasetId === ds.id ? 'border-primary bg-primary/5' : 'border-border bg-surface hover:border-gray-500'}`}
                              >
                                 <div className="flex items-center justify-between">
                                    <div>
                                       <div className="text-white font-medium">{ds.name}</div>
                                       <div className="flex gap-2 mt-1">
                                          <span className="text-xs text-gray-500">{ds.samples.toLocaleString()} rows</span>
                                          <span className="text-xs text-gray-600 font-mono">#{ds.hash}</span>
                                       </div>
                                    </div>
                                    {formData.trainDatasetId === ds.id && <span className="material-symbols-outlined text-primary">check_circle</span>}
                                 </div>
                              </div>
                           ))}
                        </div>
                     </div>

                     {/* Validation & Test Data */}
                     <div className="grid grid-cols-2 gap-8">
                        <div className="space-y-3">
                           <label className="text-xs font-bold text-gray-400 uppercase tracking-wider">Validation Set (Optional)</label>
                           <select
                              className="w-full bg-surface border border-border rounded-lg p-3 text-sm text-white focus:border-primary focus:outline-none"
                              value={formData.valDatasetId}
                              onChange={(e) => handleSelect('valDatasetId', e.target.value)}
                           >
                              <option value="">None (No evaluation during training)</option>
                              {evalDatasets.map(ds => (
                                 <option key={ds.id} value={ds.id}>{ds.name} ({ds.samples} rows)</option>
                              ))}
                           </select>
                        </div>
                        <div className="space-y-3">
                           <label className="text-xs font-bold text-gray-400 uppercase tracking-wider">Test Set (For Final Eval)</label>
                           <select
                              className="w-full bg-surface border border-border rounded-lg p-3 text-sm text-white focus:border-primary focus:outline-none"
                              value={formData.testDatasetId}
                              onChange={(e) => handleSelect('testDatasetId', e.target.value)}
                           >
                              <option value="">None (Skip evaluation)</option>
                              {/* Show Eval datasets first */}
                              {evalDatasets.filter(d => d.type === 'Eval').length > 0 && (
                                 <optgroup label="Evaluation Datasets">
                                    {evalDatasets.filter(d => d.type === 'Eval').map(ds => (
                                       <option key={ds.id} value={ds.id}>{ds.name} ({ds.samples} rows)</option>
                                    ))}
                                 </optgroup>
                              )}
                              {/* Also allow Train datasets for evaluation */}
                              {trainDatasets.length > 0 && (
                                 <optgroup label="Training Datasets (available for evaluation)">
                                    {trainDatasets.map(ds => (
                                       <option key={ds.id} value={ds.id}>{ds.name} ({ds.samples} rows)</option>
                                    ))}
                                 </optgroup>
                              )}
                           </select>
                        </div>
                     </div>
                  </div>
               )}

               {/* Step 3: Training */}
               {currentStep === 2 && (
                  <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4">

                     {/* Profile Selector */}
                     <div className="grid grid-cols-2 gap-4">
                        <div
                           onClick={() => handleSelect('useLora', true)}
                           className={`p-4 rounded-xl border cursor-pointer flex items-center gap-4 transition-colors ${formData.useLora ? 'bg-primary/10 border-primary' : 'bg-surface border-border hover:border-gray-500'}`}
                        >
                           <div className={`w-10 h-10 rounded-full flex items-center justify-center ${formData.useLora ? 'bg-primary text-white' : 'bg-white/5 text-gray-400'}`}>
                              <span className="material-symbols-outlined">extension</span>
                           </div>
                           <div>
                              <div className="font-bold text-white">QLoRA / LoRA</div>
                              <div className="text-xs text-gray-400">Parameter Efficient (Less VRAM)</div>
                           </div>
                        </div>
                        <div
                           onClick={() => handleSelect('useLora', false)}
                           className={`p-4 rounded-xl border cursor-pointer flex items-center gap-4 transition-colors ${!formData.useLora ? 'bg-primary/10 border-primary' : 'bg-surface border-border hover:border-gray-500'}`}
                        >
                           <div className={`w-10 h-10 rounded-full flex items-center justify-center ${!formData.useLora ? 'bg-primary text-white' : 'bg-white/5 text-gray-400'}`}>
                              <span className="material-symbols-outlined">speed</span>
                           </div>
                           <div>
                              <div className="font-bold text-white">Full Fine-Tune</div>
                              <div className="text-xs text-gray-400">Update all weights (High Performance)</div>
                           </div>
                        </div>
                     </div>

                     {/* ==================== Basic Parameters (P0) ==================== */}
                     <div className="bg-surface p-6 rounded-xl border border-border space-y-6">
                        <div className="flex items-center gap-2">
                           <span className="material-symbols-outlined text-primary text-lg">tune</span>
                           <h3 className="text-sm font-bold text-white uppercase tracking-wider">Basic</h3>
                           <span className="text-xs text-gray-500 ml-2">Core Hyperparameters</span>
                        </div>
                        <div className="grid grid-cols-4 gap-6">
                           <div className="space-y-2">
                              <label className="text-xs text-gray-400 flex items-center gap-1">
                                 Learning Rate
                                 <span className="text-[10px] text-gray-600" title="Recommended range: 1e-5 ~ 5e-4">ⓘ</span>
                              </label>
                              <select className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                 value={formData.lr} onChange={e => handleSelect('lr', e.target.value)}>
                                 <option value="5e-5">5e-5 (Conservative)</option>
                                 <option value="1e-4">1e-4 (Recommended)</option>
                                 <option value="2e-4">2e-4 (Standard)</option>
                                 <option value="3e-4">3e-4 (Aggressive)</option>
                                 <option value="5e-4">5e-4 (Fast)</option>
                              </select>
                           </div>
                           <div className="space-y-2">
                              <label className="text-xs text-gray-400">Epochs</label>
                              <select className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                 value={formData.epochs} onChange={e => handleSelect('epochs', parseInt(e.target.value))}>
                                 <option value={1}>1 (Quick Test)</option>
                                 <option value={2}>2 (Recommended)</option>
                                 <option value={3}>3 (Standard)</option>
                                 <option value={5}>5 (Deep)</option>
                              </select>
                           </div>
                           <div className="space-y-2">
                              <label className="text-xs text-gray-400 flex items-center gap-1">
                                 Max Seq Length
                                 <span className="text-[10px] text-gray-600" title="Affects VRAM, longer sequences require more memory">ⓘ</span>
                              </label>
                              <select className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                 value={formData.maxSeqLen} onChange={e => handleSelect('maxSeqLen', parseInt(e.target.value))}>
                                 <option value={256}>256 (Short)</option>
                                 <option value={512}>512 (Standard)</option>
                                 <option value={768}>768 (Medium)</option>
                                 <option value={1024}>1024 (Long)</option>
                                 <option value={2048}>2048 (Very Long)</option>
                              </select>
                           </div>
                           <div className="space-y-2">
                              <label className="text-xs text-gray-400 flex items-center gap-1">
                                 Gradient Accum
                                 <span className="text-[10px] text-gray-600" title="Effective batch = batchSize × gradAccum">ⓘ</span>
                              </label>
                              <select className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                 value={formData.gradAccum} onChange={e => handleSelect('gradAccum', parseInt(e.target.value))}>
                                 <option value={1}>1 (No Accum)</option>
                                 <option value={4}>4</option>
                                 <option value={8}>8</option>
                                 <option value={16}>16 (Recommended)</option>
                                 <option value={32}>32 (Large Batch)</option>
                              </select>
                           </div>
                        </div>
                     </div>

                     {/* ==================== LoRA Parameters ==================== */}
                     {formData.useLora && (
                        <div className="bg-surface p-6 rounded-xl border border-border space-y-6">
                           <div className="flex items-center gap-2">
                              <span className="material-symbols-outlined text-purple-400 text-lg">extension</span>
                              <h3 className="text-sm font-bold text-white uppercase tracking-wider">LoRA</h3>
                              <span className="text-xs text-gray-500 ml-2">Low-Rank Adapter Configuration</span>
                           </div>
                           <div className="grid grid-cols-4 gap-6">
                              <div className="space-y-2">
                                 <label className="text-xs text-gray-400 flex items-center gap-1">
                                    Rank (r)
                                    <span className="text-[10px] text-gray-600" title="LoRA capacity, larger is stronger but slower">ⓘ</span>
                                 </label>
                                 <select className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                    value={formData.loraRank} onChange={e => handleSelect('loraRank', parseInt(e.target.value))}>
                                    <option value={4}>4 (Minimal)</option>
                                    <option value={8}>8 (Light)</option>
                                    <option value={16}>16 (Standard)</option>
                                    <option value={32}>32 (Strong)</option>
                                    <option value={64}>64 (Heavy)</option>
                                 </select>
                              </div>
                              <div className="space-y-2">
                                 <label className="text-xs text-gray-400 flex items-center gap-1">
                                    Alpha
                                    <span className="text-[10px] text-gray-600" title="Usually set to rank or 2×rank">ⓘ</span>
                                 </label>
                                 <select className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                    value={formData.loraAlpha} onChange={e => handleSelect('loraAlpha', parseInt(e.target.value))}>
                                    <option value={formData.loraRank}>{formData.loraRank} (= rank)</option>
                                    <option value={formData.loraRank * 2}>{formData.loraRank * 2} (= 2×rank)</option>
                                    <option value={16}>16</option>
                                    <option value={32}>32</option>
                                    <option value={64}>64</option>
                                 </select>
                              </div>
                              <div className="space-y-2">
                                 <label className="text-xs text-gray-400 flex items-center gap-1">
                                    Dropout
                                    <span className="text-[10px] text-gray-600" title="Prevents overfitting, increase when data is limited">ⓘ</span>
                                 </label>
                                 <select className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                    value={formData.loraDropout} onChange={e => handleSelect('loraDropout', parseFloat(e.target.value))}>
                                    <option value={0}>0.0 (No Dropout)</option>
                                    <option value={0.05}>0.05 (Standard)</option>
                                    <option value={0.1}>0.1 (Moderate)</option>
                                    <option value={0.2}>0.2 (High)</option>
                                 </select>
                              </div>
                              <div className="space-y-2">
                                 <label className="text-xs text-gray-400">Quantization</label>
                                 <select className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                    value={formData.quantization} onChange={e => handleSelect('quantization', e.target.value)}>
                                    <option value="4bit">4-bit (QLoRA)</option>
                                    <option value="8bit">8-bit</option>
                                    <option value="none">None (Full Precision)</option>
                                 </select>
                              </div>
                           </div>
                        </div>
                     )}

                     {/* ==================== Advanced Parameters (Collapsible) ==================== */}
                     <div className="border border-border rounded-xl overflow-hidden">
                        <button
                           onClick={() => setShowAdvanced(!showAdvanced)}
                           className="w-full flex items-center justify-between p-4 bg-surface hover:bg-white/5 transition-colors"
                        >
                           <div className="flex items-center gap-2">
                              <span className="material-symbols-outlined text-gray-400 text-lg">settings</span>
                              <span className="text-sm font-bold text-white uppercase tracking-wider">Advanced</span>
                              <span className="text-xs text-gray-500 ml-2">Warmup, Scheduler, Seed, Target Modules...</span>
                           </div>
                           <span className="material-symbols-outlined text-gray-400">{showAdvanced ? 'expand_less' : 'expand_more'}</span>
                        </button>

                        {showAdvanced && (
                           <div className="p-6 bg-black/20 border-t border-border space-y-6">
                              {/* Row 1: Optimizer & Scheduler */}
                              <div className="grid grid-cols-3 gap-6">
                                 <div className="space-y-2">
                                    <label className="text-xs text-gray-400">Optimizer</label>
                                    <select className="w-full bg-surface border border-border rounded-lg p-2.5 text-sm text-gray-300 focus:border-primary"
                                       value={formData.optimizer} onChange={e => handleSelect('optimizer', e.target.value)}>
                                       <option value="paged_adamw_8bit">Paged AdamW 8-bit (Recommended)</option>
                                       <option value="adamw_torch">AdamW (Torch)</option>
                                       <option value="adamw_bnb_8bit">AdamW BnB 8-bit</option>
                                       <option value="sgd">SGD</option>
                                    </select>
                                 </div>
                                 <div className="space-y-2">
                                    <label className="text-xs text-gray-400">Scheduler</label>
                                    <select className="w-full bg-surface border border-border rounded-lg p-2.5 text-sm text-gray-300 focus:border-primary"
                                       value={formData.scheduler} onChange={e => handleSelect('scheduler', e.target.value)}>
                                       <option value="cosine">Cosine (Recommended)</option>
                                       <option value="linear">Linear</option>
                                       <option value="constant">Constant</option>
                                       <option value="cosine_with_restarts">Cosine with Restarts</option>
                                       <option value="polynomial">Polynomial</option>
                                    </select>
                                 </div>
                                 <div className="space-y-2">
                                    <label className="text-xs text-gray-400">Precision</label>
                                    <select className="w-full bg-surface border border-border rounded-lg p-2.5 text-sm text-gray-300 focus:border-primary"
                                       value={formData.precision} onChange={e => handleSelect('precision', e.target.value)}>
                                       <option value="none">Auto (For QLoRA)</option>
                                       <option value="bf16">BF16 (Ampere+)</option>
                                       <option value="fp16">FP16</option>
                                       <option value="fp32">FP32</option>
                                    </select>
                                 </div>
                              </div>

                              {/* Row 2: Warmup, Weight Decay, Seed */}
                              <div className="grid grid-cols-3 gap-6 pt-4 border-t border-border">
                                 <div className="space-y-2">
                                    <label className="text-xs text-gray-400 flex items-center gap-1">
                                       Warmup Ratio
                                       <span className="text-[10px] text-gray-600" title="Stabilizes training start phase">ⓘ</span>
                                    </label>
                                    <select className="w-full bg-surface border border-border rounded-lg p-2.5 text-sm text-gray-300 focus:border-primary"
                                       value={formData.warmupRatio} onChange={e => handleSelect('warmupRatio', parseFloat(e.target.value))}>
                                       <option value={0}>0% (No Warmup)</option>
                                       <option value={0.01}>1%</option>
                                       <option value={0.03}>3% (Standard)</option>
                                       <option value={0.05}>5%</option>
                                       <option value={0.1}>10%</option>
                                    </select>
                                 </div>
                                 <div className="space-y-2">
                                    <label className="text-xs text-gray-400 flex items-center gap-1">
                                       Weight Decay
                                       <span className="text-[10px] text-gray-600" title="Regularization, prevents overfitting">ⓘ</span>
                                    </label>
                                    <select className="w-full bg-surface border border-border rounded-lg p-2.5 text-sm text-gray-300 focus:border-primary"
                                       value={formData.weightDecay} onChange={e => handleSelect('weightDecay', parseFloat(e.target.value))}>
                                       <option value={0}>0 (No Decay)</option>
                                       <option value={0.001}>0.001</option>
                                       <option value={0.01}>0.01 (Standard)</option>
                                       <option value={0.05}>0.05</option>
                                       <option value={0.1}>0.1</option>
                                    </select>
                                 </div>
                                 <div className="space-y-2">
                                    <label className="text-xs text-gray-400 flex items-center gap-1">
                                       Seed
                                       <span className="text-[10px] text-gray-600" title="Random seed, ensures reproducibility">ⓘ</span>
                                    </label>
                                    <input type="number" className="w-full bg-surface border border-border rounded-lg p-2.5 text-sm text-gray-300 focus:border-primary"
                                       value={formData.seed} onChange={e => handleSelect('seed', parseInt(e.target.value) || 42)} />
                                 </div>
                              </div>

                              {/* Row 3: Logging & Saving */}
                              <div className="grid grid-cols-3 gap-6 pt-4 border-t border-border">
                                 <div className="space-y-2">
                                    <label className="text-xs text-gray-400">Logging Steps</label>
                                    <select className="w-full bg-surface border border-border rounded-lg p-2.5 text-sm text-gray-300 focus:border-primary"
                                       value={formData.loggingSteps} onChange={e => handleSelect('loggingSteps', parseInt(e.target.value))}>
                                       <option value={1}>1 (Every Step)</option>
                                       <option value={5}>5</option>
                                       <option value={10}>10 (Standard)</option>
                                       <option value={20}>20</option>
                                       <option value={50}>50</option>
                                    </select>
                                 </div>
                                 <div className="space-y-2">
                                    <label className="text-xs text-gray-400">Save Steps</label>
                                    <select className="w-full bg-surface border border-border rounded-lg p-2.5 text-sm text-gray-300 focus:border-primary"
                                       value={formData.saveSteps} onChange={e => handleSelect('saveSteps', parseInt(e.target.value))}>
                                       <option value={50}>50</option>
                                       <option value={100}>100 (Standard)</option>
                                       <option value={200}>200</option>
                                       <option value={500}>500</option>
                                    </select>
                                 </div>
                                 <div className="space-y-2">
                                    <label className="text-xs text-gray-400">Max Checkpoints</label>
                                    <select className="w-full bg-surface border border-border rounded-lg p-2.5 text-sm text-gray-300 focus:border-primary"
                                       value={formData.saveTotalLimit} onChange={e => handleSelect('saveTotalLimit', parseInt(e.target.value))}>
                                       <option value={1}>1 (Latest Only)</option>
                                       <option value={2}>2</option>
                                       <option value={3}>3 (Standard)</option>
                                       <option value={5}>5</option>
                                    </select>
                                 </div>
                              </div>

                              {/* Row 4: Target Modules (LoRA Only) */}
                              {formData.useLora && (
                                 <div className="pt-4 border-t border-border space-y-2">
                                    <label className="text-xs text-gray-400 flex items-center gap-1">
                                       Target Modules
                                       <span className="text-[10px] text-gray-600" title="Select modules to apply LoRA to">ⓘ</span>
                                    </label>
                                    <div className="flex gap-4">
                                       <label className="flex items-center gap-2 cursor-pointer">
                                          <input
                                             type="radio"
                                             name="targetModules"
                                             checked={formData.loraTargetModules.length === 4}
                                             onChange={() => handleSelect('loraTargetModules', ['q_proj', 'k_proj', 'v_proj', 'o_proj'])}
                                             className="text-primary"
                                          />
                                          <span className="text-sm text-gray-300">Attention Only (q,k,v,o)</span>
                                       </label>
                                       <label className="flex items-center gap-2 cursor-pointer">
                                          <input
                                             type="radio"
                                             name="targetModules"
                                             checked={formData.loraTargetModules.length === 7}
                                             onChange={() => handleSelect('loraTargetModules', ['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'])}
                                             className="text-primary"
                                          />
                                          <span className="text-sm text-gray-300">Attention + MLP (Recommended)</span>
                                       </label>
                                    </div>
                                 </div>
                              )}
                           </div>
                        )}
                     </div>

                     {/* Warm Start */}
                     {formData.useLora && (
                        <div className="bg-surface p-6 rounded-xl border border-border">
                           <div className="flex justify-between items-center mb-3">
                              <label className="text-xs font-bold text-gray-400 uppercase">Warm Start (Optional)</label>
                              <span className="text-[10px] text-gray-500">Initialize training from existing LoRA</span>
                           </div>
                           <select
                              className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                              value={formData.warmStartAdapterId}
                              onChange={e => handleSelect('warmStartAdapterId', e.target.value)}
                           >
                              <option value="none">None (Start Fresh)</option>
                              {compatibleAdapters.map(a => (
                                 <option key={a.id} value={a.id}>{a.name} (r={a.rank})</option>
                              ))}
                           </select>
                        </div>
                     )}
                  </div>
               )}

               {/* Step 4: Eval & Adapters - REMOVED, now separate page */}

               {/* Step 4: Review */}
               {currentStep === 3 && (
                  <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
                     <div className="flex items-center justify-between">
                        <h2 className="text-lg font-semibold text-white">Review Configuration</h2>
                        <div className="flex gap-4 items-center">
                           <span className="text-xs text-gray-400">Est. Time: <span className="text-white font-mono">{estimatedTime}</span></span>
                           <button className="px-3 py-1.5 rounded bg-surface border border-border text-xs font-bold text-success flex items-center gap-1">
                              <span className="material-symbols-outlined text-[16px]">check_circle</span> Config Validated
                           </button>
                        </div>
                     </div>

                     <div className="bg-surface rounded-xl border border-border overflow-hidden">
                        {/* Header Info */}
                        <div className="bg-white/5 p-4 border-b border-border flex justify-between items-center">
                           <div>
                              <div className="text-xs text-gray-500 uppercase font-bold">Run Name</div>
                              <div className="text-white font-mono font-bold">{formData.runName}</div>
                           </div>
                           <div className="text-right">
                              <div className="text-xs text-gray-500 uppercase font-bold">Output Path</div>
                              <div className="text-gray-300 font-mono text-xs">{fullOutputPath}</div>
                           </div>
                        </div>

                        {/* Grid Details */}
                        <div className="grid grid-cols-2 divide-x divide-border border-b border-border">
                           <div className="p-4 space-y-3">
                              <h3 className="text-xs text-primary font-bold uppercase tracking-wider flex items-center gap-2">
                                 <span className="material-symbols-outlined text-[16px]">deployed_code</span> Model & Data
                              </h3>
                              <div className="space-y-2">
                                 <div className="flex justify-between">
                                    <span className="text-sm text-gray-400">Base Model</span>
                                    <span className="text-sm text-white">{selectedModel?.name}</span>
                                 </div>
                                 <div className="flex justify-between">
                                    <span className="text-sm text-gray-400">Train Set</span>
                                    <span className="text-sm text-white flex items-center gap-2">
                                       {getDataset(formData.trainDatasetId)?.name}
                                       <span className="text-[10px] bg-white/10 px-1 rounded font-mono text-gray-300">#{getDataset(formData.trainDatasetId)?.hash}</span>
                                    </span>
                                 </div>
                                 <div className="flex justify-between">
                                    <span className="text-sm text-gray-400">Val Set</span>
                                    <span className="text-sm text-white">{getDataset(formData.valDatasetId)?.name || 'None'}</span>
                                 </div>
                              </div>
                           </div>

                           <div className="p-4 space-y-3">
                              <h3 className="text-xs text-warning font-bold uppercase tracking-wider flex items-center gap-2">
                                 <span className="material-symbols-outlined text-[16px]">tune</span> Training Config
                              </h3>
                              <div className="space-y-2">
                                 <div className="flex justify-between">
                                    <span className="text-sm text-gray-400">Type</span>
                                    <span className="text-sm text-white font-mono">{formData.useLora ? 'QLoRA' : 'Full'}</span>
                                 </div>
                                 <div className="flex justify-between">
                                    <span className="text-sm text-gray-400">Params</span>
                                    <span className="text-sm text-white font-mono">e={formData.epochs}, b={formData.batchSize}, lr={formData.lr}</span>
                                 </div>
                                 <div className="flex justify-between">
                                    <span className="text-sm text-gray-400">Precision</span>
                                    <span className="text-sm text-white font-mono">{formData.precision}</span>
                                 </div>
                              </div>
                           </div>
                        </div>

                        {/* Bottom Details */}
                        <div className="grid grid-cols-2 divide-x divide-border">
                           <div className="p-4 space-y-3">
                              <h3 className="text-xs text-purple-400 font-bold uppercase tracking-wider flex items-center gap-2">
                                 <span className="material-symbols-outlined text-[16px]">science</span> Evaluation
                              </h3>
                              <div className="text-sm text-gray-300">
                                 <p className="text-gray-400">Evaluation is configured separately</p>
                                 <a href="#/evaluation" className="text-primary hover:text-blue-400 text-xs mt-2 inline-flex items-center gap-1">
                                    <span className="material-symbols-outlined text-[14px]">open_in_new</span>
                                    Go to Evaluation page
                                 </a>
                              </div>
                           </div>
                           <div className="p-4 space-y-3">
                              <h3 className="text-xs text-gray-400 font-bold uppercase tracking-wider flex items-center gap-2">
                                 <span className="material-symbols-outlined text-[16px]">folder_zip</span> Artifacts Generated
                              </h3>
                              <ul className="text-xs text-gray-400 list-disc list-inside space-y-1 font-mono">
                                 <li>adapter_model.bin / config.json</li>
                                 <li>training_state.pt</li>
                                 <li>eval_results.jsonl</li>
                                 <li>run_report.html</li>
                              </ul>
                           </div>
                        </div>
                     </div>
                  </div>
               )}
            </div>
         </div>

         {/* Footer */}
         <div className="px-8 py-4 border-t border-border bg-surface flex justify-between shrink-0">
            <button onClick={() => navigate('/runs')} className="px-6 py-2.5 rounded-lg text-gray-400 font-medium hover:text-white transition-colors">Cancel</button>
            <div className="flex gap-3">
               <button
                  disabled={currentStep === 0}
                  onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
                  className="px-6 py-2.5 rounded-lg border border-border text-white font-medium hover:bg-white/5 disabled:opacity-50 transition-colors"
               >
                  Back
               </button>
               <button
                  disabled={!isFormValid() || submitting}
                  onClick={() => {
                     if (currentStep < 3) setCurrentStep(currentStep + 1);
                     else handleSubmit();
                  }}
                  className="px-8 py-2.5 rounded-lg bg-primary hover:bg-blue-600 text-white font-bold shadow-lg shadow-primary/20 transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
               >
                  {submitting ? 'Launching...' : currentStep === 3 ? 'Launch Run' : 'Next Step'}
                  <span className="material-symbols-outlined text-lg">{submitting ? 'hourglass_empty' : 'arrow_forward'}</span>
               </button>
            </div>
         </div>
      </div >
   );
};

export default NewRun;
