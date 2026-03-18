import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatThread, QuickAction } from '../../types'
import { MessageBubble } from './MessageBubble'
import { Composer } from './Composer'
import { QuickCards } from '../QuickCards'
import { listOpenContradictions, type ContradictionListItem } from '../../lib/api'

// Blinking cursor for streaming
function StreamCursor() {
  return (
    <span
      className="inline-block w-[2px] h-[1em] align-middle ml-0.5 animate-[blink_1s_step-end_infinite]"
      style={{ verticalAlign: '-0.1em', background: 'var(--accent-2)' }}
    />
  )
}

// Streaming message — same editorial style as an assistant message
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
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* Phase / thinking indicator */}
      {(isThinking || phase || statusLog.length > 0) && (
        <div className="mb-3 flex items-center gap-2">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full" style={{ background: 'var(--accent-2)' }} />
          <span className="text-[12px] font-medium tracking-wide" style={{ color: 'var(--text-muted)' }}>
            {isThinking ? 'Thinking…' : phase ? `${phase}` : 'Processing…'}
          </span>
          {statusLog.length > 0 && (
            <span className="text-[11px] text-white/25">
              {statusLog[statusLog.length - 1]}
            </span>
          )}
        </div>
      )}

      {/* Thinking content (collapsed preview) */}
      {isThinking && thinkingContent && (
        <div className="mb-3 max-h-[80px] overflow-hidden rounded-xl border border-white/8 bg-white/3 px-3 py-2 text-[12px] text-white/35 italic leading-relaxed">
          <div
            className="line-clamp-3"
            style={{
              maskImage: 'linear-gradient(to bottom, white 40%, transparent 100%)',
              WebkitMaskImage: 'linear-gradient(to bottom, white 40%, transparent 100%)',
            }}
          >
            {thinkingContent}
          </div>
        </div>
      )}

      {/* Streaming text */}
      {content ? (
        <div className="text-[15px] text-white/90 leading-[1.8]">
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
                  return <code className="rounded-md bg-white/8 px-1.5 py-0.5 font-mono text-[0.88em] text-violet-200">{children}</code>
                }
                return <pre className="my-2 overflow-x-auto rounded-xl border border-white/10 bg-black/40 p-4 text-sm text-white/80 font-mono">{codeText}</pre>
              },
            } as any}
          >
            {content}
          </ReactMarkdown>
          <StreamCursor />
        </div>
      ) : !isThinking ? (
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full" style={{ background: 'var(--accent-2)' }} />
          <span className="text-[13px]" style={{ color: 'var(--text-muted)' }}>Drafting response…</span>
        </div>
      ) : null}
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
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
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

  // Scroll to bottom on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [props.thread.messages.length, props.streamingResponse, props.isThinking])

  // Reset on thread change
  useEffect(() => {
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

  const empty = props.thread.messages.length === 0
  const isStreaming = Boolean(props.isThinking || props.streamingResponse || (props.streamStatusLog ?? []).length > 0)
  const showTyping = props.typing && !isStreaming

  const displayName = (props.userName || '').trim() || 'there'

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Scrollable messages area */}
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.1)_transparent]">
        <div className="mx-auto w-full px-4 py-8 md:px-8" style={{ maxWidth: '1000px' }}>

          {/* Empty state */}
          {empty && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="flex min-h-[40vh] flex-col items-center justify-center text-center"
            >
              <div
                className="font-display mb-2 text-5xl text-white md:text-7xl"
                style={{ lineHeight: 1.05 }}
              >
                Hey {displayName}
              </div>
              <div className="mb-8 text-base tracking-wide" style={{ color: 'var(--text-muted)' }}>
                What's on your mind?
              </div>

              {props.showSetNameCta && (
                <button
                  onClick={props.onRequestSetName}
                  className="mb-8 rounded-full border border-white/10 bg-white/5 px-5 py-2 text-sm text-white/60 transition hover:bg-white/8 hover:text-white/80"
                >
                  Set your name
                </button>
              )}

              <QuickCards actions={props.quickActions} onPick={props.onPickQuickAction} />
            </motion.div>
          )}

          {/* Messages */}
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

              {/* Streaming response */}
              {isStreaming && (
                <StreamingMessage
                  content={props.streamingResponse ?? ''}
                  isThinking={Boolean(props.isThinking)}
                  phase={props.streamPhase ?? null}
                  statusLog={props.streamStatusLog ?? []}
                  thinkingContent={props.streamingThinking ?? ''}
                />
              )}

              {/* Simple typing indicator (non-streaming) */}
              {showTyping && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.2 }}
                  className="flex items-center gap-2"
                >
                  <div className="flex gap-1">
                    {[0, 0.15, 0.3].map((delay, i) => (
                      <span
                        key={i}
                        className="h-1.5 w-1.5 rounded-full animate-bounce"
                      style={{ background: 'var(--accent-6)', animationDelay: `${delay}s`, animationDuration: '0.9s' }}
                      />
                    ))}
                  </div>
                </motion.div>
              )}
            </div>
          )}

          {/* Scroll anchor */}
          <div ref={bottomRef} className="h-4" />
        </div>
      </div>

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
