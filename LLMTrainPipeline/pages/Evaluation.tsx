import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchModels, fetchDatasets, fetchAdapters, createEvalRun } from '../lib/api';

const Evaluation: React.FC = () => {
    const navigate = useNavigate();
    const [models, setModels] = useState<any[]>([]);
    const [datasets, setDatasets] = useState<any[]>([]);
    const [adapters, setAdapters] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    const [formData, setFormData] = useState({
        // Task name
        name: '',

        // Model & Adapter
        modelId: '',
        adapterId: 'none',

        // Dataset
        datasetId: '',

        // Generation parameters
        evalK: '1,5,10',
        evalTemp: 0.2,
        evalSamples: 20,

        // Execution parameters
        evalTimeout: 60,
        maxNewTokens: 512,
        memoryLimit: 1024,

        // Report options
        generateReport: true,
        saveFailureCases: true,
    });

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

                if (modelsData.length > 0) {
                    setFormData(prev => ({ ...prev, modelId: modelsData[0].id }));
                }
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

    const selectedModel = models.find(m => m.id === formData.modelId);

    // Filter compatible adapters (based on selected model)
    const compatibleAdapters = adapters.filter(a =>
        !selectedModel || a.baseModel === selectedModel.name
    );

    // Filter evaluation datasets
    const evalDatasets = datasets.filter(d => d.type === 'Eval' || d.type === 'Train');

    const isFormValid = () => {
        return formData.modelId && formData.datasetId;
    };

    const handleSubmit = async () => {
        setSubmitting(true);
        try {
            const result = await createEvalRun({
                name: formData.name || undefined,  // Use default name if empty
                modelId: formData.modelId,
                adapterId: formData.adapterId !== 'none' ? formData.adapterId : undefined,
                datasetId: formData.datasetId,
                config: {
                    // Full test suite - run all evaluation metrics
                    evaluator: 'complete_pipeline',
                    k: formData.evalK,
                    temperature: formData.evalTemp,
                    numSamples: formData.evalSamples,
                    timeout: formData.evalTimeout,
                    maxTokens: formData.maxNewTokens,
                    memoryLimit: formData.memoryLimit,
                    generateReport: formData.generateReport,
                    saveFailureCases: formData.saveFailureCases,
                },
            });
            navigate(`/evaluation/${result.id}`);
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
        <div className="flex flex-col h-full bg-background overflow-y-auto">
            {/* Header */}
            <div className="px-8 py-6 border-b border-border bg-surface shrink-0">
                <div className="max-w-4xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <span className="material-symbols-outlined text-primary text-3xl">science</span>
                        <div>
                            <h1 className="text-2xl font-bold text-white">Model Evaluation</h1>
                            <p className="text-sm text-gray-400 mt-1">Run evaluation on your models with test datasets</p>
                        </div>
                    </div>
                    <button className="text-gray-400 hover:text-white" onClick={() => navigate('/')}>
                        <span className="material-symbols-outlined">close</span>
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 p-8">
                <div className="max-w-4xl mx-auto space-y-8">

                    {/* Task Name */}
                    <div className="bg-surface rounded-xl border border-border p-6 space-y-4">
                        <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-border pb-2 flex items-center gap-2">
                            <span className="material-symbols-outlined text-green-400 text-[18px]">label</span>
                            Evaluation Name
                        </h2>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-gray-400 uppercase tracking-wider">Task Name (Optional)</label>
                            <input
                                type="text"
                                value={formData.name}
                                onChange={(e) => handleSelect('name', e.target.value)}
                                placeholder={`eval-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}`}
                                className="w-full bg-black/20 border border-border rounded-lg p-3 text-sm text-white focus:border-primary focus:outline-none"
                            />
                            <p className="text-[10px] text-gray-500">
                                Leave empty to use the auto-generated name based on today's date
                            </p>
                        </div>
                    </div>

                    {/* Step 1: Model & Adapter Selection */}
                    <div className="bg-surface rounded-xl border border-border p-6 space-y-6">
                        <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-border pb-2 flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary text-[18px]">deployed_code</span>
                            Select Model & Adapter
                        </h2>

                        <div className="space-y-4">
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-wider">Base Model <span className="text-red-500">*</span></label>
                                <select
                                    value={formData.modelId}
                                    onChange={(e) => handleSelect('modelId', e.target.value)}
                                    className="w-full bg-black/20 border border-border rounded-lg p-3 text-sm text-white focus:border-primary focus:outline-none"
                                >
                                    <option value="">Select a model...</option>
                                    {models.map(m => (
                                        <option key={m.id} value={m.id}>
                                            {m.name} {m.params !== 'Unknown' ? `(${m.params})` : ''}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div className="space-y-2">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-wider">Adapter (Optional)</label>
                                <select
                                    value={formData.adapterId}
                                    onChange={(e) => handleSelect('adapterId', e.target.value)}
                                    className="w-full bg-black/20 border border-border rounded-lg p-3 text-sm text-white focus:border-primary focus:outline-none"
                                >
                                    <option value="none">None (Base Model Only)</option>
                                    {compatibleAdapters.map(a => (
                                        <option key={a.id} value={a.id}>
                                            {a.name} (r={a.rank}) - {a.created}
                                        </option>
                                    ))}
                                </select>
                                <p className="text-[10px] text-gray-500">
                                    Select a LoRA adapter to evaluate the fine-tuned model
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Step 2: Dataset Selection */}
                    <div className="bg-surface rounded-xl border border-border p-6 space-y-6">
                        <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-border pb-2 flex items-center gap-2">
                            <span className="material-symbols-outlined text-warning text-[18px]">database</span>
                            Test Dataset <span className="text-red-500">*</span>
                        </h2>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {evalDatasets.map(ds => (
                                <div
                                    key={ds.id}
                                    onClick={() => handleSelect('datasetId', ds.id)}
                                    className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${formData.datasetId === ds.id
                                        ? 'border-primary bg-primary/5'
                                        : 'border-border bg-black/20 hover:border-gray-500'
                                        }`}
                                >
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-white font-medium">{ds.name}</span>
                                                <span className={`text-[10px] px-1.5 py-0.5 rounded ${ds.type === 'Eval'
                                                    ? 'bg-purple-500/20 text-purple-400'
                                                    : 'bg-green-500/20 text-green-400'
                                                    }`}>
                                                    {ds.type}
                                                </span>
                                            </div>
                                            <div className="flex gap-2 mt-1">
                                                <span className="text-xs text-gray-500">{ds.samples.toLocaleString()} rows</span>
                                                <span className="text-xs text-gray-600 font-mono">#{ds.hash}</span>
                                            </div>
                                        </div>
                                        {formData.datasetId === ds.id && (
                                            <span className="material-symbols-outlined text-primary">check_circle</span>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>

                        {evalDatasets.length === 0 && (
                            <div className="text-center py-8 text-gray-500">
                                <span className="material-symbols-outlined text-4xl mb-2">folder_off</span>
                                <p>No evaluation datasets found</p>
                                <p className="text-xs mt-1">Import a dataset with type "Eval" to run evaluations</p>
                            </div>
                        )}
                    </div>

                    {/* Step 3: Complete Evaluation Pipeline */}
                    <div className="bg-surface rounded-xl border border-border p-6 space-y-6">
                        <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-border pb-2 flex items-center gap-2">
                            <span className="material-symbols-outlined text-purple-400 text-[18px]">science</span>
                            Complete Evaluation Pipeline
                        </h2>

                        {/* Evaluation Overview */}
                        <div className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 rounded-lg p-4 border border-purple-500/20">
                            <h3 className="text-xs font-bold text-purple-400 uppercase mb-3 flex items-center gap-2">
                                <span className="material-symbols-outlined text-[14px]">checklist</span>
                                What will be evaluated
                            </h3>
                            <div className="grid grid-cols-2 gap-3 text-xs">
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-success text-[14px]">check_circle</span>
                                    <span className="text-gray-300">Pass@k (k=1,5,10)</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-success text-[14px]">check_circle</span>
                                    <span className="text-gray-300">Compile Rate</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-success text-[14px]">check_circle</span>
                                    <span className="text-gray-300">Error Classification</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-success text-[14px]">check_circle</span>
                                    <span className="text-gray-300">Execution Time Stats</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-success text-[14px]">check_circle</span>
                                    <span className="text-gray-300">Difficulty Breakdown</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-success text-[14px]">check_circle</span>
                                    <span className="text-gray-300">Code Quality Analysis</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-success text-[14px]">check_circle</span>
                                    <span className="text-gray-300">Failure Case Analysis</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-success text-[14px]">check_circle</span>
                                    <span className="text-gray-300">Academic Report (PDF/HTML)</span>
                                </div>
                            </div>
                        </div>

                        {/* Generation Parameters */}
                        <div className="space-y-4">
                            <h3 className="text-xs font-bold text-gray-400 uppercase flex items-center gap-2">
                                <span className="material-symbols-outlined text-[14px]">tune</span>
                                Generation Parameters
                            </h3>
                            <div className="grid grid-cols-3 gap-4">
                                <div className="space-y-2">
                                    <label className="text-xs text-gray-400">Pass@k Values</label>
                                    <input
                                        type="text"
                                        className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                        value={formData.evalK}
                                        onChange={e => handleSelect('evalK', e.target.value)}
                                        placeholder="e.g. 1,5,10"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs text-gray-400">Temperature</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        min="0"
                                        max="2"
                                        className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                        value={formData.evalTemp}
                                        onChange={e => handleSelect('evalTemp', parseFloat(e.target.value) || 0.2)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs text-gray-400">Samples per Problem</label>
                                    <input
                                        type="number"
                                        min="1"
                                        max="100"
                                        className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                        value={formData.evalSamples}
                                        onChange={e => handleSelect('evalSamples', parseInt(e.target.value) || 10)}
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Execution Parameters */}
                        <div className="space-y-4">
                            <h3 className="text-xs font-bold text-gray-400 uppercase flex items-center gap-2">
                                <span className="material-symbols-outlined text-[14px]">timer</span>
                                Execution Parameters
                            </h3>
                            <div className="grid grid-cols-3 gap-4">
                                <div className="space-y-2">
                                    <label className="text-xs text-gray-400">Timeout (seconds)</label>
                                    <input
                                        type="number"
                                        min="1"
                                        max="300"
                                        className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                        value={formData.evalTimeout}
                                        onChange={e => handleSelect('evalTimeout', parseInt(e.target.value) || 60)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs text-gray-400">Max New Tokens</label>
                                    <input
                                        type="number"
                                        min="64"
                                        max="2048"
                                        className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                        value={formData.maxNewTokens}
                                        onChange={e => handleSelect('maxNewTokens', parseInt(e.target.value) || 512)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs text-gray-400">Memory Limit (MB)</label>
                                    <input
                                        type="number"
                                        min="256"
                                        max="8192"
                                        className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none"
                                        value={formData.memoryLimit}
                                        onChange={e => handleSelect('memoryLimit', parseInt(e.target.value) || 1024)}
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Report Options */}
                        <div className="space-y-4">
                            <h3 className="text-xs font-bold text-gray-400 uppercase flex items-center gap-2">
                                <span className="material-symbols-outlined text-[14px]">description</span>
                                Report Generation
                            </h3>
                            <div className="grid grid-cols-2 gap-4">
                                <label className={`cursor-pointer p-4 border rounded-lg flex items-center gap-3 transition-all ${formData.generateReport ? 'bg-primary/10 border-primary text-white' : 'bg-black/20 border-border text-gray-400 hover:border-gray-500'}`}>
                                    <input
                                        type="checkbox"
                                        className="w-4 h-4 accent-primary"
                                        checked={formData.generateReport}
                                        onChange={e => handleSelect('generateReport', e.target.checked)}
                                    />
                                    <div>
                                        <div className="text-sm font-medium">Generate Academic Report</div>
                                        <div className="text-[10px] text-gray-500">Full evaluation report in PDF/HTML format</div>
                                    </div>
                                </label>
                                <label className={`cursor-pointer p-4 border rounded-lg flex items-center gap-3 transition-all ${formData.saveFailureCases ? 'bg-primary/10 border-primary text-white' : 'bg-black/20 border-border text-gray-400 hover:border-gray-500'}`}>
                                    <input
                                        type="checkbox"
                                        className="w-4 h-4 accent-primary"
                                        checked={formData.saveFailureCases}
                                        onChange={e => handleSelect('saveFailureCases', e.target.checked)}
                                    />
                                    <div>
                                        <div className="text-sm font-medium">Save Failure Cases</div>
                                        <div className="text-[10px] text-gray-500">Detailed analysis of failed test cases</div>
                                    </div>
                                </label>
                            </div>
                        </div>
                    </div>

                    {/* Summary Card */}
                    {formData.modelId && formData.datasetId && (
                        <div className="bg-gradient-to-r from-primary/10 to-purple-500/10 rounded-xl border border-primary/30 p-6">
                            <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                                <span className="material-symbols-outlined text-primary">summarize</span>
                                Evaluation Summary
                            </h3>
                            <div className="grid grid-cols-3 gap-4 text-sm">
                                <div>
                                    <span className="text-gray-400">Model:</span>
                                    <span className="text-white ml-2 font-medium">{selectedModel?.name}</span>
                                </div>
                                <div>
                                    <span className="text-gray-400">Adapter:</span>
                                    <span className="text-white ml-2 font-medium">
                                        {formData.adapterId !== 'none'
                                            ? adapters.find(a => a.id === formData.adapterId)?.name
                                            : 'None'}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-gray-400">Dataset:</span>
                                    <span className="text-white ml-2 font-medium">
                                        {datasets.find(d => d.id === formData.datasetId)?.name}
                                    </span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Footer */}
            <div className="px-8 py-4 border-t border-border bg-surface flex justify-between shrink-0">
                <button
                    onClick={() => navigate('/')}
                    className="px-6 py-2.5 rounded-lg text-gray-400 font-medium hover:text-white transition-colors"
                >
                    Cancel
                </button>
                <button
                    disabled={!isFormValid() || submitting}
                    onClick={handleSubmit}
                    className="px-8 py-2.5 rounded-lg bg-primary hover:bg-blue-600 text-white font-bold shadow-lg shadow-primary/20 transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {submitting ? 'Starting...' : 'Run Evaluation'}
                    <span className="material-symbols-outlined text-lg">
                        {submitting ? 'hourglass_empty' : 'play_arrow'}
                    </span>
                </button>
            </div>
        </div>
    );
};

export default Evaluation;
