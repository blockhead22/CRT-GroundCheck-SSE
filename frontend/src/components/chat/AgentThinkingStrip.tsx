/**
 * AgentThinkingStrip — live step-by-step agent execution display.
 *
 * Shows above the assistant bubble while a task route is running:
 *   ◆ intent chip  [route chip]  [slot chips]
 *   ① Understand   ✓  8ms
 *   ② Plan         ✓  fetch_url → execute_instructions
 *   ③ fetch_url    ▷  moltbook.com/skill.md…   (spinner while running)
 *      └─ 3,241 bytes  89ms  ✓                  (result on complete)
 *   ④ Validate     ✓  no conflicts
 *   ⑤ Drafting…
 *
 * Each step row is clickable — opens an inline details panel.
 */

import { AnimatePresence, motion } from 'framer-motion'
import { useState } from 'react'
import type { AgentStep } from '../../lib/api'

// ── Types ─────────────────────────────────────────────────────────────────

export type AgentPlanStep = { tool: string; input: Record<string, unknown> }

export type AgentThinkingState = {
  // Set once intent_classified fires
  intent?: string
  route?: string
  slots?: Record<string, unknown>
  confidence?: number
  // Set once plan_ready fires
  plan?: AgentPlanStep[]
  // Accumulate as tool events arrive
  toolSteps: (AgentStep & { reasoning?: string })[]
  // Tracks which step_index is actively running
  activeStepIndex?: number
  // Reasoning tokens waiting to be attached to the next tool_start
  pendingReasoning?: string
  // Set once validate_result fires
  validated?: boolean
  // Set once drafting starts
  drafting?: boolean
  // Accumulates reasoning tokens during answer generation
  draftingThinking?: string
  // Set once task_done fires
  done?: boolean
}

// ── Helper: domain from URL ───────────────────────────────────────────────

function domainOf(url: string): string {
  try {
    return new URL(url).hostname
  } catch {
    return url.slice(0, 30)
  }
}

function shortUrl(url: string): string {
  try {
    const u = new URL(url)
    const path = u.pathname + (u.search ? u.search.split('&')[0] : '')
    return u.hostname + (path.length > 1 ? path.slice(0, 40) : '')
  } catch {
    return url.slice(0, 50)
  }
}

// ── Route chip colour ─────────────────────────────────────────────────────

function routeColor(route?: string) {
  if (route === 'task') return { bg: 'rgba(232,132,58,0.15)', color: '#e8843a', border: 'rgba(232,132,58,0.3)' }
  return { bg: 'rgba(240,235,225,0.08)', color: '#a09880', border: 'rgba(240,235,225,0.12)' }
}

// ── Step status icon ──────────────────────────────────────────────────────

function StepIcon({ status, active }: { status?: AgentStep['status'] | 'pending' | 'done'; active?: boolean }) {
  if (active) return (
    <span className="inline-flex gap-[2px] items-center">
      {[0, 0.15, 0.3].map((d, i) => (
        <span key={i} className="h-[3px] w-[3px] rounded-full animate-bounce inline-block"
          style={{ background: '#e8843a', opacity: 0.8, animationDelay: `${d}s`, animationDuration: '0.7s' }} />
      ))}
    </span>
  )
  if (status === 'ok') return <span style={{ color: '#6abf7b' }}>✓</span>
  if (status === 'error') return <span style={{ color: '#fb7185' }}>✗</span>
  if (status === 'queued') return <span style={{ color: '#d4a84b' }}>→</span>
  return <span style={{ color: '#3d3626' }}>·</span>
}

// ── ToolCallDetail — inline expanded view ─────────────────────────────────

function ToolCallDetail({ step }: { step: AgentStep }) {
  const url = step.input?.url as string | undefined
  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.18 }}
      className="overflow-hidden ml-6 mt-1"
    >
      <div
        className="rounded-lg px-3 py-2 text-[10px] font-mono space-y-1"
        style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(240,235,225,0.06)' }}
      >
        {/* Input */}
        <div style={{ color: '#5a5445' }}>INPUT</div>
        <pre className="text-[10px] whitespace-pre-wrap break-all" style={{ color: '#a09880' }}>
          {JSON.stringify(step.input, null, 2)}
        </pre>

        {/* Stats row */}
        {(step.byte_count || step.duration_ms) ? (
          <div className="flex gap-3 pt-1" style={{ color: '#5a5445' }}>
            {step.byte_count ? <span>{step.byte_count.toLocaleString()} bytes</span> : null}
            {step.duration_ms ? <span>{step.duration_ms.toFixed(0)}ms</span> : null}
          </div>
        ) : null}

        {/* Output preview */}
        {step.output_preview ? (
          <>
            <div className="pt-1" style={{ color: '#5a5445' }}>CONTENT PREVIEW</div>
            <div
              className="line-clamp-6 whitespace-pre-wrap break-words"
              style={{ color: '#a09880' }}
            >
              {url ? `[${domainOf(url)}]\n` : ''}{step.output_preview}
            </div>
          </>
        ) : null}

        {/* Error */}
        {step.error ? (
          <div style={{ color: '#fb7185' }}>ERROR: {step.error}</div>
        ) : null}
      </div>
    </motion.div>
  )
}

