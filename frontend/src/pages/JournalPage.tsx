import { useEffect, useMemo, useState } from 'react'
import {
  getJournalSettings,
  getReflectionJournal,
  postJournalReply,
  setJournalSettings,
  type ReflectionJournalEntry,
} from '../lib/api'

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
  if (key === 'comment') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
  return 'border-white/10 bg-white/5 text-white/70'
}

function getReplyTo(entry: ReflectionJournalEntry): number | null {
  const raw = entry.meta && (entry.meta as Record<string, unknown>).reply_to
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw
  if (typeof raw === 'string' && raw.trim()) {
    const parsed = Number(raw)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function extractTopics(entry: ReflectionJournalEntry): string[] {
  const meta = entry.meta as Record<string, unknown> | null | undefined
  if (!meta) return []
  const topics: string[] = []
  const top = Array.isArray(meta.top_topics) ? (meta.top_topics as Array<Record<string, unknown>>) : []
  for (const item of top) {
    const topic = typeof item?.topic === 'string' ? item.topic : null
    if (topic) topics.push(topic)
  }
  const trends = meta.topic_trends as Record<string, unknown> | undefined
  if (trends && typeof trends === 'object') {
    const rising = Array.isArray(trends.rising) ? (trends.rising as Array<Record<string, unknown>>) : []
    const fading = Array.isArray(trends.fading) ? (trends.fading as Array<Record<string, unknown>>) : []
    for (const item of [...rising, ...fading]) {
      const topic = typeof item?.topic === 'string' ? item.topic : null
      if (topic) topics.push(topic)
    }
  }
  return Array.from(new Set(topics))
}

export function JournalPage(props: { threadId: string }) {
  const [entries, setEntries] = useState<ReflectionJournalEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [autoReplyEnabled, setAutoReplyEnabled] = useState<boolean | null>(null)
  const [settingsLoading, setSettingsLoading] = useState(false)
  const [settingsError, setSettingsError] = useState<string | null>(null)
  const [selectedRootId, setSelectedRootId] = useState<number | null>(null)
  const [replyTargetId, setReplyTargetId] = useState<number | null>(null)
  const [commentBody, setCommentBody] = useState('')
  const [commentError, setCommentError] = useState<string | null>(null)
  const [posting, setPosting] = useState(false)
  const [activeTopic, setActiveTopic] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await getReflectionJournal({ threadId: props.threadId, limit: 200 })
      setEntries(data.entries || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  async function loadSettings() {
    setSettingsLoading(true)
    setSettingsError(null)
    try {
      const settings = await getJournalSettings({ threadId: props.threadId })
      setAutoReplyEnabled(Boolean(settings.auto_reply_enabled))
    } catch (err) {
      setSettingsError(err instanceof Error ? err.message : String(err))
      setAutoReplyEnabled(null)
    } finally {
      setSettingsLoading(false)
    }
  }

  async function toggleAutoReply() {
    if (autoReplyEnabled === null) return
    const next = !autoReplyEnabled
    setSettingsLoading(true)
    setSettingsError(null)
    try {
      const settings = await setJournalSettings({ threadId: props.threadId, autoReplyEnabled: next })
      setAutoReplyEnabled(Boolean(settings.auto_reply_enabled))
    } catch (err) {
      setSettingsError(err instanceof Error ? err.message : String(err))
    } finally {
      setSettingsLoading(false)
    }
  }

  useEffect(() => {
    void load()
    void loadSettings()
  }, [props.threadId])

  const entryMap = useMemo(() => {
    const map = new Map<number, ReflectionJournalEntry>()
    for (const entry of entries) {
      map.set(entry.id, entry)
    }
    return map
  }, [entries])

  const rootIdByEntry = useMemo(() => {
    const cache = new Map<number, number>()
    const resolve = (entry: ReflectionJournalEntry): number => {
      if (cache.has(entry.id)) return cache.get(entry.id) as number
      let current: ReflectionJournalEntry | undefined = entry
      let hops = 0
      while (current && hops < 6) {
        const meta = current.meta as Record<string, unknown> | null | undefined
        let rootHint: number | null = null
        if (meta && typeof meta.root_id === 'number' && Number.isFinite(meta.root_id)) {
          rootHint = meta.root_id
        } else if (meta && typeof meta.root_id === 'string') {
          const parsed = Number(meta.root_id)
          if (Number.isFinite(parsed)) rootHint = parsed
        }
        if (rootHint) {
          cache.set(entry.id, rootHint)
          return rootHint
        }
        const replyTo = getReplyTo(current)
        if (!replyTo) {
          cache.set(entry.id, current.id)
          return current.id
        }
        const next = entryMap.get(replyTo)
        if (!next) {
          cache.set(entry.id, current.id)
          return current.id
        }
        current = next
        hops += 1
      }
      cache.set(entry.id, entry.id)
      return entry.id
    }
    for (const entry of entries) {
      resolve(entry)
    }
    return cache
  }, [entries, entryMap])

  const rootEntriesAll = useMemo(() => {
    return entries
      .filter((entry) => getReplyTo(entry) === null)
      .sort((a, b) => b.created_at - a.created_at)
  }, [entries])

  const rootEntries = useMemo(() => {
    if (!activeTopic) return rootEntriesAll
    return rootEntriesAll.filter((entry) => extractTopics(entry).includes(activeTopic))
  }, [rootEntriesAll, activeTopic])

  const topicIndex = useMemo(() => {
    const counts = new Map<string, number>()
    for (const entry of entries) {
      if (getReplyTo(entry) !== null) continue
      for (const topic of extractTopics(entry)) {
        counts.set(topic, (counts.get(topic) || 0) + 1)
      }
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([topic]) => topic)
  }, [entries])

  useEffect(() => {
    if (rootEntries.length === 0) {
      setSelectedRootId(null)
      return
    }
    if (!selectedRootId || !rootEntries.some((entry) => entry.id === selectedRootId)) {
      setSelectedRootId(rootEntries[0].id)
    }
  }, [rootEntries, selectedRootId])

  useEffect(() => {
    if (selectedRootId) {
      setReplyTargetId(selectedRootId)
    }
  }, [selectedRootId])

  useEffect(() => {
    setCommentError(null)
  }, [selectedRootId])

  const threadEntries = useMemo(() => {
    if (!selectedRootId) return []
    return entries
      .filter((entry) => rootIdByEntry.get(entry.id) === selectedRootId)
      .sort((a, b) => a.created_at - b.created_at)
  }, [entries, rootIdByEntry, selectedRootId])

  const emptyState = useMemo(() => !loading && !error && entries.length === 0, [loading, error, entries.length])

  async function submitReply() {
    if (!selectedRootId || !replyTargetId) return
    const body = commentBody.trim()
    if (!body) {
      setCommentError('Write a comment first.')
      return
    }
    setPosting(true)
    setCommentError(null)
    try {
      await postJournalReply({
        threadId: props.threadId,
        replyTo: replyTargetId,
        body,
        author: 'user',
        title: 'Comment',
      })
      setCommentBody('')
      await load()
    } catch (err) {
      setCommentError(err instanceof Error ? err.message : String(err))
    } finally {
      setPosting(false)
    }
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-lg font-semibold text-white">Reflection Journal</div>
          <div className="mt-1 text-sm text-white/60">Background reflection + personality loop notes.</div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2">
            <div className="text-[11px] font-semibold text-white/70">Auto replies</div>
            <button
              onClick={() => void toggleAutoReply()}
              disabled={settingsLoading || autoReplyEnabled === null}
              aria-pressed={Boolean(autoReplyEnabled)}
              className={`relative h-6 w-11 rounded-full border transition ${
                autoReplyEnabled
                  ? 'border-emerald-400/50 bg-emerald-500/70'
                  : 'border-white/15 bg-white/10'
              } ${settingsLoading || autoReplyEnabled === null ? 'opacity-60' : 'hover:brightness-110'}`}
            >
              <span
                className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition ${
                  autoReplyEnabled ? 'left-5' : 'left-1'
                }`}
              />
            </button>
          </div>
          <button
            onClick={() => void load()}
            className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/80 hover:bg-white/10"
            disabled={loading}
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {settingsError ? (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs text-amber-100">
          Auto-reply settings error: {settingsError}
        </div>
      ) : null}

      <div className="space-y-3">
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

        <div className="grid gap-4 xl:grid-cols-[320px_1fr]">
          <div className="space-y-3">
            <div className="rounded-2xl glass-card px-4 py-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-white/50">Topics</div>
              {topicIndex.length === 0 ? (
                <div className="mt-2 text-xs text-white/50">Topics will appear after reflections run.</div>
              ) : (
                <div className="mt-2 flex flex-wrap gap-2">
                  {topicIndex.map((topic) => (
                    <button
                      key={topic}
                      onClick={() => {
                        setActiveTopic(topic)
                        const match = rootEntriesAll.find((entry) => extractTopics(entry).includes(topic))
                        if (match) setSelectedRootId(match.id)
                      }}
                      className={`rounded-full border px-2 py-1 text-[11px] uppercase tracking-wide ${
                        activeTopic === topic
                          ? 'border-sky-400/40 bg-sky-500/20 text-sky-100'
                          : 'border-white/10 bg-white/5 text-white/60 hover:bg-white/10'
                      }`}
                    >
                      {topic}
                    </button>
                  ))}
                  {activeTopic ? (
                    <button
                      onClick={() => setActiveTopic(null)}
                      className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[11px] uppercase tracking-wide text-white/50 hover:bg-white/10"
                    >
                      Clear
                    </button>
                  ) : null}
                </div>
              )}
            </div>

            <div className="rounded-2xl glass-card px-4 py-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-white/50">Threads</div>
              <div className="mt-3 space-y-2">
                {rootEntries.length === 0 ? (
                  <div className="text-xs text-white/50">No threads yet.</div>
                ) : (
                  rootEntries.map((entry) => {
                    const topics = extractTopics(entry).slice(0, 4)
                    const isActive = entry.id === selectedRootId
                    return (
                      <button
                        key={entry.id}
                        onClick={() => setSelectedRootId(entry.id)}
                        className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                          isActive
                            ? 'border-sky-400/40 bg-sky-500/10'
                            : 'border-white/10 bg-white/5 hover:bg-white/10'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="text-xs font-semibold text-white">{entry.title}</div>
                            <div className="mt-1 text-[11px] text-white/50">{formatTimestamp(entry.created_at)}</div>
                          </div>
                          <span
                            className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide ${entryAccent(entry.entry_type)}`}
                          >
                            {(entry.entry_type || 'note').replace(/_/g, ' ')}
                          </span>
                        </div>
                        {topics.length > 0 ? (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {topics.map((topic) => (
                              <span
                                key={topic}
                                className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/50"
                              >
                                {topic}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </button>
                    )
                  })
                )}
              </div>
            </div>
          </div>

          <div className="space-y-3">
            {!selectedRootId ? (
              <div className="rounded-2xl glass-card px-4 py-6 text-sm text-white/60">
                Select a thread to view its journal conversation.
              </div>
            ) : (
              <>
                <div className="rounded-2xl glass-card px-4 py-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-white/50">Thread</div>
                  <div className="mt-3 space-y-3">
                    {threadEntries.map((entry) => {
                      const replyTo = getReplyTo(entry)
                      const replyToText = replyTo ? `Reply to #${replyTo}` : null
                      const meta = entry.meta as Record<string, unknown> | null | undefined
                      let author = meta && typeof meta.author === 'string' ? meta.author : null
                      if (author === 'user') author = 'You'
                      if (author === 'system') author = 'System'
                      const topics = entry.id === selectedRootId ? extractTopics(entry) : []
                      const sourceType =
                        meta && typeof meta.source_entry_type === 'string' ? String(meta.source_entry_type) : null
                      const metaLine = [replyToText, sourceType ? `Source: ${sourceType}` : null]
                        .filter(Boolean)
                        .join(' | ')
                      const entryLabel = (entry.entry_type || 'note').replace(/_/g, ' ')

                      return (
                        <div key={entry.id} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="text-sm font-semibold text-white">{entry.title}</div>
                              <div className="mt-1 text-[11px] text-white/50">{formatTimestamp(entry.created_at)}</div>
                              {author ? <div className="mt-1 text-[11px] text-white/40">By {author}</div> : null}
                              {metaLine ? <div className="mt-1 text-[11px] text-white/40">{metaLine}</div> : null}
                            </div>
                            <div className="flex flex-col items-end gap-2">
                              <span
                                className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide ${entryAccent(entry.entry_type)}`}
                              >
                                {entryLabel}
                              </span>
                              <button
                                onClick={() => setReplyTargetId(entry.id)}
                                className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/60 hover:bg-white/10"
                              >
                                Reply
                              </button>
                            </div>
                          </div>
                          <div className="mt-3 whitespace-pre-line text-sm text-white/80">{entry.body}</div>
                          {topics.length > 0 ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              {topics.map((topic) => (
                                <button
                                  key={topic}
                                  onClick={() => setActiveTopic(topic)}
                                  className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/50 hover:bg-white/10"
                                >
                                  {topic}
                                </button>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      )
                    })}
                  </div>
                </div>

                <div className="rounded-2xl glass-card px-4 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-xs font-semibold uppercase tracking-wide text-white/50">Add a comment</div>
                    {replyTargetId ? (
                      <div className="text-[11px] text-white/50">Replying to #{replyTargetId}</div>
                    ) : null}
                  </div>
                  <textarea
                    value={commentBody}
                    onChange={(event) => setCommentBody(event.target.value)}
                    placeholder="Share a thought in this thread..."
                    className="mt-3 min-h-[90px] w-full resize-none rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-white placeholder:text-white/40 focus:outline-none"
                  />
                  {commentError ? <div className="mt-2 text-xs text-rose-200">{commentError}</div> : null}
                  <div className="mt-3 flex items-center justify-end gap-2">
                    <button
                      onClick={() => setReplyTargetId(selectedRootId)}
                      className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/60 hover:bg-white/10"
                      disabled={!selectedRootId}
                    >
                      Reply to root
                    </button>
                    <button
                      onClick={() => void submitReply()}
                      className="rounded-xl bg-sky-500 px-3 py-2 text-xs font-semibold text-white hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={posting || !selectedRootId}
                    >
                      {posting ? 'Posting...' : 'Post'}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
