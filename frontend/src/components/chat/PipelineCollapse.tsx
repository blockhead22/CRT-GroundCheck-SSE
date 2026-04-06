import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronRight, ChevronDown, AlertTriangle, Zap } from 'lucide-react'
import { TrustBar, type TrustShift } from './TrustBar'
import { ToolRow } from './ToolRow'
import type { ToolResult } from './ToolResultCard'
import { cleanMemoryText } from '../../lib/memoryUtils'
import { AetherMascot } from '../AetherMascot'
import type { MascotAnimation } from '../AetherMascot'

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

export type PipelineStep =
  | { kind: 'thinking'; content: string; alignment?: number }
  | { kind: 'tool'; result: ToolResult }
  | { kind: 'trust_shift'; shift: TrustShift }
  | { kind: 'retrieval'; memories: Array<RetrievalMemory>; edges?: RetrievalEdge[] }
  | { kind: 'status'; content: string }
  | { kind: 'epistemic'; eventType: 'drift' | 'contradiction'; content: string; alignment?: number; avgAlignment?: number; stepA?: number; stepB?: number }

type RetrievalMemory = {
  id: string; text: string; trust: number
  kind?: string; pca_x?: number; pca_y?: number; score?: number
}
type RetrievalEdge = { from: string; to: string; sim: number }

type AgentLoopItem =
  | { kind: 'thinking'; content: string; alignment?: number; index: number }
  | { kind: 'tool'; result: ToolResult; index: number }
  | { kind: 'epistemic'; eventType: 'drift' | 'contradiction'; content: string; alignment?: number; avgAlignment?: number; stepA?: number; stepB?: number; index: number }

// ─────────────────────────────────────────────────────────────
// Helpers — group flat steps into sections
// ─────────────────────────────────────────────────────────────

