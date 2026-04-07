import { useEffect, useState, useCallback } from 'react'

const API_BASE = (window as any).__CRT_API_BASE__ || ''
const REFRESH_INTERVAL_MS = 30_000

/* ── Helpers ──────────────────────────────────────────────── */

function pct(v: number | null | undefined, decimals = 1): string {
  if (v == null) return '\u2014'
  return `${(v * 100).toFixed(decimals)}%`
}
function num(v: number | null | undefined): string {
  if (v == null) return '\u2014'
  return v.toLocaleString()
}
function ms(v: number | null | undefined): string {
  if (v == null) return '\u2014'
  if (v >= 1000) return `${(v / 1000).toFixed(1)}s`
  return `${Math.round(v)}ms`
}

function relTime(ts: number): string {
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return `${Math.round(diff)}s ago`
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

/* ── Shared UI components (matches TelemetryPage) ─────────── */

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded border border-white/10 bg-white/5 p-4">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-white/40">{title}</h3>
      {children}
    </div>
  )
}

function StatRow({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 py-1 border-b border-white/5 last:border-0">
      <span className="text-sm text-white/60">{label}</span>
      <span className="text-sm font-mono text-white/90">
        {value}
        {sub && <span className="ml-1 text-xs text-white/40">{sub}</span>}
      </span>
    </div>
  )
}

function MiniBar({ value, max, color = 'bg-indigo-400' }: { value: number; max: number; color?: string }) {
  const w = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div className="h-1.5 w-full rounded bg-white/10">
      <div className={`h-1.5 rounded ${color}`} style={{ width: `${w}%` }} />
    </div>
  )
}

function StatusBadge({ success }: { success: boolean | null | undefined }) {
  if (success === true) return (
    <span className="inline-block rounded px-1.5 py-0.5 text-[11px] font-mono bg-emerald-500/20 text-emerald-300">
      success
    </span>
  )
  if (success === false) return (
    <span className="inline-block rounded px-1.5 py-0.5 text-[11px] font-mono bg-red-500/20 text-red-300">
      fail
    </span>
  )
  return (
    <span className="inline-block rounded px-1.5 py-0.5 text-[11px] font-mono bg-white/10 text-white/40">
      \u2014
    </span>
  )
}

/* ── Types ────────────────────────────────────────────────── */

type Analytics = {
  total_runs: number
  success_rate: number | null
  avg_iterations: number
  max_iterations: number
  iteration_limit_rate: number
  avg_drifts: number
  total_drifts: number
  verification_rate: number
  tool_error_rate: number
  avg_total_ms: number
  avg_brain_ms: number
  avg_tool_ms: number
  tool_frequency: Record<string, number>
  calibration?: {
    high_confidence_success_rate: number | null
    low_confidence_success_rate: number | null
    samples: number
  }
  error?: string
}

type RecentRun = {
  run_id: string
  timestamp: number
  intent: string
  intent_type: string | null
  total_iterations: number
  hit_iteration_limit: number
  success: number | null
  confidence: number | null
  total_ms: number | null
  brain_ms: number | null
  tool_ms: number | null
  drift_count: number
  unique_tools: number
  tool_errors: number
  alignment_avg: number | null
  step_count: number
}

type ToolUsage = Record<string, number>

type ActivationStats = {
  total_activations: number
  avg_memories_per_query: number
  avg_belief_confidence: number
  contradiction_trigger_rate: number
  error?: string
}

type DeadMemory = {
  memory_id: string
  text: string
  trust: number
}

/* ── Data fetching ────────────────────────────────────────── */

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

/* ── Main Component ───────────────────────────────────────── */

