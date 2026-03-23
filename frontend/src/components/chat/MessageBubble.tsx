import { motion, AnimatePresence } from 'framer-motion'
import { useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Editor from '@monaco-editor/react'
import type { ChatMessage, MessageRating } from '../../types'
import { formatTime } from '../../lib/time'
import { CitationViewer } from '../CitationViewer'
import { PipelineTrace } from './PipelineTrace'
import { MessageRatingBar } from './MessageRatingBar'
import { ContradictionResolutionCard } from './ContradictionResolutionCard'
import { TrustDeltaStrip } from './TrustDeltaStrip'
import { ContradictionDrawer } from './ContradictionDrawer'
import { resolveContradiction } from '../../lib/api'

function MonacoBlock({ code, language }: { code: string; language?: string }) {
  const lines = code.split('\n').length
  const height = `${Math.max(100, Math.min(320, lines * 18 + 32))}px`
  return (
    <div className="my-3 overflow-hidden rounded border border-white/10 bg-black/40">
      <Editor
        height={height}
        defaultLanguage={language || 'plaintext'}
        value={code}
        theme="vs-dark"
        options={{
          readOnly: true,
          minimap: { enabled: false },
          fontSize: 13,
          lineNumbers: 'on',
          wordWrap: 'on',
          scrollBeyondLastLine: false,
          renderLineHighlight: 'none',
          contextmenu: false,
          scrollbar: { vertical: 'auto', horizontal: 'auto' },
        }}
      />
    </div>
  )
}

const mdComponents = {
  p({ children }: { children?: React.ReactNode }) {
    return <p className="mb-3 last:mb-0 leading-[1.8]">{children}</p>
  },
  ul({ children }: { children?: React.ReactNode }) {
    return <ul className="mb-3 space-y-1.5 pl-5">{children}</ul>
  },
  ol({ children }: { children?: React.ReactNode }) {
    return <ol className="mb-3 list-decimal space-y-1.5 pl-5">{children}</ol>
  },
  li({ children }: { children?: React.ReactNode }) {
    return <li className="text-white/80 leading-relaxed marker:text-white/30">{children}</li>
  },
  code({ children, className }: { children?: React.ReactNode; className?: string }) {
    const codeText = String(children ?? '').replace(/\n$/, '')
    const match = /language-([a-zA-Z0-9_-]+)/.exec(className || '')
    const language = match ? match[1] : undefined
    const isBlock = Boolean(language) || codeText.includes('\n')
    if (!isBlock) {
      return (
        <code className="rounded-sm px-1.5 py-0.5 font-mono text-[0.88em]" style={{ background: 'rgba(212,132,92,0.12)', color: '#E8C8A0' }}>
          {children}
        </code>
      )
    }
    return <MonacoBlock code={codeText} language={language} />
  },
  blockquote({ children }: { children?: React.ReactNode }) {
    return (
      <blockquote className="my-3 pl-4 italic" style={{ borderLeft: '2px solid rgba(224,160,128,0.35)', color: 'rgba(240,235,225,0.55)' }}>
        {children}
      </blockquote>
    )
  },
  h1({ children }: { children?: React.ReactNode }) {
    return <h1 className="mb-3 mt-5 text-xl font-semibold text-white">{children}</h1>
  },
  h2({ children }: { children?: React.ReactNode }) {
    return <h2 className="mb-2 mt-4 text-lg font-semibold text-white">{children}</h2>
  },
  h3({ children }: { children?: React.ReactNode }) {
    return <h3 className="mb-2 mt-3 text-base font-semibold text-white/90">{children}</h3>
  },
  a({ children, href }: { children?: React.ReactNode; href?: string }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2" style={{ color: '#E0A080', textDecorationColor: 'rgba(224,160,128,0.4)' }}>
        {children}
      </a>
    )
  },
  hr() {
    return <hr className="my-4 border-white/10" />
  },
  table({ children }: { children?: React.ReactNode }) {
    return (
      <div className="my-3 overflow-x-auto rounded border border-white/10">
        <table className="w-full text-sm">{children}</table>
      </div>
    )
  },
  th({ children }: { children?: React.ReactNode }) {
    return <th className="border-b border-white/10 bg-white/5 px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-white/50">{children}</th>
  },
  td({ children }: { children?: React.ReactNode }) {
    return <td className="border-b border-white/5 px-4 py-2 text-white/80">{children}</td>
  },
}

