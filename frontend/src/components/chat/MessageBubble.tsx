import { motion } from 'framer-motion'
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Editor from '@monaco-editor/react'
import type { ChatMessage, MessageRating } from '../../types'
import { formatTime } from '../../lib/time'
import { CitationViewer } from '../CitationViewer'
import { PipelineTrace } from './PipelineTrace'
import { MessageRatingBar } from './MessageRatingBar'

function MonacoBlock({ code, language }: { code: string; language?: string }) {
  const lines = code.split('\n').length
  const height = `${Math.max(100, Math.min(320, lines * 18 + 32))}px`
  return (
    <div className="my-3 overflow-hidden rounded-xl border border-white/10 bg-black/40">
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
        <code className="rounded-md px-1.5 py-0.5 font-mono text-[0.88em]" style={{ background: 'rgba(201,95,40,0.12)', color: '#e8a86a' }}>
          {children}
        </code>
      )
    }
    return <MonacoBlock code={codeText} language={language} />
  },
  blockquote({ children }: { children?: React.ReactNode }) {
    return (
      <blockquote className="my-3 pl-4 italic" style={{ borderLeft: '2px solid rgba(232,132,58,0.35)', color: 'rgba(240,235,225,0.55)' }}>
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
      <a href={href} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2" style={{ color: '#e8843a', textDecorationColor: 'rgba(232,132,58,0.4)' }}>
        {children}
      </a>
    )
  },
  hr() {
    return <hr className="my-4 border-white/10" />
  },
  table({ children }: { children?: React.ReactNode }) {
    return (
      <div className="my-3 overflow-x-auto rounded-xl border border-white/10">
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
  const [localRating, setLocalRating] = useState<MessageRating | null>(props.msg.rating ?? null)
  const [localRatingCat, setLocalRatingCat] = useState<string | undefined>(props.msg.ratingCategory ?? undefined)

  function handleRated(rating: MessageRating, category?: string) {
    setLocalRating(rating)
    setLocalRatingCat(category)
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

  // User message — compact right-aligned pill
  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        className="flex justify-end"
      >
        <div className="group max-w-[72%]">
          <div className="rounded-2xl px-4 py-3 text-[14.5px] leading-relaxed" style={{ background: 'var(--user-bubble)', color: 'var(--user-bubble-fg)', boxShadow: '0 2px 12px rgba(201,95,40,0.22)' }}>
            {props.msg.text}
          </div>
          <div className="mt-1 flex justify-end pr-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            <span className="text-[11px] text-white/30">{formatTime(props.msg.createdAt)}</span>
          </div>
        </div>
      </motion.div>
    )
  }

  // Assistant message — editorial, no bubble
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      className="group"
    >
      <div
        className={[
          props.selected ? 'rounded-2xl px-4 py-3 -mx-4' : '',
          localRating === 'down' ? 'border-l-2 pl-3 -ml-3' : '',
          localRating === 'up' ? 'border-l-2 pl-3 -ml-3' : '',
        ].join(' ')}
        style={{
          ...(props.selected ? { boxShadow: '0 0 0 1px rgba(201,95,40,0.3)', background: 'rgba(201,95,40,0.05)' } : {}),
          ...(localRating === 'down' ? { borderLeftColor: 'rgba(251,113,133,0.4)' } : {}),
          ...(localRating === 'up' ? { borderLeftColor: 'rgba(52,211,153,0.25)' } : {}),
        }}
      >
        {/* Profile updates */}
        {profileUpdates.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {profileUpdates.map((u, i) => (
              <span key={`${u.slot}-${i}`} className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-[11px]" style={{ border: '1px solid rgba(232,132,58,0.2)', background: 'rgba(201,95,40,0.08)', color: 'rgba(240,235,225,0.7)' }}>
                <span className="font-mono" style={{ color: '#e8843a' }}>{u.slot}</span>
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

        {/* Gate debug — inline when gate failed */}
        {gatesFailed && meta?.gate_debug && (
          <div className="mt-3 rounded-xl px-3 py-2.5 text-[11px]" style={{ border: '1px solid rgba(224,92,32,0.2)', background: 'rgba(224,92,32,0.06)' }}>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="font-mono font-semibold" style={{ color: '#e05c20' }}>WHY BLOCKED</span>
              {meta.gate_debug.trigger && (
                <span className="rounded px-1.5 py-0.5 font-mono" style={{ background: 'rgba(224,92,32,0.12)', color: '#e8843a' }}>{meta.gate_debug.trigger}</span>
              )}
              {meta.gate_debug.slot && (
                <span className="rounded px-1.5 py-0.5 font-mono" style={{ background: 'rgba(240,235,225,0.06)', color: '#a09880' }}>slot: {meta.gate_debug.slot}</span>
              )}
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
                    <span style={{ color: '#e8843a' }}>T:{m.trust.toFixed(2)}</span>
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
                <span style={{ color: '#e05c20' }}>{meta.gate_debug.hard_conflicts} hard conflict(s)</span>
              )}
            </div>
          </div>
        )}

        {/* Pipeline trace — persisted from streaming, collapsible */}
        {(meta?.pipeline_statuses ?? []).length > 0 && (
          <div className="mt-3">
            <PipelineTrace
              statuses={meta!.pipeline_statuses!}
              streaming={false}
              defaultOpen={false}
            />
          </div>
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
          <div className="mt-3 rounded-xl border border-white/8 bg-white/3 px-3 py-2 text-[11px] text-white/40">
            <span className="font-mono">{prov.id}</span>
            {prov.id && prov.text ? ' · ' : ''}
            <span className="line-clamp-1">{prov.text}</span>
          </div>
        ) : null}

        {/* X-ray mode */}
        {props.xrayMode && meta?.xray && (
          <div className="mt-3 rounded-xl px-3 py-3 text-[11px]" style={{ border: '1px solid rgba(232,132,58,0.15)', background: 'rgba(201,95,40,0.06)' }}>
            <div className="mb-2 font-semibold tracking-wide" style={{ color: '#e8843a' }}>X-RAY</div>
            {(meta.xray.memories_used ?? []).length > 0 && (
              <div className="space-y-1">
                {(meta.xray.memories_used ?? []).map((m, i) => (
                  <div key={i} className="flex items-start gap-2" style={{ color: 'rgba(240,235,225,0.5)' }}>
                    <span className="font-mono flex-shrink-0" style={{ color: '#e8843a' }}>T:{m.trust.toFixed(2)}</span>
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

        {/* Footer row — always visible timestamp + optional meta */}
        <div className="mt-3 flex items-center gap-3">
          <span className="text-[11px] text-white/25 tabular-nums">{formatTime(props.msg.createdAt)}</span>

          {/* Status badges — condensed */}
          {meta && (
            <div className="flex items-center gap-1.5">
              {gatesFailed && (
                <span className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: 'rgba(251,113,133,0.15)', color: '#fb7185' }}>
                  gate fail
                </span>
              )}
              {contradictionDetected && (
                <span className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: 'rgba(251,146,60,0.15)', color: '#fb923c' }}>
                  contradiction
                </span>
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
                  style={{ background: 'rgba(232,132,58,0.18)', color: '#e8843a' }}
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
            className="mt-3 overflow-hidden rounded-xl border border-white/8 bg-black/20 p-3 text-[11px] text-white/50"
          >
            <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 font-mono">
              {responseType && <div><span className="text-white/30">type</span> <span className="text-white/70">{responseType}</span></div>}
              {typeof gatesPassed === 'boolean' && <div><span className="text-white/30">gates</span> <span className={gatesPassed ? 'text-emerald-300' : 'text-amber-300'}>{gatesPassed ? 'pass' : 'fail'}</span></div>}
              {meta.gate_reason && <div className="col-span-2"><span className="text-white/30">reason</span> <span className="text-white/50">{meta.gate_reason}</span></div>}
              {typeof meta.confidence === 'number' && <div><span className="text-white/30">conf</span> <span className="text-white/70">{(meta.confidence * 100).toFixed(0)}%</span></div>}
              {typeof meta.intent_alignment === 'number' && <div><span className="text-white/30">intent</span> <span className="text-white/70">{meta.intent_alignment.toFixed(3)}</span></div>}
              {typeof meta.memory_alignment === 'number' && <div><span className="text-white/30">memory</span> <span className="text-white/70">{meta.memory_alignment.toFixed(3)}</span></div>}
              {typeof meta.unresolved_contradictions_total === 'number' && <div><span className="text-white/30">open</span> <span className="text-white/70">{meta.unresolved_contradictions_total}</span></div>}
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
    </motion.div>
  )
}
