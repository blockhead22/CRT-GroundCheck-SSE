import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatThread, QuickAction } from '../../types'
import { MessageBubble } from './MessageBubble'
import { Composer } from './Composer'
import { listOpenContradictions, type ContradictionListItem } from '../../lib/api'

// Adaptive font size for theater mode — shrinks as text grows
function theaterFontSize(charCount: number): string {
  if (charCount < 80)  return '2.75rem'
  if (charCount < 200) return '2.1rem'
  if (charCount < 400) return '1.65rem'
  if (charCount < 700) return '1.35rem'
  return '1.1rem'
}

// Blinking cursor for streaming
function StreamCursor() {
  return (
    <span
      className="inline-block w-[2px] h-[1em] align-middle ml-0.5 animate-[blink_1s_step-end_infinite]"
      style={{ verticalAlign: '-0.1em', background: 'var(--accent-2)' }}
    />
  )
}

// Phase label map
const PHASE_LABELS: Record<string, string> = {
  analyze: 'READING',
  plan: 'PLANNING',
  answer: 'WRITING',
}

// Streaming message — editorial style with rich phase/status display
function StreamingMessage({
  content,
  isThinking,
  phase,
  statusLog,
  thinkingContent,
}: {
  content: string
  isThinking: boolean
  phase: string | null
  statusLog: string[]
  thinkingContent: string
}) {
  const hasContent = Boolean(content)
  const currentPhaseLabel = isThinking
    ? 'THINKING'
    : phase ? (PHASE_LABELS[phase] ?? phase.toUpperCase()) : 'PROCESSING'

  // Latest human-readable status (filter out raw ctrl: lines)
  const lastStatus = statusLog
    .slice()
    .reverse()
    .find((s) => !s.startsWith('ctrl:') && s !== 'Processing message...')

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* Pre-content pipeline activity */}
      {!hasContent && (
        <div className="mb-4">
          {/* Big phase label — Syne display font */}
          <div className="flex items-baseline gap-3 mb-2">
            <span
              className="font-display text-2xl tracking-tight"
              style={{ color: 'var(--accent-2)', opacity: 0.9 }}
            >
              {currentPhaseLabel}
            </span>
            <span className="flex gap-1 items-center">
              {[0, 0.2, 0.4].map((d, i) => (
                <span
                  key={i}
                  className="h-1 w-1 rounded-full animate-bounce"
                  style={{ background: 'var(--accent-2)', opacity: 0.6, animationDelay: `${d}s`, animationDuration: '0.8s' }}
                />
              ))}
            </span>
          </div>

          {/* Thinking preview */}
          {isThinking && thinkingContent && (
            <div
              className="mb-3 overflow-hidden rounded-xl border px-3 py-2 text-[12px] italic leading-relaxed"
              style={{ borderColor: 'var(--border-soft)', background: 'var(--surface)', color: 'var(--text-muted)' }}
            >
              <div
                className="line-clamp-3"
                style={{
                  maskImage: 'linear-gradient(to bottom, white 30%, transparent 100%)',
                  WebkitMaskImage: 'linear-gradient(to bottom, white 30%, transparent 100%)',
                }}
              >
                {thinkingContent}
              </div>
            </div>
          )}

          {/* Pipeline status tags */}
          {statusLog.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {statusLog
                .filter((s) => !s.startsWith('ctrl:') && s !== 'Processing message...')
                .slice(-4)
                .map((s, i) => (
                  <AnimatePresence key={s} mode="wait">
                    <motion.span
                      initial={{ opacity: 0, scale: 0.85, x: -4 }}
                      animate={{ opacity: 1, scale: 1, x: 0 }}
                      transition={{ duration: 0.15, delay: i * 0.04 }}
                      className="rounded-full px-2 py-0.5 text-[10px] font-mono"
                      style={{ background: 'var(--surface-3)', color: 'var(--text-muted)', border: '1px solid var(--border-soft)' }}
                    >
                      {s}
                    </motion.span>
                  </AnimatePresence>
                ))}
              {/* Show raw last status if nothing human-readable */}
              {!lastStatus && statusLog.length > 0 && (
                <span
                  className="rounded-full px-2 py-0.5 text-[10px] font-mono"
                  style={{ background: 'var(--surface-3)', color: 'var(--text-faint)', border: '1px solid var(--border-soft)' }}
                >
                  {statusLog[statusLog.length - 1].replace(/^ctrl:/, '')}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Thinking preview when content IS streaming */}
      {hasContent && isThinking && thinkingContent && (
        <div
          className="mb-3 overflow-hidden rounded-xl border px-3 py-2 text-[12px] italic leading-relaxed"
          style={{ borderColor: 'var(--border-soft)', background: 'var(--surface)', color: 'var(--text-muted)' }}
        >
          <div className="line-clamp-2">{thinkingContent}</div>
        </div>
      )}

      {/* Streaming text */}
      {hasContent && (
        <div className="text-[15px] text-white/90 leading-[1.75]">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p({ children }: any) { return <p className="mb-3 last:mb-0">{children}</p> },
              ul({ children }: any) { return <ul className="mb-3 space-y-1.5 pl-5">{children}</ul> },
              ol({ children }: any) { return <ol className="mb-3 list-decimal space-y-1.5 pl-5">{children}</ol> },
              li({ children }: any) { return <li className="text-white/80 leading-relaxed">{children}</li> },
              code({ children, className }: any) {
                const codeText = String(children ?? '').replace(/\n$/, '')
                const match = /language-([a-zA-Z0-9_-]+)/.exec(className || '')
                if (!match && !codeText.includes('\n')) {
                  return <code className="rounded-md bg-white/8 px-1.5 py-0.5 font-mono text-[0.88em]" style={{ color: 'var(--accent-6)' }}>{children}</code>
                }
                return <pre className="my-2 overflow-x-auto rounded-xl border border-white/10 bg-black/40 p-4 text-sm text-white/80 font-mono">{codeText}</pre>
              },
            } as any}
          >
            {content}
          </ReactMarkdown>
          <StreamCursor />
        </div>
      )}
    </motion.div>
  )
}

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
  streamingThinking?: string
  streamingResponse?: string
  isThinking?: boolean
  streamStatusLog?: string[]
  streamPhase?: string | null
}) {
  const empty = props.thread.messages.length === 0

  const bottomRef = useRef<HTMLDivElement | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const theaterLockRef = useRef(false)  // prevents immediate re-entry after exiting theater
  const [theaterMode, setTheaterMode] = useState(false)
  const [trayOpen, setTrayOpen] = useState(false)
  const [contradictions, setContradictions] = useState<ContradictionListItem[]>([])
  const [contradictionsLoading, setContradictionsLoading] = useState(false)
  const [contradictionsError, setContradictionsError] = useState<string | null>(null)
  const [contradictionsLoaded, setContradictionsLoaded] = useState(false)
  const [queuedContradiction, setQueuedContradiction] = useState<{
    messageId: string
    total: number | null
    createdAt: number
  } | null>(null)

  // Detect scroll-to-bottom in history mode → snap back to theater
  const handleScroll = useCallback(() => {
    if (theaterLockRef.current) return
    const el = scrollRef.current
    if (!el) return
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight
    if (dist < 80) setTheaterMode(true)
  }, [])

  // Scroll to bottom when entering history mode or when new content arrives
  useEffect(() => {
    if (theaterMode) return
    bottomRef.current?.scrollIntoView({ behavior: 'instant', block: 'end' })
  }, [theaterMode])

  useEffect(() => {
    if (theaterMode) return
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [props.thread.messages.length, props.streamingResponse, props.isThinking])

  // Enter theater mode when first message arrives
  useEffect(() => {
    if (!empty) setTheaterMode(true)
  }, [empty])

  // Reset on thread change
  useEffect(() => {
    setTheaterMode(false)
    setQueuedContradiction(null)
    setTrayOpen(false)
    setContradictions([])
    setContradictionsLoaded(false)
    setContradictionsError(null)
  }, [props.thread.id])

  const assistantSnapshot = useMemo(() => {
    let last: (typeof props.thread.messages)[number] | null = null
    let prev: (typeof props.thread.messages)[number] | null = null
    for (let i = props.thread.messages.length - 1; i >= 0; i--) {
      const m = props.thread.messages[i]
      if (m.role !== 'assistant') continue
      if (!last) { last = m } else { prev = m; break }
    }
    return { last, prev }
  }, [props.thread.messages])

  const lastAssistant = assistantSnapshot.last
  const prevAssistant = assistantSnapshot.prev

  const lastUserMsg = useMemo(() => {
    for (let i = props.thread.messages.length - 1; i >= 0; i--) {
      if (props.thread.messages[i].role === 'user') return props.thread.messages[i]
    }
    return null
  }, [props.thread.messages])
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
    listOpenContradictions(props.thread.id, 200)
      .then((items) => { if (mounted) { setContradictions(items); setContradictionsLoaded(true) } })
      .catch((err) => { if (mounted) setContradictionsError(err instanceof Error ? err.message : String(err)) })
      .finally(() => { if (mounted) setContradictionsLoading(false) })
    return () => { mounted = false }
  }, [trayOpen, props.thread.id, lastAssistant?.id])

  useEffect(() => {
    if (trayOpen || typeof lastTotal === 'number') return
    let mounted = true
    listOpenContradictions(props.thread.id, 200)
      .then((items) => { if (mounted) { setContradictions(items); setContradictionsLoaded(true) } })
      .catch((err) => { if (mounted) setContradictionsError(err instanceof Error ? err.message : String(err)) })
    return () => { mounted = false }
  }, [trayOpen, props.thread.id, lastAssistant?.id, lastTotal])

  async function refreshContradictions() {
    setContradictionsLoading(true)
    try {
      const items = await listOpenContradictions(props.thread.id, 200)
      setContradictions(items)
      setContradictionsLoaded(true)
    } catch (err) {
      setContradictionsError(err instanceof Error ? err.message : String(err))
    } finally {
      setContradictionsLoading(false)
    }
  }

  useEffect(() => {
    if (contradictionsLoaded && (typeof lastTotal === 'number' ? lastTotal : contradictions.length) === 0) {
      setQueuedContradiction(null)
    }
  }, [contradictions.length, contradictionsLoaded, lastTotal])

  const openCount = typeof lastTotal === 'number' ? lastTotal : contradictions.length
  const queuedCount = queuedContradiction
    ? (typeof queuedContradiction.total === 'number' ? queuedContradiction.total : openCount || 1)
    : openCount
  const hasOpenContradictions = queuedCount > 0
  const showBanner = hasOpenContradictions || Boolean(queuedContradiction)

  const isStreaming = Boolean(props.isThinking || props.streamingResponse || (props.streamStatusLog ?? []).length > 0)
  const showTyping = props.typing && !isStreaming

  const displayName = (props.userName || '').trim() || 'there'

  const activeTheaterMode = false

  // Content shown in theater mode bottom-left panel
  const theaterText = isStreaming
    ? (props.streamingResponse ?? '')
    : (lastAssistant?.text ?? '')
  const theaterFontPx = theaterFontSize(theaterText.length)

  return (
    <div className="flex h-full min-h-0 flex-col">

      {/* ── THEATER MODE ─────────────────────────────────────── */}
      {activeTheaterMode && (
        <div
          className="relative min-h-0 flex-1 overflow-hidden"
          onWheel={(e) => {
            if (e.deltaY < 0) {
              theaterLockRef.current = true
              setTheaterMode(false)
              setTimeout(() => { theaterLockRef.current = false }, 800)
            }
          }}
          onTouchMove={(e) => { /* handled by history scroll detection */ }}
        >

          {/* User message — top right */}
          <AnimatePresence mode="wait">
            {lastUserMsg && (
              <motion.div
                key={lastUserMsg.id}
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
                className="absolute top-6 right-8 max-w-[42%] text-right"
              >
                <p className="text-[14px] leading-snug" style={{ color: 'var(--text-muted)' }}>
                  {lastUserMsg.text}
                </p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Assistant response — bottom left, cinematic */}
          <div className="absolute inset-0 flex items-end pb-6 pl-8 pr-[46%]">
            <AnimatePresence mode="wait">
              {(theaterText || isStreaming || showTyping) && (
                <motion.div
                  key={isStreaming ? 'streaming' : (lastAssistant?.id ?? 'idle')}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                  className="w-full"
                >
                  {/* Phase label while waiting */}
                  {isStreaming && !theaterText && (
                    <div className="mb-4">
                      <span
                        className="font-display text-4xl"
                        style={{ color: 'var(--accent-2)' }}
                      >
                        {props.isThinking ? 'THINKING' : props.streamPhase ? ({ analyze: 'READING', plan: 'PLANNING', answer: 'WRITING' }[props.streamPhase] ?? props.streamPhase.toUpperCase()) : 'PROCESSING'}
                      </span>
                      <span className="ml-3 inline-flex gap-1 items-center">
                        {[0, 0.2, 0.4].map((d, i) => (
                          <span key={i} className="h-1 w-1 rounded-full animate-bounce" style={{ background: 'var(--accent-2)', opacity: 0.5, animationDelay: `${d}s`, animationDuration: '0.8s' }} />
                        ))}
                      </span>
                      {/* Status tags */}
                      {(props.streamStatusLog ?? []).filter(s => !s.startsWith('ctrl:') && s !== 'Processing message...').length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {(props.streamStatusLog ?? []).filter(s => !s.startsWith('ctrl:') && s !== 'Processing message...').slice(-3).map((s, i) => (
                            <span key={i} className="rounded-full px-2 py-0.5 text-[10px] font-mono" style={{ background: 'var(--surface-3)', color: 'var(--text-faint)', border: '1px solid var(--border-soft)' }}>{s}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Typing dots */}
                  {showTyping && (
                    <div className="flex gap-1.5 mb-2">
                      {[0, 0.15, 0.3].map((delay, i) => (
                        <span key={i} className="h-2 w-2 rounded-full animate-bounce" style={{ background: 'var(--accent-6)', animationDelay: `${delay}s`, animationDuration: '0.9s' }} />
                      ))}
                    </div>
                  )}

                  {/* The actual text — adaptive font size */}
                  {theaterText && (
                    <div
                      className="text-white leading-[1.4] font-light"
                      style={{
                        fontSize: theaterFontPx,
                        transition: 'font-size 0.4s ease',
                        maxHeight: '70vh',
                        overflow: 'hidden',
                        maskImage: 'linear-gradient(to bottom, transparent 0%, white 12%)',
                        WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, white 12%)',
                      }}
                    >
                      {theaterText}
                      {isStreaming && <StreamCursor />}
                    </div>
                  )}

                  {/* Meta row — visible on finished response */}
                  {!isStreaming && lastAssistant?.crt && (
                    <div className="mt-4 flex items-center gap-2">
                      {lastAssistant.crt.gates_passed === false && (
                        <span className="rounded-full px-2 py-0.5 text-[10px] font-mono" style={{ background: 'rgba(251,113,133,0.15)', color: '#fb7185' }}>gate fail</span>
                      )}
                      {lastAssistant.crt.contradiction_detected && (
                        <span className="rounded-full px-2 py-0.5 text-[10px] font-mono" style={{ background: 'rgba(251,146,60,0.15)', color: '#fb923c' }}>contradiction</span>
                      )}
                      {lastAssistant.crt.response_type && lastAssistant.crt.response_type !== 'speech' && (
                        <span className="text-[10px] font-mono uppercase tracking-wide" style={{ color: 'var(--text-faint)' }}>{lastAssistant.crt.response_type}</span>
                      )}
                      <button
                        onClick={() => {
                          theaterLockRef.current = true
                          setTheaterMode(false)
                          setTimeout(() => { theaterLockRef.current = false }, 800)
                        }}
                        className="ml-auto text-[11px] font-mono uppercase tracking-widest transition hover:opacity-80"
                        style={{ color: 'var(--text-faint)' }}
                      >
                        ↑ history
                      </button>
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

        </div>
      )}

      {/* ── HISTORY MODE ─────────────────────────────────────── */}
      {!activeTheaterMode && (
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="min-h-0 flex-1 overflow-y-auto [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.1)_transparent]"
        >
          <div className="mx-auto w-full px-4 py-8 md:px-8" style={{ maxWidth: '1000px' }}>

            {/* Empty state */}
            {empty && (
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                className="flex min-h-[60vh] flex-col items-center justify-center text-center"
              >
                <div className="font-display text-7xl text-white md:text-8xl lg:text-9xl" style={{ lineHeight: 1 }}>
                  Hey {displayName}
                </div>
                <div className="mt-4 text-sm tracking-widest uppercase" style={{ color: 'var(--text-faint)' }}>
                  What's on your mind?
                </div>
                {props.showSetNameCta && (
                  <button onClick={props.onRequestSetName} className="mt-8 rounded-full border border-white/10 bg-white/5 px-5 py-2 text-sm text-white/60 transition hover:bg-white/8 hover:text-white/80">
                    Set your name
                  </button>
                )}
              </motion.div>
            )}

            {/* Message history */}
            {!empty && (
              <div className="flex flex-col gap-8">
                <AnimatePresence initial={false}>
                  {props.thread.messages.map((m) => (
                    <MessageBubble
                      key={m.id}
                      msg={m}
                      threadId={props.thread.id}
                      selected={m.id === props.selectedMessageId}
                      onInspect={m.role === 'assistant' ? (id) => props.onSelectAssistantMessage(id) : undefined}
                      onOpenSourceInspector={props.onOpenSourceInspector}
                      onOpenAgentPanel={props.onOpenAgentPanel}
                      xrayMode={props.xrayMode}
                    />
                  ))}
                </AnimatePresence>

                {/* Streaming in history mode — compact */}
                {isStreaming && (
                  <StreamingMessage
                    content={props.streamingResponse ?? ''}
                    isThinking={Boolean(props.isThinking)}
                    phase={props.streamPhase ?? null}
                    statusLog={props.streamStatusLog ?? []}
                    thinkingContent={props.streamingThinking ?? ''}
                  />
                )}

                {showTyping && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }} className="flex items-center gap-2">
                    <div className="flex gap-1">
                      {[0, 0.15, 0.3].map((delay, i) => (
                        <span key={i} className="h-1.5 w-1.5 rounded-full animate-bounce" style={{ background: 'var(--accent-6)', animationDelay: `${delay}s`, animationDuration: '0.9s' }} />
                      ))}
                    </div>
                  </motion.div>
                )}
              </div>
            )}

            <div ref={bottomRef} className="h-4" />
          </div>

          {/* Snap back to theater */}
          <div className="sticky bottom-4 flex justify-center pointer-events-none">
            <motion.button
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              onClick={() => setTheaterMode(true)}
              className="pointer-events-auto rounded-full px-4 py-1.5 text-[11px] font-mono uppercase tracking-widest transition hover:opacity-80"
              style={{ background: 'var(--surface-3)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
            >
              ↓ theater
            </motion.button>
          </div>
        </div>
      )}

      {/* Contradiction banner */}
      <AnimatePresence>
        {showBanner && (
          <motion.div
            key="contradiction-banner"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.2 }}
            className="flex-shrink-0 px-4"
          >
            <div className="mx-auto w-full" style={{ maxWidth: '760px' }}>
              <AnimatePresence>
                {trayOpen && (
                  <motion.div
                    key="tray"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.18 }}
                    className="mb-2 overflow-hidden"
                  >
                    <div className="max-h-[360px] overflow-y-auto rounded-xl border border-white/10 bg-black/40 p-3 text-xs">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-white/50 font-medium">Open contradictions</span>
                        <button onClick={() => void refreshContradictions()} className="text-white/30 hover:text-white/60 transition-colors">refresh</button>
                      </div>
                      {contradictionsLoading ? (
                        <div className="text-white/40">Loading…</div>
                      ) : contradictionsError ? (
                        <div className="text-rose-300">{contradictionsError}</div>
                      ) : contradictions.length === 0 ? (
                        <div className="text-white/40">No open contradictions.</div>
                      ) : (
                        <div className="space-y-2">
                          {contradictions.map((c) => (
                            <div key={c.ledger_id} className="rounded-lg border border-white/8 bg-white/3 p-3">
                              <div className="font-semibold text-rose-200/80 text-[11px] mb-1">
                                {(c.slot || c.contradiction_type || 'Contradiction').toUpperCase()}
                              </div>
                              {(c.summary || c.query) && (
                                <div className="text-white/50 line-clamp-2 mb-1">{c.summary || c.query}</div>
                              )}
                              <div className="text-white/35 space-y-0.5">
                                <div>Old: <span className="text-white/50">{(c.old_value || c.old_memory_id || '—').trim()}</span></div>
                                <div>New: <span className="text-white/50">{(c.new_value || c.new_memory_id || '—').trim()}</span></div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <button
                onClick={() => setTrayOpen((v) => !v)}
                className={`mb-2 flex w-full items-center justify-between rounded-xl border px-3 py-2 text-xs transition ${
                  hasOpenContradictions
                    ? 'border-rose-500/25 bg-rose-500/8 text-rose-200/80 hover:bg-rose-500/12'
                    : 'border-white/8 bg-white/3 text-white/40 hover:bg-white/5'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={`h-1.5 w-1.5 rounded-full ${hasOpenContradictions ? 'animate-pulse bg-rose-400' : 'bg-white/30'}`} />
                  <span className="font-medium">{queuedCount} {queuedContradiction ? 'queued' : 'open'} contradiction{queuedCount !== 1 ? 's' : ''}</span>
                </div>
                <span className="text-white/30">{trayOpen ? '↑' : '↓'}</span>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Composer */}
      <div className="flex-shrink-0">
        <Composer
          onSend={props.onSend}
          onResearch={props.onResearch}
          researching={props.researching}
          disabled={props.typing}
        />
      </div>
    </div>
  )
}
