import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

// ─────────────────────────────────────────────────────────────
// Pipeline step definitions
// ─────────────────────────────────────────────────────────────

export const PIPELINE_STEPS = [
  { id: 'input', icon: '◎', name: 'Input', desc: 'Message received, attachments parsed' },
  { id: 'intent', icon: '◇', name: 'Intent Classification', desc: 'Classify user intent via regex/LLM/cache' },
  { id: 'routing', icon: '◈', name: 'Routing', desc: 'Select pipeline path: agent loop, legacy, conversational' },
  { id: 'context', icon: '◎', name: 'Context Binding', desc: 'Load session state, profile, conversation history' },
  { id: 'retrieval', icon: '◆', name: 'Memory Retrieval', desc: 'Semantic search + alias collapse + trust-weighted ranking' },
  { id: 'pre_governance', icon: '◉', name: 'Pre-Generation Gate', desc: 'Adaptive depth, confidence gate, hedge injection' },
  { id: 'generation', icon: '✦', name: 'Generation', desc: 'LLM response via local/cloud provider' },
  { id: 'slots', icon: '⬡', name: 'Slot Classification', desc: 'Extract fact slots from response' },
  { id: 'verification', icon: '⬡', name: 'Verification', desc: 'GroundCheck NLI critic checks response against memory' },
  { id: 'contradiction', icon: '⚡', name: 'Contradiction Check', desc: 'Cross-reference claims against stored facts' },
  { id: 'post_governance', icon: '≡', name: 'Final Governance', desc: 'Trust shifts, cascade propagation, belief recording' },
  { id: 'render', icon: '✦', name: 'Stream & Render', desc: 'Deliver response with citations and governance metadata' },
] as const

export type StepState = 'pending' | 'active' | 'complete' | 'skipped'

export type PipelineStepData = {
  id: string
  state: StepState
  timing_ms?: number
  detail?: string
}

