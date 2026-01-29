import React, { useState, useEffect } from 'react';
import { fetchDashboard } from '../lib/api';
import { Status } from '../types';
import { Link } from 'react-router-dom';

const StatCard = ({ title, value, subtext, icon, color }: any) => (
  <div className="bg-surface border border-border rounded-xl p-5 flex flex-col gap-4 relative overflow-hidden group">
    <div className={`absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity ${color}`}>
      <span className="material-symbols-outlined text-[48px]">{icon}</span>
    </div>
    <div className="flex items-center justify-between z-10">
      <h3 className="text-gray-400 text-xs font-bold uppercase tracking-wider">{title}</h3>
    </div>
    <div className="z-10">
      <div className="text-3xl font-mono font-bold text-white">{value}</div>
      <div className="text-xs text-gray-500 mt-1">{subtext}</div>
    </div>
  </div>
);

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<{
    systemHealth: string;
    activeRuns: number;
    queuedRuns: number;
    gpuUsage: string;
    gpuAvailable?: boolean;
    gpuDeviceCount?: number;
    storage: { used: string; free: string };
    recentRuns: any[];
  } | null>(null);

  // Initial load
  useEffect(() => {
    fetchDashboard()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Auto refresh (every 1 second)
  useEffect(() => {
    const interval = setInterval(() => {
      fetchDashboard()
        .then(setData)
        .catch(console.error);
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-error">
        <div className="text-center">
          <p className="text-lg font-semibold">Loading Failed</p>
          <p className="text-sm text-gray-400 mt-1">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-primary rounded-lg text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const runs = data?.recentRuns || [];

  return (
    <div className="flex flex-col h-full overflow-y-auto p-6 lg:p-8">
      <div className="max-w-7xl mx-auto w-full space-y-8">

        {/* Header */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Dashboard Overview</h1>
            <p className="text-gray-400 text-sm mt-1">Real-time system metrics and training status.</p>
          </div>
          <div className="flex gap-2">
            <Link to="/runs/new" className="bg-primary hover:bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px]">add_circle</span>
              New Run
            </Link>
            <Link to="/datasets" className="bg-surface border border-border hover:bg-white/5 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px]">upload_file</span>
              Import Dataset
            </Link>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="System Health"
            value={data?.systemHealth || 'Unknown'}
            subtext="All systems operational"
            icon="memory"
            color="text-green-500"
          />
          <StatCard
            title="Active Runs"
            value={data?.activeRuns || 0}
            subtext={`${data?.queuedRuns || 0} queued`}
            icon="play_circle"
            color="text-primary"
          />
          <StatCard
            title="GPU Usage"
            value={data?.gpuUsage || 'N/A'}
            subtext={(data as any)?.gpuName || 'No GPU detected'}
            icon="speed"
            color="text-warning"
          />
          <StatCard
            title="Storage"
            value={data?.storage?.used || 'N/A'}
            subtext={`${data?.storage?.free || 'N/A'} Free`}
            icon="hard_drive"
            color="text-purple-500"
          />
        </div>

        {/* Recent Runs Table */}
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-border flex justify-between items-center bg-white/5">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-gray-400">list_alt</span>
              Recent Activity
            </h3>
            <Link to="/runs" className="text-xs text-primary hover:text-white transition-colors">View All</Link>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="bg-black/20 text-xs uppercase text-gray-500 font-medium">
              <tr>
                <th className="px-6 py-3">Run Name</th>
                <th className="px-6 py-3">Type</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {runs.map((run: any) => (
                <tr key={run.id} className="hover:bg-white/[0.02] transition-colors cursor-pointer group">
                  <td className="px-6 py-4">
                    <Link to={run.type === 'evaluation' ? `/evaluation/${run.id}` : `/runs/${run.id}`} className="flex flex-col">
                      <span className="text-white font-medium group-hover:text-primary transition-colors">{run.name}</span>
                      <span className="text-xs text-gray-500 font-mono">{run.id}</span>
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-gray-400">{run.type}</td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      {run.status === 'running' && <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>}
                      {run.status === 'success' && <span className="w-2 h-2 rounded-full bg-success"></span>}
                      {run.status === 'failed' && <span className="w-2 h-2 rounded-full bg-error"></span>}
                      {run.status === 'stopped' && <span className="w-2 h-2 rounded-full bg-orange-500"></span>}
                      {run.status === 'queued' && <span className="w-2 h-2 rounded-full bg-gray-500"></span>}
                      <span className={`text-xs font-bold uppercase ${run.status === 'running' ? 'text-primary' :
                        run.status === 'success' ? 'text-success' :
                          run.status === 'failed' ? 'text-error' :
                            run.status === 'stopped' ? 'text-orange-500' : 'text-gray-500'
                        }`}>{run.status}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right font-mono text-gray-400">{run.duration || '-'}</td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-6 py-8 text-center text-gray-500">
                    No runs yet. Create your first run to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
