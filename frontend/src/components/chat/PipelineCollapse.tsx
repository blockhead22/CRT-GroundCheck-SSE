import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronRight, ChevronDown, AlertTriangle, Zap } from 'lucide-react'
import { TrustBar, type TrustShift } from './TrustBar'
import { ToolRow } from './ToolRow'
import type { ToolResult } from './ToolResultCard'

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

export type PipelineStep =
  | { kind: 'thinking'; content: string; alignment?: number }
  | { kind: 'tool'; result: ToolResult }
  | { kind: 'trust_shift'; shift: TrustShift }
  | { kind: 'retrieval'; memories: Array<{ id: string; text: string; trust: number }> }
  | { kind: 'status'; content: string }
  | { kind: 'epistemic'; eventType: 'drift' | 'contradiction'; content: string; alignment?: number; avgAlignment?: number; stepA?: number; stepB?: number }

type RetrievalMemory = { id: string; text: string; trust: number }

type AgentLoopItem =
  | { kind: 'thinking'; content: string; alignment?: number; index: number }
  | { kind: 'tool'; result: ToolResult; index: number }
  | { kind: 'epistemic'; eventType: 'drift' | 'contradiction'; content: string; alignment?: number; avgAlignment?: number; stepA?: number; stepB?: number; index: number }

// ─────────────────────────────────────────────────────────────
// Helpers — group flat steps into sections
// ─────────────────────────────────────────────────────────────

function groupSteps(steps: PipelineStep[]) {
  const memories: RetrievalMemory[] = []
  const agentLoop: AgentLoopItem[] = []
  const trustShifts: TrustShift[] = []
  let verification: { verdict: string; confidence?: number } | null = null

  let agentIdx = 0
  for (const step of steps) {
    switch (step.kind) {
      case 'retrieval':
        memories.push(...step.memories)
        break
      case 'status': {
        const v = step.content
        if (v.includes('verified') || v.includes('passed') || v.includes('checking') || v.includes('contradiction')) {
          verification = {
            verdict: v.includes('✓') || v.includes('verified') || v.includes('passed') ? 'pass'
              : v.includes('✗') || v.includes('contradiction') ? 'fail'
              : 'checking',
            confidence: undefined,
          }
        }
        break
      }
      case 'thinking':
        agentLoop.push({ kind: 'thinking', content: step.content, alignment: step.alignment, index: agentIdx++ })
        break
      case 'tool':
        agentLoop.push({ kind: 'tool', result: step.result, index: agentIdx++ })
        break
      case 'epistemic':
        agentLoop.push({ kind: 'epistemic', eventType: step.eventType, content: step.content, alignment: step.alignment, avgAlignment: step.avgAlignment, stepA: step.stepA, stepB: step.stepB, index: agentIdx++ })
        break
      case 'trust_shift':
        trustShifts.push(step.shift)
        break
    }
  }

  return { memories, agentLoop, trustShifts, verification }
}

// ─────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────