export function RunLogPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null)
  const [recentRuns, setRecentRuns] = useState<RecentRun[]>([])
  const [toolUsage, setToolUsage] = useState<ToolUsage>({})
  const [activationStats, setActivationStats] = useState<ActivationStats | null>(null)
  const [deadMemories, setDeadMemories] = useState<DeadMemory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const load = useCallback(async () => {
    try {
      setError(null)
      const [a, r, t, act, dead] = await Promise.all([
        fetchJson<Analytics>('/api/agent-runs/analytics'),
        fetchJson<RecentRun[]>('/api/agent-runs/recent?limit=50'),
        fetchJson<ToolUsage>('/api/agent-runs/tool-usage'),
        fetchJson<ActivationStats>('/api/agent-runs/activations/stats'),
        fetchJson<DeadMemory[]>('/api/agent-runs/activations/dead-memories'),
      ])
      setAnalytics(a)
      setRecentRuns(r)
      setToolUsage(t)
      setActivationStats(act)
      setDeadMemories(dead)
      setLastRefresh(new Date())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    void load()
  }, [load])

  useEffect(() => {
    if (!autoRefresh) return
    const id = window.setInterval(() => void load(), REFRESH_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [autoRefresh, load])

  // Derived: sorted tool list
  const toolEntries = Object.entries(toolUsage).slice(0, 10)
  const maxToolCount = toolEntries.length > 0 ? toolEntries[0][1] : 1

  return (
    <div className="flex h-full flex-col overflow-y-auto text-white">
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-white/10 bg-black/40 px-5 py-3">
        <div>
          <h2 className="text-base font-semibold text-white/90">Agent Runs</h2>
          {lastRefresh && (
            <p className="text-xs text-white/40">
              Refreshed {relTime(lastRefresh.getTime() / 1000)}
              {autoRefresh && ' \u00b7 auto-refresh 30s'}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`rounded px-2 py-1 text-xs font-mono transition ${
              autoRefresh
                ? 'bg-emerald-500/30 text-emerald-200'
                : 'bg-white/5 text-white/50 hover:bg-white/10'
            }`}
          >
            {autoRefresh ? 'Auto' : 'Paused'}
          </button>
          <button
            onClick={() => { setLoading(true); void load() }}
            className="rounded bg-white/5 px-2 py-1 text-xs text-white/50 hover:bg-white/10"
          >
            \u21bb
          </button>
        </div>
      </div>

      {loading && !analytics && (
        <div className="flex flex-1 items-center justify-center text-white/40">Loading\u2026</div>
      )}
      {error && (
        <div className="mx-5 mt-4 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      {analytics && (
        <div className="space-y-4 p-5">

          {/* ── Top Stats Row (4 cols) ──────────────────────── */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">

            {/* Total Runs + Success */}
            <Card title="Runs & Success">
              <div className="flex items-end gap-3 mb-3">
                <span className="text-3xl font-bold tabular-nums text-indigo-300">
                  {num(analytics.total_runs)}
                </span>
                <span className="mb-1 text-xs text-white/40">total runs</span>
              </div>
              <StatRow label="Success rate" value={pct(analytics.success_rate)} />
              <StatRow label="Verification rate" value={pct(analytics.verification_rate)} />
              <StatRow label="Tool error rate" value={pct(analytics.tool_error_rate)} />
              {analytics.calibration && (
                <>
                  <StatRow
                    label="High-conf success"
                    value={pct(analytics.calibration.high_confidence_success_rate)}
                    sub={`(${analytics.calibration.samples} samples)`}
                  />
                  <StatRow
                    label="Low-conf success"
                    value={pct(analytics.calibration.low_confidence_success_rate)}
                  />
                </>
              )}
            </Card>

            {/* Iterations */}
            <Card title="Iterations">
              <div className="flex items-end gap-3 mb-3">
                <span className="text-3xl font-bold tabular-nums text-sky-300">
                  {analytics.avg_iterations}
                </span>
                <span className="mb-1 text-xs text-white/40">avg steps</span>
              </div>
              <StatRow label="Max iterations" value={num(analytics.max_iterations)} />
              <StatRow label="Hit-limit rate" value={pct(analytics.iteration_limit_rate)} />
            </Card>

            {/* Latency */}
            <Card title="Latency">
              <div className="flex items-end gap-3 mb-3">
                <span className="text-3xl font-bold tabular-nums text-amber-300">
                  {ms(analytics.avg_total_ms)}
                </span>
                <span className="mb-1 text-xs text-white/40">avg total</span>
              </div>
              <StatRow label="Brain (LLM)" value={ms(analytics.avg_brain_ms)} />
              <StatRow label="Tools" value={ms(analytics.avg_tool_ms)} />
            </Card>

            {/* Drift */}
            <Card title="Drift">
              <div className="flex items-end gap-3 mb-3">
                <span className="text-3xl font-bold tabular-nums text-amber-300">
                  {analytics.avg_drifts}
                </span>
                <span className="mb-1 text-xs text-white/40">avg / run</span>
              </div>
              <StatRow label="Total drifts" value={num(analytics.total_drifts)} />
              <StatRow
                label="Drift rate"
                value={analytics.total_runs > 0
                  ? pct(analytics.total_drifts / analytics.total_runs > 0 ? analytics.total_drifts / analytics.total_runs : 0)
                  : '\u2014'}
                sub="runs with drift"
              />
            </Card>
          </div>

          {/* ── Middle Section (2 cols) ────────────────────── */}
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">

            {/* Recent Runs Table */}
            <Card title={`Recent Runs (${recentRuns.length})`}>
              {recentRuns.length === 0 ? (
                <p className="text-sm text-white/30">No runs recorded yet.</p>
              ) : (
                <div className="max-h-[420px] overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-white/10 text-white/40">
                        {['Time', 'Intent', 'Steps', 'Status', 'Conf', 'Latency'].map(h => (
                          <th key={h} className="py-1.5 pr-3 text-left font-normal">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {recentRuns.map((run) => (
                        <tr key={run.run_id} className="border-b border-white/5 hover:bg-white/5">
                          <td className="py-1.5 pr-3 font-mono text-white/40 whitespace-nowrap">
                            {relTime(run.timestamp)}
                          </td>
                          <td className="py-1.5 pr-3 text-white/60 max-w-[180px] truncate" title={run.intent}>
                            {run.intent?.slice(0, 50) || '\u2014'}
                          </td>
                          <td className="py-1.5 pr-3 font-mono text-white/70">
                            {run.total_iterations}
                            {run.hit_iteration_limit ? (
                              <span className="ml-1 text-amber-400" title="Hit iteration limit">!</span>
                            ) : null}
                          </td>
                          <td className="py-1.5 pr-3">
                            <StatusBadge success={run.success === 1 ? true : run.success === 0 ? false : null} />
                          </td>
                          <td className="py-1.5 pr-3 font-mono text-white/60">
                            {run.confidence != null ? run.confidence.toFixed(2) : '\u2014'}
                          </td>
                          <td className="py-1.5 font-mono text-white/60 whitespace-nowrap">
                            {ms(run.total_ms)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            {/* Tool Usage */}
            <Card title="Tool Usage (Top 10)">
              {toolEntries.length === 0 ? (
                <p className="text-sm text-white/30">No tool data yet.</p>
              ) : (
                <div className="space-y-1.5">
                  {toolEntries.map(([tool, count]) => (
                    <div key={tool} className="flex items-center gap-2">
                      <span className="w-36 truncate text-xs text-white/60 font-mono" title={tool}>
                        {tool}
                      </span>
                      <MiniBar value={count} max={maxToolCount} color="bg-sky-400" />
                      <span className="w-8 text-right text-xs font-mono text-white/60">{count}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* ── Bottom Section (2 cols) ────────────────────── */}
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">

            {/* Activation Stats */}
            <Card title="Activation Stats">
              {!activationStats || activationStats.error ? (
                <p className="text-sm text-white/30">
                  {activationStats?.error || 'No activation data.'}
                </p>
              ) : (
                <div className="space-y-1">
                  <StatRow
                    label="Total activations"
                    value={num(activationStats.total_activations)}
                  />
                  <StatRow
                    label="Avg memories / query"
                    value={String(activationStats.avg_memories_per_query)}
                  />
                  <StatRow
                    label="Avg belief confidence"
                    value={activationStats.avg_belief_confidence.toFixed(3)}
                  />
                  <StatRow
                    label="Contradiction trigger rate"
                    value={pct(activationStats.contradiction_trigger_rate)}
                  />

                  {/* Visual bar for contradiction rate */}
                  <div className="pt-2">
                    <div className="mb-1 flex justify-between text-xs text-white/40">
                      <span>Contradiction triggers</span>
                      <span>{pct(activationStats.contradiction_trigger_rate)}</span>
                    </div>
                    <div className="h-2 rounded bg-white/10">
                      <div
                        className="h-2 rounded bg-amber-500"
                        style={{ width: `${Math.min(100, activationStats.contradiction_trigger_rate * 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </Card>

            {/* Dead Memories */}
            <Card title={`Dead Memories (${deadMemories.length})`}>
              {deadMemories.length === 0 ? (
                <p className="text-sm text-white/30">No dead memories found.</p>
              ) : (
                <div className="max-h-[300px] overflow-y-auto space-y-1.5">
                  {deadMemories.slice(0, 20).map((mem) => (
                    <div
                      key={mem.memory_id}
                      className="rounded border border-white/5 bg-white/[0.02] px-3 py-2"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-xs text-white/50 leading-relaxed line-clamp-2">
                          {mem.text}
                        </span>
                        <span className="flex-none rounded bg-red-500/15 px-1.5 py-0.5 text-[10px] font-mono text-red-300">
                          {mem.trust.toFixed(2)}
                        </span>
                      </div>
                      <div className="mt-1 text-[10px] text-white/25 font-mono truncate">
                        {mem.memory_id}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

        </div>
      )}
    </div>
  )
}