export type PipelineStepperProps = {
  steps: PipelineStepData[]
  /** Compact mode reduces vertical spacing */
  compact?: boolean
}

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.round(ms)}ms`
}

function getStepDef(id: string) {
  return PIPELINE_STEPS.find((s) => s.id === id)
}

// ─────────────────────────────────────────────────────────────
// Step indicator (left side of timeline)
// ─────────────────────────────────────────────────────────────

function StepIndicator({ state, icon }: { state: StepState; icon: string }) {
  if (state === 'complete') {
    return (
      <motion.div
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="grid h-7 w-7 place-items-center rounded-full"
        style={{ background: 'rgba(52,211,153,0.15)', border: '1px solid rgba(52,211,153,0.3)' }}
      >
        <span style={{ color: '#34d399', fontSize: 12 }}>✓</span>
      </motion.div>
    )
  }

  if (state === 'active') {
    return (
      <motion.div
        animate={{ boxShadow: ['0 0 0px rgba(224,160,128,0.3)', '0 0 12px rgba(224,160,128,0.5)', '0 0 0px rgba(224,160,128,0.3)'] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        className="grid h-7 w-7 place-items-center rounded-full"
        style={{ background: 'rgba(224,160,128,0.15)', border: '1px solid rgba(224,160,128,0.4)' }}
      >
        <span style={{ color: '#E0A080', fontSize: 12 }}>{icon}</span>
      </motion.div>
    )
  }

  if (state === 'skipped') {
    return (
      <div
        className="grid h-7 w-7 place-items-center rounded-full"
        style={{ background: 'rgba(240,235,225,0.04)', border: '1px solid rgba(240,235,225,0.08)' }}
      >
        <span style={{ color: 'rgba(240,235,225,0.2)', fontSize: 12 }}>—</span>
      </div>
    )
  }

  // pending
  return (
    <div
      className="grid h-7 w-7 place-items-center rounded-full"
      style={{ background: 'rgba(240,235,225,0.04)', border: '1px solid rgba(240,235,225,0.08)' }}
    >
      <span style={{ color: 'rgba(240,235,225,0.25)', fontSize: 12 }}>{icon}</span>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Single step row
// ─────────────────────────────────────────────────────────────

function StepRow({ data, isLast, compact }: { data: PipelineStepData; isLast: boolean; compact?: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const def = getStepDef(data.id)
  if (!def) return null

  const isPending = data.state === 'pending'
  const isActive = data.state === 'active'
  const isComplete = data.state === 'complete'
  const isSkipped = data.state === 'skipped'

  const nameColor = isActive ? '#E0A080' : isComplete ? 'rgba(240,235,225,0.85)' : isSkipped ? 'rgba(240,235,225,0.25)' : 'rgba(240,235,225,0.4)'
  const descColor = isActive ? 'rgba(224,160,128,0.6)' : isComplete ? 'rgba(240,235,225,0.4)' : 'rgba(240,235,225,0.15)'

  const hasExpandable = Boolean(data.detail || data.timing_ms != null)
  const py = compact ? 'py-1.5' : 'py-2.5'

  return (
    <div className="relative flex gap-3">
      {/* Timeline line */}
      {!isLast && (
        <div
          className="absolute left-[13px] top-[28px] w-px"
          style={{
            bottom: 0,
            background: isComplete
              ? 'rgba(52,211,153,0.15)'
              : isActive
                ? 'linear-gradient(to bottom, rgba(224,160,128,0.3), rgba(240,235,225,0.05))'
                : 'rgba(240,235,225,0.05)',
          }}
        />
      )}

      {/* Indicator */}
      <div className="relative z-10 flex-none pt-0.5">
        <StepIndicator state={data.state} icon={def.icon} />
      </div>

      {/* Content */}
      <div className={`flex-1 min-w-0 ${py}`}>
        <button
          className="w-full text-left group"
          onClick={() => hasExpandable && setExpanded(!expanded)}
          disabled={!hasExpandable}
          style={{ cursor: hasExpandable ? 'pointer' : 'default' }}
        >
          <div className="flex items-center gap-2">
            <span
              className="text-[13px] font-medium transition-colors duration-200"
              style={{ color: nameColor }}
            >
              {def.name}
            </span>

            {data.timing_ms != null && isComplete && (
              <span
                className="text-[11px] font-mono"
                style={{ color: 'rgba(201,164,92,0.5)' }}
              >
                {formatMs(data.timing_ms)}
              </span>
            )}

            {isActive && (
              <motion.span
                animate={{ opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 1.5, repeat: Infinity }}
                className="text-[10px]"
                style={{ color: '#E0A080' }}
              >
                running
              </motion.span>
            )}

            {isSkipped && (
              <span className="text-[10px]" style={{ color: 'rgba(240,235,225,0.2)' }}>
                skipped
              </span>
            )}

            {hasExpandable && (
              <motion.span
                animate={{ rotate: expanded ? 90 : 0 }}
                transition={{ duration: 0.15 }}
                className="text-[10px] opacity-0 group-hover:opacity-60 transition-opacity"
                style={{ color: 'rgba(240,235,225,0.4)' }}
              >
                ▸
              </motion.span>
            )}
          </div>

          {!compact && (
            <div
              className="text-[11px] mt-0.5 transition-colors duration-200"
              style={{ color: descColor }}
            >
              {def.desc}
            </div>
          )}
        </button>

        {/* Expandable detail */}
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div
                className="mt-2 rounded-lg p-3 text-[12px] font-mono leading-relaxed"
                style={{
                  background: 'rgba(20,18,16,0.5)',
                  border: '1px solid rgba(240,235,225,0.05)',
                  color: 'rgba(240,235,225,0.5)',
                }}
              >
                {data.timing_ms != null && (
                  <div className="mb-1">
                    <span style={{ color: 'rgba(201,164,92,0.6)' }}>duration:</span>{' '}
                    {formatMs(data.timing_ms)}
                  </div>
                )}
                {data.detail && <div style={{ whiteSpace: 'pre-wrap' }}>{data.detail}</div>}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────

export function PipelineStepper({ steps, compact }: PipelineStepperProps) {
  // Merge provided steps with defaults
  const merged = PIPELINE_STEPS.map((def) => {
    const provided = steps.find((s) => s.id === def.id)
    return provided ?? { id: def.id, state: 'pending' as StepState }
  })

  const completedCount = merged.filter((s) => s.state === 'complete').length
  const totalSteps = merged.length
  const progressPct = totalSteps > 0 ? (completedCount / totalSteps) * 100 : 0

  return (
    <div
      className="rounded-xl p-4"
      style={{
        background: 'rgba(20,18,16,0.6)',
        border: '1px solid rgba(240,235,225,0.05)',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span style={{ color: '#E0A080', fontSize: 14 }}>≡</span>
          <span
            className="text-[13px] font-semibold tracking-wide"
            style={{ color: 'rgba(240,235,225,0.7)' }}
          >
            CRT Pipeline
          </span>
        </div>
        <span
          className="text-[11px] font-mono"
          style={{ color: 'rgba(201,164,92,0.5)' }}
        >
          {completedCount}/{totalSteps}
        </span>
      </div>

      {/* Progress bar */}
      <div
        className="h-[2px] w-full rounded-full mb-4 overflow-hidden"
        style={{ background: 'rgba(240,235,225,0.05)' }}
      >
        <motion.div
          className="h-full rounded-full"
          style={{ background: 'linear-gradient(90deg, #E0A080, #34d399)' }}
          initial={{ width: 0 }}
          animate={{ width: `${progressPct}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>

      {/* Steps */}
      <div className="flex flex-col">
        {merged.map((step, i) => (
          <StepRow
            key={step.id}
            data={step}
            isLast={i === merged.length - 1}
            compact={compact}
          />
        ))}
      </div>
    </div>
  )
}
