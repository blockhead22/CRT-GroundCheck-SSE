import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatThread, QuickAction, MessageRating } from '../../types'
import { MessageBubble } from './MessageBubble'
import { Composer } from './Composer'
import { listOpenContradictions, type ContradictionListItem } from '../../lib/api'
import { PipelineTrace } from './PipelineTrace'
import { AgentThinkingStrip, type AgentThinkingState } from './AgentThinkingStrip'
import { ActionCard } from './ActionCard'

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


// Expandable thinking trace — shows live LLM reasoning during pipeline
function ThinkingPreview({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(false)
  const lines = content.split('\n').filter(Boolean)
  const preview = lines.slice(-3).join('\n')

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-3 overflow-hidden rounded border px-3 py-2 text-[11px] leading-relaxed"
      style={{ borderColor: 'rgba(224,160,128,0.15)', background: 'rgba(0,0,0,0.2)', color: 'var(--text-muted)' }}
    >
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full text-left flex items-center gap-2 mb-1"
      >
        <span className="font-mono text-[10px]" style={{ color: '#E0A080' }}>
          {expanded ? '▼' : '▶'} thinking
        </span>
        <span className="text-[10px] font-mono" style={{ color: '#5a5445' }}>
          {lines.length} lines
        </span>
      </button>
      <div
        className={expanded ? '' : 'line-clamp-3'}
        style={expanded ? {} : {
          maskImage: 'linear-gradient(to bottom, white 40%, transparent 100%)',
          WebkitMaskImage: 'linear-gradient(to bottom, white 40%, transparent 100%)',
        }}
      >
        <pre className="whitespace-pre-wrap text-[11px] font-mono" style={{ color: 'rgba(240,235,225,0.5)' }}>
          {expanded ? content : preview}
        </pre>
      </div>
    </motion.div>
  )
}

