import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'

const API_BASE = (window as any).__CRT_API_BASE__ || ''

/* ── Layer definitions ───────────────────────────────────── */

type LayerDef = {
  id: string
  name: string
  desc: string
  color: string
  metric: string
  endpoint: string | null
}

const LAYERS: LayerDef[] = [
  { id: 'L1', name: 'Observation', desc: 'Records every orchestrator run', color: '#60a5fa',
    metric: 'total_runs', endpoint: '/api/agent-runs/analytics' },
  { id: 'L2', name: 'Drift Detection', desc: 'Per-step intent alignment scoring', color: '#c9a45c',
    metric: 'drift_rate', endpoint: '/api/agent-runs/analytics' },
  { id: 'L3', name: 'Contradiction', desc: 'Step contradictions + action receipts', color: '#D47058',
    metric: 'total_receipts', endpoint: '/api/action-receipts/summary' },
  { id: 'L4', name: 'Epistemic Routing', desc: 'Learned routing decisions', color: '#34d399',
    metric: 'routing_confidence', endpoint: null },
  { id: 'L5', name: 'Execution Beliefs', desc: 'Self-aware execution patterns', color: '#818cf8',
    metric: 'belief_count', endpoint: null },
  { id: 'L6', name: 'Epistemic Posture', desc: 'Confidence calibration', color: '#f472b6',
    metric: 'posture', endpoint: null },
]

const IMMUNE_AGENTS = [
  { id: 1, name: 'SpeechLeakDetector', desc: 'Blocks belief-speech leakage' },
  { id: 2, name: 'TemplateDetector', desc: 'Catches template collapse' },
  { id: 3, name: 'PrematureResolutionGuard', desc: 'Prevents early contradiction closure' },
  { id: 4, name: 'MemoryCorruptionGuard', desc: 'Protects memory integrity' },
  { id: 5, name: 'GapAuditor', desc: 'Audits belief-speech gap' },
  { id: 6, name: 'ContinuityAuditor', desc: 'Ensures epistemic continuity' },
]

/* ── Types for API responses ─────────────────────────────── */

type AnalyticsData = {
  total_runs?: number
  success_rate?: number | null
  avg_drifts?: number
  total_drifts?: number
  drift_rate?: number
  [key: string]: unknown
}

type ReceiptSummary = {
  total_actions?: number
  verification_pass_rate?: number | null
  [key: string]: unknown
}

type LayerMetrics = {
  L1: { total_runs: number; success_rate: string; status: 'active' | 'inactive' | 'learning' }
  L2: { drift_rate: string; avg_drifts: number; status: 'active' | 'inactive' | 'learning' }
  L3: { total_receipts: number; pass_rate: string; status: 'active' | 'inactive' | 'learning' }
  L4: { status: 'learning' }
  L5: { status: 'learning' }
  L6: { status: 'learning' }
}

/* ── Helpers ──────────────────────────────────────────────── */

