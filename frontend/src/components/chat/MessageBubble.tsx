import { motion } from 'framer-motion'
import { useState, useEffect, useCallback, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Editor from '@monaco-editor/react'
import type { ChatMessage } from '../../types'
import { formatTime } from '../../lib/time'
import { CitationViewer } from '../CitationViewer'
import { getReasoningTrace, getReflectionTrace, type ReflectionTrace } from '../../lib/api'

function pct01(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const clamped = Math.max(0, Math.min(1, v))
  return `${Math.round(clamped * 100)}%`
}


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

type TaskingMeta = {
  mode?: string
  passes?: number
  skipped?: string
  interval_seconds?: number
  plan?: {
    notes?: string | null
    tasks?: Array<{
      task_id: string
      goal: string
      acceptance_criteria: string
      status?: string
      summary?: string | null
    }>
  } | null
  coverage?: {
    score?: number
    missing_items?: string[]
    notes?: string | null
  } | null
} | null

function TaskingDropdown({ tasking }: { tasking?: TaskingMeta }) {
  const [isOpen, setIsOpen] = useState(false)
  if (!tasking) return null

  const tasks = tasking.plan?.tasks ?? []
  const missing = tasking.coverage?.missing_items ?? []
  const score = tasking.coverage?.score
  const passes = tasking.passes
  const skipped = tasking.skipped
  const tasksCount = tasks.length
  const missingCount = missing.length

  const status = (() => {
    if (skipped) {
      return { label: 'SKIPPED', className: 'border-slate-500/40 bg-slate-500/15 text-slate-200' }
    }
    if (typeof score === 'number') {
      if (score >= 0.9) return { label: 'OK', className: 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200' }
      if (score >= 0.6) return { label: 'PARTIAL', className: 'border-amber-500/40 bg-amber-500/15 text-amber-200' }
      return { label: 'LOW', className: 'border-rose-500/40 bg-rose-500/15 text-rose-200' }
    }
    return { label: 'UNKNOWN', className: 'border-cyan-500/40 bg-cyan-500/15 text-cyan-200' }
  })()

  return (
    <div className="mt-2 rounded-xl border border-cyan-500/30 bg-cyan-500/5 overflow-hidden" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={(e) => {
          e.stopPropagation()
          e.preventDefault()
          setIsOpen(!isOpen)
        }}
        className="w-full flex items-center justify-between px-3 py-2 text-[11px] font-medium text-cyan-200 hover:bg-cyan-500/10 transition-colors"
      >
        <span className="flex items-center gap-2">
          <span>Tasking Loop</span>
          <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${status.className}`}>
            {status.label}
          </span>
          {typeof score === 'number' ? (
            <span className="text-cyan-200/70">Coverage {pct01(score)}</span>
          ) : null}
          <span className="text-cyan-200/70">Tasks {tasksCount}</span>
        </span>
        <motion.span
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          v
        </motion.span>
      </button>
      {isOpen ? (
        <div className="px-3 pb-3 text-[11px] text-cyan-100">
          {skipped ? (
            <div className="rounded-lg bg-black/20 p-2 text-cyan-200/70">
              Tasking loop skipped ({skipped}).
            </div>
          ) : null}

          <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-white/70">
            {typeof passes === 'number' ? (
              <span className="rounded bg-black/20 px-2 py-0.5">Passes {passes}</span>
            ) : null}
            <span className="rounded bg-black/20 px-2 py-0.5">Missing {missingCount}</span>
            {typeof tasking.interval_seconds === 'number' && tasking.interval_seconds > 0 ? (
              <span className="rounded bg-black/20 px-2 py-0.5">Interval {tasking.interval_seconds}s</span>
            ) : null}
          </div>

          {tasking.plan?.notes ? (
            <div className="mt-2 text-cyan-200/70">Plan notes: {tasking.plan.notes}</div>
          ) : null}

          {tasks.length > 0 ? (
            <div className="mt-2">
              <div className="font-semibold text-cyan-200">Plan</div>
              <ul className="mt-1 space-y-1">
                {tasks.map((t) => (
                  <li key={t.task_id} className="rounded-md bg-black/20 px-2 py-1 border border-white/5">
                    <div className="flex items-center gap-2">
                      <div className="font-mono text-cyan-200">{t.task_id}</div>
                      {t.status ? (
                        <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-white/60">{t.status}</span>
                      ) : null}
                    </div>
                    <div className="text-white/80">{t.goal}</div>
                    <div className="text-white/50">Accept: {t.acceptance_criteria}</div>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="mt-2">
            <div className="font-semibold text-cyan-200">Coverage</div>
            <div className="text-white/70">
              Score: {typeof score === 'number' ? pct01(score) : 'n/a'}
            </div>
            {missing.length > 0 ? (
              <ul className="mt-1 space-y-1 text-amber-200">
                {missing.map((m, i) => (
                  <li key={`${m}-${i}`}>Missing: {m}</li>
                ))}
              </ul>
            ) : (
              <div className="text-white/50">Missing: none</div>
            )}
            {tasking.coverage?.notes ? (
              <div className="mt-1 text-white/50">Notes: {tasking.coverage.notes}</div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}


function PipelineDropdown({ statuses, draft }: { statuses: string[]; draft?: string | null }) {
  const [isOpen, setIsOpen] = useState(false)
  const hasDraft = Boolean(draft && draft.trim())
  if (!statuses.length && !hasDraft) return null

  return (
    <div className="mt-2 rounded-xl border border-sky-500/30 bg-sky-500/10 overflow-hidden" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={(e) => {
          e.stopPropagation()
          e.preventDefault()
          setIsOpen(!isOpen)
        }}
        className="w-full flex items-center justify-between px-3 py-2 text-[11px] font-medium text-sky-200 hover:bg-sky-500/10 transition-colors"
      >
        <span className="flex items-center gap-2">
          <span>CRT Pipeline</span>
          {statuses.length > 0 ? (
            <span className="text-sky-200/70">Steps {statuses.length}</span>
          ) : null}
          {hasDraft ? (
            <span className="text-sky-200/70">Draft saved</span>
          ) : null}
        </span>
        <motion.span animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
          v
        </motion.span>
      </button>
      {isOpen ? (
        <div className="px-3 pb-3 text-[11px] text-sky-100">
          {statuses.length > 0 ? (
            <div className="mt-2">
              <div className="font-semibold text-sky-200">Steps</div>
              <ul className="mt-1 space-y-1">
                {statuses.map((s, i) => (
                  <li key={`${s}-${i}`} className="rounded-md bg-black/20 px-2 py-1">{s}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {hasDraft ? (
            <div className="mt-3">
              <div className="font-semibold text-sky-200">Draft (live stream)</div>
              <div className="mt-1 rounded-md bg-black/20 px-2 py-2 text-white/70 whitespace-pre-wrap">{draft}</div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}


/** Collapsible thinking/reasoning dropdown */
function ThinkingDropdown({ thinking, traceId, threadId }: { thinking?: string | null; traceId?: string | null; threadId?: string | null }) {
  const [isOpen, setIsOpen] = useState(false)
  const [lazyThinking, setLazyThinking] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  
  // The actual content to display
  const displayContent = thinking || lazyThinking
  
  // Can show dropdown if we have content OR a trace_id to lazy load from
  const canShow = !!(displayContent?.trim() || traceId)
  
  // Lazy load thinking content when user opens and we only have trace_id
  const loadThinking = useCallback(async () => {
    if (!traceId || lazyThinking || thinking) return
    setIsLoading(true)
    setLoadError(null)
    try {
      const trace = await getReasoningTrace(traceId, threadId || undefined)
      if (trace?.thinking_content) {
        setLazyThinking(trace.thinking_content)
      } else {
        setLoadError('Thinking content not found')
      }
    } catch (err) {
      setLoadError('Failed to load thinking')
      console.error('Failed to load thinking trace:', err)
    } finally {
      setIsLoading(false)
    }
  }, [traceId, threadId, lazyThinking, thinking])
  
  // When opening, trigger lazy load if needed
  useEffect(() => {
    if (isOpen && !displayContent && traceId && !isLoading && !loadError) {
      loadThinking()
    }
  }, [isOpen, displayContent, traceId, isLoading, loadError, loadThinking])
  
  if (!canShow) return null
  
  const charCount = displayContent?.length || 0
  
  return (
    <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/5 overflow-hidden" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={(e) => {
          e.stopPropagation()
          e.preventDefault()
          setIsOpen(!isOpen)
        }}
        className="w-full flex items-center justify-between px-3 py-2 text-[11px] font-medium text-amber-300 hover:bg-amber-500/10 transition-colors"
      >
        <span className="flex items-center gap-2">
          <span>🧠</span>
          <span>Agent Thinking</span>
          {charCount > 0 ? (
            <span className="text-amber-300/60">({charCount} chars)</span>
          ) : traceId ? (
            <span className="text-amber-300/60">(click to load)</span>
          ) : null}
        </span>
        <motion.span
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          ▼
        </motion.span>
      </button>
      {isOpen && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="px-3 pb-3"
        >
          <div className="max-h-64 overflow-y-auto rounded-lg bg-black/30 p-3 text-[11px] text-amber-200/80 whitespace-pre-wrap font-mono leading-relaxed">
            {isLoading ? (
              <span className="text-amber-300/60 animate-pulse">Loading thinking content...</span>
            ) : loadError ? (
              <span className="text-red-400">{loadError}</span>
            ) : displayContent ? (
              displayContent
            ) : (
              <span className="text-amber-300/60">No thinking content available</span>
            )}
          </div>
        </motion.div>
      )}
    </div>
  )
}

/** Collapsible reflection/self-assessment dropdown */
function ReflectionDropdown({ 
  traceId, 
  threadId,
  confidence,
  label 
}: { 
  traceId?: string | null
  threadId?: string | null
  confidence?: number | null
  label?: string | null
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [trace, setTrace] = useState<ReflectionTrace | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  
  if (!traceId) return null
  
  // Lazy load reflection content when user opens
  const loadReflection = useCallback(async () => {
    if (!traceId || trace) return
    setIsLoading(true)
    setLoadError(null)
    try {
      const data = await getReflectionTrace(traceId, threadId || undefined)
      if (data) {
        setTrace(data)
      } else {
        setLoadError('Reflection not found')
      }
    } catch (err) {
      setLoadError('Failed to load reflection')
      console.error('Failed to load reflection trace:', err)
    } finally {
      setIsLoading(false)
    }
  }, [traceId, threadId, trace])
  
  // Trigger load on open
  useEffect(() => {
    if (isOpen && !trace && !isLoading && !loadError) {
      loadReflection()
    }
  }, [isOpen, trace, isLoading, loadError, loadReflection])
  
  // Color coding based on confidence
  const getConfidenceColor = (score: number | null | undefined) => {
    if (score === null || score === undefined) return 'text-purple-300'
    if (score >= 0.7) return 'text-green-400'
    if (score >= 0.4) return 'text-yellow-400'
    return 'text-red-400'
  }
  
  const confScore = trace?.confidence_score ?? confidence
  const confLabel = trace?.confidence_label ?? label ?? 'unknown'
  const colorClass = getConfidenceColor(confScore)
  
  return (
    <div className="mt-2 rounded-xl border border-purple-500/30 bg-purple-500/5 overflow-hidden" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={(e) => {
          e.stopPropagation()
          e.preventDefault()
          setIsOpen(!isOpen)
        }}
        className="w-full flex items-center justify-between px-3 py-2 text-[11px] font-medium text-purple-300 hover:bg-purple-500/10 transition-colors"
      >
        <span className="flex items-center gap-2">
          <span>🔍</span>
          <span>Self-Assessment</span>
          {confScore !== null && confScore !== undefined ? (
            <span className={`${colorClass} font-mono`}>
              {Math.round(confScore * 100)}% ({confLabel})
            </span>
          ) : (
            <span className="text-purple-300/60">(click to load)</span>
          )}
        </span>
        <motion.span
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          ▼
        </motion.span>
      </button>
      {isOpen && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="px-3 pb-3"
        >
          {isLoading ? (
            <div className="text-purple-300/60 animate-pulse text-[11px]">Loading self-assessment...</div>
          ) : loadError ? (
            <div className="text-red-400 text-[11px]">{loadError}</div>
          ) : trace ? (
            <div className="space-y-3 text-[11px]">
              {/* Confidence Bar */}
              <div className="flex items-center gap-2">
                <span className="text-white/50">Confidence:</span>
                <div className="flex-1 h-2 bg-black/30 rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all ${
                      trace.confidence_score >= 0.7 ? 'bg-green-500' :
                      trace.confidence_score >= 0.4 ? 'bg-yellow-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${trace.confidence_score * 100}%` }}
                  />
                </div>
                <span className={colorClass}>{Math.round(trace.confidence_score * 100)}%</span>
              </div>
              
              {/* Hallucination Risk */}
              <div className="flex items-center gap-2">
                <span className="text-white/50">Hallucination Risk:</span>
                <span className={
                  trace.hallucination_risk === 'low' ? 'text-green-400' :
                  trace.hallucination_risk === 'medium' ? 'text-yellow-400' :
                  trace.hallucination_risk === 'high' ? 'text-red-400' : 'text-white/60'
                }>
                  {trace.hallucination_risk.toUpperCase()}
                </span>
              </div>
              
              {/* Reasoning */}
              {trace.reasoning && (
                <div>
                  <span className="text-white/50">Assessment:</span>
                  <div className="mt-1 text-white/70 bg-black/20 rounded p-2">
                    {trace.reasoning}
                  </div>
                </div>
              )}
              
              {/* Fact Checks */}
              {trace.fact_checks && trace.fact_checks.length > 0 && (
                <div>
                  <span className="text-white/50">Fact Checks:</span>
                  <ul className="mt-1 space-y-1">
                    {trace.fact_checks.map((fc, i) => (
                      <li key={i} className={`flex items-start gap-2 ${fc.supported ? 'text-green-400/80' : 'text-red-400/80'}`}>
                        <span>{fc.supported ? '✓' : '✗'}</span>
                        <span className="text-white/70">{fc.claim}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              {/* Suggested Action */}
              <div className="flex items-center gap-2 pt-1 border-t border-purple-500/20">
                <span className="text-white/50">Action:</span>
                <span className={`font-medium ${
                  trace.suggested_action === 'accept' ? 'text-green-400' :
                  trace.suggested_action === 'refine' ? 'text-yellow-400' : 'text-red-400'
                }`}>
                  {trace.suggested_action.toUpperCase()}
                </span>
              </div>
            </div>
          ) : (
            <div className="text-purple-300/60 text-[11px]">No reflection data available</div>
          )}
        </motion.div>
      )}
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
  const pipelineStatuses = meta?.pipeline_statuses ?? []
  const draftResponse = meta?.draft_response ?? null
  const showPipeline = isAssistant && (pipelineStatuses.length > 0 || Boolean(draftResponse))

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
            ? 'bg-violet-600 text-white'
            : 'bg-white/5 text-white border border-white/10') +
          (props.selected ? ' ring-2 ring-violet-500/60' : '')
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

        {showPipeline ? (
          <PipelineDropdown statuses={pipelineStatuses} draft={draftResponse} />
        ) : null}

        {meta?.tasking && isAssistant ? (
          <TaskingDropdown tasking={meta.tasking as TaskingMeta} />
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

        {/* Collapsible Thinking Section */}
        {(meta?.thinking || meta?.thinking_trace_id) && isAssistant ? (
          <ThinkingDropdown thinking={meta.thinking} traceId={meta.thinking_trace_id} threadId={props.threadId} />
        ) : null}

        {/* Collapsible Reflection/Self-Assessment Section */}
        {meta?.reflection_trace_id && isAssistant ? (
          <ReflectionDropdown 
            traceId={meta.reflection_trace_id} 
            threadId={props.threadId}
            confidence={meta.reflection_confidence}
            label={meta.reflection_label}
          />
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
