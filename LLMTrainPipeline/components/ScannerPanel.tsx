import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = 'http://localhost:3001/api';

interface ScannerPanelProps {
  entityType?: 'Models' | 'Datasets' | 'Adapters';
  contextPath?: string;
  contextTitle?: string;
}

interface ScanEvent {
  id: string;
  path: string;
  status: 'Scanning' | 'Error' | 'Idle' | 'Added' | 'Updated' | 'Removed';
  message?: string;
  timestamp: string;
}

interface ScanResult {
  added: number;
  updated: number;
  removed: number;
  errors: string[];
}

const ScannerPanel: React.FC<ScannerPanelProps> = ({
  entityType = 'Models',
  contextPath,
  contextTitle
}) => {
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [isScanning, setIsScanning] = useState(false);

  // Set default path based on entityType
  const defaultPaths: Record<string, string> = {
    Models: './storage/models',
    Datasets: './storage/train_datasets',
    Adapters: './storage/adapters',
  };

  const watchPath = contextPath || defaultPaths[entityType] || './storage';
  const title = contextTitle || `${entityType} Scanner`;

  // Get scan API endpoint
  const getScanEndpoint = () => {
    switch (entityType) {
      case 'Models': return `${API_BASE}/models/rescan`;
      case 'Datasets': return `${API_BASE}/datasets/rescan`;
      case 'Adapters': return `${API_BASE}/adapters/rescan`;
      default: return `${API_BASE}/models/rescan`;
    }
  };

  // Execute scan
  const runScan = useCallback(async () => {
    setIsScanning(true);

    const scanEvent: ScanEvent = {
      id: Date.now().toString(),
      path: watchPath,
      status: 'Scanning',
      message: 'Scanning in progress...',
      timestamp: new Date().toISOString().slice(0, 19).replace('T', ' '),
    };
    setEvents(prev => [scanEvent, ...prev.slice(0, 9)]);

    try {
      const res = await fetch(getScanEndpoint(), { method: 'POST' });
      const result: ScanResult = await res.json();

      const newEvents: ScanEvent[] = [];
      const timestamp = new Date().toISOString().slice(0, 19).replace('T', ' ');

      if (result.added > 0) {
        newEvents.push({
          id: `added-${Date.now()}`,
          path: watchPath,
          status: 'Added',
          message: `${result.added} new ${entityType.toLowerCase()} found`,
          timestamp,
        });
      }

      if (result.updated > 0) {
        newEvents.push({
          id: `updated-${Date.now()}`,
          path: watchPath,
          status: 'Updated',
          message: `${result.updated} ${entityType.toLowerCase()} updated`,
          timestamp,
        });
      }

      if (result.removed > 0) {
        newEvents.push({
          id: `removed-${Date.now()}`,
          path: watchPath,
          status: 'Removed',
          message: `${result.removed} ${entityType.toLowerCase()} removed`,
          timestamp,
        });
      }

      if (result.errors && result.errors.length > 0) {
        result.errors.forEach((error, i) => {
          newEvents.push({
            id: `error-${Date.now()}-${i}`,
            path: watchPath,
            status: 'Error',
            message: String(error),
            timestamp,
          });
        });
      }

      if (newEvents.length === 0) {
        newEvents.push({
          id: `idle-${Date.now()}`,
          path: watchPath,
          status: 'Idle',
          message: 'No changes detected',
          timestamp,
        });
      }

      setEvents(prev => [...newEvents, ...prev.filter(e => e.status !== 'Scanning').slice(0, 9)]);
    } catch (err: any) {
      setEvents(prev => [{
        id: `error-${Date.now()}`,
        path: watchPath,
        status: 'Error',
        message: err.message || 'Scan failed',
        timestamp: new Date().toISOString().slice(0, 19).replace('T', ' '),
      }, ...prev.filter(e => e.status !== 'Scanning').slice(0, 9)]);
    } finally {
      setIsScanning(false);
    }
  }, [entityType, watchPath]);

  // Execute scan once on initial load
  useEffect(() => {
    // Only add one initial state event
    setEvents([{
      id: 'initial',
      path: watchPath,
      status: 'Idle',
      message: 'Ready to scan',
      timestamp: new Date().toISOString().slice(0, 19).replace('T', ' '),
    }]);
  }, [watchPath]);

  const clearEvents = () => {
    setEvents([]);
  };

  const getStatusIcon = (status: ScanEvent['status']) => {
    switch (status) {
      case 'Scanning': return <span className="material-symbols-outlined text-primary text-[16px] animate-spin">sync</span>;
      case 'Error': return <span className="material-symbols-outlined text-red-500 text-[16px]">error</span>;
      case 'Added': return <span className="material-symbols-outlined text-green-500 text-[16px]">add_circle</span>;
      case 'Updated': return <span className="material-symbols-outlined text-blue-500 text-[16px]">update</span>;
      case 'Removed': return <span className="material-symbols-outlined text-orange-500 text-[16px]">remove_circle</span>;
      default: return <span className="material-symbols-outlined text-gray-500 text-[16px]">check_circle</span>;
    }
  };

  return (
    <aside className="w-80 bg-surface border-l border-border flex flex-col shrink-0 z-10">
      <div className="h-14 flex items-center justify-between px-4 border-b border-border bg-surface/50">
        <h3 className="font-semibold text-gray-200 text-sm flex items-center gap-2">
          <span className="material-symbols-outlined text-gray-400 text-[18px]">radar</span>
          {title}
        </h3>
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
          <span className={`w-1.5 h-1.5 rounded-full ${isScanning ? 'bg-primary animate-pulse' : 'bg-emerald-500'}`}></span>
          <span className={`text-[10px] font-bold uppercase ${isScanning ? 'text-primary' : 'text-emerald-500'}`}>
            {isScanning ? 'Scanning' : 'Ready'}
          </span>
        </div>
      </div>

      <div className="p-4 border-b border-border">
        <div className="text-[10px] font-bold text-gray-500 mb-2 uppercase tracking-wider">Watching Folder</div>
        <div className="flex items-center gap-2 text-gray-300 bg-black/20 p-2 rounded border border-border text-xs font-mono break-all cursor-pointer hover:border-primary/50 transition-colors">
          <span className="material-symbols-outlined text-[16px] text-primary">folder_open</span>
          {watchPath}
        </div>
        <button
          onClick={runScan}
          disabled={isScanning}
          className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 rounded bg-primary/10 border border-primary/20 text-primary text-xs font-medium hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <span className={`material-symbols-outlined text-[16px] ${isScanning ? 'animate-spin' : ''}`}>
            {isScanning ? 'sync' : 'refresh'}
          </span>
          {isScanning ? 'Scanning...' : 'Scan Now'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Recent Events</span>
          <button onClick={clearEvents} className="text-[10px] text-gray-500 hover:text-white">Clear</button>
        </div>

        <div className="space-y-3">
          {events.length === 0 ? (
            <div className="text-center text-gray-500 text-xs py-4">
              No recent events
            </div>
          ) : (
            events.map((event) => (
              <div key={event.id} className={`relative p-3 rounded-lg border text-xs ${event.status === 'Error' ? 'bg-red-500/5 border-red-500/20' : 'bg-black/20 border-border'}`}>
                <div className="flex gap-2 items-start">
                  {getStatusIcon(event.status)}

                  <div className="flex-1 min-w-0">
                    <p className="text-gray-200 font-mono truncate">{event.path.split('/').pop()}</p>
                    {event.message && <p className={`mt-1 ${event.status === 'Error' ? 'text-red-400' : 'text-gray-400'}`}>{event.message}</p>}
                    <p className="text-[10px] text-gray-600 mt-2">{event.timestamp}</p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </aside>
  );
};

export default ScannerPanel;