function groupSteps(steps: PipelineStep[]) {
  const memories: RetrievalMemory[] = []
  const retrievalEdges: RetrievalEdge[] = []
  const agentLoop: AgentLoopItem[] = []
  const trustShifts: TrustShift[] = []
  const sessionNotes: string[] = []
  let verification: { verdict: string; confidence?: number } | null = null

  let agentIdx = 0
  for (const step of steps) {
    switch (step.kind) {
      case 'retrieval':
        memories.push(...step.memories)
        if (step.edges) retrievalEdges.push(...step.edges)
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
        } else if (v.startsWith('density') || v.includes('open conflict')) {
          // Session state snapshot — show as a muted footer note
          sessionNotes.push(v)
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

  return { memories, retrievalEdges, agentLoop, trustShifts, verification, sessionNotes }
}

// ─────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────

export function PipelineCollapse({
  steps,
  streaming,
  beliefConfidence,
  costUsd,
}: {
  steps: PipelineStep[]
  streaming: boolean
  beliefConfidence?: number | null
  costUsd?: number | null
}) {
  const [expanded, setExpanded] = useState(true)
  const startRef = useRef<number>(0)
  const [elapsedMs, setElapsedMs] = useState<number | null>(null)
  const wasStreamingRef = useRef(false)

  // Track latency — start clock on first step, stop on stream end transition
  const hasSteps = steps.length > 0
  useEffect(() => {
    if (streaming && hasSteps && startRef.current === 0) {
      startRef.current = Date.now()
      setElapsedMs(null)
    }
  }, [streaming, hasSteps])

  // Detect stream end transition (was streaming → not streaming)
  // This avoids race conditions from multiple useEffects watching `streaming`
  useEffect(() => {
    const wasStreaming = wasStreamingRef.current
    wasStreamingRef.current = streaming

    if (wasStreaming && !streaming && hasSteps) {
      // Stream just ended — record latency
      if (startRef.current > 0) {
        setElapsedMs(Date.now() - startRef.current)
        startRef.current = 0
      }
      // Auto-collapse after 1.5s (was 700ms — too fast to read summary)
      const t = setTimeout(() => setExpanded(false), 1500)
      return () => clearTimeout(t)
    }

    if (!wasStreaming && streaming) {
      // Stream just started — expand and reset clock
      setExpanded(true)
      startRef.current = 0
      setElapsedMs(null)
    }
  }, [streaming, hasSteps])

  if (steps.length === 0) return null

  const { memories, retrievalEdges, agentLoop, trustShifts, verification, sessionNotes } = groupSteps(steps)

  // Merge trust shifts into memory bars by id
  const shiftById: Record<string, TrustShift> = {}
  for (const ts of trustShifts) {
    if (ts.memoryId) shiftById[ts.memoryId] = ts
  }

  const hasRetrieval = memories.length > 0
  const hasAgentLoop = agentLoop.length > 0
  const toolCount = agentLoop.filter(i => i.kind === 'tool').length
  const thoughtCount = agentLoop.filter(i => i.kind === 'thinking').length
  const shiftCount = trustShifts.length
  // Drift detection — color shifts from amber to red when alignment drops
  const driftItems = agentLoop.filter(i => i.kind === 'epistemic' && (i as any).eventType === 'drift') as Array<Extract<typeof agentLoop[0], { kind: 'epistemic' }>>
  const driftEvents = driftItems.length
  const hasDrift = driftEvents > 0
  // Get worst alignment score from drift events
  const worstAlignment = driftItems.reduce((min, d) => {
    const a = (d as any).alignment
    return typeof a === 'number' && a < min ? a : min
  }, 1.0)
  // Drift severity: 0 = no drift, 1 = severe
  const driftSeverity = hasDrift ? Math.max(0, Math.min(1, 1 - worstAlignment)) : 0

  // Bar color interpolation: amber (#E0A080) → red (#D47058) based on drift severity
  const barColor = hasDrift
    ? `rgb(${Math.round(212 + (212 - 212) * driftSeverity)}, ${Math.round(160 - (160 - 112) * driftSeverity)}, ${Math.round(128 - (128 - 88) * driftSeverity)})`
    : '#E0A080'
  const barGlow = hasDrift
    ? `0 0 8px rgba(212,112,88,${0.3 + driftSeverity * 0.4})`
    : '0 0 8px rgba(212,132,92,0.3)'

  const latencyStr = elapsedMs != null
    ? elapsedMs >= 1000 ? `${(elapsedMs / 1000).toFixed(1)}s` : `${elapsedMs}ms`
    : null

  // Summary line — "5 mem · ◉ 0.73 · ✓ · $0.01 · 2.1s"
  const summaryParts: string[] = []
  if (memories.length > 0) summaryParts.push(`${memories.length} mem`)
  if (thoughtCount > 0) summaryParts.push(`${thoughtCount} thought${thoughtCount !== 1 ? 's' : ''}`)
  if (toolCount > 0) summaryParts.push(`${toolCount} tool${toolCount !== 1 ? 's' : ''}`)
  if (beliefConfidence != null && beliefConfidence > 0) summaryParts.push(`◉ ${beliefConfidence.toFixed(2)}`)
  if (verification?.verdict === 'pass') summaryParts.push('✓ verified')
  if (verification?.verdict === 'fail') summaryParts.push('✗ conflict')
  if (shiftCount > 0) summaryParts.push(`${shiftCount} shift${shiftCount !== 1 ? 's' : ''}`)
  if (driftEvents > 0) summaryParts.push(`⚠ ${driftEvents} drift`)
  if (costUsd != null && costUsd > 0) summaryParts.push(`$${costUsd < 0.01 ? costUsd.toFixed(4) : costUsd.toFixed(2)}`)
  if (latencyStr) summaryParts.push(latencyStr)

  return (
    <div className="my-2 select-none">

      {/* ── Drift-aware progress bar with mascot (streaming only) ── */}
      {streaming && (() => {
        const progressPct = `${Math.min(90, (steps.length / Math.max(steps.length + 2, 8)) * 100)}%`
        // Determine mascot state from latest pipeline activity
        const lastStep = steps[steps.length - 1]
        let mascotAnim: MascotAnimation = 'loading'
        let mascotMood: 'calm' | 'warm' | 'curious' | 'intense' | 'uncertain' = 'curious'
        if (hasDrift) {
          mascotAnim = 'alert'; mascotMood = 'intense'
        } else if (lastStep?.kind === 'thinking') {
          mascotAnim = 'thinking'; mascotMood = 'curious'
        } else if (lastStep?.kind === 'tool') {
          mascotAnim = 'working'; mascotMood = 'warm'
        } else if (lastStep?.kind === 'retrieval') {
          mascotAnim = 'curious'; mascotMood = 'curious'
        } else if (lastStep?.kind === 'status') {
          const s = (lastStep as any).content?.toLowerCase?.() || ''
          if (s.includes('generat') || s.includes('draft')) { mascotAnim = 'working'; mascotMood = 'warm' }
          else if (s.includes('verif')) { mascotAnim = 'nod'; mascotMood = 'warm' }
          else if (s.includes('contradict')) { mascotAnim = 'alert'; mascotMood = 'intense' }
          else { mascotAnim = 'curious'; mascotMood = 'curious' }
        }
        return (
          <div className="relative mb-1.5">
            {/* Mascot walking along the bar */}
            <motion.div
              className="absolute z-10"
              style={{ bottom: 2, marginLeft: -12 }}
              initial={{ left: '0%', opacity: 0 }}
              animate={{ left: progressPct, opacity: 1 }}
              exit={{ left: '0%', bottom: -180, opacity: 0 }}
              transition={{ left: { duration: 0.6, ease: 'easeOut' }, opacity: { duration: 0.3 } }}
            >
              <AetherMascot mood={mascotMood} animation={mascotAnim} size={24} />
            </motion.div>

            {/* Progress bar */}
            <div className="h-[2px] rounded-full overflow-hidden" style={{ background: 'rgba(240,235,225,0.04)' }}>
              <motion.div
                className="h-full rounded-full"
                style={{ background: barColor, boxShadow: barGlow }}
                initial={{ width: '0%' }}
                animate={{ width: progressPct }}
                transition={{ duration: 0.4, ease: 'easeOut' }}
              />
            </div>
            {/* Drift pulse overlay */}
            {hasDrift && (
              <motion.div
                className="h-[2px] rounded-full mt-[-2px]"
                style={{ background: 'rgba(212,112,88,0.6)' }}
                initial={{ opacity: 0 }}
                animate={{ opacity: [0, 0.8, 0] }}
                transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
              />
            )}
          </div>
        )
      })()}

      {/* ── Collapsed summary line ── */}
      {!streaming && (
        <button
          onClick={() => setExpanded(v => !v)}
          className="flex items-center gap-1.5 text-[11px] font-mono w-full text-left py-0.5 transition-opacity hover:opacity-80"
          style={{ color: hasDrift ? 'rgba(212,112,88,0.6)' : 'rgba(240,235,225,0.3)' }}
        >
          {expanded
            ? <ChevronDown size={11} style={{ color: hasDrift ? '#D47058' : '#E0A080', flexShrink: 0 }} />
            : <ChevronRight size={11} style={{ color: hasDrift ? '#D47058' : '#E0A080', flexShrink: 0 }} />
          }
          <span>{summaryParts.join(' · ')}</span>
          {!expanded && (
            <span className="flex-1 border-b ml-1" style={{ borderColor: hasDrift ? 'rgba(212,112,88,0.1)' : 'rgba(240,235,225,0.05)' }} />
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
                  backendEdges={retrievalEdges}
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

              {/* ── SECTION 4: Generating pulse (live only) — shifts red on drift ── */}
              {streaming && (
                <div className="flex items-center gap-2 text-[11px] font-mono pl-1" style={{ color: hasDrift ? 'rgba(212,112,88,0.5)' : 'rgba(240,235,225,0.3)' }}>
                  <span
                    className="w-1.5 h-1.5 rounded-full animate-pulse flex-shrink-0"
                    style={{ background: hasDrift ? '#D47058' : '#E0A080' }}
                  />
                  <span>{hasDrift ? 'generating (drift detected)…' : 'generating…'}</span>
                </div>
              )}

              {/* ── SECTION 5: Session state footer (density / open conflicts) ── */}
              {!streaming && sessionNotes.length > 0 && (
                <div className="flex items-center gap-2 text-[10px] font-mono pl-1 pt-0.5" style={{ color: 'rgba(240,235,225,0.18)' }}>
                  <span className="opacity-50">◇</span>
                  <span>{sessionNotes[sessionNotes.length - 1]}</span>
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

// Kind → color palette for domain clustering
const KIND_COLORS: Record<string, string> = {
  user_fact: '#34d399',       // green
  preference: '#c9a45c',     // gold
  identity_constant: '#818cf8', // purple
  narrative_note: '#f472b6', // pink
  observation: 'rgba(240,235,225,0.5)', // muted
  ops: '#60a5fa',            // blue
  learned: '#fb923c',        // orange
}
const KIND_LABELS: Record<string, string> = {
  user_fact: 'fact',
  preference: 'pref',
  identity_constant: 'identity',
  narrative_note: 'note',
  observation: 'obs',
  ops: 'ops',
  learned: 'learned',
}

function RetrievalSection({
  memories,
  backendEdges,
  shiftById,
  hasTrustShifts,
}: {
  memories: RetrievalMemory[]
  backendEdges: RetrievalEdge[]
  shiftById: Record<string, TrustShift>
  hasTrustShifts: boolean
}) {
  const hasPCA = memories.some(m => m.pca_x !== undefined && m.pca_x !== 0)
  const W = 280, H = 190, CX = W / 2, CY = H / 2, PAD = 28

  // Compute node positions — use real PCA if available, fallback to hash circle
  const nodes = memories.map((mem, i) => {
    const trust = shiftById[mem.id] ? shiftById[mem.id].to : mem.trust
    const prevTrust = shiftById[mem.id] ? mem.trust : undefined
    const reason = shiftById[mem.id]?.reason
    const kind = mem.kind || 'observation'

    let cx: number, cy: number
    if (hasPCA && mem.pca_x !== undefined && mem.pca_y !== undefined) {
      // PCA coords are [-1, 1] → map to viewBox with padding
      cx = PAD + ((mem.pca_x + 1) / 2) * (W - 2 * PAD)
      cy = PAD + ((mem.pca_y + 1) / 2) * (H - 2 * PAD)
    } else {
      // Fallback: arrange in a circle with hash-based spread
      const textHash = mem.text.split('').reduce((a, c) => ((a << 5) - a + c.charCodeAt(0)) | 0, 0)
      const angle = (i / memories.length) * Math.PI * 2
      const radius = 65 + (Math.abs(textHash % 30))
      cx = CX + Math.cos(angle) * radius
      cy = CY + Math.sin(angle) * radius * 0.7
    }
    return { ...mem, trust, prevTrust, reason, kind, cx, cy, radius: Math.max(5, trust * 14 + 3), index: i }
  })

  // Build edges from backend cosine similarities (preferred) or fallback to word overlap
  const nodeById = new Map(nodes.map(n => [n.id, n]))
  type GraphEdge = { from: typeof nodes[0]; to: typeof nodes[0]; type: 'similar' | 'contradiction'; strength: number }
  const edges: GraphEdge[] = []

  if (backendEdges.length > 0) {
    for (const be of backendEdges) {
      const a = nodeById.get(be.from)
      const b = nodeById.get(be.to)
      if (!a || !b) continue
      const trustDiff = Math.abs(a.trust - b.trust)
      const isContradiction = be.sim > 0.6 && trustDiff > 0.35
      edges.push({
        from: a, to: b,
        type: isContradiction ? 'contradiction' : 'similar',
        strength: Math.min(1, Math.abs(be.sim)),
      })
    }
  } else {
    // Fallback: word overlap
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i].text.toLowerCase()
        const b = nodes[j].text.toLowerCase()
        const wordsA = new Set(a.split(/\s+/).filter(w => w.length > 3))
        const wordsB = new Set(b.split(/\s+/).filter(w => w.length > 3))
        const overlap = [...wordsA].filter(w => wordsB.has(w)).length
        const maxWords = Math.max(wordsA.size, wordsB.size, 1)
        const similarity = overlap / maxWords
        if (similarity > 0.15) {
          const hasNegation = (a.includes('not') && !b.includes('not')) || (!a.includes('not') && b.includes('not'))
          const trustDiff = Math.abs(nodes[i].trust - nodes[j].trust)
          edges.push({
            from: nodes[i], to: nodes[j],
            type: (hasNegation || trustDiff > 0.4) ? 'contradiction' : 'similar',
            strength: similarity,
          })
        }
      }
    }
  }

  // Collect unique kinds for centroid labels
  const kindCentroids = new Map<string, { x: number; y: number; count: number }>()
  for (const n of nodes) {
    const k = n.kind
    const c = kindCentroids.get(k) || { x: 0, y: 0, count: 0 }
    c.x += n.cx; c.y += n.cy; c.count++
    kindCentroids.set(k, c)
  }

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
          {memories.length} {memories.length === 1 ? 'memory' : 'memories'} retrieved
          {hasPCA && <span className="opacity-40 ml-1">(PCA)</span>}
        </span>
      </motion.div>

      {/* Epistemic graph */}
      <div style={{ position: 'relative', height: 200, borderRadius: 8, background: 'rgba(20,18,16,0.6)', border: '1px solid rgba(240,235,225,0.05)', overflow: 'hidden', marginBottom: 4 }}>
        <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} style={{ position: 'absolute', top: 0, left: 0 }}>
          {/* Query pulse — golden ring expanding from center */}
          <motion.circle
            cx={CX} cy={CY} r={8}
            fill="none" stroke="rgba(201,164,92,0.4)" strokeWidth={1.5}
            initial={{ r: 4, opacity: 0.8 }}
            animate={{ r: 80, opacity: 0 }}
            transition={{ duration: 1.5, ease: 'easeOut' }}
          />

          {/* Centroid labels — domain clusters */}
          {[...kindCentroids.entries()].filter(([, c]) => c.count >= 1).map(([kind, c]) => {
            const x = c.x / c.count, y = c.y / c.count
            const color = KIND_COLORS[kind] || 'rgba(240,235,225,0.3)'
            return (
              <motion.g key={`centroid-${kind}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.8, duration: 0.4 }}
              >
                {/* Centroid halo — soft circle showing cluster boundary */}
                <circle cx={x} cy={y} r={c.count > 1 ? 35 : 22}
                  fill="none" stroke={color} strokeWidth={0.5} opacity={0.15}
                  strokeDasharray="3 4" />
                {/* Label */}
                <text x={x} y={y - (c.count > 1 ? 38 : 25)}
                  textAnchor="middle" fill={color}
                  fontSize={7} fontFamily="var(--font-mono, monospace)" opacity={0.5}>
                  {KIND_LABELS[kind] || kind}
                </text>
              </motion.g>
            )
          })}

          {/* Edges — connections between memories */}
          {edges.map((edge, i) => {
            const color = edge.type === 'contradiction'
              ? 'rgba(212,112,88,0.5)'
              : `rgba(52,211,153,${0.1 + edge.strength * 0.4})`
            return (
              <motion.line
                key={`e-${i}`}
                x1={edge.from.cx} y1={edge.from.cy} x2={edge.to.cx} y2={edge.to.cy}
                stroke={color}
                strokeWidth={Math.max(0.5, edge.strength * 2.5)}
                strokeDasharray={edge.type === 'contradiction' ? '4 3' : 'none'}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ delay: 0.5 + i * 0.08, duration: 0.35 }}
              />
            )
          })}

          {/* Nodes — memory dots positioned by PCA */}
          {nodes.map((node, i) => {
            const kindColor = KIND_COLORS[node.kind] || 'rgba(240,235,225,0.5)'
            const trustBrightness = 0.4 + node.trust * 0.6
            const glowActive = node.trust >= 0.6
            return (
              <motion.g key={node.id || i}
                initial={{ opacity: 0, scale: 0 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.3 + i * 0.1, type: 'spring', damping: 15 }}
              >
                {/* Trust glow halo */}
                {glowActive && (
                  <motion.circle cx={node.cx} cy={node.cy} r={node.radius + 5}
                    fill="none" stroke={kindColor} strokeWidth={1.5} opacity={0.25}
                    initial={{ r: node.radius }}
                    animate={{ r: node.radius + 5 }}
                    transition={{ duration: 0.5, delay: 0.5 + i * 0.1 }}
                  />
                )}
                {/* Node circle */}
                <circle cx={node.cx} cy={node.cy} r={node.radius}
                  fill={kindColor} opacity={trustBrightness} />
                {/* Score connection line to center (query) */}
                {node.score && node.score > 0.3 && (
                  <line x1={CX} y1={CY} x2={node.cx} y2={node.cy}
                    stroke="rgba(201,164,92,0.08)" strokeWidth={0.5}
                    strokeDasharray="2 4" />
                )}
              </motion.g>
            )
          })}
        </svg>

        {/* Legend */}
        <div style={{ position: 'absolute', bottom: 3, right: 6, display: 'flex', gap: 8, fontSize: 7, fontFamily: 'var(--font-mono, monospace)' }}>
          {edges.some(e => e.type === 'similar') && (
            <span style={{ color: 'rgba(52,211,153,0.6)' }}>— similar</span>
          )}
          {edges.some(e => e.type === 'contradiction') && (
            <span style={{ color: 'rgba(212,112,88,0.6)' }}>-- contra</span>
          )}
          {hasPCA && <span style={{ color: 'rgba(201,164,92,0.4)' }}>◎ pca</span>}
        </div>
      </div>

      {/* Memory labels below graph — with kind badge */}
      <div className="ml-1 space-y-0.5">
        {nodes.map((node, i) => {
          const kindColor = KIND_COLORS[node.kind] || 'rgba(240,235,225,0.35)'
          const trustColor = node.trust >= 0.7 ? '#34d399' : node.trust >= 0.4 ? '#c9a45c' : 'rgba(240,235,225,0.35)'
          return (
            <motion.div
              key={node.id || i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.6 + i * 0.08, duration: 0.15 }}
              className="flex items-center gap-1.5 text-[10px]"
            >
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: kindColor, flexShrink: 0 }} />
              <span className="font-mono" style={{ color: trustColor, flexShrink: 0, width: 26 }}>{node.trust.toFixed(2)}</span>
              <span className="font-mono px-1 rounded" style={{
                color: kindColor, background: `${kindColor}15`,
                fontSize: 8, flexShrink: 0, lineHeight: '14px',
              }}>
                {KIND_LABELS[node.kind] || node.kind}
              </span>
              <span className="truncate" style={{ color: 'rgba(240,235,225,0.4)' }}>
                {cleanMemoryText(node.text).slice(0, 70)}
              </span>
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