function pct(v: number | null | undefined): string {
  if (v == null) return '\u2014'
  return `${(v * 100).toFixed(1)}%`
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

/* ── Sub-components ──────────────────────────────────────── */

function StatusDot({ status, color }: { status: 'active' | 'inactive' | 'learning'; color: string }) {
  if (status === 'active') {
    return (
      <span className="relative flex h-2.5 w-2.5">
        <span
          className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-50"
          style={{ backgroundColor: color }}
        />
        <span
          className="relative inline-flex h-2.5 w-2.5 rounded-full"
          style={{ backgroundColor: color }}
        />
      </span>
    )
  }
  if (status === 'learning') {
    return (
      <span
        className="inline-flex h-2.5 w-2.5 rounded-full animate-pulse"
        style={{ backgroundColor: color, opacity: 0.5 }}
      />
    )
  }
  return (
    <span className="inline-flex h-2.5 w-2.5 rounded-full bg-white/20" />
  )
}

function StatusLabel({ status }: { status: 'active' | 'inactive' | 'learning' }) {
  const styles: Record<string, string> = {
    active: 'bg-emerald-500/15 text-emerald-300',
    learning: 'bg-amber-500/15 text-amber-300',
    inactive: 'bg-white/5 text-white/30',
  }
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider ${styles[status]}`}>
      {status}
    </span>
  )
}

function LayerCard({
  layer,
  index,
  metrics,
}: {
  layer: LayerDef
  index: number
  metrics: LayerMetrics
}) {
  const [expanded, setExpanded] = useState(false)
  const m = metrics[layer.id as keyof LayerMetrics]
  const status = m.status

  const renderMetric = () => {
    switch (layer.id) {
      case 'L1': {
        const d = m as LayerMetrics['L1']
        return (
          <div className="mt-3 space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-white/50">Total runs</span>
              <span className="font-mono text-white/90">{d.total_runs.toLocaleString()}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-white/50">Success rate</span>
              <span className="font-mono text-white/90">{d.success_rate}</span>
            </div>
          </div>
        )
      }
      case 'L2': {
        const d = m as LayerMetrics['L2']
        return (
          <div className="mt-3 space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-white/50">Drift rate</span>
              <span className="font-mono text-white/90">{d.drift_rate}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-white/50">Avg drifts / run</span>
              <span className="font-mono text-white/90">{d.avg_drifts.toFixed(2)}</span>
            </div>
          </div>
        )
      }
      case 'L3': {
        const d = m as LayerMetrics['L3']
        return (
          <div className="mt-3 space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-white/50">Total receipts</span>
              <span className="font-mono text-white/90">{d.total_receipts.toLocaleString()}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-white/50">Verification pass</span>
              <span className="font-mono text-white/90">{d.pass_rate}</span>
            </div>
          </div>
        )
      }
      default:
        return (
          <div className="mt-3">
            <span className="text-xs text-white/30 italic">Awaiting min. 50 runs to activate...</span>
          </div>
        )
    }
  }

  const expandedDetail = () => {
    switch (layer.id) {
      case 'L1':
        return 'Captures run_id, intent, iterations, tool calls, timing, and success/failure for every orchestrator execution. Foundation for all upper layers.'
      case 'L2':
        return 'Computes per-step alignment scores between stated intent and actual actions. Fires drift events when alignment drops below threshold. Feeds into governance steering.'
      case 'L3':
        return 'Issues cryptographic action receipts for each step. Detects contradictions between consecutive actions. Tracks verification pass rates for audit trails.'
      case 'L4':
        return 'Learns routing preferences from run outcomes. Builds belief-weighted heuristics for tool selection and response depth. Requires 50+ runs to bootstrap.'
      case 'L5':
        return 'Tracks patterns in execution behavior: which tools succeed in which contexts, latency distributions, error clusters. Self-updates as new runs complete.'
      case 'L6':
        return 'Calibrates confidence by comparing predicted vs actual outcomes. Adjusts response depth and verification requirements based on earned accuracy.'
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4, ease: 'easeOut' }}
      onClick={() => setExpanded(!expanded)}
      className="group relative cursor-pointer rounded-xl border border-white/[0.08] p-5 transition-all duration-300 hover:border-white/[0.15]"
      style={{
        background: 'rgba(255,255,255,0.03)',
        backdropFilter: 'blur(12px)',
        boxShadow: expanded
          ? `0 0 30px ${layer.color}15, inset 0 1px 0 rgba(255,255,255,0.05)`
          : 'inset 0 1px 0 rgba(255,255,255,0.04)',
      }}
    >
      {/* Top glow line */}
      <div
        className="absolute top-0 left-4 right-4 h-px opacity-40 transition-opacity group-hover:opacity-70"
        style={{ background: `linear-gradient(90deg, transparent, ${layer.color}, transparent)` }}
      />

      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          {/* Layer badge */}
          <div
            className="flex h-9 w-9 items-center justify-center rounded-lg text-xs font-bold"
            style={{
              background: `${layer.color}18`,
              color: layer.color,
              border: `1px solid ${layer.color}30`,
            }}
          >
            {layer.id}
          </div>
          <div>
            <div className="text-sm font-semibold text-white/90">{layer.name}</div>
            <div className="text-xs text-white/40 mt-0.5">{layer.desc}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusDot status={status} color={layer.color} />
          <StatusLabel status={status} />
        </div>
      </div>

      {renderMetric()}

      {/* Expandable detail */}
      <motion.div
        initial={false}
        animate={{ height: expanded ? 'auto' : 0, opacity: expanded ? 1 : 0 }}
        transition={{ duration: 0.25, ease: 'easeOut' }}
        className="overflow-hidden"
      >
        <div className="mt-3 pt-3 border-t border-white/[0.06] text-xs text-white/50 leading-relaxed">
          {expandedDetail()}
        </div>
      </motion.div>

      {/* Expand hint */}
      <div className="mt-2 text-center">
        <span className="text-[10px] text-white/20 transition-colors group-hover:text-white/40">
          {expanded ? 'click to collapse' : 'click to expand'}
        </span>
      </div>
    </motion.div>
  )
}

/* ── Main Page ───────────────────────────────────────────── */

export function GovernanceLayersPage() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [receipts, setReceipts] = useState<ReceiptSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [a, r] = await Promise.allSettled([
          fetchJson<AnalyticsData>('/api/agent-runs/analytics'),
          fetchJson<ReceiptSummary>('/api/action-receipts/summary'),
        ])
        if (cancelled) return
        if (a.status === 'fulfilled') setAnalytics(a.value)
        if (r.status === 'fulfilled') setReceipts(r.value)
      } catch (e: any) {
        if (!cancelled) setError(e.message)
      }
    }

    load()
    const iv = setInterval(load, 30_000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [])

  const metrics: LayerMetrics = {
    L1: {
      total_runs: analytics?.total_runs ?? 0,
      success_rate: analytics ? pct(analytics.success_rate) : '\u2014',
      status: (analytics?.total_runs ?? 0) > 0 ? 'active' : 'inactive',
    },
    L2: {
      drift_rate: analytics ? pct(analytics.drift_rate ?? (analytics.total_drifts && analytics.total_runs
        ? analytics.total_drifts / analytics.total_runs : null)) : '\u2014',
      avg_drifts: analytics?.avg_drifts ?? 0,
      status: (analytics?.total_runs ?? 0) > 0 ? 'active' : 'inactive',
    },
    L3: {
      total_receipts: receipts?.total_actions ?? 0,
      pass_rate: receipts ? pct(receipts.verification_pass_rate) : '\u2014',
      status: (receipts?.total_actions ?? 0) > 0 ? 'active' : 'inactive',
    },
    L4: { status: 'learning' },
    L5: { status: 'learning' },
    L6: { status: 'learning' },
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl px-6 py-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="mb-8"
        >
          <h1 className="text-xl font-semibold text-white/90 font-display tracking-wide">
            Governance Layers
          </h1>
          <p className="mt-1 text-sm text-white/40">
            Six layers of epistemic governance, from raw observation to confidence calibration.
          </p>
          {error && (
            <div className="mt-2 text-xs text-red-400/80">
              Failed to load some data: {error}
            </div>
          )}
        </motion.div>

        {/* Layer grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {LAYERS.map((layer, i) => (
            <LayerCard key={layer.id} layer={layer} index={i} metrics={metrics} />
          ))}
        </div>

        {/* Immune Agents footer */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5, duration: 0.4 }}
          className="mt-10"
        >
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-white/30">
            Constitutional Laws (Immune Agents)
          </h2>
          <div className="flex flex-wrap gap-3">
            {IMMUNE_AGENTS.map((agent) => (
              <div
                key={agent.id}
                className="group/badge flex items-center gap-2 rounded-lg border border-white/[0.06] px-3 py-2 transition-all hover:border-white/[0.12] hover:bg-white/[0.03]"
                title={agent.desc}
              >
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-40" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
                </span>
                <span className="text-xs text-white/60 group-hover/badge:text-white/80 transition-colors">
                  <span className="font-mono text-white/30 mr-1">L{agent.id}</span>
                  {agent.name}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  )
}
