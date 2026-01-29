import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { API_BASE } from '../lib/api';

interface SearchResult {
    id: string;
    type: 'run' | 'model' | 'dataset' | 'adapter';
    name: string;
    description?: string;
    path: string;
}

interface CommandPaletteProps {
    isOpen: boolean;
    onClose: () => void;
}

const typeIcons: Record<string, string> = {
    run: 'play_circle',
    model: 'deployed_code',
    dataset: 'database',
    adapter: 'extension',
};

const typeColors: Record<string, string> = {
    run: 'text-green-400',
    model: 'text-blue-400',
    dataset: 'text-purple-400',
    adapter: 'text-orange-400',
};

const CommandPalette: React.FC<CommandPaletteProps> = ({ isOpen, onClose }) => {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<SearchResult[]>([]);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [isLoading, setIsLoading] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);
    const navigate = useNavigate();

    // Focus input when opened
    useEffect(() => {
        if (isOpen && inputRef.current) {
            inputRef.current.focus();
            setQuery('');
            setResults([]);
            setSelectedIndex(0);
        }
    }, [isOpen]);

    // Debounced search
    useEffect(() => {
        if (!query.trim()) {
            setResults([]);
            return;
        }

        const timer = setTimeout(async () => {
            setIsLoading(true);
            try {
                const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}`);
                if (res.ok) {
                    const data = await res.json();
                    setResults(data.results || []);
                    setSelectedIndex(0);
                }
            } catch (e) {
                console.error('Search failed:', e);
            } finally {
                setIsLoading(false);
            }
        }, 200);

        return () => clearTimeout(timer);
    }, [query]);

    // Keyboard navigation
    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setSelectedIndex(i => Math.min(i + 1, results.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setSelectedIndex(i => Math.max(i - 1, 0));
        } else if (e.key === 'Enter' && results.length > 0) {
            e.preventDefault();
            const selected = results[selectedIndex];
            if (selected) {
                navigate(selected.path);
                onClose();
            }
        } else if (e.key === 'Escape') {
            onClose();
        }
    }, [results, selectedIndex, navigate, onClose]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Modal */}
            <div className="relative w-full max-w-xl bg-surface border border-border rounded-xl shadow-2xl overflow-hidden">
                {/* Search Input */}
                <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
                    <span className="material-symbols-outlined text-gray-500">search</span>
                    <input
                        ref={inputRef}
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Search runs, models, datasets, adapters..."
                        className="flex-1 bg-transparent text-white placeholder-gray-500 focus:outline-none text-sm"
                    />
                    {isLoading && (
                        <span className="material-symbols-outlined text-gray-500 animate-spin text-[18px]">progress_activity</span>
                    )}
                    <kbd className="text-[10px] text-gray-500 border border-gray-700 rounded px-1.5 py-0.5 bg-gray-800">ESC</kbd>
                </div>

                {/* Results */}
                <div className="max-h-80 overflow-y-auto">
                    {results.length === 0 && query && !isLoading && (
                        <div className="px-4 py-8 text-center text-gray-500 text-sm">
                            No results found for "{query}"
                        </div>
                    )}

                    {results.length === 0 && !query && (
                        <div className="px-4 py-6 text-center text-gray-500 text-sm">
                            <p className="mb-2">Type to search across all resources</p>
                            <div className="flex justify-center gap-4 text-xs">
                                <span className="flex items-center gap-1">
                                    <span className="material-symbols-outlined text-[14px]">play_circle</span>
                                    Runs
                                </span>
                                <span className="flex items-center gap-1">
                                    <span className="material-symbols-outlined text-[14px]">deployed_code</span>
                                    Models
                                </span>
                                <span className="flex items-center gap-1">
                                    <span className="material-symbols-outlined text-[14px]">database</span>
                                    Datasets
                                </span>
                                <span className="flex items-center gap-1">
                                    <span className="material-symbols-outlined text-[14px]">extension</span>
                                    Adapters
                                </span>
                            </div>
                        </div>
                    )}

                    {results.map((result, index) => (
                        <div
                            key={`${result.type}-${result.id}`}
                            onClick={() => {
                                navigate(result.path);
                                onClose();
                            }}
                            className={`px-4 py-3 flex items-center gap-3 cursor-pointer transition-colors ${index === selectedIndex
                                ? 'bg-primary/10 border-l-2 border-primary'
                                : 'hover:bg-white/5 border-l-2 border-transparent'
                                }`}
                        >
                            <span className={`material-symbols-outlined ${typeColors[result.type]}`}>
                                {typeIcons[result.type]}
                            </span>
                            <div className="flex-1 min-w-0">
                                <div className="text-sm text-white truncate">{result.name}</div>
                                {result.description && (
                                    <div className="text-xs text-gray-500 truncate">{result.description}</div>
                                )}
                            </div>
                            <span className="text-[10px] text-gray-600 uppercase tracking-wider">{result.type}</span>
                        </div>
                    ))}
                </div>

                {/* Footer */}
                {results.length > 0 && (
                    <div className="px-4 py-2 border-t border-border flex items-center gap-4 text-[10px] text-gray-500">
                        <span className="flex items-center gap-1">
                            <kbd className="border border-gray-700 rounded px-1 bg-gray-800">↑</kbd>
                            <kbd className="border border-gray-700 rounded px-1 bg-gray-800">↓</kbd>
                            Navigate
                        </span>
                        <span className="flex items-center gap-1">
                            <kbd className="border border-gray-700 rounded px-1 bg-gray-800">Enter</kbd>
                            Open
                        </span>
                        <span className="flex items-center gap-1">
                            <kbd className="border border-gray-700 rounded px-1 bg-gray-800">Esc</kbd>
                            Close
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default CommandPalette;
