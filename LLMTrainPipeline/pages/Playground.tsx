import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { fetchModels, fetchAdapters, inferPlaygroundStream } from '../lib/api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001/api';

// Model load status type
interface LoadedModelInfo {
  modelId: string;
  modelName: string;
  modelPath: string;
  adapterId?: string;
  adapterName?: string;
  quantization: string;
}

const Playground: React.FC = () => {
  const [models, setModels] = useState<any[]>([]);
  const [adapters, setAdapters] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [serviceStatus, setServiceStatus] = useState<{ available: boolean; message: string } | null>(null);

  // Model loading states
  const [loadedModel, setLoadedModel] = useState<LoadedModelInfo | null>(null);
  const [isLoadingModel, setIsLoadingModel] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Selection states (for when model is NOT loaded)
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedAdapter, setSelectedAdapter] = useState('none');
  const [selectedQuantization, setSelectedQuantization] = useState<'4bit' | '8bit' | 'none'>('4bit');

  const [systemPrompt, setSystemPrompt] = useState('You are a helpful AI assistant. Please think step-by-step before answering. Wrap your detailed analysis and thought process in <think> tags. For example:\n<think>\nStep 1: Analyze the request...\n</think>\nHere is the answer...');
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant', content: string }[]>([]);
  const [input, setInput] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [modelStatus, setModelStatus] = useState<string>('');
  const [generationTime, setGenerationTime] = useState<number | null>(null);
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(512);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Fetch initial data and check if a model is already loaded
  useEffect(() => {
    const loadData = async () => {
      try {
        // Check inference service status
        const statusRes = await fetch(`${API_BASE}/playground/status`);
        const status = await statusRes.json();
        setServiceStatus({ available: status.available, message: status.message });

        // If server already has a loaded model, set state
        if (status.loaded && status.loadedModel) {
          // Try to match loaded model to our model list
          const modelsData = await fetchModels();
          const adaptersData = await fetchAdapters();
          setModels(modelsData);
          setAdapters(adaptersData);

          const matchedModel = modelsData.find((m: any) => m.path === status.loadedModel.modelPath);
          const matchedAdapter = status.loadedModel.adapterPath
            ? adaptersData.find((a: any) => a.path === status.loadedModel.adapterPath)
            : null;

          if (matchedModel) {
            setLoadedModel({
              modelId: matchedModel.id,
              modelName: matchedModel.name,
              modelPath: matchedModel.path,
              adapterId: matchedAdapter?.id,
              adapterName: matchedAdapter?.name,
              quantization: status.loadedModel.quantization || 'none',
            });
            setSelectedModel(matchedModel.id);
            if (matchedAdapter) {
              setSelectedAdapter(matchedAdapter.id);
            }
          }
        } else {
          // No loaded model, load data normally
          const [modelsData, adaptersData] = await Promise.all([
            fetchModels(),
            fetchAdapters()
          ]);
          setModels(modelsData);
          setAdapters(adaptersData);
          if (modelsData.length > 0) {
            const smallerModel = modelsData.find((m: any) => m.name.includes('3B')) || modelsData[0];
            setSelectedModel(smallerModel.id);
          }
        }
      } catch (e) {
        console.error(e);
        setServiceStatus({ available: false, message: 'Failed to connect to backend' });
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const compatibleAdapters = adapters.filter(a => {
    const model = models.find(m => m.id === selectedModel);
    return model && a.baseModel === model.name;
  });

  const handleSend = async () => {
    if (!input.trim() || isGenerating) return;

    const userInput = input;
    const userMessage = { role: 'user' as const, content: userInput };

    setInput('');
    setMessages(prev => [...prev, userMessage]);
    setIsGenerating(true);
    setGenerationTime(null);
    setModelStatus('Initializing...');

    const startTime = Date.now();
    let assistantMessage = { role: 'assistant' as const, content: '' };

    // Add empty assistant message immediately
    setMessages(prev => [...prev, assistantMessage]);

    try {
      const response = await inferPlaygroundStream({
        modelId: selectedModel,
        adapterId: selectedAdapter !== 'none' ? selectedAdapter : undefined,
        systemPrompt,
        messages: [...messages, { role: 'user', content: userInput }],
        temperature,
        maxTokens,
      });

      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');

        // Keep the last potentially incomplete line in the buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          // Handle Keep-Alive and Status updates
          if (line.startsWith(': ')) {
            if (line.includes('keeping connection alive')) {
              setModelStatus('Loading...');
            } else if (line.includes('log')) {
              console.log('Backend log:', line.slice(6));
            }
            continue;
          }

          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            if (dataStr === '[DONE]') continue; // Standard SSE done marker check (just in case)

            try {
              const data = JSON.parse(dataStr);

              if (data.token) {
                if (modelStatus !== 'Generating...') setModelStatus('Generating...');
                assistantMessage.content += data.token;
                // Update the last message (assistant's)
                setMessages(prev => {
                  const newMessages = [...prev];
                  newMessages[newMessages.length - 1] = { ...assistantMessage };
                  return newMessages;
                });
                // Force scroll to bottom on new token if near bottom (autoscroll handled by useEffect currently)
              } else if (data.done) {
                // Generation finished normally
              } else if (data.error) {
                throw new Error(data.error);
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }

      // Final check for remaining buffer
      if (buffer.startsWith('data: ')) {
        try {
          const data = JSON.parse(buffer.slice(6));
          if (data.token) {
            assistantMessage.content += data.token;
            setMessages(prev => {
              const newMessages = [...prev];
              newMessages[newMessages.length - 1] = { ...assistantMessage };
              return newMessages;
            });
          }
        } catch (e) { }
      }

      setGenerationTime(Date.now() - startTime);
      setModelStatus('');

    } catch (e: any) {
      console.error('Inference error:', e);
      setMessages(prev => {
        const newMessages = [...prev];
        const lastMsg = newMessages[newMessages.length - 1];
        // Append error to current message or create new one
        if (lastMsg.role === 'assistant') {
          lastMsg.content += `\n\n**Error:** ${e.message || 'Failed to generate response.'}`;
        } else {
          newMessages.push({
            role: 'assistant',
            content: `Error: ${e.message || 'Failed to generate response.'}`
          });
        }
        return newMessages;
      });
    } finally {
      setIsGenerating(false);
      setModelStatus('');
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setModelStatus('');
    setGenerationTime(null);
  };

  // Load model
  const handleLoadModel = async () => {
    if (!selectedModel || isLoadingModel) return;

    setIsLoadingModel(true);
    setLoadError(null);
    setModelStatus('Loading model...');

    try {
      const response = await fetch(`${API_BASE}/playground/load`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          modelId: selectedModel,
          adapterId: selectedAdapter !== 'none' ? selectedAdapter : undefined,
          quantization: selectedQuantization,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to load model');
      }

      // Set loaded model info
      setLoadedModel({
        modelId: data.model.id,
        modelName: data.model.name,
        modelPath: data.model.path,
        adapterId: data.adapter?.id,
        adapterName: data.adapter?.name,
        quantization: data.quantization,
      });

      setServiceStatus({ available: true, message: 'Model loaded and ready' });
      setModelStatus('');
    } catch (e: any) {
      console.error('Load model error:', e);
      setLoadError(e.message || 'Failed to load model');
      setModelStatus('');
    } finally {
      setIsLoadingModel(false);
    }
  };

  // Unload model
  const handleUnload = async () => {
    try {
      await fetch(`${API_BASE}/playground/unload`, { method: 'POST' });
      setLoadedModel(null);
      setServiceStatus({ available: true, message: 'Model unloaded' });
      setModelStatus('');
      setLoadError(null);
    } catch (e) {
      console.error(e);
    }
  };

  const renderMessageContent = (content: string) => {
    // Check for <think> tag
    const thinkMatch = /<think>([\s\S]*?)(?:<\/think>|$)/.exec(content);

    if (thinkMatch) {
      const thought = thinkMatch[1];
      const isThinking = !content.includes('</think>');
      // Remove the think block to get the actual response
      const response = content.replace(/<think>[\s\S]*?(?:<\/think>|$)/, '').trim();

      return (
        <div className="space-y-4">
          <details open className="group bg-black/20 rounded-lg border border-white/10 overflow-hidden">
            <summary className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-white/5 text-xs font-mono text-gray-500 select-none">
              <span className="material-symbols-outlined text-[14px] transition-transform group-open:rotate-90">chevron_right</span>
              <span>Thinking Process</span>
              {isThinking && <span className="animate-pulse ml-2">...</span>}
            </summary>
            <div className="px-3 pb-3 pt-0 text-gray-400 text-sm font-mono whitespace-pre-wrap leading-relaxed border-t border-white/5 mt-1 relative">
              {thought}
              {isThinking && <span className="inline-block w-1.5 h-3 bg-gray-400 ml-1 animate-pulse"></span>}
            </div>
          </details>

          {response && (
            <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ node, inline, className, children, ...props }: any) {
                    const match = /language-(\w+)/.exec(className || '');
                    return !inline && match ? (
                      <div className="rounded-md overflow-hidden my-2 border border-gray-700">
                        <div className="bg-[#1a1a1a] px-3 py-1 text-xs text-gray-400 flex justify-between items-center border-b border-gray-700">
                          <span>{match[1]}</span>
                          <span className="material-symbols-outlined text-[14px] cursor-pointer hover:text-white" onClick={() => navigator.clipboard.writeText(String(children))}>content_copy</span>
                        </div>
                        <SyntaxHighlighter
                          style={vscDarkPlus}
                          language={match[1]}
                          PreTag="div"
                          customStyle={{ margin: 0, borderRadius: 0, padding: '1rem', backgroundColor: '#0d0d0d' }}
                          {...props}
                        >
                          {String(children).replace(/\n$/, '')}
                        </SyntaxHighlighter>
                      </div>
                    ) : (
                      <code className={`${className} bg-gray-800 px-1 py-0.5 rounded text-sm`} {...props}>
                        {children}
                      </code>
                    );
                  },
                  a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">{children}</a>,
                  table: ({ children }) => <div className="overflow-x-auto my-2 border border-gray-700 rounded"><table className="w-full text-left text-xs border-collapse">{children}</table></div>,
                  thead: ({ children }) => <thead className="bg-[#1a1a1a] text-gray-300 font-bold">{children}</thead>,
                  tbody: ({ children }) => <tbody className="divide-y divide-gray-700 bg-[#0d0d0d]">{children}</tbody>,
                  tr: ({ children }) => <tr className="hover:bg-white/5 transition-colors">{children}</tr>,
                  th: ({ children }) => <th className="px-3 py-2 border-r border-gray-700 last:border-r-0">{children}</th>,
                  td: ({ children }) => <td className="px-3 py-2 border-r border-gray-700 last:border-r-0">{children}</td>,
                }}
              >
                {response}
              </ReactMarkdown>
            </div>
          )}
        </div>
      );
    }

    // Default rendering for content without <think> tags
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '');
            return !inline && match ? (
              <div className="rounded-md overflow-hidden my-2 border border-gray-700">
                <div className="bg-[#1a1a1a] px-3 py-1 text-xs text-gray-400 flex justify-between items-center border-b border-gray-700">
                  <span>{match[1]}</span>
                  <span className="material-symbols-outlined text-[14px] cursor-pointer hover:text-white" onClick={() => navigator.clipboard.writeText(String(children))}>content_copy</span>
                </div>
                <SyntaxHighlighter
                  style={vscDarkPlus}
                  language={match[1]}
                  PreTag="div"
                  customStyle={{ margin: 0, borderRadius: 0, padding: '1rem', backgroundColor: '#0d0d0d' }}
                  {...props}
                >
                  {String(children).replace(/\n$/, '')}
                </SyntaxHighlighter>
              </div>
            ) : (
              <code className={`${className} bg-gray-800 px-1 py-0.5 rounded text-sm`} {...props}>
                {children}
              </code>
            );
          },
          a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">{children}</a>,
          table: ({ children }) => <div className="overflow-x-auto my-2 border border-gray-700 rounded"><table className="w-full text-left text-xs border-collapse">{children}</table></div>,
          thead: ({ children }) => <thead className="bg-[#1a1a1a] text-gray-300 font-bold">{children}</thead>,
          tbody: ({ children }) => <tbody className="divide-y divide-gray-700 bg-[#0d0d0d]">{children}</tbody>,
          tr: ({ children }) => <tr className="hover:bg-white/5 transition-colors">{children}</tr>,
          th: ({ children }) => <th className="px-3 py-2 border-r border-gray-700 last:border-r-0">{children}</th>,
          td: ({ children }) => <td className="px-3 py-2 border-r border-gray-700 last:border-r-0">{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    );
  };

  const selectedModelInfo = models.find(m => m.id === selectedModel);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-gray-400 text-sm">Loading models and checking inference service...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full bg-background">
      {/* Config Sidebar */}
      <div className="w-80 bg-surface border-r border-border flex flex-col p-6 overflow-y-auto shrink-0">
        <h2 className="text-lg font-bold text-white mb-4">Configuration</h2>

        {/* Service Status */}
        <div className={`mb-6 p-3 rounded-lg border ${serviceStatus?.available
          ? 'bg-success/10 border-success/20'
          : 'bg-error/10 border-error/20'
          }`}>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${serviceStatus?.available ? 'bg-success' : 'bg-error'}`}></span>
            <span className={`text-xs font-bold ${serviceStatus?.available ? 'text-success' : 'text-error'}`}>
              {loadedModel ? 'Model Loaded' : (serviceStatus?.available ? 'No Model Loaded' : 'Service Unavailable')}
            </span>
          </div>
          <p className="text-[10px] text-gray-400 mt-1">{serviceStatus?.message}</p>
        </div>

        {/* Model Loading/Loaded State */}
        {loadedModel ? (
          /* Model is loaded - show loaded info */
          <div className="space-y-6">
            <div className="bg-primary/10 border border-primary/30 rounded-lg p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">check_circle</span>
                <span className="text-sm font-bold text-primary">Model Active</span>
              </div>

              <div className="space-y-2">
                <div>
                  <span className="text-[10px] text-gray-500 uppercase">Model</span>
                  <p className="text-sm text-white font-medium">{loadedModel.modelName}</p>
                </div>
                {loadedModel.adapterName && (
                  <div>
                    <span className="text-[10px] text-gray-500 uppercase">Adapter</span>
                    <p className="text-sm text-white font-medium">{loadedModel.adapterName}</p>
                  </div>
                )}
                <div>
                  <span className="text-[10px] text-gray-500 uppercase">Quantization</span>
                  <p className="text-sm text-white font-medium">{loadedModel.quantization || 'None'}</p>
                </div>
              </div>

              <button
                onClick={handleUnload}
                className="w-full mt-2 flex items-center justify-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors text-sm font-medium"
              >
                <span className="material-symbols-outlined text-[18px]">eject</span>
                Unload Model
              </button>
            </div>

            {/* System Prompt - always visible */}
            <div className="space-y-2">
              <label className="text-xs font-bold text-gray-400 uppercase">System Prompt</label>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-xs text-gray-300 focus:border-primary focus:outline-none h-28 resize-none font-mono"
              />
            </div>

            {/* Generation Parameters - always visible */}
            <div className="pt-4 border-t border-border space-y-4">
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-gray-400">
                  <span>Temperature</span>
                  <span className="font-mono">{temperature.toFixed(1)}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer"
                />
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-gray-400">
                  <span>Max Tokens</span>
                  <span className="font-mono">{maxTokens}</span>
                </div>
                <input
                  type="range"
                  min="64"
                  max="2048"
                  step="64"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                  className="w-full h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer"
                />
              </div>
            </div>
          </div>
        ) : (
          /* No model loaded - show selection interface */
          <div className="space-y-6">
            {/* Load Error Alert */}
            {loadError && (
              <div className="bg-error/10 border border-error/30 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <span className="material-symbols-outlined text-error text-[18px]">error</span>
                  <div>
                    <p className="text-sm text-error font-medium">Load Failed</p>
                    <p className="text-xs text-error/80 mt-1">{loadError}</p>
                  </div>
                </div>
              </div>
            )}

            <div className="space-y-2">
              <label className="text-xs font-bold text-gray-400 uppercase">Base Model</label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                disabled={isLoadingModel}
                className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none disabled:opacity-50"
              >
                {models.map(m => (
                  <option key={m.id} value={m.id}>
                    {m.name} {m.params !== 'Unknown' ? `(${m.params})` : ''}
                  </option>
                ))}
              </select>
              {selectedModelInfo && (
                <div className="text-[10px] text-gray-500 font-mono break-all">
                  {selectedModelInfo.path}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-gray-400 uppercase">Adapter (LoRA)</label>
              <select
                value={selectedAdapter}
                onChange={(e) => setSelectedAdapter(e.target.value)}
                disabled={isLoadingModel}
                className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none disabled:opacity-50"
              >
                <option value="none">None (Base Model Only)</option>
                {compatibleAdapters.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-gray-400 uppercase">Quantization</label>
              <select
                value={selectedQuantization}
                onChange={(e) => setSelectedQuantization(e.target.value as '4bit' | '8bit' | 'none')}
                disabled={isLoadingModel}
                className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-sm text-white focus:border-primary focus:outline-none disabled:opacity-50"
              >
                <option value="4bit">4-bit (Recommended)</option>
                <option value="8bit">8-bit</option>
                <option value="none">None (Full Precision)</option>
              </select>
            </div>

            {/* Load Model Button */}
            <button
              onClick={handleLoadModel}
              disabled={!selectedModel || isLoadingModel || !serviceStatus?.available}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-primary hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors text-sm font-medium"
            >
              {isLoadingModel ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                  Loading Model...
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-[18px]">download</span>
                  Load Model
                </>
              )}
            </button>

            {isLoadingModel && (
              <p className="text-[10px] text-gray-500 text-center">
                This may take a few minutes for large models...
              </p>
            )}

            {/* System Prompt */}
            <div className="space-y-2 pt-4 border-t border-border">
              <label className="text-xs font-bold text-gray-400 uppercase">System Prompt</label>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="w-full bg-black/20 border border-border rounded-lg p-2.5 text-xs text-gray-300 focus:border-primary focus:outline-none h-28 resize-none font-mono"
              />
            </div>

            {/* Generation Parameters */}
            <div className="pt-4 border-t border-border space-y-4">
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-gray-400">
                  <span>Temperature</span>
                  <span className="font-mono">{temperature.toFixed(1)}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer"
                />
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-gray-400">
                  <span>Max Tokens</span>
                  <span className="font-mono">{maxTokens}</span>
                </div>
                <input
                  type="range"
                  min="64"
                  max="2048"
                  step="64"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                  className="w-full h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer"
                />
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 flex flex-col bg-background text-foreground">
        {/* Header */}
        <div className="h-16 border-b border-border flex items-center justify-between px-6 shrink-0">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary">terminal</span>
            <h1 className="font-semibold text-lg">Playground</h1>
            {loadedModel ? (
              <span className="text-xs px-2.5 py-1 rounded-full bg-primary/20 text-primary flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>
                {loadedModel.modelName}
              </span>
            ) : (
              <span className="text-xs px-2.5 py-1 rounded-full bg-yellow-500/20 text-yellow-500">
                No Model Loaded
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleClearChat}
              disabled={messages.length === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-400 hover:text-white hover:bg-white/10 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-[18px]">delete_sweep</span>
              Clear Chat
            </button>
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Generation time indicator */}
          {generationTime !== null && (
            <div className="absolute top-20 right-8 text-xs text-gray-500 bg-surface/80 px-2 py-1 rounded z-10">
              Last response: {(generationTime / 1000).toFixed(1)}s
            </div>
          )}

          <div className="flex-1 overflow-y-auto p-4 space-y-6 scrollbar-thin scrollbar-thumb-gray-800 scrollbar-track-transparent">
            {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-gray-500 space-y-4">
                <span className="material-symbols-outlined text-6xl opacity-20">smart_toy</span>
                {loadedModel ? (
                  <p>Model loaded! Start chatting below.</p>
                ) : (
                  <div className="text-center space-y-2">
                    <p>No model loaded</p>
                    <p className="text-xs text-gray-600">Select a model from the sidebar and click "Load Model" to begin.</p>
                  </div>
                )}
              </div>
            )}

            {messages.map((msg, idx) => {
              // Hide the last assistant message if it's empty and generating (because the Loading component handles this state)
              if (msg.role === 'assistant' && isGenerating && idx === messages.length - 1 && msg.content === '') {
                return null;
              }
              return (
                <div key={idx} className={`flex gap-4 ${msg.role === 'assistant' ? 'bg-transparent' : 'flex-row-reverse'}`}>
                  <div className={`w-8 h-8 rounded flex items-center justify-center shrink-0 ${msg.role === 'assistant' ? 'bg-purple-500 text-white' : 'bg-primary text-white'
                    }`}>
                    <span className="material-symbols-outlined text-[18px]">
                      {msg.role === 'assistant' ? 'smart_toy' : 'person'}
                    </span>
                  </div>
                  <div className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm overflow-hidden ${msg.role === 'assistant'
                    ? 'bg-surface border border-border text-gray-300 rounded-tl-none'
                    : 'bg-primary text-white rounded-tr-none'
                    }`}>
                    {msg.role === 'user' ? (
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                    ) : (
                      renderMessageContent(msg.content)
                    )}
                    {/* Cursor for streaming effect */}
                    {isGenerating && idx === messages.length - 1 && msg.role === 'assistant' && (
                      <span className="inline-block w-2 h-4 bg-gray-400 ml-1 align-middle animate-pulse">▍</span>
                    )}
                  </div>
                </div>
              );
            })}

            {isGenerating && messages[messages.length - 1]?.content === '' && (
              <div className="flex gap-4">
                <div className="w-8 h-8 rounded flex items-center justify-center shrink-0 bg-purple-500 text-white">
                  <span className="material-symbols-outlined text-[18px]">smart_toy</span>
                </div>
                <div className="bg-surface border border-border px-4 py-3 rounded-2xl rounded-tl-none">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                      <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                      <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></div>
                    </div>
                    <span className="text-xs text-gray-500 ml-2">{modelStatus || 'Generating response...'}</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="p-4 border-t border-border bg-surface">
            <div className="max-w-3xl mx-auto flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && loadedModel && handleSend()}
                placeholder={!loadedModel ? "Load a model first..." : (isGenerating ? "Generating response..." : "Type your message...")}
                className="flex-1 bg-black/20 border border-border rounded-lg px-4 py-3 text-white focus:border-primary focus:outline-none disabled:opacity-50"
                disabled={isGenerating || !loadedModel}
              />
              <button
                onClick={handleSend}
                disabled={isGenerating || !input.trim() || !loadedModel}
                className="bg-primary hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 rounded-lg font-medium transition-colors flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-[18px]">
                  {isGenerating ? 'hourglass_empty' : 'send'}
                </span>
              </button>
            </div>
            {!loadedModel && serviceStatus?.available && (
              <p className="text-center text-xs text-yellow-500 mt-2">
                Please load a model from the sidebar to start chatting.
              </p>
            )}
            {!serviceStatus?.available && (
              <p className="text-center text-xs text-error mt-2">
                Inference service is not available. Please check if Python and required packages are installed.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Playground;
