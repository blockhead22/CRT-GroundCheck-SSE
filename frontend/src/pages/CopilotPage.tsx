import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  getCopilotMemories,
  type CopilotMemory,
  type CopilotStats,
  type CopilotMemoriesResponse,
} from '../lib/api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(ts: number): string {
  const diff = Math.floor(Date.now() / 1000) - ts
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`
  return new Date(ts * 1000).toLocaleDateString()
}

function trustColor(trust: number): string {
  if (trust >= 0.7) return 'text-emerald-400'
  if (trust >= 0.4) return 'text-amber-400'
  return 'text-red-400'
}

function trustBg(trust: number): string {
  if (trust >= 0.7) return 'bg-emerald-500/20 border-emerald-500/40'
  if (trust >= 0.4) return 'bg-amber-500/20 border-amber-500/40'
  return 'bg-red-500/20 border-red-500/40'
}

function sourceBadge(source: string): { label: string; className: string } {
  switch (source) {
    case 'inferred':
      return { label: '⚡ Auto-learned', className: 'bg-violet-500/20 text-violet-300 border-violet-500/30' }
    case 'user':
      return { label: '👤 Explicit', className: 'bg-sky-500/20 text-sky-300 border-sky-500/30' }
    case 'document':
      return { label: '📄 Document', className: 'bg-teal-500/20 text-teal-300 border-teal-500/30' }
    case 'code':
      return { label: '💻 Code', className: 'bg-orange-500/20 text-orange-300 border-orange-500/30' }
    default:
      return { label: source, className: 'bg-white/10 text-white/60 border-white/20' }
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatCard({ label, value, sub, accent }: {
  label: string
  value: string | number
  sub?: string
  accent?: string
}) {
  return (
    <div className="flex flex-col gap-1 rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="text-xs font-medium uppercase tracking-wider text-white/40">{label}</div>
      <div className={`text-2xl font-bold ${accent || 'text-white'}`}>{value}</div>
      {sub && <div className="text-xs text-white/40">{sub}</div>}
    </div>
  )
}

function TrustBar({ distribution }: { distribution: Record<string, number> }) {
  const total = Object.values(distribution).reduce((a, b) => a + b, 0)
  if (total === 0) return null
  const segments = [
    { key: 'very_high (0.8-1.0)', color: 'bg-emerald-500', label: 'Very High' },
    { key: 'high (0.6-0.8)', color: 'bg-emerald-400', label: 'High' },
    { key: 'medium (0.3-0.6)', color: 'bg-amber-400', label: 'Medium' },
    { key: 'low (0-0.3)', color: 'bg-red-400', label: 'Low' },
  ]
  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-white/5">
        {segments.map(seg => {
          const count = distribution[seg.key] || 0
          const pct = total > 0 ? (count / total) * 100 : 0
          if (pct === 0) return null
          return (
            <div
              key={seg.key}
              className={`${seg.color} transition-all duration-500`}
              style={{ width: `${pct}%` }}
              title={`${seg.label}: ${count}`}
            />
          )
        })}
      </div>
      <div className="flex flex-wrap gap-3 text-xs text-white/50">
        {segments.map(seg => {
          const count = distribution[seg.key] || 0
          if (count === 0) return null
          return (
            <span key={seg.key} className="flex items-center gap-1">
              <span className={`inline-block h-2 w-2 rounded-full ${seg.color}`} />
              {seg.label}: {count}
            </span>
          )
        })}
      </div>
    </div>
  )
}

function MemoryCard({ memory, expanded, onToggle }: {
  memory: CopilotMemory
  expanded: boolean
  onToggle: () => void
}) {
  const src = sourceBadge(memory.source)
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="group cursor-pointer rounded-xl border border-white/8 bg-white/[0.03] hover:bg-white/[0.06] transition-all"
      onClick={onToggle}
    >
      <div className="flex items-start gap-3 p-4">
        {/* Trust indicator */}
        <div className={`mt-0.5 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border ${trustBg(memory.trust)}`}>
          <span className={`text-sm font-bold ${trustColor(memory.trust)}`}>
            {(memory.trust * 100).toFixed(0)}
          </span>
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-medium ${src.className}`}>
              {src.label}
            </span>
            <span className="text-[10px] text-white/30 font-mono">{memory.namespace}</span>
            <span className="ml-auto text-[10px] text-white/30">{timeAgo(memory.timestamp)}</span>
          </div>
          <p className="text-sm text-white/80 leading-relaxed">{memory.text}</p>
        </div>
      </div>

      {/* Expanded details */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-white/5"
          >
            <div className="grid grid-cols-2 gap-3 p-4 text-xs sm:grid-cols-4">
              <div>
                <span className="text-white/30">ID</span>
                <div className="mt-0.5 font-mono text-white/50 break-all">{memory.id}</div>
              </div>
              <div>
                <span className="text-white/30">Thread</span>
                <div className="mt-0.5 font-mono text-white/50">{memory.thread_id}</div>
              </div>
              <div>
                <span className="text-white/30">Trust</span>
                <div className={`mt-0.5 font-mono font-bold ${trustColor(memory.trust)}`}>{memory.trust.toFixed(2)}</div>
              </div>
              <div>
                <span className="text-white/30">Stored</span>
                <div className="mt-0.5 text-white/50">
                  {memory.created_at || new Date(memory.timestamp * 1000).toLocaleString()}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

type SortOrder = 'newest' | 'oldest' | 'trust_high' | 'trust_low'

export function CopilotPage() {
  // Data
  const [data, setData] = useState<CopilotMemoriesResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filters
  const [nsFilter, setNsFilter] = useState<string>('')
  const [sourceFilter, setSourceFilter] = useState<string>('')
  const [searchQ, setSearchQ] = useState<string>('')
  const [sortOrder, setSortOrder] = useState<SortOrder>('newest')

  // Live polling
  const [live, setLive] = useState(true)
  const [pollInterval, setPollInterval] = useState(2000)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())
  const [newCount, setNewCount] = useState(0)
  const prevTotalRef = useRef<number>(0)

  // UI
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'cards' | 'timeline'>('cards')

  const fetchData = useCallback(async () => {
    try {
      const resp = await getCopilotMemories({
        namespace: nsFilter || undefined,
        source: sourceFilter || undefined,
        search: searchQ || undefined,
        sort: sortOrder,
        limit: 200,
      })
      setData(resp)
      setError(null)
      setLastRefresh(new Date())

      // Track new memories arriving
      if (prevTotalRef.current > 0 && resp.stats.total_memories > prevTotalRef.current) {
        setNewCount(prev => prev + (resp.stats.total_memories - prevTotalRef.current))
      }
      prevTotalRef.current = resp.stats.total_memories
    } catch (e: any) {
      setError(e.message || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }, [nsFilter, sourceFilter, searchQ, sortOrder])

  // Initial load
  useEffect(() => {
    setLoading(true)
    fetchData()
  }, [fetchData])

  // Live polling
  useEffect(() => {
    if (live) {
      intervalRef.current = setInterval(fetchData, pollInterval)
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [live, pollInterval, fetchData])

  const stats = data?.stats
  const memories = data?.memories || []

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="flex flex-col gap-4 border-b border-white/10 p-4 sm:p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white font-display">Copilot Interactions</h1>
            <p className="mt-0.5 text-xs text-white/40">
              GroundCheck memory — what Copilot knows about you
            </p>
          </div>

          {/* Live indicator + controls */}
          <div className="flex items-center gap-3">
            {newCount > 0 && (
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="rounded-full bg-violet-500/20 border border-violet-500/40 px-2 py-0.5 text-xs text-violet-300"
              >
                +{newCount} new
              </motion.span>
            )}

            <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5">
              <button
                onClick={() => setLive(v => !v)}
                className="flex items-center gap-1.5 text-xs"
              >
                <span className={`inline-block h-2 w-2 rounded-full ${live ? 'bg-emerald-400 animate-pulse' : 'bg-white/20'}`} />
                <span className={live ? 'text-emerald-400' : 'text-white/40'}>
                  {live ? 'Live' : 'Paused'}
                </span>
              </button>
              <span className="mx-1 h-4 w-px bg-white/10" />
              <button
                onClick={() => { setLoading(true); fetchData() }}
                className="text-xs text-white/40 hover:text-white transition-colors"
                title="Refresh now"
              >
                ↻
              </button>
            </div>

            <span className="text-[10px] text-white/20">
              {lastRefresh.toLocaleTimeString()}
            </span>
          </div>
        </div>

        {/* Stats cards */}
        {stats && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
            <StatCard
              label="Total Memories"
              value={stats.total_memories}
              accent="text-white"
            />
            <StatCard
              label="Auto-learned"
              value={stats.auto_learned_count}
              sub={stats.total_memories > 0
                ? `${Math.round((stats.auto_learned_count / stats.total_memories) * 100)}% of total`
                : undefined}
              accent="text-violet-400"
            />
            <StatCard
              label="Explicit"
              value={stats.explicit_count}
              accent="text-sky-400"
            />
            <StatCard
              label="Namespaces"
              value={stats.namespaces.length}
              sub={stats.namespaces.slice(0, 3).join(', ')}
            />
            <div className="col-span-2 sm:col-span-4 lg:col-span-1">
              <div className="flex flex-col gap-1 rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-xs font-medium uppercase tracking-wider text-white/40">Trust Distribution</div>
                <div className="mt-1">
                  <TrustBar distribution={stats.trust_distribution} />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Toolbar — filters */}
      <div className="flex flex-wrap items-center gap-2 border-b border-white/5 px-4 py-3 sm:px-6">
        {/* Search */}
        <input
          type="text"
          placeholder="Search memories..."
          value={searchQ}
          onChange={e => setSearchQ(e.target.value)}
          className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white placeholder-white/30 outline-none focus:border-violet-500/50 w-48"
        />

        {/* Namespace filter */}
        <select
          value={nsFilter}
          onChange={e => setNsFilter(e.target.value)}
          className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white outline-none cursor-pointer"
        >
          <option value="">All Namespaces</option>
          {(stats?.namespaces || []).map(ns => (
            <option key={ns} value={ns}>{ns}</option>
          ))}
        </select>

        {/* Source filter */}
        <select
          value={sourceFilter}
          onChange={e => setSourceFilter(e.target.value)}
          className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white outline-none cursor-pointer"
        >
          <option value="">All Sources</option>
          <option value="inferred">⚡ Auto-learned</option>
          <option value="user">👤 Explicit</option>
          <option value="document">📄 Document</option>
          <option value="code">💻 Code</option>
        </select>

        {/* Sort */}
        <select
          value={sortOrder}
          onChange={e => setSortOrder(e.target.value as SortOrder)}
          className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white outline-none cursor-pointer"
        >
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
          <option value="trust_high">Highest trust</option>
          <option value="trust_low">Lowest trust</option>
        </select>

        {/* View toggle */}
        <div className="ml-auto flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 p-0.5">
          <button
            onClick={() => setViewMode('cards')}
            className={`rounded-md px-2 py-1 text-xs transition-colors ${viewMode === 'cards' ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/60'}`}
          >
            Cards
          </button>
          <button
            onClick={() => setViewMode('timeline')}
            className={`rounded-md px-2 py-1 text-xs transition-colors ${viewMode === 'timeline' ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/60'}`}
          >
            Timeline
          </button>
        </div>

        {/* Count */}
        <span className="text-xs text-white/30">
          {data ? `${data.total} memories` : '...'}
        </span>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6">
        {loading && !data ? (
          <div className="flex items-center justify-center py-20">
            <div className="flex flex-col items-center gap-3">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-500" />
              <span className="text-sm text-white/40">Loading GroundCheck memories...</span>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center py-20">
            <div className="flex flex-col items-center gap-3 rounded-2xl border border-red-500/20 bg-red-500/5 p-8 text-center">
              <span className="text-4xl">⚠️</span>
              <span className="text-sm text-red-400">{error}</span>
              <button
                onClick={() => { setLoading(true); fetchData() }}
                className="mt-2 rounded-lg bg-white/10 px-4 py-2 text-xs text-white hover:bg-white/15 transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        ) : memories.length === 0 ? (
          <div className="flex items-center justify-center py-20">
            <div className="flex flex-col items-center gap-3 text-center">
              <span className="text-5xl opacity-40">🧠</span>
              <span className="text-sm text-white/40">No memories yet</span>
              <span className="text-xs text-white/20 max-w-sm">
                Start chatting with Copilot — it will automatically learn facts about you
                through the GroundCheck MCP integration.
              </span>
            </div>
          </div>
        ) : viewMode === 'cards' ? (
          <div className="flex flex-col gap-2">
            <AnimatePresence mode="popLayout">
              {memories.map(m => (
                <MemoryCard
                  key={m.id}
                  memory={m}
                  expanded={expandedId === m.id}
                  onToggle={() => setExpandedId(expandedId === m.id ? null : m.id)}
                />
              ))}
            </AnimatePresence>
          </div>
        ) : (
          /* Timeline view */
          <div className="relative ml-4 border-l border-white/10 pl-6">
            <AnimatePresence mode="popLayout">
              {memories.map((m, i) => {
                const src = sourceBadge(m.source)
                const showDateDivider = i === 0 || (
                  new Date(memories[i - 1].timestamp * 1000).toDateString() !==
                  new Date(m.timestamp * 1000).toDateString()
                )
                return (
                  <motion.div
                    key={m.id}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                  >
                    {showDateDivider && (
                      <div className="mb-3 -ml-[33px] flex items-center gap-2">
                        <div className={`h-3 w-3 rounded-full ${i === 0 ? 'bg-violet-500' : 'bg-white/20'}`} />
                        <span className="text-xs font-medium text-white/50">
                          {new Date(m.timestamp * 1000).toLocaleDateString(undefined, {
                            weekday: 'short', month: 'short', day: 'numeric'
                          })}
                        </span>
                      </div>
                    )}
                    <div className="relative mb-4 rounded-xl border border-white/8 bg-white/[0.03] p-4">
                      {/* dot on timeline */}
                      <div className="absolute -left-[33px] top-5 h-2 w-2 rounded-full bg-white/20" />
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-medium ${src.className}`}>
                          {src.label}
                        </span>
                        <span className={`text-xs font-mono font-bold ${trustColor(m.trust)}`}>
                          {(m.trust * 100).toFixed(0)}%
                        </span>
                        <span className="text-[10px] font-mono text-white/20">{m.namespace}</span>
                        <span className="ml-auto text-[10px] text-white/30">{timeAgo(m.timestamp)}</span>
                      </div>
                      <p className="text-sm text-white/80 leading-relaxed">{m.text}</p>
                    </div>
                  </motion.div>
                )
              })}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  )
}
