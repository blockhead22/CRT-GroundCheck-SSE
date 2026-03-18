import { motion } from 'framer-motion'
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Editor from '@monaco-editor/react'
import type { ChatMessage } from '../../types'
import { formatTime } from '../../lib/time'
import { CitationViewer } from '../CitationViewer'

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
        <code className="rounded-md bg-white/8 px-1.5 py-0.5 font-mono text-[0.88em] text-violet-200">
          {children}
        </code>
      )
    }
    return <MonacoBlock code={codeText} language={language} />
  },
  blockquote({ children }: { children?: React.ReactNode }) {
    return (
      <blockquote className="my-3 border-l-2 border-violet-500/40 pl-4 text-white/60 italic">
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
      <a href={href} target="_blank" rel="noopener noreferrer" className="text-violet-300 underline decoration-violet-500/40 underline-offset-2 hover:text-violet-200">
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
          <div className="rounded-2xl px-4 py-3 text-[14.5px] leading-relaxed shadow-[0_2px_12px_rgba(56,189,248,0.18)]" style={{ background: 'var(--user-bubble)', color: 'var(--user-bubble-fg)' }}>
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
      <div className={props.selected ? 'rounded-2xl ring-1 ring-violet-500/30 bg-violet-500/5 px-4 py-3 -mx-4' : ''}>
        {/* Profile updates */}
        {profileUpdates.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {profileUpdates.map((u, i) => (
              <span key={`${u.slot}-${i}`} className="inline-flex items-center gap-1 rounded-full border border-indigo-500/25 bg-indigo-500/8 px-3 py-1 text-[11px] text-indigo-200/80">
                <span className="font-mono text-indigo-300">{u.slot}</span>
                <span className="text-indigo-200/40">·</span>
                <span>{(u.old || '—')} → {(u.new || '—')}</span>
              </span>
            ))}
          </div>
        )}

        {/* Main message text */}
        <div className="text-[15px] text-white/90">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents as any}>
            {props.msg.text}
          </ReactMarkdown>
        </div>

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
          <div className="mt-3 rounded-xl border border-violet-500/20 bg-violet-500/5 px-3 py-3 text-[11px]">
            <div className="mb-2 font-semibold tracking-wide text-violet-300">X-RAY</div>
            {(meta.xray.memories_used ?? []).length > 0 && (
              <div className="space-y-1">
                {(meta.xray.memories_used ?? []).map((m, i) => (
                  <div key={i} className="flex items-start gap-2 text-white/60">
                    <span className="font-mono text-violet-300 flex-shrink-0">T:{m.trust.toFixed(2)}</span>
                    <span className="line-clamp-1">{m.text}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
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
                  style={{ background: 'rgba(56,189,248,0.15)', color: '#38bdf8' }}
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
              {meta.gate_reason && <div className="col-span-2"><span className="text-white/30">reason</span> <span className="text-white/60">{meta.gate_reason}</span></div>}
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
