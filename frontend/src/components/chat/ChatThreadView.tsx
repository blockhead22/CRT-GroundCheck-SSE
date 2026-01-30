import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChatThread, QuickAction } from '../../types'
import { MessageBubble } from './MessageBubble'
import { Composer } from './Composer'
import { QuickCards } from '../QuickCards'
import {
  listOpenContradictions,
  type ContradictionListItem,
} from '../../lib/api'

export function ChatThreadView(props: {
  thread: ChatThread
  typing: boolean
  onSend: (text: string) => void
  quickActions: QuickAction[]
  onPickQuickAction: (a: QuickAction) => void
  userName: string
  showSetNameCta?: boolean
  onRequestSetName?: () => void
  selectedMessageId: string | null
  onSelectAssistantMessage: (messageId: string) => void
  onResearch?: (query: string) => void
  researching?: boolean
  onOpenSourceInspector?: (memoryId: string) => void
  onOpenAgentPanel?: (messageId: string) => void
  xrayMode?: boolean
  // Streaming props
  streamingThinking?: string
  streamingResponse?: string
  isThinking?: boolean
  streamPhase?: string | null
  streamStatusLog?: string[]
}) {
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const draftScrollRef = useRef<HTMLDivElement | null>(null)
  const [queuedContradiction, setQueuedContradiction] = useState<{
    messageId: string
    total: number | null
    createdAt: number
  } | null>(null)
  const [trayOpen, setTrayOpen] = useState(false)
  const [contradictions, setContradictions] = useState<ContradictionListItem[]>([])
  const [contradictionsLoading, setContradictionsLoading] = useState(false)
  const [contradictionsError, setContradictionsError] = useState<string | null>(null)
  const [contradictionsLoaded, setContradictionsLoaded] = useState(false)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [props.thread.messages.length, props.typing, props.streamingThinking, props.streamingResponse])

  useEffect(() => {
    if (!props.streamingResponse) return
    const el = draftScrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [props.streamingResponse])

  useEffect(() => {
    setQueuedContradiction(null)
    setTrayOpen(false)
    setContradictions([])
    setContradictionsLoading(false)
    setContradictionsError(null)
    setContradictionsLoaded(false)
  }, [props.thread.id])

  const assistantSnapshot = useMemo(() => {
    let last: (typeof props.thread.messages)[number] | null = null
    let prev: (typeof props.thread.messages)[number] | null = null
    for (let i = props.thread.messages.length - 1; i >= 0; i -= 1) {
      const m = props.thread.messages[i]
      if (m.role !== 'assistant') continue
      if (!last) {
        last = m
      } else {
        prev = m
        break
      }
    }
    return { last, prev }
  }, [props.thread.messages])

  const lastAssistant = assistantSnapshot.last
  const prevAssistant = assistantSnapshot.prev
  const lastTotal = lastAssistant?.crt?.unresolved_contradictions_total ?? null
  const prevTotal = prevAssistant?.crt?.unresolved_contradictions_total ?? null
  const hasNewQueue =
    Boolean(lastAssistant?.crt?.contradiction_detected) ||
    (typeof lastTotal === 'number' && (typeof prevTotal === 'number' ? lastTotal > prevTotal : lastTotal > 0))

  useEffect(() => {
    if (!lastAssistant || !hasNewQueue) return
    if (queuedContradiction?.messageId === lastAssistant.id) return
    setQueuedContradiction({
      messageId: lastAssistant.id,
      total: typeof lastTotal === 'number' ? lastTotal : null,
      createdAt: lastAssistant.createdAt,
    })
  }, [lastAssistant, lastTotal, hasNewQueue, queuedContradiction?.messageId])

  useEffect(() => {
    if (!trayOpen) return
    let mounted = true
    setContradictionsLoading(true)
    setContradictionsError(null)
    listOpenContradictions(props.thread.id, 200)
      .then((items) => {
        if (!mounted) return
        setContradictions(items)
        setContradictionsLoaded(true)
      })
      .catch((err) => {
        if (!mounted) return
        setContradictionsError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!mounted) return
        setContradictionsLoading(false)
      })
    return () => {
      mounted = false
    }
  }, [trayOpen, props.thread.id, lastAssistant?.id])

  useEffect(() => {
    if (trayOpen) return
    if (typeof lastTotal === 'number') return
    let mounted = true
    listOpenContradictions(props.thread.id, 200)
      .then((items) => {
        if (!mounted) return
        setContradictions(items)
        setContradictionsLoaded(true)
      })
      .catch((err) => {
        if (!mounted) return
        setContradictionsError(err instanceof Error ? err.message : String(err))
      })
    return () => {
      mounted = false
    }
  }, [trayOpen, props.thread.id, lastAssistant?.id, lastTotal])

  const empty = props.thread.messages.length === 0
  const openCount =
    typeof lastTotal === 'number'
      ? lastTotal
      : contradictions.length
  const queuedCount = queuedContradiction
    ? (typeof queuedContradiction.total === 'number' ? queuedContradiction.total : openCount || 1)
    : openCount
  const hasOpenContradictions = queuedCount > 0
  const showBanner = hasOpenContradictions || Boolean(queuedContradiction)
  const bannerTitle = queuedContradiction ? 'Contradiction queued' : 'Contradictions'
  const bannerAccentClass = hasOpenContradictions ? 'text-rose-200/60' : 'text-white/40'
  useEffect(() => {
    if (!contradictionsLoaded) return
    if (openCount === 0) {
      setQueuedContradiction(null)
    }
  }, [openCount, contradictionsLoaded])

  async function refreshContradictions(silent = false) {
    if (!silent) setContradictionsLoading(true)
    setContradictionsError(null)
    try {
      const items = await listOpenContradictions(props.thread.id, 200)
      setContradictions(items)
      setContradictionsLoaded(true)
    } catch (err) {
      setContradictionsError(err instanceof Error ? err.message : String(err))
    } finally {
      if (!silent) setContradictionsLoading(false)
    }
  }

  const hint = useMemo(() => {
    if (!empty) return null

    const displayName = (props.userName || '').trim() || 'there'
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="w-full max-w-[760px]"
      >
        <div className="text-center">
          <div className="bg-gradient-to-r from-violet-300 via-violet-200 to-white bg-clip-text text-4xl font-semibold text-transparent md:text-5xl">
            Hello {displayName}
          </div>
          <div className="mt-2 text-xl font-medium text-white/60 md:text-2xl">How can I help you today?</div>

          {props.showSetNameCta ? (
            <div className="mt-5 flex justify-center">
              <button
                onClick={props.onRequestSetName}
                className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/80 hover:bg-white/10"
              >
                Set your name
              </button>
            </div>
          ) : null}
        </div>
        <div className="mt-10">
          <QuickCards actions={props.quickActions} onPick={props.onPickQuickAction} />
        </div>
      </motion.div>
    )
  }, [empty, props.onPickQuickAction, props.quickActions, props.userName])

  const selectedMessageId = props.selectedMessageId

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-hidden px-2 py-4 md:px-6">
        <div className="mx-auto flex h-full w-full max-w-[1180px] gap-4">
          <div className="min-w-0 flex-1 overflow-auto">
            <div className="flex w-full flex-col gap-3">
              {hint}

              <AnimatePresence initial={false}>
                {props.thread.messages.map((m) => (
                  <div key={m.id}>
                    <MessageBubble
                      msg={m}
                      threadId={props.thread.id}
                      selected={m.id === selectedMessageId}
                      onInspect={(messageId) => props.onSelectAssistantMessage(messageId)}
                      onOpenSourceInspector={props.onOpenSourceInspector}
                      onOpenAgentPanel={props.onOpenAgentPanel}
                      xrayMode={props.xrayMode}
                    />
                  </div>
                ))}
              </AnimatePresence>

              {/* Streaming CRT pipeline status */}
              {props.streamStatusLog && props.streamStatusLog.length > 0 ? (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18 }}
                  className="flex justify-start"
                >
                  <div className="max-w-[85%] rounded-2xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-3 text-xs text-cyan-100 shadow-card">
                    <div className="mb-2 font-semibold text-cyan-200">CRT Pipeline</div>
                    <ul className="space-y-1">
                      {props.streamStatusLog.map((status, idx) => (
                        <li key={`${status}-${idx}`} className="flex items-start gap-2 text-white/70">
                          <span className="mt-1 h-1.5 w-1.5 rounded-full bg-cyan-400" />
                          <span>{status}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </motion.div>
              ) : null}

              {/* Streaming thinking display */}
              {props.streamPhase ? (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18 }}
                  className="flex justify-start"
                >
                  <div className="rounded-2xl border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-200 shadow-card">
                    Phase: {props.streamPhase.charAt(0).toUpperCase() + props.streamPhase.slice(1)}
                  </div>
                </motion.div>
              ) : null}

              {props.isThinking && props.streamingThinking ? (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18 }}
                  className="flex justify-start"
                >
                  <div className="max-w-[85%] rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm shadow-card">
                    <div className="mb-2 flex items-center gap-2 text-amber-400">
                      <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
                      <span className="font-medium">Thinking...</span>
                    </div>
                    <div className="max-h-[200px] overflow-y-auto whitespace-pre-wrap text-white/70">
                      {props.streamingThinking}
                    </div>
                  </div>
                </motion.div>
              ) : null}

              {/* Streaming response display */}
              {props.streamingResponse && !props.isThinking ? (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18 }}
                  className="flex justify-start"
                >
                  <div className="max-w-[85%] rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/90 shadow-card">
                    <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-white/40">
                      Draft
                    </div>
                    <div
                      ref={draftScrollRef}
                      className="max-h-[260px] overflow-y-auto whitespace-pre-wrap pr-2 text-white/80 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
                      style={{
                        WebkitMaskImage:
                          'linear-gradient(to bottom, rgba(0,0,0,0) 0%, rgba(0,0,0,1) 20%, rgba(0,0,0,1) 80%, rgba(0,0,0,0) 100%)',
                        maskImage:
                          'linear-gradient(to bottom, rgba(0,0,0,0) 0%, rgba(0,0,0,1) 20%, rgba(0,0,0,1) 80%, rgba(0,0,0,0) 100%)',
                      }}
                    >
                      {props.streamingResponse}
                    </div>
                    <span className="ml-1 inline-block h-4 w-1 animate-pulse bg-violet-500" />
                  </div>
                </motion.div>
              ) : null}

              {/* Simple typing indicator (when not streaming) */}
              {props.typing && !props.streamingThinking && !props.streamingResponse ? (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18 }}
                  className="flex justify-start"
                >
                  <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/70 shadow-card">
                    <span className="inline-flex items-center gap-2">
                      <span className="h-2 w-2 animate-pulse rounded-full bg-violet-500" />
                      CRT is thinking…
                    </span>
                  </div>
                </motion.div>
              ) : null}

              <div ref={bottomRef} />
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-white/10 bg-white/5 px-4 py-4 backdrop-blur-xl">
        <div className="mx-auto w-full max-w-[1180px]">
          <AnimatePresence initial={false}>
            {showBanner ? (
              <motion.div
                key="contradiction-queued"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                transition={{ duration: 0.2 }}
                className="mb-3"
              >
                <AnimatePresence initial={false}>
                  {trayOpen ? (
                    <motion.div
                      key="contradiction-tray"
                      initial={{ opacity: 0, height: 0, y: 6 }}
                      animate={{ opacity: 1, height: 'auto', y: 0 }}
                      exit={{ opacity: 0, height: 0, y: 6 }}
                      transition={{ duration: 0.2 }}
                      className="mb-2 overflow-hidden"
                    >
                      <div className="max-h-[440px] overflow-y-auto rounded-xl border border-white/10 bg-black/30 px-3 py-3 text-xs text-white/70 shadow-card">
                        <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                          <div className="flex items-center justify-between">
                            <div className="text-xs font-semibold text-white/70">Open contradictions</div>
                            <button
                              type="button"
                              onClick={() => void refreshContradictions()}
                              className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-white/70 hover:bg-white/10"
                            >
                              Refresh
                            </button>
                          </div>
                          <div className="mt-2">
                            {contradictionsLoading ? (
                              <div className="text-white/60">Loading contradictions...</div>
                            ) : contradictionsError ? (
                              <div className="text-rose-300">Failed to load contradictions: {contradictionsError}</div>
                            ) : contradictions.length === 0 ? (
                              <div className="text-white/60">No open contradictions.</div>
                            ) : (
                              <div className="space-y-2">
                                {contradictions.map((c) => {
                                  const title = (c.slot || c.contradiction_type || 'Contradiction').toUpperCase()
                                  const summary = c.summary || c.query || ''
                                  const oldValue = (c.old_value || c.old_memory_id || 'N/A').trim()
                                  const newValue = (c.new_value || c.new_memory_id || 'N/A').trim()
                                  return (
                                    <div key={c.ledger_id} className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">
                                      <div className="flex items-start justify-between gap-3">
                                        <div className="text-xs font-semibold text-rose-100">{title}</div>
                                        <div className="text-[10px] text-white/40">{(c.status || 'pending').toUpperCase()}</div>
                                      </div>
                                      {summary ? (
                                        <div className="mt-1 line-clamp-2 text-[11px] text-white/70">{summary}</div>
                                      ) : null}
                                      <div className="mt-2 grid gap-1 text-[11px] text-white/60">
                                        <div className="flex gap-2">
                                          <span className="text-white/40">Old:</span>
                                          <span className="line-clamp-2">{oldValue}</span>
                                        </div>
                                        <div className="flex gap-2">
                                          <span className="text-white/40">New:</span>
                                          <span className="line-clamp-2">{newValue}</span>
                                        </div>
                                      </div>
                                    </div>
                                  )
                                })}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ) : null}
                </AnimatePresence>
                <button
                  type="button"
                  onClick={() => setTrayOpen((v) => !v)}
                  className={
                    'flex w-full items-center justify-between rounded-xl border px-3 py-2 text-xs shadow-card transition ' +
                    (hasOpenContradictions
                      ? 'border-rose-500/30 bg-rose-500/10 text-rose-100 hover:bg-rose-500/15'
                      : 'border-white/10 bg-white/5 text-white/60 hover:bg-white/10')
                  }
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={
                        'h-2 w-2 rounded-full ' +
                        (hasOpenContradictions ? 'animate-pulse bg-rose-400' : 'bg-white/30')
                      }
                    />
                    <span
                      className={
                        'inline-flex min-w-[20px] items-center justify-center rounded-full border px-1.5 text-[11px] font-semibold ' +
                        (hasOpenContradictions
                          ? 'border-rose-400/40 bg-rose-500/20 text-rose-100'
                          : 'border-white/10 bg-white/5 text-white/60')
                      }
                    >
                      {queuedCount}
                    </span>
                    <span className="font-semibold">{bannerTitle}</span>
                  </div>
                  <div className={`flex items-center gap-2 ${bannerAccentClass}`}>
                    <span className="text-[11px]">{trayOpen ? 'Hide list' : 'View list'}</span>
                    <span className="text-[11px]">{trayOpen ? '^' : 'v'}</span>
                  </div>
                </button>
              </motion.div>
            ) : null}
          </AnimatePresence>
          <Composer
            onSend={props.onSend}
            onResearch={props.onResearch}
            researching={props.researching}
          />
        </div>
      </div>
    </div>
  )
}
