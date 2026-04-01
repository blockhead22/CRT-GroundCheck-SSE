import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ThinkingStub } from './ThinkingStub'
import { ToolResultCard, type ToolResult } from './ToolResultCard'
import { TrustBar, type TrustShift } from './TrustBar'

export type PipelineStep =
  | { kind: 'thinking'; content: string }
  | { kind: 'tool'; result: ToolResult }
  | { kind: 'trust_shift'; shift: TrustShift }
  | { kind: 'status'; content: string }

/**
 * PipelineCollapse — shows pipeline steps live during streaming,
 * auto-collapses to a summary line when done, expands on tap.
 *
 * Lifecycle:
 *   streaming=true  → all steps visible, live
 *   streaming=false → auto-collapse to summary, tap to expand
 */
export function PipelineCollapse({
  steps,
  streaming,
}: {
  steps: PipelineStep[]
  streaming: boolean
}) {
  const [expanded, setExpanded] = useState(true)

  // Auto-collapse when streaming ends
  useEffect(() => {
    if (!streaming && steps.length > 0) {
      const timer = setTimeout(() => setExpanded(false), 600)
      return () => clearTimeout(timer)
    }
  }, [streaming])

  // Auto-expand when streaming starts
  useEffect(() => {
    if (streaming) setExpanded(true)
  }, [streaming])

  if (steps.length === 0) return null

  // Compute summary stats
  const thinkingCount = steps.filter(s => s.kind === 'thinking').length
  const toolCount = steps.filter(s => s.kind === 'tool').length
  const trustShiftCount = steps.filter(s => s.kind === 'trust_shift').length
  const toolNames = steps
    .filter((s): s is Extract<PipelineStep, { kind: 'tool' }> => s.kind === 'tool')
    .map(s => s.result.tool)
  const uniqueTools = [...new Set(toolNames)]

  const summaryParts: string[] = []
  if (toolCount > 0) summaryParts.push(`${toolCount} tool call${toolCount !== 1 ? 's' : ''}`)
  if (uniqueTools.length > 0 && uniqueTools.length <= 3) summaryParts.push(uniqueTools.join(', '))
  if (trustShiftCount > 0) summaryParts.push(`${trustShiftCount} trust shift${trustShiftCount !== 1 ? 's' : ''}`)
  if (thinkingCount > 0) summaryParts.push(`${thinkingCount} reasoning step${thinkingCount !== 1 ? 's' : ''}`)

  return (
    <div className="my-2">
      {/* Summary / toggle bar */}
      {!streaming && (
        <button
          onClick={() => setExpanded(v => !v)}
          className="flex items-center gap-2 text-[11px] font-mono w-full text-left py-1 transition-colors hover:opacity-80"
          style={{ color: 'rgba(240,235,225,0.35)' }}
        >
          <span style={{ color: '#E0A080' }}>
            {expanded ? '\u25BE' : '\u25B8'}
          </span>
          <span>{summaryParts.join(' \u00B7 ')}</span>
          {!expanded && (
            <span
              className="flex-1 border-b ml-2"
              style={{ borderColor: 'rgba(240,235,225,0.06)' }}
            />
          )}
        </button>
      )}

      {/* Expanded content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={streaming ? false : { opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div
              className={streaming ? '' : 'ml-2 pl-3'}
              style={streaming ? {} : { borderLeft: '1px solid rgba(224,160,128,0.1)' }}
            >
              {steps.map((step, i) => {
                switch (step.kind) {
                  case 'thinking':
                    return <ThinkingStub key={`t-${i}`} content={step.content} />
                  case 'tool':
                    return <ToolResultCard key={`tool-${i}`} result={step.result} />
                  case 'trust_shift':
                    return (
                      <div key={`ts-${i}`} className="my-1">
                        <TrustBar
                          trust={step.shift.to}
                          prevTrust={step.shift.from}
                          text={step.shift.text}
                          reason={step.shift.reason}
                          compact
                        />
                      </div>
                    )
                  case 'status':
                    return (
                      <div key={`s-${i}`} className="my-0.5 text-[11px] font-mono" style={{ color: 'rgba(240,235,225,0.25)' }}>
                        <span style={{ color: '#E0A080' }}>{'\u25CB'}</span> {step.content}
                      </div>
                    )
                }
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
