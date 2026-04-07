import { useState, useEffect } from 'react'
import { PipelineStepper, PIPELINE_STEPS, type PipelineStepData, type StepState } from '../components/PipelineStepper'

// ─────────────────────────────────────────────────────────────
// Example data sets
// ─────────────────────────────────────────────────────────────

const EXAMPLE_COMPLETE: PipelineStepData[] = [
  { id: 'input', state: 'complete', timing_ms: 2, detail: 'Text message, 47 chars, no attachments' },
  { id: 'intent', state: 'complete', timing_ms: 34, detail: 'Matched: factual_question (regex)\nConfidence: 0.92' },
  { id: 'routing', state: 'complete', timing_ms: 1, detail: 'Path: conversational (no agent tools needed)' },
  { id: 'context', state: 'complete', timing_ms: 12, detail: 'Session density: 0.73\nProfile trust: 0.85\nHistory: 6 turns' },
  { id: 'retrieval', state: 'complete', timing_ms: 89, detail: '4 memories retrieved\nAlias collapse: "nick" -> "Nick Block"\nTop trust: 0.91' },
  { id: 'pre_governance', state: 'complete', timing_ms: 5, detail: 'Depth: standard\nConfidence gate: passed (0.85 > 0.6)\nNo hedge needed' },
  { id: 'generation', state: 'complete', timing_ms: 1240, detail: 'Provider: cloud/claude-3.5-sonnet\nTokens: 342 in / 187 out\nCost: $0.0023' },
  { id: 'slots', state: 'complete', timing_ms: 18, detail: 'Extracted 2 fact slots:\n  user.project = "CRT"\n  user.language = "Python"' },
  { id: 'verification', state: 'complete', timing_ms: 156, detail: 'GroundCheck NLI: PASS\nEntailment: 0.87\nContradiction: 0.02' },
  { id: 'contradiction', state: 'complete', timing_ms: 23, detail: 'No contradictions detected\n0 claims flagged' },
  { id: 'post_governance', state: 'complete', timing_ms: 8, detail: 'Trust shift: +0.02 (verified response)\nNo cascade triggered' },
  { id: 'render', state: 'complete', timing_ms: 3, detail: 'Streamed 187 tokens\n0 citations attached' },
]

const EXAMPLE_MID_RUN: PipelineStepData[] = [
  { id: 'input', state: 'complete', timing_ms: 3 },
  { id: 'intent', state: 'complete', timing_ms: 28, detail: 'Matched: correction (LLM)\nConfidence: 0.88' },
  { id: 'routing', state: 'complete', timing_ms: 1, detail: 'Path: agent_loop (correction detected)' },
  { id: 'context', state: 'complete', timing_ms: 15 },
  { id: 'retrieval', state: 'complete', timing_ms: 112, detail: '7 memories retrieved, 2 contradictory' },
  { id: 'pre_governance', state: 'complete', timing_ms: 4 },
  { id: 'generation', state: 'active', detail: 'Provider: cloud/claude-3.5-sonnet\nStreaming...' },
  { id: 'slots', state: 'pending' },
  { id: 'verification', state: 'pending' },
  { id: 'contradiction', state: 'pending' },
  { id: 'post_governance', state: 'pending' },
  { id: 'render', state: 'pending' },
]

const EXAMPLE_SKIPPED: PipelineStepData[] = [
  { id: 'input', state: 'complete', timing_ms: 1 },
  { id: 'intent', state: 'complete', timing_ms: 8, detail: 'Matched: greeting (regex)\nConfidence: 0.99' },
  { id: 'routing', state: 'complete', timing_ms: 1, detail: 'Path: fast_reply (simple greeting)' },
  { id: 'context', state: 'complete', timing_ms: 3 },
  { id: 'retrieval', state: 'skipped', detail: 'Skipped: greeting does not need memory retrieval' },
  { id: 'pre_governance', state: 'skipped', detail: 'Skipped: fast path' },
  { id: 'generation', state: 'complete', timing_ms: 320, detail: 'Provider: local/llama3.2\nTokens: 12 in / 24 out' },
  { id: 'slots', state: 'skipped' },
  { id: 'verification', state: 'skipped' },
  { id: 'contradiction', state: 'skipped' },
  { id: 'post_governance', state: 'complete', timing_ms: 2, detail: 'No trust changes' },
  { id: 'render', state: 'complete', timing_ms: 1 },
]

const EXAMPLES = [
  { label: 'Complete Run', data: EXAMPLE_COMPLETE },
  { label: 'Mid-Generation', data: EXAMPLE_MID_RUN },
  { label: 'Fast Path (Skipped Steps)', data: EXAMPLE_SKIPPED },
] as const

// ─────────────────────────────────────────────────────────────
// Animated demo — steps complete one by one
// ─────────────────────────────────────────────────────────────

