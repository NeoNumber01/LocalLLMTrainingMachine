import React, { useState, useEffect } from 'react';
import { fetchSettings, updateSettings } from '../lib/api';

interface Settings {
  watchFolders: {
    models: string;
    datasets: string;
    adapters: string;
  };
  compute: {
    maxSimultaneousRuns: number;
    gpuStrategy: string;
  };
  notifications: {
    runCompletion: boolean;
    resourceAlerts: boolean;
  };
  storage: {
    checkpointRetention: number;  // 0 = keep all, N = keep last N
  };
}

const Settings: React.FC = () => {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchSettings()
      .then(setSettings)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleUpdate = (section: string, key: string, value: any) => {
    if (!settings) return;
    setSettings(prev => prev ? {
      ...prev,
      [section]: {
        ...prev[section as keyof Settings],
        [key]: value,
      }
    } : null);
    setSaved(false);
  };

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      await updateSettings(settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
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
    <div className="flex h-full p-6 lg:p-8 overflow-y-auto">
      <div className="max-w-4xl mx-auto w-full space-y-8">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <button
            onClick={handleSave}
            disabled={saving}
            className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${saved
              ? 'bg-success text-white'
              : 'bg-primary hover:bg-blue-600 text-white'
              } disabled:opacity-50`}
          >
            <span className="material-symbols-outlined text-[18px]">
              {saved ? 'check' : saving ? 'hourglass_empty' : 'save'}
            </span>
            {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>

        {/* Watch Folders */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-white border-b border-border pb-2">Watch Folders (Drop-in)</h2>
          <div className="bg-surface border border-border rounded-xl overflow-hidden">
            <div className="p-4 flex items-center justify-between border-b border-border">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-gray-400">folder_open</span>
                <div>
                  <div className="text-sm font-medium text-white">Models Directory</div>
                  <input
                    className="text-xs text-gray-500 font-mono bg-transparent border-none focus:outline-none w-64"
                    value={settings?.watchFolders?.models || ''}
                    onChange={(e) => handleUpdate('watchFolders', 'models', e.target.value)}
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                <span className="text-xs text-emerald-500 font-bold uppercase">Active</span>
              </div>
            </div>
            <div className="p-4 flex items-center justify-between border-b border-border">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-gray-400">database</span>
                <div>
                  <div className="text-sm font-medium text-white">Datasets Directory</div>
                  <input
                    className="text-xs text-gray-500 font-mono bg-transparent border-none focus:outline-none w-64"
                    value={settings?.watchFolders?.datasets || ''}
                    onChange={(e) => handleUpdate('watchFolders', 'datasets', e.target.value)}
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                <span className="text-xs text-emerald-500 font-bold uppercase">Active</span>
              </div>
            </div>
            <div className="p-4 flex items-center justify-between border-b border-border">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-gray-400">extension</span>
                <div>
                  <div className="text-sm font-medium text-white">Adapters Directory</div>
                  <input
                    className="text-xs text-gray-500 font-mono bg-transparent border-none focus:outline-none w-64"
                    value={settings?.watchFolders?.adapters || ''}
                    onChange={(e) => handleUpdate('watchFolders', 'adapters', e.target.value)}
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                <span className="text-xs text-emerald-500 font-bold uppercase">Active</span>
              </div>
            </div>
          </div>
        </section>

        {/* Compute Resources */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-white border-b border-border pb-2">Compute Resources</h2>
          <div className="bg-surface border border-border rounded-xl p-6 space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="font-bold text-white">Max Simultaneous Runs</h3>
                <p className="text-xs text-gray-500">Limit concurrent training jobs to prevent OOM.</p>
              </div>
              <input
                type="number"
                className="bg-black/20 border border-border rounded w-20 px-2 py-1 text-white text-right focus:border-primary focus:outline-none"
                value={settings?.compute?.maxSimultaneousRuns || 1}
                onChange={(e) => handleUpdate('compute', 'maxSimultaneousRuns', parseInt(e.target.value))}
              />
            </div>

            <div className="flex justify-between items-center pt-4 border-t border-border">
              <div>
                <h3 className="font-bold text-white">GPU Strategy</h3>
                <p className="text-xs text-gray-500">Default strategy for multi-gpu systems.</p>
              </div>
              <select
                className="bg-black/20 border border-border rounded px-2 py-1 text-white text-sm focus:border-primary focus:outline-none"
                value={settings?.compute?.gpuStrategy || 'DDP'}
                onChange={(e) => handleUpdate('compute', 'gpuStrategy', e.target.value)}
              >
                <option value="DDP">DDP (Distributed Data Parallel)</option>
                <option value="FSDP">FSDP (Fully Sharded Data Parallel)</option>
                <option value="DeepSpeed">DeepSpeed</option>
              </select>
            </div>
          </div>
        </section>

        {/* Notifications */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-white border-b border-border pb-2">Notifications</h2>
          <div className="bg-surface border border-border rounded-xl p-6 space-y-4">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-gray-400">notifications</span>
                <div>
                  <h3 className="font-bold text-white">Run Completion Alerts</h3>
                  <p className="text-xs text-gray-500">Get notified when training finishes or fails.</p>
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings?.notifications?.runCompletion ?? true}
                  onChange={(e) => handleUpdate('notifications', 'runCompletion', e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
              </label>
            </div>

            <div className="flex justify-between items-center pt-4 border-t border-border">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-gray-400">warning</span>
                <div>
                  <h3 className="font-bold text-white">System Resource Alerts</h3>
                  <p className="text-xs text-gray-500">Alert on GPU OOM or High Disk Usage.</p>
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings?.notifications?.resourceAlerts ?? true}
                  onChange={(e) => handleUpdate('notifications', 'resourceAlerts', e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
              </label>
            </div>
          </div>
        </section>

        {/* Storage Policy */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-white border-b border-border pb-2">Storage & Retention</h2>
          <div className="bg-surface border border-border rounded-xl p-6 space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="font-bold text-white">Checkpoint Retention</h3>
                <p className="text-xs text-gray-500">Number of checkpoints to keep (0 = keep all).</p>
              </div>
              <input
                type="number"
                min="0"
                className="bg-black/20 border border-border rounded w-20 px-2 py-1 text-white text-right focus:border-primary focus:outline-none"
                value={settings?.storage?.checkpointRetention ?? 3}
                onChange={(e) => handleUpdate('storage', 'checkpointRetention', parseInt(e.target.value) || 0)}
              />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default Settings;
