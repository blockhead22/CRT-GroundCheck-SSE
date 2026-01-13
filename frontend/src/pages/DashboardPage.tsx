import { useEffect, useMemo, useState } from 'react'
import {
  getDashboardOverview,
  getMemory,
  getMemoryTrustHistory,
  listOpenContradictions,
  listRecentMemories,
  exportThread,
  resetThread,
  resolveContradiction,
  searchMemories,
  type ContradictionListItem,
  type DashboardOverview,
  type MemoryListItem,
  type TrustHistoryRow,
} from '../lib/api'
import { ThreadToolsLightbox } from '../components/ThreadToolsLightbox'

function fmtPct01(v: number): string {
  const clamped = Math.max(0, Math.min(1, v))
  return `${Math.round(clamped * 100)}%`
}

export function DashboardPage(props: { threadId: string }) {
  type Tab = 'overview' | 'memory' | 'ledger'
  const [tab, setTab] = useState<Tab>('overview')

  type MemoryMode = 'recent' | 'search'
  const [memoryMode, setMemoryMode] = useState<MemoryMode>('recent')

  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [memories, setMemories] = useState<MemoryListItem[]>([])
  const [contras, setContras] = useState<ContradictionListItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [searchQ, setSearchQ] = useState('')
  const [searchMinTrust, setSearchMinTrust] = useState(0)
  const [searchK, setSearchK] = useState(25)
  const [searchResults, setSearchResults] = useState<MemoryListItem[]>([])
  const [searching, setSearching] = useState(false)
  const [sourceFilter, setSourceFilter] = useState<string>('all')
  const [kindFilter, setKindFilter] = useState<'all' | 'facts' | 'prefs' | 'other'>('all')
  const [sortBy, setSortBy] = useState<'timestamp' | 'trust' | 'confidence'>('timestamp')
  const [selectedMemoryId, setSelectedMemoryId] = useState<string | null>(null)
  const [selectedMemory, setSelectedMemory] = useState<MemoryListItem | null>(null)
  const [trustRows, setTrustRows] = useState<TrustHistoryRow[]>([])
  const [toolsOpen, setToolsOpen] = useState(false)

  function isFact(text: string): boolean {
    return text.trimStart().toUpperCase().startsWith('FACT:')
  }

  function isPref(text: string): boolean {
    return text.trimStart().toUpperCase().startsWith('PREF:')
  }

  function matchesKind(m: MemoryListItem): boolean {
    if (kindFilter === 'all') return true
    if (kindFilter === 'facts') return isFact(m.text)
    if (kindFilter === 'prefs') return isPref(m.text)
    return !isFact(m.text) && !isPref(m.text)
  }

  function safeCopy(text: string) {
    try {
      void navigator.clipboard.writeText(text)
    } catch {
      // ignore
    }
  }

  function renderHighlight(text: string, query: string) {
    const q = query.trim()
    if (!q) return text
    const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const re = new RegExp(escaped, 'ig')
    const parts = text.split(re)
    const matches = text.match(re)
    if (!matches) return text
    const out: Array<string | JSX.Element> = []
    for (let i = 0; i < parts.length; i++) {
      out.push(parts[i])
      if (i < matches.length) {
        out.push(
          <mark key={`${i}-${matches[i]}`} className="rounded bg-violet-500/25 px-1 text-white">
            {matches[i]}
          </mark>,
        )
      }
    }
    return out
  }

  async function refresh() {
    setError(null)
    const tid = props.threadId
    const [o, m, c] = await Promise.all([
      getDashboardOverview(tid),
      listRecentMemories(tid, 25),
      listOpenContradictions(tid, 50),
    ])
    setOverview(o)
    setMemories(m)
    setContras(c)
  }

  useEffect(() => {
    void refresh().catch((e) => setError(e instanceof Error ? e.message : String(e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.threadId])

  async function doResolve(item: ContradictionListItem, method: string) {
    setBusy(true)
    try {
      await resolveContradiction({ threadId: props.threadId, ledgerId: item.ledger_id, method, newStatus: 'resolved' })
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function doExport() {
    setError(null)
    setBusy(true)
    try {
      const data = await exportThread({ threadId: props.threadId, includeResolved: true })
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const stamp = new Date().toISOString().replace(/[:.]/g, '-')
      a.href = url
      a.download = `crt_thread_${props.threadId}_${stamp}.json`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function doReset(target: 'memory' | 'ledger' | 'all') {
    setError(null)
    setBusy(true)
    try {
      await resetThread({ threadId: props.threadId, target })
      setSelectedMemoryId(null)
      setSearchResults([])
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
      setToolsOpen(false)
    }
  }

  const trustColumns = useMemo(() => {
    const cols = new Set<string>()
    for (const row of trustRows) {
      for (const key of Object.keys(row)) cols.add(key)
    }
    const preferred = ['timestamp', 'trust', 'reason', 'delta', 'source']
    const ordered: string[] = []
    for (const p of preferred) if (cols.has(p)) ordered.push(p)
    for (const c of Array.from(cols)) if (!ordered.includes(c)) ordered.push(c)
    return ordered.slice(0, 6)
  }, [trustRows])

  async function runSearch() {
    setError(null)
    const q = searchQ.trim()
    if (!q) {
      setSearchResults([])
      return
    }
    try {
      setSearching(true)
      const results = await searchMemories({ threadId: props.threadId, q, k: searchK, minTrust: searchMinTrust })
      setSearchResults(results)
      if (results[0]) setSelectedMemoryId(results[0].memory_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSearching(false)
    }
  }

  useEffect(() => {
    if (tab !== 'memory') return
    if (memoryMode !== 'search') return
    const q = searchQ.trim()
    if (q.length < 2) {
      setSearchResults([])
      return
    }
    const id = window.setTimeout(() => void runSearch(), 320)
    return () => window.clearTimeout(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, memoryMode, searchQ, searchMinTrust, searchK, props.threadId])

  useEffect(() => {
    if (!selectedMemoryId) {
      setSelectedMemory(null)
      setTrustRows([])
      return
    }
    let mounted = true
    setError(null)
    Promise.all([
      getMemory(props.threadId, selectedMemoryId),
      getMemoryTrustHistory(props.threadId, selectedMemoryId),
    ])
      .then(([m, t]) => {
        if (!mounted) return
        setSelectedMemory(m)
        setTrustRows(t)
      })
      .catch((e) => {
        if (!mounted) return
        setError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      mounted = false
    }
  }, [props.threadId, selectedMemoryId])

  const allSources = useMemo(() => {
    const s = new Set<string>()
    for (const m of memories) s.add(m.source)
    for (const m of searchResults) s.add(m.source)
    return Array.from(s).sort()
  }, [memories, searchResults])

  const visibleMemories = useMemo(() => {
    const base = memoryMode === 'recent' ? memories : searchResults
    const q = searchQ.trim().toLowerCase()
    const filtered = base
      .filter((m) => (sourceFilter === 'all' ? true : m.source === sourceFilter))
      .filter(matchesKind)
      .filter((m) => (memoryMode === 'recent' && q ? m.text.toLowerCase().includes(q) : true))
    const sorted = [...filtered].sort((a, b) => {
      if (sortBy === 'trust') return b.trust - a.trust
      if (sortBy === 'confidence') return b.confidence - a.confidence
      return b.timestamp - a.timestamp
    })
    return sorted
  }, [memories, searchResults, memoryMode, sourceFilter, kindFilter, sortBy, searchQ])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <div>
          <div className="text-lg font-semibold text-white">Dashboard</div>
          <div className="mt-1 text-sm text-white/60">Thread: {props.threadId}</div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-2xl border border-white/10 bg-white/5 p-1">
            {(
              [
                { id: 'overview', label: 'Overview' },
                { id: 'memory', label: 'Memory' },
                { id: 'ledger', label: 'Ledger' },
              ] as const
            ).map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={
                  'rounded-xl px-3 py-2 text-xs font-semibold ' +
                  (tab === t.id ? 'bg-violet-600 text-white' : 'text-white/70 hover:bg-white/10')
                }
              >
                {t.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => void refresh()}
            className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/80 hover:bg-white/10"
          >
            Refresh
          </button>
          <button
            disabled={busy}
            onClick={() => setToolsOpen(true)}
            className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/80 hover:bg-white/10 disabled:opacity-50"
          >
            Thread tools
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-5">
        {error ? (
          <div className="mb-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
            {error}
          </div>
        ) : null}

        {tab === 'overview' ? (
          <>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-xs font-semibold tracking-wide text-white/60">Memories</div>
                <div className="mt-2 text-3xl font-semibold text-white">{overview?.memories_total ?? '—'}</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-xs font-semibold tracking-wide text-white/60">Open contradictions</div>
                <div className="mt-2 text-3xl font-semibold text-white">{overview?.open_contradictions ?? '—'}</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-xs font-semibold tracking-wide text-white/60">Belief vs Speech (7d)</div>
                <div className="mt-2 text-sm text-white/80">
                  Belief {overview ? fmtPct01(overview.belief_ratio) : '—'} · Speech{' '}
                  {overview ? fmtPct01(overview.speech_ratio) : '—'}
                </div>
                <div className="mt-1 text-xs text-white/50">
                  {overview?.belief_count ?? 0} belief · {overview?.speech_count ?? 0} speech
                </div>
              </div>
            </div>

            <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold text-white">Open contradictions</div>
                  <div className="text-xs text-white/50">{contras.length} shown</div>
                </div>
                <div className="mt-3 space-y-2">
                  {contras.slice(0, 10).map((c) => (
                    <div key={c.ledger_id} className="rounded-2xl border border-white/10 bg-black/20 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-xs text-white/50">
                            {c.contradiction_type.toUpperCase()} · drift {c.drift_mean.toFixed(2)}
                          </div>
                          <div className="mt-1 line-clamp-2 text-sm text-white">{c.summary || '—'}</div>
                          <div className="mt-1 text-xs text-white/50">{c.ledger_id}</div>
                        </div>
                        <div className="flex flex-none items-center gap-2">
                          <button
                            disabled={busy}
                            onClick={() => void doResolve(c, 'accept_both')}
                            className="rounded-xl border border-white/10 bg-white/5 px-2 py-1 text-xs font-semibold text-white/80 hover:bg-white/10 disabled:opacity-50"
                          >
                            Accept
                          </button>
                          <button
                            disabled={busy}
                            onClick={() => void doResolve(c, 'user_clarified')}
                            className="rounded-xl border border-white/10 bg-white/5 px-2 py-1 text-xs font-semibold text-white/80 hover:bg-white/10 disabled:opacity-50"
                          >
                            Resolved
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                  {!contras.length ? <div className="text-sm text-white/60">No open contradictions.</div> : null}
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold text-white">Recent memories</div>
                  <div className="text-xs text-white/50">{memories.length} shown</div>
                </div>
                <div className="mt-3 space-y-2">
                  {memories.slice(0, 12).map((m) => (
                    <div key={m.memory_id} className="rounded-2xl border border-white/10 bg-black/20 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-xs text-white/50">
                            {m.source} · trust {m.trust.toFixed(2)} · conf {m.confidence.toFixed(2)}
                          </div>
                          <div className="mt-1 line-clamp-3 whitespace-pre-wrap text-sm text-white">{m.text}</div>
                          <div className="mt-1 text-xs text-white/50">{m.memory_id}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                  {!memories.length ? <div className="text-sm text-white/60">No memories yet.</div> : null}
                </div>
              </div>
            </div>
          </>
        ) : null}

        {tab === 'memory' ? (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[380px_1fr]">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-sm font-semibold text-white">Memory explorer</div>
              <div className="mt-3 space-y-3">
                <div className="flex items-center gap-1 rounded-2xl border border-white/10 bg-white/5 p-1">
                  {(
                    [
                      { id: 'recent', label: 'Recent' },
                      { id: 'search', label: 'Search' },
                    ] as const
                  ).map((m) => (
                    <button
                      key={m.id}
                      onClick={() => setMemoryMode(m.id)}
                      className={
                        'flex-1 rounded-xl px-3 py-2 text-xs font-semibold ' +
                        (memoryMode === m.id ? 'bg-violet-600 text-white' : 'text-white/70 hover:bg-white/10')
                      }
                    >
                      {m.label}
                    </button>
                  ))}
                </div>

                <input
                  value={searchQ}
                  onChange={(e) => setSearchQ(e.target.value)}
                  onKeyDown={(e) => (e.key === 'Enter' ? void runSearch() : undefined)}
                  placeholder={memoryMode === 'search' ? 'Search memories…' : 'Filter by text…'}
                  className="w-full rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none"
                />

                <div className="grid grid-cols-2 gap-2">
                  <label className="space-y-1">
                    <div className="text-xs font-semibold tracking-wide text-white/50">Source</div>
                    <select
                      value={sourceFilter}
                      onChange={(e) => setSourceFilter(e.target.value)}
                      className="w-full rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white/90 focus:outline-none"
                    >
                      <option value="all">All</option>
                      {allSources.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="space-y-1">
                    <div className="text-xs font-semibold tracking-wide text-white/50">Kind</div>
                    <select
                      value={kindFilter}
                      onChange={(e) => setKindFilter(e.target.value as typeof kindFilter)}
                      className="w-full rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white/90 focus:outline-none"
                    >
                      <option value="all">All</option>
                      <option value="facts">FACT</option>
                      <option value="prefs">PREF</option>
                      <option value="other">Other</option>
                    </select>
                  </label>
                </div>

                <div className="flex items-center gap-2">
                  <div className="text-xs text-white/50">min trust</div>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={searchMinTrust}
                    onChange={(e) => setSearchMinTrust(Number(e.target.value))}
                    className="w-full"
                  />
                  <div className="w-10 text-right text-xs text-white/60">{searchMinTrust.toFixed(2)}</div>
                </div>

                {memoryMode === 'search' ? (
                  <>
                    <div className="flex items-center gap-2">
                      <div className="text-xs text-white/50">top k</div>
                      <input
                        type="range"
                        min={5}
                        max={60}
                        step={5}
                        value={searchK}
                        onChange={(e) => setSearchK(Number(e.target.value))}
                        className="w-full"
                      />
                      <div className="w-10 text-right text-xs text-white/60">{searchK}</div>
                    </div>
                    <button
                      onClick={() => void runSearch()}
                      className="w-full rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm font-semibold text-white/80 hover:bg-white/10"
                    >
                      {searching ? 'Searching…' : 'Search now'}
                    </button>
                  </>
                ) : null}

                <div className="flex items-center justify-between gap-2">
                  <label className="flex items-center gap-2 text-xs text-white/60">
                    Sort
                    <select
                      value={sortBy}
                      onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                      className="rounded-xl border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/90"
                    >
                      <option value="timestamp">Recent</option>
                      <option value="trust">Trust</option>
                      <option value="confidence">Confidence</option>
                    </select>
                  </label>
                  <button
                    onClick={() => {
                      setSearchQ('')
                      setSearchResults([])
                      setSourceFilter('all')
                      setKindFilter('all')
                    }}
                    className="text-xs text-white/60 hover:underline"
                  >
                    Clear
                  </button>
                </div>
              </div>

              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-xs text-white/50">
                    Showing {visibleMemories.length} {memoryMode === 'recent' ? 'recent' : 'results'}
                  </div>
                  {memoryMode === 'recent' ? (
                    <button onClick={() => void refresh()} className="text-xs text-white/60 hover:underline">
                      Refresh
                    </button>
                  ) : null}
                </div>

                {visibleMemories.map((m) => (
                  <button
                    key={m.memory_id}
                    onClick={() => setSelectedMemoryId(m.memory_id)}
                    className={
                      'w-full rounded-2xl border px-3 py-2 text-left ' +
                      (m.memory_id === selectedMemoryId
                        ? 'border-violet-500/50 bg-violet-500/10'
                        : 'border-white/10 bg-black/20 hover:bg-white/5')
                    }
                  >
                    <div className="text-xs text-white/50">
                      {m.source} · trust {m.trust.toFixed(2)} · conf {m.confidence.toFixed(2)}
                    </div>
                    <div className="mt-1 line-clamp-3 text-sm text-white">
                      {memoryMode === 'search' ? renderHighlight(m.text, searchQ) : m.text}
                    </div>
                  </button>
                ))}
                {!visibleMemories.length ? (
                  <div className="text-sm text-white/60">
                    {memoryMode === 'recent'
                      ? 'No memories yet for this thread.'
                      : searchQ.trim().length < 2
                        ? 'Type at least 2 characters to search.'
                        : searching
                          ? 'Searching…'
                          : 'No matches.'}
                  </div>
                ) : null}
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-white">Details</div>
                <div className="text-xs text-white/50">{selectedMemoryId || '—'}</div>
              </div>

              {selectedMemory ? (
                <>
                  <div className="mt-3 rounded-2xl border border-white/10 bg-black/20 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-xs text-white/50">
                        {selectedMemory.source} · trust {selectedMemory.trust.toFixed(2)} · conf {selectedMemory.confidence.toFixed(2)} ·{' '}
                        {new Date(selectedMemory.timestamp * 1000).toLocaleString()}
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => safeCopy(selectedMemory.memory_id)}
                          className="rounded-xl border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/70 hover:bg-white/10"
                        >
                          Copy ID
                        </button>
                        <button
                          onClick={() => safeCopy(selectedMemory.text)}
                          className="rounded-xl border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/70 hover:bg-white/10"
                        >
                          Copy text
                        </button>
                      </div>
                    </div>
                    <div className="mt-2 whitespace-pre-wrap text-sm text-white">{selectedMemory.text}</div>
                  </div>

                  <div className="mt-4">
                    <div className="text-sm font-semibold text-white">Trust history</div>
                    <div className="mt-2 overflow-auto rounded-2xl border border-white/10 bg-black/20">
                      <table className="w-full min-w-[520px] text-left text-xs">
                        <thead className="border-b border-white/10 text-white/60">
                          <tr>
                            {trustColumns.map((c) => (
                              <th key={c} className="px-3 py-2 font-semibold">
                                {c}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {trustRows.slice(0, 50).map((r, idx) => (
                            <tr key={idx} className="border-b border-white/5 text-white/80">
                              {trustColumns.map((c) => (
                                <td key={c} className="px-3 py-2 align-top">
                                  {typeof r[c] === 'string' || typeof r[c] === 'number' ? String(r[c]) : JSON.stringify(r[c])}
                                </td>
                              ))}
                            </tr>
                          ))}
                          {!trustRows.length ? (
                            <tr>
                              <td className="px-3 py-3 text-white/60" colSpan={trustColumns.length || 1}>
                                No trust history rows.
                              </td>
                            </tr>
                          ) : null}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              ) : (
                <div className="mt-6 text-sm text-white/60">Select a memory from the search results.</div>
              )}
            </div>
          </div>
        ) : null}

        {tab === 'ledger' ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-white">Contradiction ledger</div>
              <div className="text-xs text-white/50">{contras.length} open</div>
            </div>
            <div className="mt-3 space-y-2">
              {contras.map((c) => (
                <div key={c.ledger_id} className="rounded-2xl border border-white/10 bg-black/20 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-xs text-white/50">
                        {c.contradiction_type.toUpperCase()} · drift {c.drift_mean.toFixed(2)} · Δconf {c.confidence_delta.toFixed(2)}
                      </div>
                      <div className="mt-1 whitespace-pre-wrap text-sm text-white">{c.summary || c.query || '—'}</div>
                      <div className="mt-2 text-xs text-white/50">
                        old {c.old_memory_id} · new {c.new_memory_id}
                      </div>
                      <div className="mt-1 text-xs text-white/50">{c.ledger_id}</div>
                    </div>
                    <div className="flex flex-none items-center gap-2">
                      <button
                        disabled={busy}
                        onClick={() => void doResolve(c, 'accept_both')}
                        className="rounded-xl border border-white/10 bg-white/5 px-2 py-1 text-xs font-semibold text-white/80 hover:bg-white/10 disabled:opacity-50"
                      >
                        Accept
                      </button>
                      <button
                        disabled={busy}
                        onClick={() => void doResolve(c, 'user_clarified')}
                        className="rounded-xl border border-white/10 bg-white/5 px-2 py-1 text-xs font-semibold text-white/80 hover:bg-white/10 disabled:opacity-50"
                      >
                        Resolved
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              {!contras.length ? <div className="text-sm text-white/60">No open contradictions.</div> : null}
            </div>
          </div>
        ) : null}
      </div>

      <ThreadToolsLightbox
        open={toolsOpen}
        threadId={props.threadId}
        onClose={() => setToolsOpen(false)}
        onExport={doExport}
        onReset={doReset}
      />
    </div>
  )
}