function useAnimatedRun(source: PipelineStepData[], active: boolean) {
  const [steps, setSteps] = useState<PipelineStepData[]>(() =>
    PIPELINE_STEPS.map((s) => ({ id: s.id, state: 'pending' as StepState }))
  )

  useEffect(() => {
    if (!active) {
      setSteps(source)
      return
    }

    // Reset to all pending
    setSteps(PIPELINE_STEPS.map((s) => ({ id: s.id, state: 'pending' as StepState })))

    const timers: ReturnType<typeof setTimeout>[] = []
    let cumulative = 0

    source.forEach((step, i) => {
      if (step.state === 'pending') return

      // Set active
      const activeDelay = cumulative
      timers.push(
        setTimeout(() => {
          setSteps((prev) =>
            prev.map((s) => (s.id === step.id ? { ...step, state: step.state === 'skipped' ? 'skipped' : 'active' } : s))
          )
        }, activeDelay)
      )

      // Set final state
      const duration = step.timing_ms ?? 200
      cumulative += Math.min(duration, 400) + 150

      if (step.state !== 'skipped') {
        timers.push(
          setTimeout(() => {
            setSteps((prev) =>
              prev.map((s) => (s.id === step.id ? { ...step } : s))
            )
          }, cumulative)
        )
      }
    })

    return () => timers.forEach(clearTimeout)
  }, [active, source])

  return steps
}

// ─────────────────────────────────────────────────────────────
// Page component
// ─────────────────────────────────────────────────────────────

export function PipelineStepperPage() {
  const [selectedExample, setSelectedExample] = useState(0)
  const [animating, setAnimating] = useState(false)
  const [compact, setCompact] = useState(false)

  const animatedSteps = useAnimatedRun(EXAMPLES[selectedExample].data as PipelineStepData[], animating)
  const displaySteps = animating ? animatedSteps : (EXAMPLES[selectedExample].data as PipelineStepData[])

  return (
    <div className="flex h-full flex-col overflow-y-auto px-6 py-8" style={{ background: 'transparent' }}>
      {/* Page header */}
      <div className="mb-8">
        <h1
          className="text-xl font-semibold tracking-wide font-display"
          style={{ color: 'rgba(240,235,225,0.85)' }}
        >
          Pipeline Stepper
        </h1>
        <p className="text-[13px] mt-1" style={{ color: 'rgba(240,235,225,0.4)' }}>
          Visual trace of the 12-phase CRT pipeline. Click any step to see details.
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        {EXAMPLES.map((ex, i) => (
          <button
            key={i}
            onClick={() => { setSelectedExample(i); setAnimating(false) }}
            className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition-all duration-200"
            style={{
              background: selectedExample === i ? 'rgba(224,160,128,0.15)' : 'rgba(240,235,225,0.04)',
              border: `1px solid ${selectedExample === i ? 'rgba(224,160,128,0.3)' : 'rgba(240,235,225,0.06)'}`,
              color: selectedExample === i ? '#E0A080' : 'rgba(240,235,225,0.45)',
            }}
          >
            {ex.label}
          </button>
        ))}

        <div className="h-4 w-px mx-1" style={{ background: 'rgba(240,235,225,0.08)' }} />

        <button
          onClick={() => setAnimating(!animating)}
          className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition-all duration-200"
          style={{
            background: animating ? 'rgba(52,211,153,0.12)' : 'rgba(240,235,225,0.04)',
            border: `1px solid ${animating ? 'rgba(52,211,153,0.25)' : 'rgba(240,235,225,0.06)'}`,
            color: animating ? '#34d399' : 'rgba(240,235,225,0.45)',
          }}
        >
          {animating ? 'Stop Animation' : 'Animate'}
        </button>

        <button
          onClick={() => setCompact(!compact)}
          className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition-all duration-200"
          style={{
            background: compact ? 'rgba(201,164,92,0.12)' : 'rgba(240,235,225,0.04)',
            border: `1px solid ${compact ? 'rgba(201,164,92,0.25)' : 'rgba(240,235,225,0.06)'}`,
            color: compact ? '#c9a45c' : 'rgba(240,235,225,0.45)',
          }}
        >
          {compact ? 'Full' : 'Compact'}
        </button>
      </div>

      {/* Stepper */}
      <div className="max-w-lg">
        <PipelineStepper steps={displaySteps} compact={compact} />
      </div>

      {/* Legend */}
      <div
        className="mt-8 rounded-lg p-4 max-w-lg"
        style={{
          background: 'rgba(20,18,16,0.4)',
          border: '1px solid rgba(240,235,225,0.04)',
        }}
      >
        <div
          className="text-[11px] font-semibold uppercase tracking-wider mb-3"
          style={{ color: 'rgba(240,235,225,0.3)' }}
        >
          Legend
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-[12px]">
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full" style={{ background: 'rgba(240,235,225,0.15)', border: '1px solid rgba(240,235,225,0.08)' }} />
            <span style={{ color: 'rgba(240,235,225,0.4)' }}>Pending</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full" style={{ background: 'rgba(224,160,128,0.3)', border: '1px solid rgba(224,160,128,0.4)' }} />
            <span style={{ color: 'rgba(240,235,225,0.4)' }}>Active</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full" style={{ background: 'rgba(52,211,153,0.3)', border: '1px solid rgba(52,211,153,0.3)' }} />
            <span style={{ color: 'rgba(240,235,225,0.4)' }}>Complete</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full" style={{ background: 'rgba(240,235,225,0.04)', border: '1px solid rgba(240,235,225,0.08)' }} />
            <span style={{ color: 'rgba(240,235,225,0.4)' }}>Skipped</span>
          </div>
        </div>
      </div>
    </div>
  )
}
