import React, { useState, useEffect } from 'react';
import { Zap, Settings, Play, Square, RefreshCw, FileText } from 'lucide-react';
import { getEffectiveApiBaseUrl } from '../lib/api';

interface HeartbeatConfig {
  enabled: boolean;
  every: number;
  target: string;
  model?: string;
  max_tokens: number;
  temperature: number;
  dry_run: boolean;
  curiosity_enabled: boolean;
  curiosity_threshold: number;
  curiosity_cooldown_seconds: number;
  curiosity_post_enabled: boolean;
  curiosity_post_submolt: string;
}

interface HeartbeatPanelProps {
  threadId: string;
}

export const HeartbeatPanel: React.FC<HeartbeatPanelProps> = ({ threadId }) => {
  const defaultConfig: HeartbeatConfig = {
    enabled: true,
    every: 1800,
    target: 'none',
    model: '',
    max_tokens: 500,
    temperature: 0.7,
    dry_run: false,
    curiosity_enabled: true,
    curiosity_threshold: 0.42,
    curiosity_cooldown_seconds: 7200,
    curiosity_post_enabled: true,
    curiosity_post_submolt: 'reflections',
  };

  const [config, setConfig] = useState<HeartbeatConfig | null>(null);
  const [heartbeatMd, setHeartbeatMd] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [lastRun, setLastRun] = useState<string | null>(null);
  const [schedulerRunning, setSchedulerRunning] = useState(false);
  const [showMdEditor, setShowMdEditor] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Use dynamic API base URL for external access
  const API_BASE = `${getEffectiveApiBaseUrl()}/api`;

  useEffect(() => {
    loadHeartbeatConfig();
    loadHeartbeatMd();
    checkSchedulerStatus();
  }, [threadId]);

  const normalizeConfig = (raw: any): HeartbeatConfig => {
    const merged = { ...defaultConfig, ...(raw || {}) };
    return {
      ...merged,
      curiosity_threshold: Math.max(0.1, Math.min(0.95, Number(merged.curiosity_threshold) || defaultConfig.curiosity_threshold)),
      curiosity_cooldown_seconds: Math.max(900, Number(merged.curiosity_cooldown_seconds) || defaultConfig.curiosity_cooldown_seconds),
    };
  };

  const loadHeartbeatConfig = async () => {
    try {
      const response = await fetch(`${API_BASE}/threads/${threadId}/heartbeat/config`);
      if (response.ok) {
        const data = await response.json();
        setConfig(normalizeConfig(data.config));
        if (data.last_run) {
          setLastRun(new Date(data.last_run * 1000).toLocaleString());
        }
      }
    } catch (err) {
      console.error('Failed to load heartbeat config:', err);
    }
  };

  const loadHeartbeatMd = async () => {
    try {
      const response = await fetch(`${API_BASE}/heartbeat/heartbeat.md`);
      if (response.ok) {
        const data = await response.json();
        setHeartbeatMd(data.content || '');
      }
    } catch (err) {
      console.error('Failed to load HEARTBEAT.md:', err);
    }
  };

  const checkSchedulerStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/heartbeat/status`);
      if (response.ok) {
        const data = await response.json();
        setSchedulerRunning(data.running);
      }
    } catch (err) {
      console.error('Failed to check scheduler status:', err);
    }
  };

  const handleStartScheduler = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${API_BASE}/heartbeat/start`, { method: 'POST' });
      if (response.ok) {
        setSchedulerRunning(true);
        setSuccessMessage('Heartbeat scheduler started');
      }
    } catch (err) {
      setError('Failed to start scheduler');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStopScheduler = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${API_BASE}/heartbeat/stop`, { method: 'POST' });
      if (response.ok) {
        setSchedulerRunning(false);
        setSuccessMessage('Heartbeat scheduler stopped');
      }
    } catch (err) {
      setError('Failed to stop scheduler');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRunNow = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${API_BASE}/threads/${threadId}/heartbeat/run-now`, {
        method: 'POST',
      });
      if (response.ok) {
        const data = await response.json();
        setLastRun(new Date(data.timestamp * 1000).toLocaleString());
        setSuccessMessage(`Heartbeat completed: ${data.decision_summary}`);
      }
    } catch (err) {
      setError('Failed to run heartbeat');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateConfig = async (newConfig: HeartbeatConfig) => {
    try {
      setIsLoading(true);
      const response = await fetch(`${API_BASE}/threads/${threadId}/heartbeat/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig),
      });
      if (response.ok) {
        const data = await response.json();
        setConfig(normalizeConfig(data.config));
        setSuccessMessage('Heartbeat config updated');
      }
    } catch (err) {
      setError('Failed to update config');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveHeartbeatMd = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${API_BASE}/heartbeat/heartbeat.md`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: heartbeatMd }),
      });
      if (response.ok) {
        setSuccessMessage('HEARTBEAT.md saved');
        setShowMdEditor(false);
      }
    } catch (err) {
      setError('Failed to save HEARTBEAT.md');
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfigChange = (field: keyof HeartbeatConfig, value: any) => {
    if (config) {
      const newConfig = { ...config, [field]: value };
      setConfig(newConfig);
    }
  };

  const formatInterval = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    return `${Math.floor(seconds / 3600)}h`;
  };

  return (
    <div className="p-4 space-y-4 bg-slate-50 rounded-lg">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
          <Zap className="w-5 h-5 text-amber-500" />
          Heartbeat System
        </h2>
        <div className="flex gap-2">
          {schedulerRunning ? (
            <button
              onClick={handleStopScheduler}
              disabled={isLoading}
              className="px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600 disabled:opacity-50"
            >
              <Square className="w-4 h-4 inline mr-1" />
              Stop
            </button>
          ) : (
            <button
              onClick={handleStartScheduler}
              disabled={isLoading}
              className="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600 disabled:opacity-50"
            >
              <Play className="w-4 h-4 inline mr-1" />
              Start
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="p-2 bg-red-100 text-red-700 text-sm rounded">
          {error}
          <button onClick={() => setError(null)} className="float-right">✕</button>
        </div>
      )}

      {successMessage && (
        <div className="p-2 bg-green-100 text-green-700 text-sm rounded">
          {successMessage}
          <button onClick={() => setSuccessMessage(null)} className="float-right">✕</button>
        </div>
      )}

      {/* Status */}
      <div className="p-3 bg-white rounded border border-slate-200">
        <div className="text-sm text-slate-600">
          <div>Status: <span className={`font-bold ${schedulerRunning ? 'text-green-600' : 'text-slate-600'}`}>
            {schedulerRunning ? '🟢 Running' : '⚪ Stopped'}
          </span></div>
          {lastRun && <div>Last Run: {lastRun}</div>}
        </div>
      </div>

      {/* Config */}
      {config && (
        <div className="space-y-3 p-3 bg-white rounded border border-slate-200">
          <h3 className="font-semibold text-slate-700 flex items-center gap-2">
            <Settings className="w-4 h-4" />
            Configuration
          </h3>

          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={config.enabled}
                onChange={(e) => handleConfigChange('enabled', e.target.checked)}
                className="w-4 h-4"
              />
              <span>Enabled</span>
            </label>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-slate-600">Interval</label>
                <select
                  value={config.every}
                  onChange={(e) => handleConfigChange('every', parseInt(e.target.value))}
                  className="w-full p-1 text-sm border rounded"
                >
                  <option value={300}>5 minutes</option>
                  <option value={900}>15 minutes</option>
                  <option value={1800}>30 minutes</option>
                  <option value={3600}>1 hour</option>
                  <option value={14400}>4 hours</option>
                  <option value={86400}>1 day</option>
                </select>
              </div>

              <div>
                <label className="block text-xs text-slate-600">Target</label>
                <select
                  value={config.target}
                  onChange={(e) => handleConfigChange('target', e.target.value)}
                  className="w-full p-1 text-sm border rounded"
                >
                  <option value="none">Silent (none)</option>
                  <option value="last">Last Channel</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-slate-600">Max Tokens</label>
                <input
                  type="number"
                  value={config.max_tokens}
                  onChange={(e) => handleConfigChange('max_tokens', parseInt(e.target.value))}
                  className="w-full p-1 text-sm border rounded"
                  min="100"
                  max="2000"
                />
              </div>

              <div>
                <label className="block text-xs text-slate-600">Temperature</label>
                <input
                  type="number"
                  value={config.temperature}
                  onChange={(e) => handleConfigChange('temperature', parseFloat(e.target.value))}
                  className="w-full p-1 text-sm border rounded"
                  min="0"
                  max="1"
                  step="0.1"
                />
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={config.dry_run}
                onChange={(e) => handleConfigChange('dry_run', e.target.checked)}
                className="w-4 h-4"
              />
              <span>Dry Run (simulate without executing)</span>
            </label>

            <div className="pt-2 border-t border-slate-200">
              <div className="text-sm font-semibold text-slate-700 mb-2">Curiosity Learning</div>

              <label className="flex items-center gap-2 text-sm mb-2">
                <input
                  type="checkbox"
                  checked={config.curiosity_enabled}
                  onChange={(e) => handleConfigChange('curiosity_enabled', e.target.checked)}
                  className="w-4 h-4"
                />
                <span>Enable curiosity pulse</span>
              </label>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-600">Trigger Threshold</label>
                  <input
                    type="number"
                    value={config.curiosity_threshold}
                    onChange={(e) => handleConfigChange('curiosity_threshold', parseFloat(e.target.value))}
                    className="w-full p-1 text-sm border rounded"
                    min="0.1"
                    max="0.95"
                    step="0.05"
                  />
                </div>

                <div>
                  <label className="block text-xs text-slate-600">Cooldown</label>
                  <select
                    value={config.curiosity_cooldown_seconds}
                    onChange={(e) => handleConfigChange('curiosity_cooldown_seconds', parseInt(e.target.value))}
                    className="w-full p-1 text-sm border rounded"
                  >
                    <option value={900}>15 minutes</option>
                    <option value={1800}>30 minutes</option>
                    <option value={3600}>1 hour</option>
                    <option value={7200}>2 hours</option>
                    <option value={14400}>4 hours</option>
                    <option value={28800}>8 hours</option>
                  </select>
                </div>
              </div>

              <label className="flex items-center gap-2 text-sm mt-2">
                <input
                  type="checkbox"
                  checked={config.curiosity_post_enabled}
                  onChange={(e) => handleConfigChange('curiosity_post_enabled', e.target.checked)}
                  className="w-4 h-4"
                />
                <span>Post curiosity notes to Moltbook</span>
              </label>

              <div className="mt-2">
                <label className="block text-xs text-slate-600">Curiosity Submolt</label>
                <input
                  type="text"
                  value={config.curiosity_post_submolt}
                  onChange={(e) => handleConfigChange('curiosity_post_submolt', e.target.value)}
                  className="w-full p-1 text-sm border rounded"
                  placeholder="reflections"
                />
              </div>
            </div>

            <button
              onClick={() => handleUpdateConfig(config)}
              disabled={isLoading}
              className="w-full px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:opacity-50"
            >
              <RefreshCw className="w-4 h-4 inline mr-1" />
              Save Config
            </button>
          </div>
        </div>
      )}

      {/* HEARTBEAT.md Editor */}
      <div className="p-3 bg-white rounded border border-slate-200">
        <button
          onClick={() => setShowMdEditor(!showMdEditor)}
          className="w-full flex items-center gap-2 font-semibold text-slate-700 hover:text-slate-900"
        >
          <FileText className="w-4 h-4" />
          HEARTBEAT.md Instructions
        </button>

        {showMdEditor && (
          <div className="mt-3 space-y-2">
            <textarea
              value={heartbeatMd}
              onChange={(e) => setHeartbeatMd(e.target.value)}
              placeholder="## Checklist&#10;- Check email&#10;&#10;## Rules&#10;If no urgent items → reply HEARTBEAT_OK only."
              className="w-full h-40 p-2 text-sm border rounded font-mono resize-none"
            />
            <div className="flex gap-2">
              <button
                onClick={handleSaveHeartbeatMd}
                disabled={isLoading}
                className="flex-1 px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600 disabled:opacity-50"
              >
                Save
              </button>
              <button
                onClick={() => setShowMdEditor(false)}
                className="flex-1 px-3 py-1 bg-slate-300 text-slate-800 rounded text-sm hover:bg-slate-400"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Manual Trigger */}
      <button
        onClick={handleRunNow}
        disabled={isLoading}
        className="w-full px-4 py-2 bg-amber-500 text-white rounded font-semibold hover:bg-amber-600 disabled:opacity-50"
      >
        <RefreshCw className="w-4 h-4 inline mr-2" />
        Run Heartbeat Now
      </button>
    </div>
  );
};

export default HeartbeatPanel;
