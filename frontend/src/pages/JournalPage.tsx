import { useEffect, useMemo, useState } from 'react'
import { getReflectionJournal, type ReflectionJournalEntry } from '../lib/api'

function formatTimestamp(ts: number): string {
  if (!ts || Number.isNaN(ts)) return '--'
  const ms = ts > 1_000_000_000_000 ? ts : ts * 1000
  return new Date(ms).toLocaleString()
}

function entryAccent(type: string): string {
  const key = (type || '').toLowerCase()
  if (key === 'reflection') return 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200'
  if (key === 'personality') return 'border-sky-500/30 bg-sky-500/10 text-sky-200'
  if (key === 'self_reply') return 'border-amber-500/30 bg-amber-500/10 text-amber-200'
  return 'border-white/10 bg-white/5 text-white/70'
}

export function JournalPage(props: { threadId: string }) {
  const [entries, setEntries] = useState<ReflectionJournalEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await getReflectionJournal({ threadId: props.threadId, limit: 80 })
      setEntries(data.entries || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [props.threadId])

  const emptyState = useMemo(() => !loading && !error && entries.length === 0, [loading, error, entries.length])

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-lg font-semibold text-white">Reflection Journal</div>
          <div className="mt-1 text-sm text-white/60">Background reflection + personality loop notes.</div>
        </div>
        <button
          onClick={() => void load()}
          className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/80 hover:bg-white/10"
          disabled={loading}
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <div className="max-w-[980px] space-y-3">
        {error ? (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            Failed to load journal: {error}
          </div>
        ) : null}

        {emptyState ? (
          <div className="rounded-2xl glass-card px-4 py-6 text-sm text-white/60">
            No journal entries yet. The reflection/personality loops will append here as they run.
          </div>
        ) : null}

        {entries.map((entry) => {
          const rawReplyTo = entry.meta && (entry.meta as Record<string, unknown>).reply_to
          let replyTo: number | null = null
          if (typeof rawReplyTo === 'number' && Number.isFinite(rawReplyTo)) {
            replyTo = rawReplyTo
          } else if (typeof rawReplyTo === 'string' && rawReplyTo.trim()) {
            const parsed = Number(rawReplyTo)
            if (Number.isFinite(parsed)) replyTo = parsed
          }
          const replyToText = replyTo !== null ? `Reply to #${replyTo}` : null
          const sourceType =
            entry.meta && typeof (entry.meta as Record<string, unknown>).source_entry_type === 'string'
              ? String((entry.meta as Record<string, unknown>).source_entry_type)
              : null
          const metaLine = [replyToText, sourceType ? `Source: ${sourceType}` : null].filter(Boolean).join(' | ')
          const entryLabel = (entry.entry_type || 'note').replace(/_/g, ' ')

          return (
            <div key={entry.id} className="rounded-2xl glass-card px-4 py-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-white">{entry.title}</div>
                  <div className="mt-1 text-[11px] text-white/50">{formatTimestamp(entry.created_at)}</div>
                  {metaLine ? <div className="mt-1 text-[11px] text-white/40">{metaLine}</div> : null}
                </div>
                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide ${entryAccent(entry.entry_type)}`}
                >
                  {entryLabel}
                </span>
              </div>
              <div className="mt-3 whitespace-pre-line text-sm text-white/80">{entry.body}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
