import React, { useState, useEffect, useCallback } from 'react';
import { browseFiles, getDrives, getQuickPaths, FileItem, BrowseResult } from '../lib/api';

interface FileBrowserProps {
    isOpen: boolean;
    onClose: () => void;
    onSelect: (file: FileItem) => void;
    title?: string;
    filter?: string; // e.g. ".jsonl,.json,.parquet"
    selectMode?: 'file' | 'directory';
}

const FileBrowser: React.FC<FileBrowserProps> = ({
    isOpen,
    onClose,
    onSelect,
    title = 'Select File',
    filter = '.jsonl,.json,.parquet',
    selectMode = 'file',
}) => {
    const [currentPath, setCurrentPath] = useState<string>('');
    const [items, setItems] = useState<FileItem[]>([]);
    const [parent, setParent] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [drives, setDrives] = useState<string[]>([]);
    const [quickPaths, setQuickPaths] = useState<{ name: string; path: string }[]>([]);
    const [error, setError] = useState<string | null>(null);

    const loadDirectory = useCallback(async (path?: string) => {
        setLoading(true);
        setError(null);
        try {
            const result = await browseFiles(path, selectMode === 'file' ? filter : undefined);
            setCurrentPath(result.currentPath);
            setItems(result.items);
            setParent(result.parent);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, [filter, selectMode]);

    useEffect(() => {
        if (isOpen) {
            // Load initial data
            loadDirectory();
            getDrives().then(r => setDrives(r.drives)).catch(console.error);
            getQuickPaths().then(r => setQuickPaths(r.paths)).catch(console.error);
        }
    }, [isOpen, loadDirectory]);

    const handleItemClick = (item: FileItem) => {
        if (item.isDirectory) {
            loadDirectory(item.path);
        }
    };

    const handleItemDoubleClick = (item: FileItem) => {
        if (item.isDirectory) {
            if (selectMode === 'directory') {
                onSelect(item);
                onClose();
            } else {
                loadDirectory(item.path);
            }
        } else {
            onSelect(item);
            onClose();
        }
    };

    const handleSelectCurrent = () => {
        if (selectMode === 'directory' && currentPath) {
            onSelect({
                name: currentPath.split(/[/\\]/).pop() || currentPath,
                path: currentPath,
                isDirectory: true,
                size: null,
                ext: null,
            });
            onClose();
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
            <div className="bg-surface border border-border rounded-xl w-[800px] max-h-[600px] flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                    <h2 className="text-white font-bold">{title}</h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-white">
                        <span className="material-symbols-outlined">close</span>
                    </button>
                </div>

                <div className="flex flex-1 min-h-0">
                    {/* Sidebar */}
                    <div className="w-48 border-r border-border p-3 flex flex-col gap-2 overflow-y-auto">
                        <div className="text-[10px] font-bold text-gray-500 uppercase">Quick Access</div>
                        {quickPaths.map((p) => (
                            <button
                                key={p.path}
                                onClick={() => loadDirectory(p.path)}
                                className="text-left px-2 py-1.5 rounded text-sm text-gray-300 hover:bg-white/10 truncate"
                            >
                                {p.name}
                            </button>
                        ))}

                        {drives.length > 1 && (
                            <>
                                <div className="text-[10px] font-bold text-gray-500 uppercase mt-3">Drives</div>
                                {drives.map((d) => (
                                    <button
                                        key={d}
                                        onClick={() => loadDirectory(d)}
                                        className="text-left px-2 py-1.5 rounded text-sm text-gray-300 hover:bg-white/10"
                                    >
                                        {d}
                                    </button>
                                ))}
                            </>
                        )}
                    </div>

                    {/* Main Content */}
                    <div className="flex-1 flex flex-col min-w-0">
                        {/* Path Bar */}
                        <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-black/20">
                            <button
                                onClick={() => parent && loadDirectory(parent)}
                                disabled={!parent}
                                className="text-gray-400 hover:text-white disabled:opacity-30"
                            >
                                <span className="material-symbols-outlined text-[20px]">arrow_upward</span>
                            </button>
                            <div className="flex-1 bg-black/30 rounded px-3 py-1.5 text-sm text-gray-300 font-mono truncate">
                                {currentPath}
                            </div>
                            <button
                                onClick={() => loadDirectory(currentPath)}
                                className="text-gray-400 hover:text-white"
                            >
                                <span className="material-symbols-outlined text-[20px]">refresh</span>
                            </button>
                        </div>

                        {/* File List */}
                        <div className="flex-1 overflow-y-auto p-2">
                            {loading ? (
                                <div className="flex items-center justify-center h-full">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                                </div>
                            ) : error ? (
                                <div className="flex items-center justify-center h-full text-red-400">
                                    {error}
                                </div>
                            ) : items.length === 0 ? (
                                <div className="flex items-center justify-center h-full text-gray-500">
                                    Empty folder
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 gap-1">
                                    {items.map((item) => (
                                        <div
                                            key={item.path}
                                            onClick={() => handleItemClick(item)}
                                            onDoubleClick={() => handleItemDoubleClick(item)}
                                            className={`flex items-center gap-3 px-3 py-2 rounded cursor-pointer hover:bg-white/10 ${!item.isDirectory && selectMode === 'directory' ? 'opacity-50' : ''
                                                }`}
                                        >
                                            <span className={`material-symbols-outlined text-[20px] ${item.isDirectory ? 'text-yellow-400' : 'text-blue-400'
                                                }`}>
                                                {item.isDirectory ? 'folder' : 'description'}
                                            </span>
                                            <span className="flex-1 text-sm text-gray-200 truncate">{item.name}</span>
                                            {item.size && (
                                                <span className="text-xs text-gray-500">{item.size}</span>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between px-4 py-3 border-t border-border bg-black/20">
                    <div className="text-xs text-gray-500">
                        {selectMode === 'file' ? `Filter: ${filter}` : 'Select a folder'}
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={onClose}
                            className="px-4 py-1.5 rounded text-sm text-gray-300 border border-border hover:bg-white/10"
                        >
                            Cancel
                        </button>
                        {selectMode === 'directory' && (
                            <button
                                onClick={handleSelectCurrent}
                                className="px-4 py-1.5 rounded text-sm bg-primary text-white hover:bg-blue-600"
                            >
                                Select This Folder
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default FileBrowser;