export function MessageBubble(props: {
  msg: ChatMessage
  threadId?: string
  selected?: boolean
  onInspect?: (messageId: string) => void
  onOpenSourceInspector?: (memoryId: string) => void
  onOpenAgentPanel?: (messageId: string) => void
  xrayMode?: boolean
  onRated?: (msgId: string, rating: MessageRating, category?: string) => void
}) {
  const isUser = props.msg.role === 'user'
  const meta = props.msg.crt
  const isAssistant = !isUser

  const responseType = (meta?.response_type ?? '').toLowerCase()
  const isBelief = responseType === 'belief'
  const isExplanation = responseType === 'explanation'
  const gatesPassed = meta?.gates_passed
  const gatesFailed = typeof gatesPassed === 'boolean' && !gatesPassed
  const contradictionDetected = meta?.contradiction_detected

  const [metaExpanded, setMetaExpanded] = useState(false)
  const [gateDebugOpen, setGateDebugOpen] = useState(false)
  const [gateAccepting, setGateAccepting] = useState(false)
  const [gateAccepted, setGateAccepted] = useState(false)
  const [contradictionDrawerOpen, setContradictionDrawerOpen] = useState(false)
  const [contraResolved, setContraResolved] = useState(false)

  // ledger_id from gate_debug — declared early so handleAcceptGateClaim can close over it
  const ledgerId = meta?.gate_debug?.ledger_id ?? null

  const handleAcceptGateClaim = useCallback(async () => {
    if (!ledgerId || gateAccepting || gateAccepted) return
    setGateAccepting(true)
    try {
      await resolveContradiction({
        threadId: props.threadId ?? 'default',
        ledgerId,
        method: 'accept_new',
        newStatus: 'resolved',
      })
      setGateAccepted(true)
    } catch { /* non-critical */ }
    finally { setGateAccepting(false) }
  }, [ledgerId, props.threadId, gateAccepting, gateAccepted])
  const [localRating, setLocalRating] = useState<MessageRating | null>(props.msg.rating ?? null)
  const [localRatingCat, setLocalRatingCat] = useState<string | undefined>(props.msg.ratingCategory ?? undefined)
  const [ratedAt, setRatedAt] = useState<number | null>(null)

  function handleRated(rating: MessageRating, category?: string) {
    setLocalRating(rating)
    setLocalRatingCat(category)
    setRatedAt(Date.now() / 1000)
    props.onRated?.(props.msg.id, rating, category)
  }

  const profileUpdates = meta?.profile_updates ?? []

  const prov = (() => {
    if (!isAssistant || !meta || !(isBelief || isExplanation)) return null
    const pm = meta.prompt_memories ?? []
    const rm = meta.retrieved_memories ?? []
    const best =
      (pm as any[]).find((m: any) => String(m?.memory_id || '').toLowerCase().startsWith('doc:')) ||
      (pm as any[]).find((m: any) => (m.text || '').trim().toLowerCase().startsWith('fact:')) ||
      pm[0] || rm[0]
    const text = (best?.text || '').trim()
    const id = (best as any)?.memory_id ? String((best as any).memory_id) : ''
    if (!text && !id) return null
    return { id, text }
  })()

  // User message — compact right-aligned pill with depth
  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        className="flex justify-end"
      >
        <div className="group max-w-[72%]">
          <div
            className="rounded-sm px-5 py-3.5 text-[14.5px] leading-relaxed"
            style={{
              background: 'linear-gradient(135deg, #D4845C 0%, #B87050 100%)',
              color: 'var(--user-bubble-fg)',
              boxShadow: '0 2px 8px rgba(212,132,92,0.3), 0 8px 24px rgba(212,132,92,0.15), inset 0 1px 0 rgba(255,255,255,0.1)',
            }}
          >
            {props.msg.text}
          </div>
          <div className="mt-1.5 flex justify-end pr-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            <span className="text-[10px] text-white/25 font-mono">{formatTime(props.msg.createdAt)}</span>
          </div>
        </div>
      </motion.div>
    )
  }

  // Assistant message — card-style with subtle depth
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -1 }}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      className="group"
    >
      <div
        className={[
          'rounded-sm px-5 py-4 transition-all duration-200',
          props.selected ? '' : '',
          localRating === 'down' ? 'border-l-2' : '',
          localRating === 'up' ? 'border-l-2' : '',
          gatesFailed && !localRating ? 'border-l-2' : '',
        ].join(' ')}
        style={{
          background: props.selected
            ? 'rgba(212,132,92,0.06)'
            : 'rgba(29,27,22,0.5)',
          border: props.selected
            ? '1px solid rgba(212,132,92,0.2)'
            : '1px solid rgba(240,235,225,0.04)',
          boxShadow: props.selected
            ? '0 0 24px rgba(212,132,92,0.1), 0 2px 8px rgba(0,0,0,0.15)'
            : '0 1px 4px rgba(0,0,0,0.1), 0 4px 16px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.02)',
          ...(localRating === 'down' ? { borderLeftColor: 'rgba(251,113,133,0.4)' } : {}),
          ...(localRating === 'up' ? { borderLeftColor: 'rgba(52,211,153,0.25)' } : {}),
          ...(gatesFailed && !localRating ? { borderLeftColor: 'rgba(251,146,60,0.35)', background: 'rgba(251,146,60,0.04)' } : {}),
        }}
      >
        {/* Profile updates */}
        {profileUpdates.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {profileUpdates.map((u, i) => (
              <span key={`${u.slot}-${i}`} className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-[11px]" style={{ border: '1px solid rgba(224,160,128,0.2)', background: 'rgba(212,132,92,0.08)', color: 'rgba(240,235,225,0.7)' }}>
                <span className="font-mono" style={{ color: '#E0A080' }}>{u.slot}</span>
                <span style={{ color: 'rgba(240,235,225,0.3)' }}>·</span>
                <span>{(u.old || '—')} → {(u.new || '—')}</span>
              </span>
            ))}
          </div>
        )}

        {/* Main message text */}
        <div className="text-[15px] text-white/90 leading-[1.75]">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents as any}>
            {props.msg.text}
          </ReactMarkdown>
        </div>

        {/* Gate debug — collapsible, opened by clicking the gate fail badge */}
        <AnimatePresence>
          {gatesFailed && meta?.gate_debug && gateDebugOpen && (
            <motion.div
              key="gate-debug"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.18 }}
              className="mt-3 overflow-hidden rounded px-3 py-2.5 text-[11px]"
              style={{ border: '1px solid rgba(212,112,88,0.2)', background: 'rgba(212,112,88,0.06)' }}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="font-mono font-semibold" style={{ color: '#D47058' }}>WHY BLOCKED</span>
                {meta.gate_debug.trigger && (
                  <span className="rounded px-1.5 py-0.5 font-mono" style={{ background: 'rgba(212,112,88,0.12)', color: '#E0A080' }}>{meta.gate_debug.trigger}</span>
                )}
                {meta.gate_debug.slot && (
                  <span className="rounded px-1.5 py-0.5 font-mono" style={{ background: 'rgba(240,235,225,0.06)', color: '#a09880' }}>slot: {meta.gate_debug.slot}</span>
                )}
                <button
                  onClick={() => setGateDebugOpen(false)}
                  className="ml-auto text-[10px] transition-opacity hover:opacity-60"
                  style={{ color: '#5a5445' }}
                >
                  close
                </button>
              </div>
              {meta.gate_debug.explanation && (
                <div className="mb-1.5" style={{ color: 'rgba(240,235,225,0.7)' }}>{meta.gate_debug.explanation}</div>
              )}
              {(meta.gate_debug.stored || meta.gate_debug.incoming) && (
                <div className="mt-1.5 space-y-1 font-mono">
                  {meta.gate_debug.stored && (
                    <div className="flex items-start gap-2">
                      <span style={{ color: '#5a5445' }}>stored</span>
                      <span className="line-clamp-2" style={{ color: 'rgba(240,235,225,0.55)' }}>{meta.gate_debug.stored}</span>
                    </div>
                  )}
                  {meta.gate_debug.incoming && (
                    <div className="flex items-start gap-2">
                      <span style={{ color: '#5a5445' }}>said&nbsp;&nbsp;</span>
                      <span className="line-clamp-2" style={{ color: 'rgba(240,235,225,0.55)' }}>{meta.gate_debug.incoming}</span>
                    </div>
                  )}
                </div>
              )}
              {(meta.gate_debug.conflicting_memories ?? []).length > 0 && (
                <div className="mt-2 space-y-1">
                  <div className="font-mono" style={{ color: '#5a5445' }}>conflicting memories</div>
                  {(meta.gate_debug.conflicting_memories ?? []).map((m, i) => (
                    <div key={i} className="flex items-start gap-2 font-mono">
                      <span style={{ color: '#E0A080' }}>T:{m.trust.toFixed(2)}</span>
                      <span className="line-clamp-1" style={{ color: 'rgba(240,235,225,0.45)' }}>{m.text}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-2 flex items-center gap-3 font-mono" style={{ color: '#5a5445' }}>
                {meta.gate_debug.intent_align != null && <span>intent {meta.gate_debug.intent_align.toFixed(2)}</span>}
                {meta.gate_debug.memory_align != null && <span>memory {meta.gate_debug.memory_align.toFixed(2)}</span>}
                {meta.gate_debug.grounding != null && <span>grounding {meta.gate_debug.grounding.toFixed(2)}</span>}
                {meta.gate_debug.hard_conflicts != null && meta.gate_debug.hard_conflicts > 0 && (
                  <span style={{ color: '#D47058' }}>{meta.gate_debug.hard_conflicts} hard conflict(s)</span>
                )}
              </div>
              {/* Action row — accept claim if a ledger entry exists */}
              <div className="mt-2.5 flex items-center gap-2 pt-2" style={{ borderTop: '1px solid rgba(240,235,225,0.06)' }}>
                {ledgerId ? (
                  gateAccepted ? (
                    <span className="text-[10px] font-medium" style={{ color: '#34d399' }}>✓ Accepted — memory updated</span>
                  ) : (
                    <button
                      onClick={handleAcceptGateClaim}
                      disabled={gateAccepting}
                      className="rounded-full px-2.5 py-1 text-[10px] font-medium transition-all hover:opacity-90 disabled:opacity-40"
                      style={{ border: '1px solid rgba(52,211,153,0.35)', background: 'rgba(52,211,153,0.08)', color: '#34d399' }}
                    >
                      {gateAccepting ? 'Accepting…' : 'My claim is correct — accept it'}
                    </button>
                  )
                ) : (
                  <span className="text-[10px]" style={{ color: '#5a5445' }}>Confidence threshold block — use the thumbs-down to flag a correction</span>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Contradiction resolution card — shown inline when contradiction detected */}
        <AnimatePresence>
          {contradictionDetected && ledgerId && !contraResolved && (
            <ContradictionResolutionCard
              key={ledgerId}
              ledgerId={ledgerId}
              threadId={props.threadId ?? 'default'}
              contradictionType={(meta as any)?.contradiction_type ?? null}
              summary={(meta as any)?.contradiction_summary ?? null}
              onResolved={() => setContraResolved(true)}
            />
          )}
        </AnimatePresence>

        {/* Pipeline trace — persisted from streaming, enriched with metadata */}
        {(meta?.pipeline_statuses ?? []).length > 0 && (() => {
          const statuses = [...(meta!.pipeline_statuses ?? [])]
          // Enrich with metadata-derived steps
          const memCount = (meta?.retrieved_memories?.length ?? 0) + (meta?.prompt_memories?.length ?? 0)
          if (memCount > 0 && !statuses.some(s => s.match(/\d+ mem/))) {
            statuses.push(`${memCount} memories read`)
          }
          // Show top memory citation if available
          const topMem = (meta?.retrieved_memories as any[])?.[0]
          if (topMem?.text) {
            const memPreview = String(topMem.text).slice(0, 80)
            const trust = typeof topMem.trust === 'number' ? `T:${topMem.trust.toFixed(2)}` : ''
            statuses.push(`${topMem.memory_id ?? ''} ·${trust ? trust + ' ' : ''}${memPreview}`)
          }
          // Show gate result
          if (gatesFailed && meta?.gate_reason) {
            statuses.push(`gate: ${meta.gate_reason}`)
          }
          return (
            <div className="mt-3">
              <PipelineTrace
                statuses={statuses}
                streaming={false}
                defaultOpen={false}
              />
            </div>
          )
        })()}

        {/* Cited memories — compact list of memories that grounded this response */}
        {isAssistant && (meta?.retrieved_memories as any[])?.length > 0 && (
          <details className="mt-2 text-[11px]" style={{ color: 'rgba(240,235,225,0.4)' }}>
            <summary className="cursor-pointer hover:text-white/60 transition-colors font-mono">
              ↑↓{(meta!.retrieved_memories as any[]).length} memories cited
            </summary>
            <div className="mt-1.5 pl-3 flex flex-col gap-1" style={{ borderLeft: '1px solid rgba(224,160,128,0.15)' }}>
              {(meta!.retrieved_memories as any[]).slice(0, 5).map((mem: any, i: number) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="font-mono flex-shrink-0" style={{ color: '#E0A080' }}>
                    T:{typeof mem.trust === 'number' ? mem.trust.toFixed(2) : '?'}
                  </span>
                  <span className="truncate" style={{ color: 'rgba(240,235,225,0.5)' }}>
                    {String(mem.text || '').slice(0, 120)}
                  </span>
                </div>
              ))}
            </div>
          </details>
        )}

        {/* Citations */}
        {meta?.research_packet ? (
          <CitationViewer
            citations={meta.research_packet.citations}
            onCitationClick={() => {
              if (meta.research_packet?.memory_id && props.onOpenSourceInspector) {
                props.onOpenSourceInspector(meta.research_packet.memory_id)
              }
            }}
          />
        ) : prov ? (
          <div className="mt-3 rounded border border-white/8 bg-white/3 px-3 py-2 text-[11px] text-white/40">
            <span className="font-mono">{prov.id}</span>
            {prov.id && prov.text ? ' · ' : ''}
            <span className="line-clamp-1">{prov.text}</span>
          </div>
        ) : null}

        {/* X-ray mode */}
        {props.xrayMode && meta?.xray && (
          <div className="mt-3 rounded px-3 py-3 text-[11px]" style={{ border: '1px solid rgba(224,160,128,0.15)', background: 'rgba(212,132,92,0.06)' }}>
            <div className="mb-2 font-semibold tracking-wide" style={{ color: '#E0A080' }}>X-RAY</div>
            {(meta.xray.memories_used ?? []).length > 0 && (
              <div className="space-y-1">
                {(meta.xray.memories_used ?? []).map((m, i) => (
                  <div key={i} className="flex items-start gap-2" style={{ color: 'rgba(240,235,225,0.5)' }}>
                    <span className="font-mono flex-shrink-0" style={{ color: '#E0A080' }}>T:{m.trust.toFixed(2)}</span>
                    <span className="line-clamp-1">{m.text}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Rating bar — thumbs up/down with memory citation panel */}
        {isAssistant && meta?.interaction_id && (
          <MessageRatingBar
            msg={{ ...props.msg, rating: localRating ?? undefined, ratingCategory: localRatingCat }}
            threadId={props.threadId}
            onRated={handleRated}
          />
        )}

        {/* Trust delta strip — shows trust movements since this turn (or last rating) */}
        {isAssistant && props.threadId && (
          <TrustDeltaStrip
            threadId={props.threadId}
            sinceTs={ratedAt != null ? ratedAt - 5 : props.msg.createdAt / 1000 - 2}
          />
        )}

        {/* Footer row — always visible timestamp + optional meta */}
        <div className="mt-4 flex items-center gap-3 pt-3" style={{ borderTop: '1px solid rgba(240,235,225,0.04)' }}>
          <span className="text-[10px] text-white/20 tabular-nums font-mono">{formatTime(props.msg.createdAt)}</span>

          {/* Cloud generation source indicator */}
          {meta?.generation_source && meta.generation_source !== 'local' && (
            <span
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
              style={{ background: 'rgba(212,132,92,0.1)', color: 'rgba(212,132,92,0.7)', border: '1px solid rgba(212,132,92,0.15)' }}
              title={`Generated by ${meta.generation_source === 'cloud_openai' ? 'OpenAI' : meta.generation_source === 'cloud_claude' ? 'Claude' : meta.generation_source}`}
            >
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
              </svg>
              {meta.generation_source === 'cloud_openai' ? 'via GPT-4o Mini'
                : meta.generation_source === 'cloud_claude' ? 'via Claude Sonnet'
                : meta.generation_source === 'cloud_fallback' ? 'via cloud fallback'
                : meta.generation_source === 'claude_fallback' ? 'via Claude fallback'
                : `via ${meta.generation_source}`}
            </span>
          )}

          {/* Status badges — condensed */}
          {meta && (
            <div className="flex items-center gap-1.5">
              {gatesFailed && (
                <button
                  onClick={() => setGateDebugOpen((v) => !v)}
                  className="rounded-full px-2 py-0.5 text-[10px] font-medium transition-opacity hover:opacity-80"
                  style={{ background: 'rgba(251,113,133,0.15)', color: '#fb7185' }}
                  title={meta?.gate_reason ? `Gate blocked: ${meta.gate_reason}` : 'Click to see why this was blocked'}
                >
                  gate fail{meta?.gate_reason ? ` · ${meta.gate_reason.replace(/_/g, ' ').slice(0, 30)}` : ''} {meta?.gate_debug ? (gateDebugOpen ? '▲' : '▼') : ''}
                </button>
              )}
              {contradictionDetected && (
                <button
                  onClick={() => setContradictionDrawerOpen(true)}
                  className="rounded-full px-2 py-0.5 text-[10px] font-medium transition-opacity hover:opacity-80"
                  style={{ background: 'rgba(251,146,60,0.15)', color: '#fb923c' }}
                  title="Open contradiction ledger"
                >
                  contradiction ›
                </button>
              )}
              {(meta as any)?.gaslighting_detected && (
                <span className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: 'rgba(251,113,133,0.12)', color: '#fb7185' }}>
                  ⚠ gaslighting
                </span>
              )}
              {((meta as any)?.reintroduced_claims_count ?? 0) > 0 && (
                <span className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: 'rgba(251,146,60,0.15)', color: '#fb923c' }}>
                  {(meta as any).reintroduced_claims_count} contradicted
                </span>
              )}
              {meta?.agent_activated && (
                <button
                  onClick={(e) => { e.stopPropagation(); props.onOpenAgentPanel?.(props.msg.id) }}
                  className="rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors hover:opacity-80"
                  style={{ background: 'rgba(224,160,128,0.18)', color: '#E0A080' }}
                >
                  agent trace
                </button>
              )}
              {responseType && responseType !== 'speech' && (
                <span className="text-[10px] text-white/20 uppercase tracking-wide">{responseType}</span>
              )}
            </div>
          )}

          <div className="ml-auto flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            {meta && (
              <button
                onClick={() => setMetaExpanded((v) => !v)}
                className="text-[11px] text-white/30 hover:text-white/60 transition-colors"
              >
                {metaExpanded ? 'less' : 'more'}
              </button>
            )}
            {props.onInspect && (
              <button
                onClick={(e) => { e.stopPropagation(); props.onInspect?.(props.msg.id) }}
                className="text-[11px] text-white/30 hover:text-white/60 transition-colors"
              >
                inspect
              </button>
            )}
          </div>
        </div>

        {/* Expanded meta panel */}
        {metaExpanded && meta && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
            className="mt-3 overflow-hidden rounded border border-white/8 bg-black/20 p-3 text-[11px] text-white/50"
          >
            <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 font-mono">
              {responseType && <div><span className="text-white/30">type</span> <span className="text-white/70">{responseType}</span></div>}
              {typeof gatesPassed === 'boolean' && <div><span className="text-white/30">gates</span> <span className={gatesPassed ? 'text-emerald-300' : 'text-amber-300'}>{gatesPassed ? 'pass' : 'fail'}</span></div>}
              {meta.gate_reason && <div className="col-span-2"><span className="text-white/30">reason</span> <span className="text-white/50">{meta.gate_reason}</span></div>}
              {typeof meta.confidence === 'number' && <div><span className="text-white/30">conf</span> <span className="text-white/70">{(meta.confidence * 100).toFixed(0)}%</span></div>}
              {typeof meta.intent_alignment === 'number' && <div><span className="text-white/30">intent</span> <span className="text-white/70">{meta.intent_alignment.toFixed(3)}</span></div>}
              {typeof meta.memory_alignment === 'number' && <div><span className="text-white/30">memory</span> <span className="text-white/70">{meta.memory_alignment.toFixed(3)}</span></div>}
              {typeof meta.unresolved_contradictions_total === 'number' && <div><span className="text-white/30">open</span> <span className="text-white/70">{meta.unresolved_contradictions_total}</span></div>}
              {meta.generation_source && <div><span className="text-white/30">gen</span> <span className="text-white/70">{meta.generation_source}</span></div>}
            </div>
            {(meta.pipeline_statuses ?? []).length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {(meta.pipeline_statuses ?? []).map((s, i) => (
                  <span key={i} className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-white/40">{s}</span>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </div>

      {/* Contradiction ledger drawer — portal-style, triggered by badge */}
      <ContradictionDrawer
        threadId={props.threadId ?? 'default'}
        open={contradictionDrawerOpen}
        onClose={() => setContradictionDrawerOpen(false)}
      />
    </motion.div>
  )
}
