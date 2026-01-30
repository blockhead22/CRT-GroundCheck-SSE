import { motion } from 'framer-motion'
import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Editor from '@monaco-editor/react'
import type { ChatMessage } from '../../types'
import { formatTime } from '../../lib/time'
import { CitationViewer } from '../CitationViewer'


function MonacoBlock({ code, language }: { code: string; language?: string }) {
  const height = useMemo(() => {
    const lines = code.split('\n').length
    const base = Math.max(120, Math.min(320, lines * 18 + 32))
    return `${base}px`
  }, [code])

  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/40">
      <Editor
        height={height}
        defaultLanguage={language || 'plaintext'}
        value={code}
        theme="vs-dark"
        options={{
          readOnly: true,
          minimap: { enabled: false },
          fontSize: 12,
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
  const showMeta = isAssistant && Boolean(meta)
  const profileUpdates = meta?.profile_updates ?? []
  const showProfileUpdates = isAssistant && profileUpdates.length > 0
  const grounding = (() => {
    if (!isAssistant || !meta) return null
    const pm: any[] = (meta as any).prompt_memories ?? []
    const rm: any[] = (meta as any).retrieved_memories ?? []

    const hasSystemRetrieved = rm.some((m) => String(m?.source || '').toLowerCase() === 'system')
    const hasFallbackRetrieved = rm.some((m) => String(m?.source || '').toLowerCase() === 'fallback')
    const hasNonAuditableRetrieved = rm.some((m) => {
      const s = String(m?.source || '').toLowerCase()
      return s && s !== 'user' && s !== 'external'
    })

    const factLines = pm.filter((m) => String(m?.text || '').trim().toLowerCase().startsWith('fact:'))
    const badFactSource = factLines.some((m) => {
      const s = String(m?.source || '').toLowerCase()
      return s && s !== 'user'
    })

    const responseType = String((meta as any).response_type || '').toLowerCase()
    const isExplanation = responseType === 'explanation'
    const hasDocCitation = pm.some((m) => String(m?.memory_id || '').toLowerCase().startsWith('doc:'))

    if (badFactSource || hasSystemRetrieved || hasFallbackRetrieved) {
      return { level: 'bad', reason: 'Non-auditable sources present (system/fallback or non-user FACT lines).' }
    }
    if (isExplanation && !hasDocCitation) {
      return { level: 'weak', reason: 'Explanation without doc citations.' }
    }
    if (hasNonAuditableRetrieved) {
      return { level: 'weak', reason: 'Retrieved memories include non-user sources.' }
    }
    return { level: 'ok', reason: 'Grounded in user/external memories or doc citations.' }
  })()

  const prov = (() => {
    if (!isAssistant || !meta || !(isBelief || isExplanation)) return null
    const pm = meta.prompt_memories ?? []
    const rm = meta.retrieved_memories ?? []
    const best =
      pm.find((m: any) => String(m?.memory_id || '').toLowerCase().startsWith('doc:')) ||
      pm.find((m) => (m.text || '').trim().toLowerCase().startsWith('fact:')) ||
      pm[0] ||
      rm[0]
    const text = (best?.text || '').trim()
    const id = (best as any)?.memory_id ? String((best as any).memory_id) : ''
    if (!text && !id) return null
    return { id, text }
  })()

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      className={isUser ? 'flex justify-end' : 'flex justify-start'}
    >
      <div
        className={
          'max-w-[80%] rounded-2xl px-4 py-3 text-sm shadow-card md:max-w-[70%] ' +
          (isUser
            ? 'accent-bubble text-white'
            : 'bg-white/5 text-white border border-white/10') +
          (props.selected ? ' ring-2 ring-cyan-400/60' : '')
        }
      >
        {showMeta ? (
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span
              className={
                'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ' +
                (isBelief
                  ? 'bg-emerald-500/15 text-emerald-200'
                  : isExplanation
                    ? 'bg-sky-500/15 text-sky-200'
                    : 'bg-white/10 text-white/80')
              }
              title="CRT response type"
            >
              {isBelief ? 'BELIEF' : (responseType || 'SPEECH').toUpperCase()}
            </span>

            {typeof gatesPassed === 'boolean' ? (
              <span
                className={
                  'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ' +
                  (gatesPassed ? 'bg-emerald-500/15 text-emerald-200' : 'bg-amber-500/15 text-amber-200')
                }
                title={
                  gatesPassed
                    ? 'Reconstruction gates passed'
                    : `Reconstruction gates failed${meta?.gate_reason ? `: ${meta.gate_reason}` : ''}`
                }
              >
                {gatesPassed ? 'GATES: PASS' : 'GATES: FAIL'}
              </span>
            ) : null}

            {meta?.contradiction_detected ? (
              <span
                className="inline-flex items-center rounded-full bg-rose-500/15 px-2 py-0.5 text-[11px] font-medium text-rose-200"
                title="A contradiction was detected and recorded"
              >
                CONTRADICTION
              </span>
            ) : null}

            {(meta as any)?.gaslighting_detected ? (
              <span
                className="inline-flex items-center rounded-full bg-orange-500/15 px-2 py-0.5 text-[11px] font-medium text-orange-200"
                title="Gaslighting attempt detected - citing original claim"
              >
                ⚠️ GASLIGHTING
              </span>
            ) : null}

            {(meta as any)?.llm_disclosures && (meta as any).llm_disclosures.length > 0 ? (
              <span
                className="inline-flex items-center rounded-full bg-cyan-500/15 px-2 py-0.5 text-[11px] font-medium text-cyan-200"
                title="LLM made claims that contradict user facts or previous LLM claims"
              >
                📝 LLM CONFLICT ({(meta as any).llm_disclosures.length})
              </span>
            ) : null}

            {(meta?.reintroduced_claims_count ?? 0) > 0 ? (
              <span
                className="inline-flex items-center rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-200"
                title={`This answer uses ${meta!.reintroduced_claims_count} contradicted ${meta!.reintroduced_claims_count === 1 ? 'memory' : 'memories'}`}
              >
                ⚠️ CONTRADICTED CLAIMS ({meta!.reintroduced_claims_count})
              </span>
            ) : null}

            {grounding ? (
              <span
                className={
                  'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ' +
                  (grounding.level === 'ok'
                    ? 'bg-emerald-500/15 text-emerald-200'
                    : grounding.level === 'bad'
                      ? 'bg-rose-500/15 text-rose-200'
                      : 'bg-amber-500/15 text-amber-200')
                }
                title={grounding.reason}
              >
                {grounding.level === 'ok' ? 'GROUNDING: OK' : grounding.level === 'bad' ? 'GROUNDING: BAD' : 'GROUNDING: WEAK'}
              </span>
            ) : null}

            {meta?.agent_activated ? (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  props.onOpenAgentPanel?.(props.msg.id)
                }}
                className="inline-flex items-center rounded-full bg-blue-500/15 px-2 py-0.5 text-[11px] font-medium text-blue-200 hover:bg-blue-500/25 transition-colors"
                title="Agent was activated - click to view execution trace"
              >
                🤖 AGENT TRACE
              </button>
            ) : null}
          </div>
        ) : null}

        {showProfileUpdates ? (
          <div className="mb-2 rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-3 py-2 text-[11px] text-indigo-100">
            <div className="font-semibold tracking-wide text-indigo-200">PROFILE UPDATE</div>
            <div className="mt-1 space-y-1">
              {profileUpdates.map((update, index) => {
                const oldValue = (update.old || '').trim() || '(empty)'
                const newValue = (update.new || '').trim() || '(empty)'
                return (
                  <div key={`${update.slot}-${index}`} className="flex flex-col gap-0.5">
                    <div className="font-mono text-indigo-200">{update.slot}</div>
                    <div className="text-white/70">{oldValue} -&gt; {newValue}</div>
                  </div>
                )
              })}
            </div>
          </div>
        ) : null}

        <div className="text-white/90 leading-6">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p({ children }) {
                return <p className="mb-2 last:mb-0">{children}</p>
              },
              ul({ children }) {
                return <ul className="mb-2 list-disc space-y-1 pl-5">{children}</ul>
              },
              ol({ children }) {
                return <ol className="mb-2 list-decimal space-y-1 pl-5">{children}</ol>
              },
              li({ children }) {
                return <li className="text-white/80">{children}</li>
              },
              code(props) {
                const { children, className, inline } = props
                const codeText = String(children ?? '').replace(/\n$/, '')
                const match = /language-([a-zA-Z0-9_-]+)/.exec(className || '')
                const language = match ? match[1] : undefined
                const isBlock = Boolean(language) || codeText.includes('\n')
                if (inline || !isBlock) {
                  return (
                    <code className="rounded bg-white/10 px-1 py-0.5 text-[0.9em] text-white/90">
                      {children}
                    </code>
                  )
                }
                return <MonacoBlock code={codeText} language={language} />
              },
              blockquote({ children }) {
                return (
                  <blockquote className="border-l-2 border-white/20 pl-3 text-white/70">
                    {children}
                  </blockquote>
                )
              },
            }}
          >
            {props.msg.text}
          </ReactMarkdown>
        </div>

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
          <div className="mt-3 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-[11px] text-white/60">
            <div className="font-semibold tracking-wide text-white/50">{isExplanation ? 'CITATIONS' : 'PROVENANCE'}</div>
            <div className="mt-1 line-clamp-2 whitespace-pre-wrap text-white/70">
              {prov.id ? <span className="font-mono text-white/60">{prov.id}</span> : null}
              {prov.id && prov.text ? <span className="text-white/40"> · </span> : null}
              {prov.text || '—'}
            </div>
          </div>
        ) : null}

        {props.xrayMode && meta?.xray && isAssistant ? (
          <div className="mt-3 rounded-xl border border-violet-500/30 bg-violet-500/10 px-3 py-3 text-[11px]">
            <div className="font-semibold tracking-wide text-violet-300">🔬 X-RAY MODE</div>
            
            {meta.xray.memories_used && meta.xray.memories_used.length > 0 ? (
              <div className="mt-2">
                <div className="text-white/50">Memories Used:</div>
                <ul className="mt-1 space-y-1">
                  {meta.xray.memories_used.map((m, i) => (
                    <li key={i} className="text-white/70">
                      <span className="font-mono text-violet-300">T:{m.trust.toFixed(2)}</span>
                      <span className="mx-1 text-white/40">·</span>
                      {m.reintroduced_claim ? (
                        <span className="inline-flex items-center rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-medium text-amber-200 mr-1">
                          ⚠️ CONTRADICTED
                        </span>
                      ) : null}
                      <span className="line-clamp-1">{m.text}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            
            {meta.xray.conflicts_detected && meta.xray.conflicts_detected.length > 0 ? (
              <div className="mt-3">
                <div className="text-rose-300">⚠️ Conflicts Detected:</div>
                <ul className="mt-1 space-y-2">
                  {meta.xray.conflicts_detected.map((c, i) => (
                    <li key={i} className="rounded border border-rose-500/20 bg-rose-500/10 p-2">
                      <div className="text-white/60"><span className="font-semibold">Old:</span> {c.old}</div>
                      <div className="text-white/60 mt-1"><span className="font-semibold">New:</span> {c.new}</div>
                      <div className="text-rose-300 mt-1 text-[10px]">Status: {c.status}</div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}

        <div
          className={
            isUser
              ? 'mt-2 flex items-center justify-end gap-2 text-[11px] text-white/80'
              : 'mt-2 flex items-center justify-end gap-2 text-[11px] text-white/40'
          }
        >
          {!isUser ? (
            <button
              onClick={(e) => {
                e.stopPropagation()
                props.onInspect?.(props.msg.id)
              }}
              className="text-white/70 underline decoration-white/30 underline-offset-2 hover:text-white"
            >
              Inspector
            </button>
          ) : null}
          <span>{formatTime(props.msg.createdAt)}</span>
        </div>
      </div>
    </motion.div>
  )
}