export function PipelineCollapse({
  steps,
  streaming,
}: {
  steps: PipelineStep[]
  streaming: boolean
}) {
  const [expanded, setExpanded] = useState(true)
  const startRef = useRef<number>(0)
  const [elapsedMs, setElapsedMs] = useState<number | null>(null)

  // Track latency — start clock on first step, stop when streaming ends
  const hasSteps = steps.length > 0
  useEffect(() => {
    if (streaming && hasSteps && startRef.current === 0) {
      startRef.current = Date.now()
      setElapsedMs(null)
    }
  }, [streaming, hasSteps])

  useEffect(() => {
    if (!streaming && hasSteps && startRef.current > 0) {
      setElapsedMs(Date.now() - startRef.current)
      startRef.current = 0
    }
  }, [streaming, hasSteps])

  // Reset clock when new stream starts
  useEffect(() => {
    if (streaming) {
      startRef.current = 0
      setElapsedMs(null)
    }
  }, [streaming])

  // Auto-collapse 700ms after done
  useEffect(() => {
    if (!streaming && steps.length > 0) {
      const t = setTimeout(() => setExpanded(false), 700)
      return () => clearTimeout(t)
    }
  }, [streaming, steps.length])

  // Re-expand when new stream starts
  useEffect(() => {
    if (streaming) setExpanded(true)
  }, [streaming])

  if (steps.length === 0) return null

  const { memories, agentLoop, trustShifts, verification } = groupSteps(steps)

  // Merge trust shifts into memory bars by id
  const shiftById: Record<string, TrustShift> = {}
  for (const ts of trustShifts) {
    if (ts.memoryId) shiftById[ts.memoryId] = ts
  }

  const hasRetrieval = memories.length > 0
  const hasAgentLoop = agentLoop.length > 0
  const toolCount = agentLoop.filter(i => i.kind === 'tool').length
  const latencyStr = elapsedMs != null
    ? elapsedMs >= 1000 ? `${(elapsedMs / 1000).toFixed(1)}s` : `${elapsedMs}ms`
    : null

  // Summary line parts
  const summaryParts: string[] = []
  if (memories.length > 0) summaryParts.push(`${memories.length} mem`)
  if (verification?.verdict === 'pass') summaryParts.push('✓')
  if (verification?.verdict === 'fail') summaryParts.push('✗')
  if (toolCount > 0) summaryParts.push(`${toolCount} tool${toolCount !== 1 ? 's' : ''}`)
  if (latencyStr) summaryParts.push(latencyStr)

  return (
    <div className="my-2 select-none">

      {/* ── Collapsed summary line ── */}
      {!streaming && (
        <button
          onClick={() => setExpanded(v => !v)}
          className="flex items-center gap-1.5 text-[11px] font-mono w-full text-left py-0.5 transition-opacity hover:opacity-80"
          style={{ color: 'rgba(240,235,225,0.3)' }}
        >
          {expanded
            ? <ChevronDown size={11} style={{ color: '#E0A080', flexShrink: 0 }} />
            : <ChevronRight size={11} style={{ color: '#E0A080', flexShrink: 0 }} />
          }
          <span>{summaryParts.join(' · ')}</span>
          {!expanded && (
            <span className="flex-1 border-b ml-1" style={{ borderColor: 'rgba(240,235,225,0.05)' }} />
          )}
        </button>
      )}

      {/* ── Expanded content ── */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={streaming ? false : { opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="space-y-2 pt-0.5">

              {/* ── SECTION 1: Retrieval ── */}
              {hasRetrieval && (
                <RetrievalSection
                  memories={memories}
                  shiftById={shiftById}
                  hasTrustShifts={trustShifts.length > 0}
                />
              )}

              {/* ── SECTION 2: Verification badge ── */}
              {verification && (
                <VerificationRow verdict={verification.verdict} />
              )}

              {/* ── SECTION 3: Agent loop ── */}
              {hasAgentLoop && (
                <AgentLoopSection items={agentLoop} streaming={streaming} />
              )}

              {/* ── SECTION 4: Generating pulse (live only) ── */}
              {streaming && (
                <div className="flex items-center gap-2 text-[11px] font-mono pl-1" style={{ color: 'rgba(240,235,225,0.3)' }}>
                  <span
                    className="w-1.5 h-1.5 rounded-full animate-pulse flex-shrink-0"
                    style={{ background: '#E0A080' }}
                  />
                  <span>generating…</span>
                </div>
              )}

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Section: Retrieval
// ─────────────────────────────────────────────────────────────

function RetrievalSection({
  memories,
  shiftById,
  hasTrustShifts,
}: {
  memories: RetrievalMemory[]
  shiftById: Record<string, TrustShift>
  hasTrustShifts: boolean
}) {
  return (
    <div>
      {/* Section header */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.15 }}
        className="flex items-center gap-2 text-[11px] font-mono mb-1"
        style={{ color: '#E0A080' }}
      >
        <span className="opacity-60">◆</span>
        <span className="tracking-widest uppercase text-[10px]">
          Retrieving {memories.length} {memories.length === 1 ? 'memory' : 'memories'}
        </span>
      </motion.div>

      {/* Staggered bars */}
      <div className="ml-3 space-y-0.5">
        {memories.map((mem, i) => {
          const shift = shiftById[mem.id]
          const displayTrust = shift ? shift.to : mem.trust
          const prevTrust = shift ? mem.trust : undefined
          const reason = shift?.reason

          return (
            <motion.div
              key={mem.id || i}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
            >
              <TrustBar
                trust={displayTrust}
                prevTrust={hasTrustShifts ? prevTrust : undefined}
                text={mem.text}
                reason={reason}
                compact
              />
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Section: Verification
// ─────────────────────────────────────────────────────────────

function VerificationRow({ verdict }: { verdict: string }) {
  const isPass = verdict === 'pass'
  const isFail = verdict === 'fail'
  const color = isPass ? '#34d399' : isFail ? '#D47058' : 'rgba(240,235,225,0.3)'
  const label = isPass ? '✓ verified' : isFail ? '✗ contradiction' : '◇ checking…'

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.15 }}
      className="flex items-center gap-2 text-[11px] font-mono pl-1"
      style={{ color }}
    >
      {label}
    </motion.div>
  )
}

// ─────────────────────────────────────────────────────────────
// Section: Agent Loop
// ─────────────────────────────────────────────────────────────

function AgentLoopSection({
  items,
  streaming,
}: {
  items: AgentLoopItem[]
  streaming: boolean
}) {
  return (
    <div>
      {/* Section header */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.15 }}
        className="flex items-center gap-2 text-[11px] font-mono mb-1.5"
        style={{ color: '#E0A080' }}
      >
        <span className="opacity-60">◆</span>
        <span className="tracking-widest uppercase text-[10px]">Agent Loop</span>
      </motion.div>

      <div className="ml-3 space-y-0">
        {items.map((item, i) =>
          item.kind === 'thinking' ? (
            <motion.div
              key={`think-${i}`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.15 }}
              className="flex items-start gap-2 py-1 text-[11px] font-mono"
            >
              <span className="flex-shrink-0 mt-px" style={{ color: 'rgba(224,160,128,0.4)' }}>┊</span>
              <span
                className="italic leading-snug"
                style={{
                  // Color shifts from muted toward warning as alignment drops
                  color: item.alignment != null && item.alignment < 0.35
                    ? 'rgba(212,112,88,0.6)'
                    : 'rgba(240,235,225,0.35)',
                }}
              >
                {item.content.length > 80
                  ? item.content.slice(0, 80).trimEnd() + '…'
                  : item.content}
                {streaming && i === items.length - 1 && (
                  <span
                    className="inline-block w-[2px] h-[0.85em] align-middle ml-0.5 animate-[blink_1s_step-end_infinite]"
                    style={{ background: 'rgba(224,160,128,0.35)' }}
                  />
                )}
              </span>
              {item.alignment != null && (
                <span
                  className="flex-shrink-0 text-[10px] ml-auto tabular-nums"
                  style={{
                    color: item.alignment < 0.35 ? 'rgba(212,112,88,0.7)'
                      : item.alignment < 0.6 ? 'rgba(212,180,80,0.5)'
                      : 'rgba(240,235,225,0.2)',
                  }}
                >
                  {item.alignment.toFixed(2)}
                </span>
              )}
            </motion.div>
          ) : item.kind === 'tool' ? (
            <motion.div
              key={`tool-${i}`}
              initial={{ opacity: 0, y: 3 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.15 }}
            >
              <ToolRow result={item.result} />
            </motion.div>
          ) : (
            <motion.div
              key={`ep-${i}`}
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
            >
              <EpistemicRow item={item} />
            </motion.div>
          )
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Epistemic event row — drift warning or contradiction
// ─────────────────────────────────────────────────────────────

type EpistemicItem = Extract<AgentLoopItem, { kind: 'epistemic' }>

function EpistemicRow({ item }: { item: EpistemicItem }) {
  const isDrift = item.eventType === 'drift'

  return (
    <div
      className="flex items-start gap-2 py-1.5 px-2 rounded text-[11px] font-mono my-0.5"
      style={{
        background: isDrift
          ? 'rgba(212,112,88,0.07)'
          : 'rgba(212,180,80,0.07)',
        border: `1px solid ${isDrift ? 'rgba(212,112,88,0.2)' : 'rgba(212,180,80,0.2)'}`,
      }}
    >
      {/* Icon */}
      {isDrift
        ? <AlertTriangle size={11} style={{ color: '#D47058', flexShrink: 0, marginTop: 1 }} />
        : <Zap size={11} style={{ color: '#d4b44b', flexShrink: 0, marginTop: 1 }} />
      }

      {/* Label */}
      <span style={{ color: isDrift ? '#D47058' : '#d4b44b', flexShrink: 0 }}>
        {isDrift ? 'drift' : 'contradiction'}
      </span>

      {/* Content */}
      <span className="truncate" style={{ color: 'rgba(240,235,225,0.4)' }}>
        {item.content.length > 70 ? item.content.slice(0, 70) + '…' : item.content}
      </span>

      {/* Alignment scores for drift */}
      {isDrift && item.alignment != null && (
        <span className="flex-shrink-0 ml-auto tabular-nums" style={{ color: 'rgba(212,112,88,0.6)' }}>
          {item.alignment.toFixed(2)}
          {item.avgAlignment != null && ` ← ${item.avgAlignment.toFixed(2)}`}
        </span>
      )}

      {/* Step numbers for contradiction */}
      {!isDrift && item.stepA != null && item.stepB != null && (
        <span className="flex-shrink-0 ml-auto" style={{ color: 'rgba(212,180,80,0.5)' }}>
          step {item.stepA} ↔ {item.stepB}
        </span>
      )}
    </div>
  )
}