// Streaming message — rich activity timeline + streaming text
function StreamingMessage({
  content,
  isThinking,
  statusLog,
  thinkingContent,
  hideTrace,
}: {
  content: string
  isThinking: boolean
  phase: string | null
  statusLog: string[]
  thinkingContent: string
  hideTrace?: boolean
}) {
  const hasContent = Boolean(content)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* Pipeline trace — hidden when AgentThinkingStrip is active (task routes) */}
      {!hideTrace && <PipelineTrace statuses={statusLog} streaming={!hasContent} />}

      {/* Thinking trace — expandable live reasoning */}
      {isThinking && thinkingContent && (
        <ThinkingPreview content={thinkingContent} />
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
                  return <code className="rounded bg-white/8 px-1.5 py-0.5 font-mono text-[0.88em]" style={{ color: 'var(--accent-6)' }}>{children}</code>
                }
                return <pre className="my-2 overflow-x-auto rounded border border-white/10 bg-black/40 p-4 text-sm text-white/80 font-mono">{codeText}</pre>
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
  intentPreview?: { intent: string; slots: string[]; label: string } | null
  agentThinkingState?: AgentThinkingState | null
  onRated?: (msgId: string, rating: MessageRating, category?: string) => void
  diagnosticsOpen?: boolean
  onToggleDiagnostics?: () => void
  pendingCheckpoint?: { message: string; metadata: Record<string, unknown> } | null
  onCheckpointRespond?: (text: string) => void
  onStopGeneration?: () => void
}) {
  const empty = props.thread.messages.length === 0

  const bottomRef = useRef<HTMLDivElement | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const [theaterMode, setTheaterMode] = useState(false)
  const [trayOpen, setTrayOpen] = useState(false)
  const [contradictions, setContradictions] = useState<ContradictionListItem[]>([])
  const [contradictionsLoading, setContradictionsLoading] = useState(false)
  // Local overlay for ratings so UI updates immediately without a full re-render cycle
  const [localRatings, setLocalRatings] = useState<Record<string, { rating: MessageRating; category?: string }>>({})

  function handleMessageRated(msgId: string, rating: MessageRating, category?: string) {
    setLocalRatings((prev) => ({ ...prev, [msgId]: { rating, category } }))
    props.onRated?.(msgId, rating, category)
  }
  const [contradictionsError, setContradictionsError] = useState<string | null>(null)
  const [contradictionsLoaded, setContradictionsLoaded] = useState(false)
  const [queuedContradiction, setQueuedContradiction] = useState<{
    messageId: string
    total: number | null
    createdAt: number
  } | null>(null)

  // Scroll to bottom in history mode when new content arrives
  useEffect(() => {
    if (theaterMode) return
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
    // Always scroll on new messages; only smooth-scroll during streaming if near bottom
    if (props.thread.messages.length > 0) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    } else if (atBottom) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
  }, [props.thread.messages.length, props.streamingResponse, props.isThinking, theaterMode])

  // Stay in history mode by default — user can switch to theater manually

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

  const activeTheaterMode = theaterMode && !empty

  // Content shown in theater mode bottom-left panel
  const theaterText = isStreaming
    ? (props.streamingResponse ?? '')
    : (lastAssistant?.text ?? '')
  const theaterFontPx = theaterFontSize(theaterText.length)

  // Show action card only when the backend has emitted an agent_checkpoint event
  const showActionCard = !!props.pendingCheckpoint && !isStreaming && !showTyping

  return (
    <div className="flex h-full min-h-0 flex-col">

      {/* ── Mode toggle bar ── */}
      {!empty && (
        <motion.div
          className="flex-shrink-0 flex justify-center py-2"
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        >
          <div
            className="inline-flex rounded-full p-[3px] gap-[2px]"
            style={{
              background: 'rgba(29,27,22,0.6)',
              border: '1px solid rgba(240,235,225,0.05)',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            }}
          >
            {(['history', 'theater'] as const).map((mode) => {
              const active = mode === 'theater' ? activeTheaterMode : !activeTheaterMode
              return (
                <motion.button
                  key={mode}
                  onClick={() => setTheaterMode(mode === 'theater')}
                  className="rounded-full px-4 py-1 text-[10px] font-mono uppercase tracking-widest"
                  animate={{
                    background: active ? 'rgba(212,132,92,0.9)' : 'transparent',
                    color: active ? '#F0EBE1' : '#5a5445',
                    boxShadow: active ? '0 0 12px rgba(212,132,92,0.3)' : '0 0 0 transparent',
                  }}
                  transition={{ duration: 0.2 }}
                >
                  {mode}
                </motion.button>
              )
            })}
          </div>
        </motion.div>
      )}

      {/* ── THEATER MODE ─────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        {activeTheaterMode && (
        <motion.div
          key="theater"
          className="relative min-h-0 flex-1 overflow-hidden"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
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
                      {/* Intent preview chip — appears immediately before pipeline starts */}
                      {props.intentPreview && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          <span
                            className="rounded-full px-2.5 py-0.5 text-[10px] font-mono"
                            style={{ background: 'color-mix(in srgb, var(--accent-2) 15%, transparent)', color: 'var(--accent-2)', border: '1px solid color-mix(in srgb, var(--accent-2) 30%, transparent)' }}
                          >
                            {props.intentPreview.intent}
                            {props.intentPreview.slots.length > 0 && (
                              <span style={{ opacity: 0.7 }}> · {props.intentPreview.slots.slice(0, 3).join(', ')}</span>
                            )}
                          </span>
                        </div>
                      )}
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

                  {/* The actual text — adaptive font size, cinematic entrance */}
                  {theaterText && (
                    <motion.div
                      key={isStreaming ? 'streaming-text' : lastAssistant?.id}
                      initial={{ opacity: 0, y: 20, filter: 'blur(8px)' }}
                      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                      style={{
                        fontSize: theaterFontPx,
                        transition: 'font-size 0.4s ease',
                        maxHeight: '70vh',
                        overflow: 'hidden',
                        lineHeight: 1.35,
                        fontWeight: 300,
                        color: '#F0EBE1',
                        maskImage: 'linear-gradient(to bottom, transparent 0%, white 10%)',
                        WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, white 10%)',
                      }}
                    >
                      {theaterText}
                      {isStreaming && <StreamCursor />}
                    </motion.div>
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
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

        </motion.div>
        )}
      </AnimatePresence>

      {/* ── HISTORY MODE ─────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        {!activeTheaterMode && (
          <motion.div
            key="history"
            ref={scrollRef}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="min-h-0 flex-1 overflow-y-auto [scrollbar-width:thin] [scrollbar-color:rgba(212,132,92,0.35)_transparent]"
          >
            <div className="mx-auto w-full px-5 py-8 md:px-10" style={{ maxWidth: '780px' }}>

              {/* Empty state */}
              {empty && (
                <motion.div
                  initial={{ opacity: 0, y: 24 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                  className="flex min-h-[60vh] flex-col items-center justify-center text-center"
                >
                  {/* Subtle ambient glow behind hero text */}
                  <div className="relative">
                    <div
                      className="absolute inset-0 -z-10 blur-[80px] opacity-20"
                      style={{ background: 'radial-gradient(ellipse at center, rgba(212,132,92,0.5) 0%, transparent 70%)' }}
                    />
                    <motion.div
                      className="font-display md:text-8xl lg:text-9xl"
                      style={{ fontSize: 'clamp(4rem, 12vw, 9rem)', lineHeight: 1, color: '#F0EBE1' }}
                      initial={{ opacity: 0, y: 32, letterSpacing: '0.1em' }}
                      animate={{ opacity: 1, y: 0, letterSpacing: '0.04em' }}
                      transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                    >
                      Hey {displayName}
                    </motion.div>
                  </div>
                  <motion.div
                    className="mt-5 text-[13px] tracking-[0.2em] uppercase font-mono"
                    style={{ color: 'var(--text-faint)' }}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.3, duration: 0.5 }}
                  >
                    What's on your mind?
                  </motion.div>
                  {props.showSetNameCta && (
                    <motion.button
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.5 }}
                      onClick={props.onRequestSetName}
                      className="mt-10 rounded-full border px-6 py-2.5 text-sm transition-all hover:bg-white/[0.04] hover:border-white/15"
                      style={{ borderColor: 'rgba(240,235,225,0.08)', color: 'var(--text-muted)' }}
                    >
                      Set your name
                    </motion.button>
                  )}
                </motion.div>
              )}

              {/* Message history — staggered entrance */}
              {!empty && (
                <div className="flex flex-col gap-6">
                  {props.thread.messages.map((m, idx) => (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 18, filter: 'blur(4px)' }}
                      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                      transition={{
                        duration: 0.38,
                        ease: [0.16, 1, 0.3, 1],
                        delay: Math.min(idx * 0.04, 0.3),
                      }}
                    >
                      {/* Persisted agent thinking strip for task-route messages */}
                      {m.role === 'assistant' && m.agentThinking && (
                        <AgentThinkingStrip state={m.agentThinking} />
                      )}
                      <MessageBubble
                        msg={{
                          ...m,
                          rating: localRatings[m.id]?.rating ?? m.rating,
                          ratingCategory: localRatings[m.id]?.category ?? m.ratingCategory,
                        }}
                        threadId={props.thread.id}
                        selected={m.id === props.selectedMessageId}
                        onInspect={m.role === 'assistant' ? (id) => props.onSelectAssistantMessage(id) : undefined}
                        onOpenSourceInspector={props.onOpenSourceInspector}
                        onOpenAgentPanel={props.onOpenAgentPanel}
                        xrayMode={props.xrayMode}
                        onRated={handleMessageRated}
                      />
                    </motion.div>
                  ))}

                  {/* Agent thinking strip — appears above streaming bubble for task routes */}
                  <AnimatePresence>
                    {props.agentThinkingState && (
                      <motion.div
                        key="agent-thinking"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.25 }}
                      >
                        <AgentThinkingStrip state={props.agentThinkingState} />
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {/* Streaming in history mode */}
                  <AnimatePresence>
                    {isStreaming && (
                      <motion.div
                        key="streaming"
                        initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }}
                        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                        exit={{ opacity: 0, y: -4 }}
                        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                      >
                        <StreamingMessage
                          content={props.streamingResponse ?? ''}
                          isThinking={Boolean(props.isThinking)}
                          phase={props.streamPhase ?? null}
                          statusLog={props.streamStatusLog ?? []}
                          thinkingContent={props.streamingThinking ?? ''}
                          hideTrace={Boolean(props.agentThinkingState)}
                        />
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {showTyping && (
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="flex items-center gap-2"
                    >
                      {[0, 0.15, 0.3].map((delay, i) => (
                        <span key={i} className="h-1.5 w-1.5 rounded-full animate-bounce"
                          style={{ background: 'var(--accent-3)', animationDelay: `${delay}s`, animationDuration: '0.9s' }} />
                      ))}
                    </motion.div>
                  )}
                </div>
              )}

              <div ref={bottomRef} className="h-8" />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

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
                    <div className="max-h-[360px] overflow-y-auto rounded border border-white/10 bg-black/40 p-3 text-xs">
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
                            <div key={c.ledger_id} className="rounded border border-white/8 bg-white/3 p-3">
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
                className={`mb-2 flex w-full items-center justify-between rounded border px-3 py-2 text-xs transition ${
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

      {/* Action card — quick-reply buttons for agent checkpoint confirmations */}
      <AnimatePresence>
        {showActionCard && props.pendingCheckpoint && (
          <div className="flex-shrink-0 mb-1">
            <ActionCard
              checkpointMessage={props.pendingCheckpoint.message}
              checkpointMeta={props.pendingCheckpoint.metadata}
              onRespond={props.onCheckpointRespond ?? props.onSend}
            />
          </div>
        )}
      </AnimatePresence>

      {/* Composer */}
      <div className="flex-shrink-0">
        <Composer
          onSend={props.onSend}
          onResearch={props.onResearch}
          researching={props.researching}
          disabled={props.typing}
          typing={props.typing}
          onStop={props.onStopGeneration}
          diagnosticsOpen={props.diagnosticsOpen}
          onToggleDiagnostics={props.onToggleDiagnostics}
        />
      </div>
    </div>
  )
}