// ── AgentThinkingStrip ─────────────────────────────────────────────────────

export function AgentThinkingStrip({ state }: { state: AgentThinkingState }) {
  const [expandedStep, setExpandedStep] = useState<number | null>(null)
  const [thinkingExpanded, setThinkingExpanded] = useState(false)

  const rc = routeColor(state.route)
  const isActive = !state.done

  // Nothing to show yet
  if (!state.intent && state.toolSteps.length === 0) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="mb-4 rounded-xl overflow-hidden"
      style={{ border: '1px solid rgba(240,235,225,0.07)', background: 'rgba(0,0,0,0.18)' }}
    >
      {/* Header ── intent + route chips */}
      <div className="px-3 py-2 flex items-center gap-2 flex-wrap"
        style={{ borderBottom: '1px solid rgba(240,235,225,0.05)' }}>
        <span className="text-[10px] font-mono" style={{ color: '#5a5445' }}>AGENT</span>

        {state.intent && (
          <span className="rounded-full px-2 py-0.5 text-[10px] font-mono"
            style={{ background: rc.bg, color: rc.color, border: `1px solid ${rc.border}` }}>
            {state.intent}
          </span>
        )}

        {state.route && (
          <span className="rounded-full px-2 py-0.5 text-[10px] font-mono"
            style={{ background: 'rgba(240,235,225,0.05)', color: '#7a7060', border: '1px solid rgba(240,235,225,0.08)' }}>
            {state.route}
          </span>
        )}

        {/* Slot chips */}
        {state.slots && Object.entries(state.slots).slice(0, 3).map(([k, v]) => (
          <span key={k} className="rounded-full px-2 py-0.5 text-[10px] font-mono"
            style={{ background: 'rgba(240,235,225,0.04)', color: '#5a5445', border: '1px solid rgba(240,235,225,0.06)' }}
            title={String(v)}>
            {k}: {String(v).length > 28 ? String(v).slice(0, 26) + '…' : String(v)}
          </span>
        ))}

        {/* Live indicator */}
        {isActive && (
          <span className="ml-auto h-[6px] w-[6px] rounded-full animate-ping flex-shrink-0"
            style={{ background: '#e8843a', opacity: 0.5 }} />
        )}
      </div>

      {/* Steps ── plan + tool calls */}
      <div className="px-3 py-2 flex flex-col gap-[2px]">

        {/* Plan steps (before tools arrive) */}
        {state.plan && state.toolSteps.length === 0 && (
          <div className="flex flex-col gap-[2px] mb-1">
            {state.plan.map((s, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px] font-mono" style={{ color: '#3d3626' }}>
                <span className="w-3 text-center">≡</span>
                <span>{s.tool}</span>
                {s.input.url ? (
                  <span style={{ color: '#5a5445' }}>← {domainOf(String(s.input.url))}</span>
                ) : null}
              </div>
            ))}
          </div>
        )}

        {/* Tool execution steps — with reasoning before each */}
        {state.toolSteps.map((step) => {
          const isRunning = step.status === 'running' || step.step_index === state.activeStepIndex
          const isExpanded = expandedStep === step.step_index
          return (
            <div key={step.step_index}>
              {/* Reasoning text — shown before the tool call it explains */}
              {step.reasoning && (
                <div className="ml-5 mb-1 mt-1 text-[11px] leading-relaxed" style={{ color: '#a09880' }}>
                  {step.reasoning.trim()}
                </div>
              )}
              <button
                className="w-full flex items-center gap-2 text-[11px] font-mono text-left rounded px-1 py-[2px] transition-colors hover:bg-white/4"
                onClick={() => setExpandedStep(isExpanded ? null : step.step_index)}
              >
                <span className="w-3 text-center flex-shrink-0">
                  <StepIcon status={step.status} active={isRunning} />
                </span>
                <span style={{ color: isRunning ? '#F0EBE1' : step.status === 'ok' ? '#a09880' : step.status === 'error' ? '#fb7185' : '#3d3626' }}>
                  {step.tool_name}
                </span>
                {step.input.url ? (
                  <span className="truncate max-w-[240px]" style={{ color: '#5a5445' }}>
                    {shortUrl(String(step.input.url))}
                  </span>
                ) : null}
                {step.status === 'ok' && step.byte_count ? (
                  <span className="ml-auto text-[10px] flex-shrink-0" style={{ color: '#5a5445' }}>
                    {step.byte_count.toLocaleString()}b  {step.duration_ms?.toFixed(0)}ms
                  </span>
                ) : null}
                {step.status === 'error' && (
                  <span className="ml-auto text-[10px] flex-shrink-0" style={{ color: '#fb7185' }}>
                    failed
                  </span>
                )}
                {/* Expand indicator */}
                {(step.output_preview || step.error) && (
                  <span className="ml-1 text-[9px] flex-shrink-0" style={{ color: '#3d3626' }}>
                    {isExpanded ? '▲' : '▼'}
                  </span>
                )}
              </button>

              <AnimatePresence>
                {isExpanded && <ToolCallDetail step={step} />}
              </AnimatePresence>
            </div>
          )
        })}

        {/* Pending reasoning — LLM is thinking before next tool call */}
        {state.pendingReasoning && (
          <div className="ml-5 mt-1 text-[11px] leading-relaxed" style={{ color: '#a09880' }}>
            {state.pendingReasoning.trim()}
          </div>
        )}

        {/* Validate row */}
        {state.validated && (
          <div className="flex items-center gap-2 text-[11px] font-mono px-1 py-[2px]" style={{ color: '#3d3626' }}>
            <span className="w-3 text-center" style={{ color: '#6abf7b' }}>⬡</span>
            <span>validate</span>
            <span style={{ color: '#5a5445' }}>no conflicts</span>
          </div>
        )}

        {/* Drafting row — with live thinking expansion */}
        {state.drafting && !state.done && (
          <div className="flex flex-col gap-[2px]">
            <div className="flex items-center gap-2 text-[11px] font-mono px-1 py-[2px]">
              <span className="w-3 text-center">
                <StepIcon active={true} />
              </span>
              <span style={{ color: '#F0EBE1' }}>drafting</span>
              {state.draftingThinking && (
                <span className="ml-auto text-[9px] flex-shrink-0" style={{ color: '#5a5445' }}>
                  thinking…
                </span>
              )}
            </div>
            {/* Live thinking stream */}
            <AnimatePresence>
              {state.draftingThinking && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  className="overflow-hidden ml-5"
                >
                  <div
                    className="rounded px-2 py-1 text-[10px] font-mono line-clamp-6 whitespace-pre-wrap break-words"
                    style={{ background: 'rgba(0,0,0,0.2)', color: '#5a5445', borderLeft: '2px solid rgba(232,132,58,0.25)' }}
                  >
                    {state.draftingThinking}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {state.done && (
          <div className="flex flex-col gap-[2px]">
            <button
              className="w-full flex items-center gap-2 text-[11px] font-mono px-1 py-[2px] text-left rounded hover:bg-white/4 transition-colors"
              style={{ color: '#5a5445' }}
              onClick={() => state.draftingThinking && setThinkingExpanded(e => !e)}
            >
              <span className="w-3 text-center" style={{ color: '#6abf7b' }}>✓</span>
              <span>done</span>
              {state.draftingThinking && (
                <>
                  <span className="text-[9px]" style={{ color: '#3d3626' }}>
                    reasoned {Math.round(state.draftingThinking.length / 4)}t
                  </span>
                  <span className="ml-auto text-[9px]" style={{ color: '#3d3626' }}>
                    {thinkingExpanded ? '▲' : '▼'}
                  </span>
                </>
              )}
            </button>
            <AnimatePresence>
              {thinkingExpanded && state.draftingThinking && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.18 }}
                  className="overflow-hidden ml-5"
                >
                  <div
                    className="rounded px-2 py-2 text-[10px] font-mono whitespace-pre-wrap break-words max-h-64 overflow-y-auto"
                    style={{ background: 'rgba(0,0,0,0.25)', color: '#5a5445', borderLeft: '2px solid rgba(232,132,58,0.2)' }}
                  >
                    {state.draftingThinking}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </motion.div>
  )
}
