import { useEffect, useState, useCallback } from 'react'
import {
  getTelemetrySummary,
  type TelemetrySummary,
  type TelemetryRecentEvent,
} from '../lib/api'

const REFRESH_INTERVAL_MS = 30_000

type HoursOption = 1 | 6 | 24 | 72 | 168

function pct(v: number | null | undefined, decimals = 1): string {
  if (v == null) return '—'
  return `${(v * 100).toFixed(decimals)}%`
}
function num(v: number | null | undefined): string {
  if (v == null) return '—'
  return v.toLocaleString()
}
function fmt3(v: number | null | undefined): string {
  if (v == null) return '—'
  return v.toFixed(3)
}

function relTime(ts: number): string {
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return `${Math.round(diff)}s ago`
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  return `${Math.round(diff / 3600)}h ago`
}

function EventBadge({ type }: { type: string }) {
  const colours: Record<string, string> = {
    gate_pass: 'bg-emerald-500/20 text-emerald-300',
    gate_fail: 'bg-red-500/20 text-red-300',
    feedback_up: 'bg-sky-500/20 text-sky-300',
    feedback_down: 'bg-orange-500/20 text-orange-300',
    reflection_queued: 'bg-purple-500/20 text-purple-300',
    contradiction_resolved: 'bg-teal-500/20 text-teal-300',
    trust_delta_batch: 'bg-indigo-500/20 text-indigo-300',
  }
  const cls = colours[type] ?? 'bg-white/10 text-white/60'
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-mono ${cls}`}>
      {type}
    </span>
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

export function TelemetryPage({ threadId }: { threadId?: string }) {
  const [data, setData] = useState<TelemetrySummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hours, setHours] = useState<HoursOption>(24)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)

  const load = useCallback(async () => {
    try {
      setError(null)
      const result = await getTelemetrySummary({ hours, threadId })
      setData(result)
      setLastRefresh(new Date())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [hours, threadId])

  useEffect(() => {
    setLoading(true)
    void load()
    const id = window.setInterval(() => void load(), REFRESH_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [load])

  const hoursOpts: HoursOption[] = [1, 6, 24, 72, 168]

  // Derive EIS from gate performance + feedback
  const eis = (() => {
    if (!data) return null
    const gp = data.gate_performance.pass_rate
    const fb = data.feedback.thumbs_up_rate
    if (gp == null && fb == null) return null
    const parts: number[] = []
    if (gp != null) parts.push(gp * 0.5)
    if (fb != null) parts.push(fb * 0.5)
    return parts.reduce((a, b) => a + b, 0) / parts.length * 2
  })()

  // Sort events by count desc for the event count table
  const eventRows = data
    ? Object.entries(data.event_counts)
        .sort(([, a], [, b]) => b - a)
    : []
  const maxEventCount = eventRows.length > 0 ? eventRows[0][1] : 1

  return (
    <div className="flex h-full flex-col overflow-y-auto text-white">
      {/* Header */}
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-white/10 bg-black/40 px-5 py-3">
        <div>
          <h2 className="text-base font-semibold text-white/90">Telemetry</h2>
          {lastRefresh && (
            <p className="text-xs text-white/40">
              Refreshed {relTime(lastRefresh.getTime() / 1000)} · auto-refresh 30s
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/40">Window:</span>
          {hoursOpts.map((h) => (
            <button
              key={h}
              onClick={() => setHours(h)}
              className={`rounded px-2 py-1 text-xs font-mono transition ${
                hours === h
                  ? 'bg-indigo-500/40 text-indigo-200'
                  : 'bg-white/5 text-white/50 hover:bg-white/10'
              }`}
            >
              {h < 24 ? `${h}h` : `${h / 24}d`}
            </button>
          ))}
          <button
            onClick={() => { setLoading(true); void load() }}
            className="rounded bg-white/5 px-2 py-1 text-xs text-white/50 hover:bg-white/10"
          >
            ↻
          </button>
        </div>
      </div>

      {loading && !data && (
        <div className="flex flex-1 items-center justify-center text-white/40">Loading…</div>
      )}
      {error && (
        <div className="mx-5 mt-4 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      {data && (
        <div className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-2 xl:grid-cols-3">

          {/* ── Epistemic Improvement Score ──────────────────────────── */}
          <Card title="Epistemic Improvement Score">
            <div className="flex items-end gap-3">
              <span className="text-4xl font-bold tabular-nums text-indigo-300">
                {eis != null ? pct(Math.min(eis, 1)) : '—'}
              </span>
              <span className="mb-1 text-xs text-white/40">composite (gate × feedback)</span>
            </div>
            <div className="mt-3 space-y-1">
              <StatRow label="Gate pass rate" value={pct(data.gate_performance.pass_rate)} />
              <StatRow label="Thumbs-up rate" value={pct(data.feedback.thumbs_up_rate)} />
              <StatRow label="High-priority feedback" value={num(data.feedback.high_priority_count)} />
            </div>
          </Card>

          {/* ── Gate Performance ─────────────────────────────────────── */}
          <Card title="Gate Performance">
            <div className="mb-3 flex gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-emerald-300">{num(data.gate_performance.pass_count)}</div>
                <div className="text-xs text-white/40">pass</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-red-300">{num(data.gate_performance.fail_count)}</div>
                <div className="text-xs text-white/40">fail</div>
              </div>
            </div>
            {/* Pass rate bar */}
            {data.gate_performance.pass_rate != null && (
              <div className="mb-3">
                <div className="mb-1 flex justify-between text-xs text-white/40">
                  <span>Pass rate</span><span>{pct(data.gate_performance.pass_rate)}</span>
                </div>
                <div className="h-2 rounded bg-white/10">
                  <div
                    className="h-2 rounded bg-emerald-500"
                    style={{ width: pct(data.gate_performance.pass_rate) }}
                  />
                </div>
              </div>
            )}
            {Object.keys(data.gate_performance.fail_reasons).length > 0 && (
              <div className="space-y-1">
                <div className="text-xs text-white/40 mb-1">Fail reasons</div>
                {Object.entries(data.gate_performance.fail_reasons)
                  .sort(([,a],[,b]) => b - a)
                  .slice(0, 5)
                  .map(([reason, cnt]) => (
                    <div key={reason} className="flex items-center gap-2">
                      <span className="w-32 truncate text-xs text-white/50">{reason}</span>
                      <MiniBar value={cnt} max={data.gate_performance.fail_count || 1} color="bg-red-400" />
                      <span className="w-6 text-right text-xs font-mono text-white/50">{cnt}</span>
                    </div>
                  ))
                }
              </div>
            )}
          </Card>

          {/* ── Feedback Signal ──────────────────────────────────────── */}
          <Card title="Feedback Signal">
            <div className="mb-3 flex gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-sky-300">{num(data.feedback.thumbs_up)}</div>
                <div className="text-xs text-white/40">thumbs up</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-orange-300">{num(data.feedback.thumbs_down)}</div>
                <div className="text-xs text-white/40">thumbs down</div>
              </div>
            </div>
            <StatRow label="Satisfaction rate" value={pct(data.feedback.thumbs_up_rate)} />
            <StatRow label="High-priority events" value={num(data.feedback.high_priority_count)} sub="(severity ≥ 0.67)" />
          </Card>

          {/* ── Learning Queue ───────────────────────────────────────── */}
          <Card title="Learning Queue">
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-white/60">Pending reflections</span>
                  <span className="font-mono text-purple-300">{num(data.learning_queue.pending_reflections)}</span>
                </div>
                <MiniBar value={data.learning_queue.pending_reflections} max={Math.max(data.learning_queue.pending_reflections, 10)} color="bg-purple-400" />
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-white/60">High-priority feedback</span>
                  <span className="font-mono text-orange-300">{num(data.learning_queue.high_priority_feedback)}</span>
                </div>
                <MiniBar value={data.learning_queue.high_priority_feedback} max={Math.max(data.learning_queue.high_priority_feedback, 10)} color="bg-orange-400" />
              </div>
            </div>
          </Card>

          {/* ── Severity Distribution ────────────────────────────────── */}
          <Card title="Severity Distribution">
            {(['low','medium','high'] as const).map((band) => {
              const v = data.severity_distribution[band]
              const total = data.severity_distribution.low + data.severity_distribution.medium + data.severity_distribution.high
              const colours = { low: 'bg-emerald-400', medium: 'bg-yellow-400', high: 'bg-red-400' } as const
              return (
                <div key={band} className="mb-2">
                  <div className="flex justify-between text-xs mb-0.5">
                    <span className="capitalize text-white/50">{band}</span>
                    <span className="font-mono text-white/70">{v} <span className="text-white/30">({total > 0 ? Math.round(v/total*100) : 0}%)</span></span>
                  </div>
                  <MiniBar value={v} max={total || 1} color={colours[band]} />
                </div>
              )
            })}
          </Card>

          {/* ── Event Counts ─────────────────────────────────────────── */}
          <Card title={`Event Counts (${hours < 24 ? hours + 'h' : hours / 24 + 'd'})`}>
            {eventRows.length === 0 ? (
              <p className="text-sm text-white/30">No events in window.</p>
            ) : (
              <div className="space-y-1.5">
                {eventRows.map(([et, cnt]) => (
                  <div key={et} className="flex items-center gap-2">
                    <EventBadge type={et} />
                    <MiniBar value={cnt} max={maxEventCount} />
                    <span className="w-8 text-right text-xs font-mono text-white/60">{cnt}</span>
                    <span className="text-xs text-white/30">{data.event_rate_per_hour[et]}/h</span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* ── Thread Metrics Trend (last 10 rows) ─────────────────── */}
          {data.thread_metrics_trend.length > 0 && (
            <div className="sm:col-span-2 xl:col-span-3">
              <Card title="Thread Metrics Trend (latest 10)">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-white/10 text-white/40">
                        {['Time', 'Thread', 'Turn', 'Contradiction%', 'Gate fail%', 'Trust mean', 'Recovery', 'Open Ctrs'].map(h => (
                          <th key={h} className="py-1.5 pr-4 text-left font-normal">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.thread_metrics_trend.slice(0, 10).map((row, i) => (
                        <tr key={i} className="border-b border-white/5 hover:bg-white/5">
                          <td className="py-1 pr-4 font-mono text-white/40">{relTime(row.ts)}</td>
                          <td className="py-1 pr-4 font-mono text-white/60 max-w-[80px] truncate">{row.thread_id}</td>
                          <td className="py-1 pr-4 font-mono text-white/70">{row.turn_number}</td>
                          <td className="py-1 pr-4 font-mono">{pct(row.contradiction_rate)}</td>
                          <td className="py-1 pr-4 font-mono">{pct(row.gate_fail_rate)}</td>
                          <td className="py-1 pr-4 font-mono">{fmt3(row.trust_mean)}</td>
                          <td className="py-1 pr-4 font-mono">{pct(row.correction_recovery)}</td>
                          <td className="py-1 pr-4 font-mono">{row.open_contradictions}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          )}

          {/* ── Recent Events ────────────────────────────────────────── */}
          {data.recent_events.length > 0 && (
            <div className="sm:col-span-2 xl:col-span-3">
              <Card title="Recent Events">
                <div className="space-y-1">
                  {data.recent_events.map((ev: TelemetryRecentEvent, i) => (
                    <div key={i} className="flex items-center gap-3 rounded px-2 py-1 hover:bg-white/5">
                      <span className="w-16 text-right text-xs font-mono text-white/30">{relTime(ev.ts)}</span>
                      <EventBadge type={ev.event_type} />
                      <span className="text-xs text-white/40 truncate max-w-[120px]">{ev.thread_id || '—'}</span>
                      {ev.severity > 0 && (
                        <span className={`text-xs font-mono ${ev.severity >= 0.67 ? 'text-red-400' : ev.severity >= 0.33 ? 'text-yellow-400' : 'text-white/30'}`}>
                          sev {ev.severity.toFixed(2)}
                        </span>
                      )}
                      {ev.payload && Object.keys(ev.payload).length > 0 && (
                        <span className="truncate text-xs text-white/30 font-mono">
                          {JSON.stringify(ev.payload).slice(0, 60)}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

        </div>
      )}
    </div>
  )
}
