import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChatThread, QuickAction } from '../../types'
import { MessageBubble } from './MessageBubble'
import { Composer } from './Composer'
import { QuickCards } from '../QuickCards'
import {
  getContradictionNext,
  listOpenContradictions,
  markContradictionAsked,
  respondToContradiction,
  type ContradictionListItem,
  type ContradictionNextResponse,
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
}) {
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const [queuedContradiction, setQueuedContradiction] = useState<{
    messageId: string
    total: number | null
    createdAt: number
  } | null>(null)
  const [trayOpen, setTrayOpen] = useState(false)
  const [contradictions, setContradictions] = useState<ContradictionListItem[]>([])
  const [contradictionsLoading, setContradictionsLoading] = useState(false)
  const [contradictionsError, setContradictionsError] = useState<string | null>(null)
  const [nextContra, setNextContra] = useState<ContradictionNextResponse | null>(null)
  const [contraAnswer, setContraAnswer] = useState('')
  const [contraBusy, setContraBusy] = useState(false)
  const [contraError, setContraError] = useState<string | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [props.thread.messages.length, props.typing, props.streamingThinking, props.streamingResponse])

  useEffect(() => {
    setQueuedContradiction(null)
    setTrayOpen(false)
    setContradictions([])
    setContradictionsLoading(false)
    setContradictionsError(null)
    setNextContra(null)
    setContraAnswer('')
    setContraBusy(false)
    setContraError(null)
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
    setContraError(null)
    listOpenContradictions(props.thread.id, 200)
      .then((items) => {
        if (!mounted) return
        setContradictions(items)
      })
      .catch((err) => {
        if (!mounted) return
        setContradictionsError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!mounted) return
        setContradictionsLoading(false)
      })
    getContradictionNext(props.thread.id)
      .then((nxt) => {
        if (!mounted) return
        setNextContra(nxt)
      })
      .catch((err) => {
        if (!mounted) return
        setContraError(err instanceof Error ? err.message : String(err))
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
      })
      .catch((err) => {
        if (!mounted) return
        setContradictionsError(err instanceof Error ? err.message : String(err))
      })
    return () => {
      mounted = false
    }
  }, [trayOpen, props.thread.id, lastAssistant?.id, lastTotal])

  useEffect(() => {
    setContraAnswer('')
  }, [nextContra?.item?.ledger_id])

  const empty = props.thread.messages.length === 0
  const openCount =
    typeof lastTotal === 'number'
      ? lastTotal
      : contradictions.length
  const queuedCount = queuedContradiction
    ? (typeof queuedContradiction.total === 'number' ? queuedContradiction.total : openCount || 1)
    : openCount
  const hasOpenContradictions = queuedCount > 0
  const bannerTitle = queuedContradiction ? 'Contradiction queued' : 'Contradictions'
  const bannerAccentClass = hasOpenContradictions ? 'text-rose-200/60' : 'text-white/40'
  const nextDetail = useMemo(() => {
    if (!nextContra?.item) return null
    return contradictions.find((c) => c.ledger_id === nextContra.item.ledger_id) ?? null
  }, [nextContra?.item?.ledger_id, contradictions])

  const suggestedOption = useMemo(() => {
    if (!nextDetail) return null
    const slot = (nextDetail.slot || '').trim()
    const oldValue = (nextDetail.old_value || '').trim()
    const newValue = (nextDetail.new_value || '').trim()
    if (!slot || (!oldValue && !newValue)) return null

    const threshold = 0.25
    const delta = typeof nextDetail.confidence_delta === 'number' ? nextDetail.confidence_delta : null
    const oldTrust = typeof nextDetail.old_trust === 'number' ? nextDetail.old_trust : null
    const newTrust = typeof nextDetail.new_trust === 'number' ? nextDetail.new_trust : null

    let pick: 'old' | 'new' | null = null
    if (delta !== null) {
      if (delta >= threshold) pick = 'old'
      if (delta <= -threshold) pick = 'new'
    } else if (oldTrust !== null && newTrust !== null) {
      if (oldTrust - newTrust >= threshold) pick = 'old'
      if (newTrust - oldTrust >= threshold) pick = 'new'
    }

    if (!pick) return null
    const value = pick === 'old' ? oldValue : newValue
    if (!value) return null
    return {
      label: pick === 'old' ? 'Prefer old value' : 'Prefer new value',
      value: `${slot} = ${value}`,
    }
  }, [nextDetail])

  function safeCopy(text: string) {
    try {
      void navigator.clipboard.writeText(text)
    } catch {
      // ignore
    }
  }

  async function refreshContradictions(silent = false) {
    if (!silent) setContradictionsLoading(true)
    setContradictionsError(null)
    try {
      const items = await listOpenContradictions(props.thread.id, 200)
      setContradictions(items)
    } catch (err) {
      setContradictionsError(err instanceof Error ? err.message : String(err))
    } finally {
      if (!silent) setContradictionsLoading(false)
    }
  }

  async function refreshNextContra() {
    setContraError(null)
    try {
      const nxt = await getContradictionNext(props.thread.id)
      setNextContra(nxt)
    } catch (err) {
      setContraError(err instanceof Error ? err.message : String(err))
    }
  }

  async function doMarkAsked() {
    const item = nextContra?.item
    if (!item) return
    setContraBusy(true)
    setContraError(null)
    try {
      await markContradictionAsked({ threadId: props.thread.id, ledgerId: item.ledger_id })
      await refreshNextContra()
    } catch (err) {
      setContraError(err instanceof Error ? err.message : String(err))
    } finally {
      setContraBusy(false)
    }
  }

  async function doRespond(resolve: boolean) {
    const item = nextContra?.item
    if (!item) return
    setContraBusy(true)
    setContraError(null)
    try {
      const res = await respondToContradiction({
        threadId: props.thread.id,
        ledgerId: item.ledger_id,
        answer: contraAnswer,
        resolve,
        resolutionMethod: 'user_clarified',
        newStatus: resolve ? 'resolved' : 'open',
      })
      setContraAnswer('')
      setNextContra(res.next)
      void refreshContradictions()
    } catch (err) {
      setContraError(err instanceof Error ? err.message : String(err))
    } finally {
      setContraBusy(false)
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
                  <div
                    key={m.id}
                    onClick={() => {
                      if (m.role === 'assistant') props.onSelectAssistantMessage(m.id)
                    }}
                    className={
                      m.role === 'assistant'
                        ? 'cursor-pointer rounded-2xl ring-1 ring-transparent hover:ring-white/10'
                        : undefined
                    }
                    title={m.role === 'assistant' ? 'Click to inspect CRT details' : undefined}
                  >
                    <MessageBubble
                      msg={m}
                      threadId={props.thread.id}
                      selected={m.id === selectedMessageId}
                      onOpenSourceInspector={props.onOpenSourceInspector}
                      onOpenAgentPanel={props.onOpenAgentPanel}
                      xrayMode={props.xrayMode}
                    />
                  </div>
                ))}
              </AnimatePresence>

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
                    <div className="whitespace-pre-wrap">{props.streamingResponse}</div>
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
                      <div className="space-y-3">
                        <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                          <div className="flex items-center justify-between">
                            <div className="text-xs font-semibold text-white/70">Contradiction workflow</div>
                            <button
                              type="button"
                              onClick={() => {
                                void refreshNextContra()
                                void refreshContradictions()
                              }}
                              className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-white/70 hover:bg-white/10"
                            >
                              Refresh
                            </button>
                          </div>

                          {contraError ? (
                            <div className="mt-2 text-[11px] text-rose-300">Failed to load work item: {contraError}</div>
                          ) : null}

                          {!nextContra?.has_item || !nextContra?.item ? (
                            <div className="mt-2 text-[11px] text-white/60">
                              No open contradiction work item found for this thread.
                            </div>
                          ) : (
                            <div className="mt-2 space-y-3">
                              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                                <div className="flex items-start justify-between gap-3">
                                  <div>
                                    <div className="text-xs font-semibold text-rose-100">{nextContra.item.contradiction_type}</div>
                                    <div className="mt-0.5 text-[10px] text-white/40">{nextContra.item.ledger_id}</div>
                                  </div>
                                  <div className="text-[10px] text-white/50">
                                    drift {nextContra.item.drift_mean.toFixed(2)} / asks {nextContra.item.ask_count}
                                  </div>
                                </div>
                                {nextContra.item.summary ? (
                                  <div className="mt-2 text-[11px] text-white/70">{nextContra.item.summary}</div>
                                ) : null}
                                <div className="mt-2 flex flex-wrap gap-2">
                                  {nextContra.item.next_action ? (
                                    <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-200">
                                      Suggested: {nextContra.item.next_action.replace(/_/g, ' ')}
                                    </span>
                                  ) : null}
                                  <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-white/60">
                                    Status: {nextContra.item.status || 'open'}
                                  </span>
                                </div>
                              </div>

                              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                                <div className="flex items-center justify-between">
                                  <div className="text-[11px] font-semibold text-white/60">Suggested question</div>
                                  <div className="flex items-center gap-2">
                                    <button
                                      type="button"
                                      onClick={() => safeCopy(nextContra.item.suggested_question)}
                                      className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-white/70 hover:bg-white/10"
                                    >
                                      Copy
                                    </button>
                                    <button
                                      type="button"
                                      disabled={contraBusy}
                                      onClick={() => void doMarkAsked()}
                                      className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-white/70 hover:bg-white/10 disabled:opacity-50"
                                    >
                                      Mark asked
                                    </button>
                                  </div>
                                </div>
                                <pre className="mt-2 whitespace-pre-wrap rounded-lg border border-white/10 bg-black/30 p-2 text-[11px] text-white/80">
                                  {nextContra.item.suggested_question}
                                </pre>
                              </div>

                              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                                <div className="text-[11px] font-semibold text-white/60">User clarification</div>
                                <textarea
                                  value={contraAnswer}
                                  onChange={(e) => setContraAnswer(e.target.value)}
                                  placeholder="Example: Employer = Amazon"
                                  className="mt-2 h-24 w-full resize-none rounded-lg border border-white/10 bg-black/30 p-2 text-[11px] text-white outline-none placeholder:text-white/30 focus:border-violet-500/40"
                                />
                                {suggestedOption ? (
                                  <button
                                    type="button"
                                    onClick={() => setContraAnswer(suggestedOption.value)}
                                    className="mt-2 inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-200 hover:bg-emerald-500/20"
                                    title={suggestedOption.value}
                                  >
                                    Suggested: {suggestedOption.label}
                                  </button>
                                ) : null}
                                <div className="mt-2 flex flex-wrap gap-2">
                                  <button
                                    type="button"
                                    disabled={contraBusy || !contraAnswer.trim()}
                                    onClick={() => void doRespond(true)}
                                    className="rounded-full bg-violet-600 px-3 py-1.5 text-[10px] font-semibold text-white hover:bg-violet-500 disabled:opacity-50"
                                  >
                                    Record answer + resolve
                                  </button>
                                  <button
                                    type="button"
                                    disabled={contraBusy || !contraAnswer.trim()}
                                    onClick={() => void doRespond(false)}
                                    className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[10px] text-white/70 hover:bg-white/10 disabled:opacity-50"
                                  >
                                    Record answer only
                                  </button>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>

                        <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                          <div className="flex items-center justify-between">
                            <div className="text-xs font-semibold text-white/70">Open contradictions</div>
                            <div className="text-[10px] text-white/40">{contradictions.length} total</div>
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
                  <span className="text-[11px]">{trayOpen ? 'Hide workflow' : 'View workflow'}</span>
                  <span className="text-[11px]">{trayOpen ? '^' : 'v'}</span>
                </div>
              </button>
            </motion.div>
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
