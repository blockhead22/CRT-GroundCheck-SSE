import { motion } from 'framer-motion'
import { useCallback, useEffect, useState } from 'react'
import type { ChatMessage } from '../../types'
import { getReasoningTrace, getReflectionTrace, type ReflectionTrace } from '../../lib/api'

function pct01(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const clamped = Math.max(0, Math.min(1, v))
  return `${Math.round(clamped * 100)}%`
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

function PipelineCrumbs({ statuses, phase }: { statuses: string[]; phase?: string | null }) {
  if (!statuses.length && !phase) return null

  return (
    <div className="rounded-xl glass-card px-3 py-2 text-xs text-white/80">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-semibold uppercase tracking-wide text-white/40">Pipeline</div>
        {phase ? (
          <div className="text-[11px] text-cyan-200">Phase: {phase.charAt(0).toUpperCase() + phase.slice(1)}</div>
        ) : null}
      </div>
      {statuses.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {statuses.map((status, idx) => (
            <span
              key={`${status}-${idx}`}
              className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-white/70"
            >
              {status}
            </span>
          ))}
        </div>
      ) : (
        <div className="mt-1 text-[11px] text-white/40">No pipeline updates yet.</div>
      )}
    </div>
  )
}

function TaskingSection({ tasking }: { tasking?: TaskingMeta }) {
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
    <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
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
        <motion.span animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
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

function PipelineSection({ statuses, draft }: { statuses: string[]; draft?: string | null }) {
  const [isOpen, setIsOpen] = useState(false)
  const hasDraft = Boolean(draft && draft.trim())
  if (!statuses.length && !hasDraft) return null

  return (
    <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
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

function ThinkingSection({ thinking, traceId, threadId }: { thinking?: string | null; traceId?: string | null; threadId?: string | null }) {
  const [isOpen, setIsOpen] = useState(false)
  const [lazyThinking, setLazyThinking] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const displayContent = thinking || lazyThinking
  const canShow = !!(displayContent?.trim() || traceId)

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

  useEffect(() => {
    if (isOpen && !displayContent && traceId && !isLoading && !loadError) {
      loadThinking()
    }
  }, [isOpen, displayContent, traceId, isLoading, loadError, loadThinking])

  if (!canShow) return null

  const charCount = displayContent?.length || 0

  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
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
        <motion.span animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
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

function ReflectionSection({ 
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

  useEffect(() => {
    if (isOpen && !trace && !isLoading && !loadError) {
      loadReflection()
    }
  }, [isOpen, trace, isLoading, loadError, loadReflection])

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
    <div className="rounded-xl border border-purple-500/30 bg-purple-500/5 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
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
        <motion.span animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
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

              {trace.reasoning && (
                <div>
                  <span className="text-white/50">Assessment:</span>
                  <div className="mt-1 text-white/70 bg-black/20 rounded p-2">
                    {trace.reasoning}
                  </div>
                </div>
              )}

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

export function CrtInspector(props: {
  message: ChatMessage | null
  onClear: () => void
  threadId?: string | null
  streamStatusLog?: string[]
  streamPhase?: string | null
}) {
  const hasMessage = Boolean(props.message && props.message.role === 'assistant')
  const meta = hasMessage ? props.message?.crt : null
  const pipelineCrumbs = hasMessage
    ? (meta?.pipeline_statuses ?? [])
    : (props.streamStatusLog ?? [])
  const pipelinePhase = hasMessage ? null : (props.streamPhase ?? null)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-white">Inspector</div>
        {hasMessage ? (
          <button
            onClick={props.onClear}
            className="rounded-xl border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/80 hover:bg-white/10"
            title="Clear selection"
          >
            Clear
          </button>
        ) : null}
      </div>

      <PipelineCrumbs statuses={pipelineCrumbs} phase={pipelinePhase} />

      {!hasMessage ? (
        <div className="text-sm text-white/60">Select an assistant message to inspect CRT details.</div>
      ) : (
        <>
          <div className="rounded-xl glass-card px-3 py-2 text-xs text-white/80">
            <div className="font-medium text-white">Message</div>
            <div className="mt-1 line-clamp-6 whitespace-pre-wrap text-white/80">{props.message?.text}</div>
          </div>

          <div className="mt-1 grid grid-cols-2 gap-3 text-xs">
            <div className="rounded-xl glass-card px-3 py-2">
              <div className="text-white/60">Response</div>
              <div className="mt-0.5 font-medium text-white">{(meta?.response_type ?? '—').toUpperCase()}</div>
            </div>
            <div className="rounded-xl glass-card px-3 py-2">
              <div className="text-white/60">Gates</div>
              <div className="mt-0.5 font-medium text-white">
                {typeof meta?.gates_passed === 'boolean' ? (meta.gates_passed ? 'PASS' : 'FAIL') : '—'}
              </div>
              <div className="mt-0.5 text-white/60">{meta?.gate_reason ?? '—'}</div>
            </div>
            <div className="rounded-xl glass-card px-3 py-2">
              <div className="text-white/60">Confidence</div>
              <div className="mt-0.5 font-medium text-white">{pct01(meta?.confidence)}</div>
            </div>
            <div className="rounded-xl glass-card px-3 py-2">
              <div className="text-white/60">Session</div>
              <div className="mt-0.5 font-medium text-white">{meta?.session_id ?? '—'}</div>
            </div>
            <div className="rounded-xl glass-card px-3 py-2">
              <div className="text-white/60">Intent align</div>
              <div className="mt-0.5 font-medium text-white">{pct01(meta?.intent_alignment)}</div>
            </div>
            <div className="rounded-xl glass-card px-3 py-2">
              <div className="text-white/60">Memory align</div>
              <div className="mt-0.5 font-medium text-white">{pct01(meta?.memory_alignment)}</div>
            </div>
          </div>

          <PipelineSection statuses={meta?.pipeline_statuses ?? []} draft={meta?.draft_response ?? null} />
          <TaskingSection tasking={meta?.tasking as TaskingMeta} />
          <ThinkingSection thinking={meta?.thinking} traceId={meta?.thinking_trace_id} threadId={props.threadId} />
          <ReflectionSection
            traceId={meta?.reflection_trace_id}
            threadId={props.threadId}
            confidence={meta?.reflection_confidence}
            label={meta?.reflection_label}
          />

          <div className="mt-4">
            <div className="text-xs font-semibold tracking-wide text-white/60">Retrieved memories</div>
            <div className="mt-2 space-y-2">
              {(meta?.retrieved_memories ?? []).slice(0, 8).map((m, idx) => (
                <div key={idx} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                  {m.memory_id ? <div className="font-mono text-[11px] text-white/50">{m.memory_id}</div> : null}
                  <div className="line-clamp-3 whitespace-pre-wrap text-xs text-white/80">{m.text || '—'}</div>
                  <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-white/60">
                    <span>src: {m.source ?? '—'}</span>
                    <span>trust: {m.trust ?? '—'}</span>
                    <span>conf: {m.confidence ?? '—'}</span>
                    {typeof (m as any).score === 'number' ? <span>score: {(m as any).score.toFixed(3)}</span> : null}
                  </div>
                </div>
              ))}
              {!(meta?.retrieved_memories && meta.retrieved_memories.length) ? (
                <div className="text-sm text-white/60">No retrieved memories in this response.</div>
              ) : null}
            </div>
          </div>

          <div className="mt-4">
            <div className="text-xs font-semibold tracking-wide text-white/60">Prompt memories</div>
            <div className="mt-2 space-y-2">
              {(meta?.prompt_memories ?? []).slice(0, 8).map((m, idx) => (
                <div key={idx} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                  {m.memory_id ? <div className="font-mono text-[11px] text-white/50">{m.memory_id}</div> : null}
                  <div className="line-clamp-3 whitespace-pre-wrap text-xs text-white/80">{m.text || '—'}</div>
                  <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-white/60">
                    <span>src: {m.source ?? '—'}</span>
                    <span>trust: {m.trust ?? '—'}</span>
                    <span>conf: {m.confidence ?? '—'}</span>
                  </div>
                </div>
              ))}
              {!(meta?.prompt_memories && meta.prompt_memories.length) ? (
                <div className="text-sm text-white/60">No prompt memories in this response.</div>
              ) : null}
            </div>
          </div>

          {(meta as any)?.gaslighting_detected && (meta as any)?.gaslighting_citation ? (
            <div className="mt-4">
              <div className="text-xs font-semibold tracking-wide text-orange-400">⚠️ Gaslighting Detection</div>
              <div className="mt-2 rounded-xl border border-orange-500/30 bg-orange-500/10 px-3 py-2">
                <div className="whitespace-pre-wrap text-xs text-orange-200">{(meta as any).gaslighting_citation}</div>
              </div>
            </div>
          ) : null}

          {(meta as any)?.llm_claims && (meta as any).llm_claims.length > 0 ? (
            <div className="mt-4">
              <div className="text-xs font-semibold tracking-wide text-cyan-400">📝 LLM Claims Extracted</div>
              <div className="mt-2 space-y-2">
                {(meta as any).llm_claims.map((claim: any, idx: number) => (
                  <div key={idx} className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2">
                    <div className="text-[11px] font-medium text-cyan-200">{claim.slot}</div>
                    <div className="mt-1 text-xs text-white/90">Value: {claim.value}</div>
                    <div className="mt-1 text-[11px] text-white/60">Trust: {claim.trust.toFixed(2)} | Source: {claim.source}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {(meta as any)?.llm_disclosures && (meta as any).llm_disclosures.length > 0 ? (
            <div className="mt-4">
              <div className="text-xs font-semibold tracking-wide text-amber-400">⚠️ LLM Contradictions</div>
              <div className="mt-2 space-y-2">
                {(meta as any).llm_disclosures.map((disclosure: string, idx: number) => (
                  <div key={idx} className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                    <div className="whitespace-pre-wrap text-xs text-amber-200">{disclosure}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  )
}
