import { motion, AnimatePresence } from 'framer-motion'
import { useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage, MessageRating } from '../../types'
import { formatTime } from '../../lib/time'
import { CitationViewer } from '../CitationViewer'
import { FilePill } from '../ui/FilePill'
import { ClaudeLogo } from '../icons/ClaudeLogo'
import { OpenAILogo } from '../icons/OpenAILogo'
import { PipelineTrace } from './PipelineTrace'
import { PipelineCollapse, type PipelineStep } from './PipelineCollapse'
import { MessageRatingBar } from './MessageRatingBar'
import { ContradictionResolutionCard } from './ContradictionResolutionCard'
import { TrustDeltaStrip } from './TrustDeltaStrip'
import { cleanMemoryText } from '../../lib/memoryUtils'
import { ContradictionDrawer } from './ContradictionDrawer'
import { GateFailDrawer } from './GateFailDrawer'
import { resolveContradiction } from '../../lib/api'

// ─────────────────────────────────────────────────────────────
// Mini Belief Map — persistent PCA graph in message footer
// ─────────────────────────────────────────────────────────────

const MINI_KIND_COLORS: Record<string, string> = {
  user_fact: '#34d399', preference: '#c9a45c', identity_constant: '#818cf8',
  narrative_note: '#f472b6', observation: 'rgba(240,235,225,0.5)',
  ops: '#60a5fa', learned: '#fb923c', user_belief: '#a78bfa',
}

function MiniBeliefMap({ memories, edges }: {
  memories: any[]
  edges: Array<{ from: string; to: string; sim: number }>
}) {
  const W = 240, H = 120, PAD = 18

  const nodes = memories.map((mem: any, i: number) => {
    const trust = typeof mem.trust === 'number' ? mem.trust : 0.5
    const kind = String(mem.kind || 'observation')
    const pca_x = typeof mem.pca_x === 'number' ? mem.pca_x : 0
    const pca_y = typeof mem.pca_y === 'number' ? mem.pca_y : 0
    const cx = PAD + ((pca_x + 1) / 2) * (W - 2 * PAD)
    const cy = PAD + ((pca_y + 1) / 2) * (H - 2 * PAD)
    const id = mem.memory_id || mem.id || `m${i}`
    return { id, trust, kind, cx, cy, radius: Math.max(4, trust * 10 + 2), text: String(mem.text || '') }
  })

  const nodeById = new Map(nodes.map(n => [n.id, n]))

  // Build edge lines from backend cosine similarities
  const graphEdges: Array<{ from: typeof nodes[0]; to: typeof nodes[0]; sim: number; isContra: boolean }> = []
  for (const e of edges) {
    const a = nodeById.get(e.from), b = nodeById.get(e.to)
    if (!a || !b) continue
    const trustDiff = Math.abs(a.trust - b.trust)
    graphEdges.push({ from: a, to: b, sim: e.sim, isContra: e.sim > 0.6 && trustDiff > 0.3 })
  }

  return (
    <div
      className="mt-2 mb-1 rounded-lg overflow-hidden"
      style={{ background: 'rgba(20,18,16,0.5)', border: '1px solid rgba(240,235,225,0.05)' }}
    >
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`}>
        {/* Edges */}
        {graphEdges.map((e, i) => (
          <line key={`e${i}`}
            x1={e.from.cx} y1={e.from.cy} x2={e.to.cx} y2={e.to.cy}
            stroke={e.isContra ? 'rgba(212,112,88,0.4)' : `rgba(52,211,153,${0.1 + e.sim * 0.3})`}
            strokeWidth={Math.max(0.5, e.sim * 2)}
            strokeDasharray={e.isContra ? '3 3' : 'none'}
          />
        ))}
        {/* Nodes */}
        {nodes.map((n, i) => {
          const color = MINI_KIND_COLORS[n.kind] || 'rgba(240,235,225,0.4)'
          return (
            <g key={n.id}>
              {n.trust >= 0.6 && (
                <circle cx={n.cx} cy={n.cy} r={n.radius + 3}
                  fill="none" stroke={color} strokeWidth={1} opacity={0.2} />
              )}
              <circle cx={n.cx} cy={n.cy} r={n.radius}
                fill={color} opacity={0.4 + n.trust * 0.5} />
            </g>
          )
        })}
      </svg>
      {/* Legend */}
      <div className="flex items-center gap-3 px-2 pb-1.5" style={{ fontSize: 8, fontFamily: 'var(--font-mono, monospace)', color: 'rgba(240,235,225,0.25)' }}>
        <span>◎ belief map</span>
        {graphEdges.some(e => !e.isContra) && <span style={{ color: 'rgba(52,211,153,0.5)' }}>— similar</span>}
        {graphEdges.some(e => e.isContra) && <span style={{ color: 'rgba(212,112,88,0.5)' }}>-- contra</span>}
        <span className="ml-auto">{nodes.length} memories</span>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Contradiction Mini-Graph — animated node-pair resolution
// ─────────────────────────────────────────────────────────────

function ContradictionMiniGraph({ entry }: {
  entry: NonNullable<import('../../types').CtrMessageMeta['contradiction_entry']>
}) {
  const oldText = cleanMemoryText(entry.old_text || 'previous belief')
  const newText = cleanMemoryText(entry.new_text || 'new information')
  const oldTrust = entry.old_trust ?? 0.5
  const newTrust = entry.new_trust ?? 0.5
  const type = entry.contradiction_type || 'conflict'
  const resolved = !!entry.resolution_method

  // Winner is higher trust
  const oldWins = oldTrust >= newTrust
  const winColor = '#34d399'
  const loseColor = 'rgba(212,112,88,0.6)'
  const W = 260, H = 70

  return (
    <div
      style={{
        borderRadius: 8,
        background: 'rgba(212,112,88,0.06)',
        border: '1px solid rgba(212,112,88,0.15)',
        padding: '8px 10px',
        fontSize: 10,
        fontFamily: 'var(--font-mono, monospace)',
      }}
    >
      <div className="flex items-center gap-1.5 mb-1" style={{ color: 'rgba(212,112,88,0.7)' }}>
        <span>⚡</span>
        <span className="uppercase tracking-widest text-[9px]">
          {type === 'REVISION' ? 'revision' : type === 'TEMPORAL' ? 'temporal shift' : 'contradiction'} detected
          {resolved && <span style={{ color: winColor, marginLeft: 6 }}>✓ resolved</span>}
        </span>
      </div>
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`}>
        {/* Dashed red edge between nodes */}
        <motion.line
          x1={50} y1={28} x2={210} y2={28}
          stroke="rgba(212,112,88,0.4)" strokeWidth={1.5}
          strokeDasharray="5 4"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.6, delay: 0.2 }}
        />
        {/* Old memory node */}
        <motion.g
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1, type: 'spring', damping: 15 }}
        >
          <circle cx={50} cy={28} r={oldWins ? 14 : 10}
            fill={oldWins ? winColor : loseColor} opacity={oldWins ? 0.8 : 0.4} />
          <text x={50} y={55} textAnchor="middle" fill="rgba(240,235,225,0.5)" fontSize={8}>
            T:{oldTrust.toFixed(2)}
          </text>
        </motion.g>
        {/* New memory node */}
        <motion.g
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3, type: 'spring', damping: 15 }}
        >
          <circle cx={210} cy={28} r={!oldWins ? 14 : 10}
            fill={!oldWins ? winColor : loseColor} opacity={!oldWins ? 0.8 : 0.4} />
          <text x={210} y={55} textAnchor="middle" fill="rgba(240,235,225,0.5)" fontSize={8}>
            T:{newTrust.toFixed(2)}
          </text>
        </motion.g>
        {/* Labels */}
        <text x={50} y={65} textAnchor="middle" fill="rgba(240,235,225,0.3)" fontSize={7}>prior</text>
        <text x={210} y={65} textAnchor="middle" fill="rgba(240,235,225,0.3)" fontSize={7}>new</text>
        {/* Resolution arrow */}
        {resolved && (
          <motion.text
            x={130} y={22} textAnchor="middle" fill={winColor} fontSize={10}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
          >
            {oldWins ? '←' : '→'} resolved
          </motion.text>
        )}
      </svg>
      {/* Text previews */}
      <div className="flex gap-3 mt-0.5">
        <div className="flex-1 truncate" style={{ color: oldWins ? 'rgba(52,211,153,0.7)' : 'rgba(212,112,88,0.5)' }}>
          {oldText.slice(0, 50)}
        </div>
        <div className="flex-1 truncate text-right" style={{ color: !oldWins ? 'rgba(52,211,153,0.7)' : 'rgba(212,112,88,0.5)' }}>
          {newText.slice(0, 50)}
        </div>
      </div>
    </div>
  )
}

/** Detect if text looks like a file or directory path */
const FILE_PATH_RE = /^[A-Za-z]:[/\\][\w./\\ -]+(?:\.\w+)?$|^[\w./\\-]+\.(?:py|tsx?|jsx?|json|md|ya?ml|toml|rs|go|css|html|txt|cfg|ini|sh|bat)$/

function CodeBlock({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false)
  const lines = code.split('\n')

  function handleCopy() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="my-3 rounded overflow-hidden" style={{ border: '1px solid rgba(240,235,225,0.06)' }}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2"
        style={{ background: 'rgba(0,0,0,0.5)', borderBottom: '1px solid rgba(240,235,225,0.04)' }}
      >
        <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: '#5a5445' }}>
          {language || 'code'}
        </span>
        <button
          onClick={handleCopy}
          className="text-[10px] font-mono px-2 py-0.5 rounded transition-all hover:bg-white/[0.06]"
          style={{ color: copied ? '#6abf7b' : '#5a5445' }}
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      {/* Code with line numbers */}
      <div className="overflow-x-auto" style={{ background: 'rgba(0,0,0,0.35)' }}>
        <table className="w-full">
          <tbody>
            {lines.map((line, i) => (
              <tr key={i} className="hover:bg-white/[0.02]">
                <td
                  className="select-none text-right px-3 py-0 text-[12px] font-mono align-top"
                  style={{ color: '#332e22', width: '1%', whiteSpace: 'nowrap', userSelect: 'none' }}
                >
                  {i + 1}
                </td>
                <td className="px-3 py-0 text-[13px] font-mono whitespace-pre" style={{ color: '#F0EBE1' }}>
                  {line || ' '}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const mdComponents = {
  p({ children }: { children?: React.ReactNode }) {
    return <p className="mb-4 last:mb-0 text-[15px] leading-[1.85]" style={{ color: 'rgba(240,235,225,0.85)' }}>{children}</p>
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
      // Check if inline code looks like a file path → render as FilePill
      if (FILE_PATH_RE.test(codeText)) {
        return <FilePill path={codeText} size="sm" />
      }
      return (
        <code className="rounded px-1.5 py-0.5 font-mono text-[0.88em]" style={{ background: 'rgba(212,132,92,0.12)', color: '#E8C8A0' }}>
          {children}
        </code>
      )
    }
    return <CodeBlock code={codeText} language={language} />
  },
  blockquote({ children }: { children?: React.ReactNode }) {
    return (
      <blockquote className="my-3 pl-4 italic" style={{ borderLeft: '2px solid rgba(224,160,128,0.35)', color: 'rgba(240,235,225,0.55)' }}>
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
      <a href={href} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2" style={{ color: '#E0A080', textDecorationColor: 'rgba(224,160,128,0.4)' }}>
        {children}
      </a>
    )
  },
  hr() {
    return <hr className="my-4 border-white/10" />
  },
  table({ children }: { children?: React.ReactNode }) {
    return (
      <div className="my-3 overflow-x-auto rounded border border-white/10">
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
  onRated?: (msgId: string, rating: MessageRating, category?: string) => void
}) {
  const isUser = props.msg.role === 'user'
  const meta = props.msg.crt
  const isAssistant = !isUser

  const responseType = (meta?.response_type ?? '').toLowerCase()
  const isNotification = responseType === 'notification'
  const isBelief = responseType === 'belief'
  const isExplanation = responseType === 'explanation'
  const gatesPassed = meta?.gates_passed
  const gatesFailed = typeof gatesPassed === 'boolean' && !gatesPassed
  const contradictionDetected = meta?.contradiction_detected

  const [metaExpanded, setMetaExpanded] = useState(false)
  const [gateDebugOpen, setGateDebugOpen] = useState(false)
  const [gateAccepting, setGateAccepting] = useState(false)
  const [gateAccepted, setGateAccepted] = useState(false)
  const [contradictionDrawerOpen, setContradictionDrawerOpen] = useState(false)
  const [gateFailDrawerOpen, setGateFailDrawerOpen] = useState(false)
  const [contraResolved, setContraResolved] = useState(false)

  // ledger_id from gate_debug — declared early so handleAcceptGateClaim can close over it
  const ledgerId = meta?.gate_debug?.ledger_id ?? null

  const handleAcceptGateClaim = useCallback(async () => {
    if (!ledgerId || gateAccepting || gateAccepted) return
    setGateAccepting(true)
    try {
      await resolveContradiction({
        threadId: props.threadId ?? 'default',
        ledgerId,
        method: 'accept_new',
        newStatus: 'resolved',
      })
      setGateAccepted(true)
    } catch { /* non-critical */ }
    finally { setGateAccepting(false) }
  }, [ledgerId, props.threadId, gateAccepting, gateAccepted])
  const [localRating, setLocalRating] = useState<MessageRating | null>(props.msg.rating ?? null)
  const [localRatingCat, setLocalRatingCat] = useState<string | undefined>(props.msg.ratingCategory ?? undefined)
  const [ratedAt, setRatedAt] = useState<number | null>(null)

  function handleRated(rating: MessageRating, category?: string) {
    setLocalRating(rating)
    setLocalRatingCat(category)
    setRatedAt(Date.now() / 1000)
    props.onRated?.(props.msg.id, rating, category)
  }

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

  // User message — right-aligned, borderless text
  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
        className="flex justify-end group"
      >
        <div className="max-w-[80%] text-left">
          <div
            className="text-[14.5px] leading-relaxed"
            style={{ color: 'rgba(240,235,225,0.55)' }}
          >
            {props.msg.text}
          </div>
          <div className="mt-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            <span className="text-[10px] font-mono" style={{ color: 'rgba(240,235,225,0.2)' }}>{formatTime(props.msg.createdAt)}</span>
          </div>
        </div>
      </motion.div>
    )
  }

  // Assistant message — borderless, left-aligned text
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      className="group"
    >
      <div
        className={[
          'py-2 transition-all duration-200',
          isNotification ? 'border-l-[3px] pl-4' : '',
          gatesFailed && !localRating ? 'border-l-2 pl-4' : '',
          localRating === 'down' ? 'border-l-2 pl-4' : '',
          localRating === 'up' ? 'border-l-2 pl-4' : '',
        ].join(' ')}
        style={{
          ...(isNotification ? { borderLeftColor: 'rgba(212,132,92,0.6)' } : {}),
          ...(localRating === 'down' ? { borderLeftColor: 'rgba(251,113,133,0.4)' } : {}),
          ...(localRating === 'up' ? { borderLeftColor: 'rgba(52,211,153,0.25)' } : {}),
          ...(gatesFailed && !localRating ? { borderLeftColor: 'rgba(251,146,60,0.35)' } : {}),
        }}
      >
        {/* Notification header (Sprint 4) */}
        {isNotification && (
          <div className="flex items-center gap-2 mb-2 text-[11px] font-mono" style={{ color: 'rgba(212,132,92,0.7)' }}>
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
              <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
            </svg>
            <span className="uppercase tracking-wider">Aether Reminder</span>
            {meta?.priority === 'high' || meta?.priority === 'critical' ? (
              <span className="rounded px-1.5 py-0.5" style={{ background: 'rgba(212,132,92,0.15)', color: 'rgba(212,132,92,0.9)' }}>
                {meta.priority}
              </span>
            ) : null}
          </div>
        )}

        {/* Profile updates */}
        {profileUpdates.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {profileUpdates.map((u, i) => (
              <span key={`${u.slot}-${i}`} className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-[11px]" style={{ border: '1px solid rgba(224,160,128,0.2)', background: 'rgba(212,132,92,0.08)', color: 'rgba(240,235,225,0.7)' }}>
                <span className="font-mono" style={{ color: '#E0A080' }}>{u.slot}</span>
                <span style={{ color: 'rgba(240,235,225,0.3)' }}>·</span>
                <span>{(u.old || '—')} → {(u.new || '—')}</span>
              </span>
            ))}
          </div>
        )}

        {/* Main message text */}
        <div className="text-[15px] text-white/90 leading-[1.75]">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents as any}>
            {props.msg.text}
          </ReactMarkdown>
        </div>

        {/* Gate debug — collapsible, opened by clicking the gate fail badge */}
        <AnimatePresence>
          {gatesFailed && meta?.gate_debug && gateDebugOpen && (
            <motion.div
              key="gate-debug"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.18 }}
              className="mt-3 overflow-hidden rounded px-3 py-2.5 text-[11px]"
              style={{ border: '1px solid rgba(212,112,88,0.2)', background: 'rgba(212,112,88,0.06)' }}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="font-mono font-semibold" style={{ color: '#D47058' }}>WHY BLOCKED</span>
                {meta.gate_debug.trigger && (
                  <span className="rounded px-1.5 py-0.5 font-mono" style={{ background: 'rgba(212,112,88,0.12)', color: '#E0A080' }}>{meta.gate_debug.trigger}</span>
                )}
                {meta.gate_debug.slot && (
                  <span className="rounded px-1.5 py-0.5 font-mono" style={{ background: 'rgba(240,235,225,0.06)', color: '#a09880' }}>slot: {meta.gate_debug.slot}</span>
                )}
                <button
                  onClick={() => setGateDebugOpen(false)}
                  className="ml-auto text-[10px] transition-opacity hover:opacity-60"
                  style={{ color: '#5a5445' }}
                >
                  close
                </button>
              </div>
              {meta.gate_debug.explanation && (
                <div className="mb-1.5" style={{ color: 'rgba(240,235,225,0.7)' }}>{meta.gate_debug.explanation}</div>
              )}
              {(meta.gate_debug.stored || meta.gate_debug.incoming) && (
                <div className="mt-1.5 space-y-1 font-mono">
                  {meta.gate_debug.stored && (
                    <div className="flex items-start gap-2">
                      <span style={{ color: '#5a5445' }}>stored</span>
                      <span className="line-clamp-2" style={{ color: 'rgba(240,235,225,0.55)' }}>{meta.gate_debug.stored}</span>
                    </div>
                  )}
                  {meta.gate_debug.incoming && (
                    <div className="flex items-start gap-2">
                      <span style={{ color: '#5a5445' }}>said&nbsp;&nbsp;</span>
                      <span className="line-clamp-2" style={{ color: 'rgba(240,235,225,0.55)' }}>{meta.gate_debug.incoming}</span>
                    </div>
                  )}
                </div>
              )}
              {(meta.gate_debug.conflicting_memories ?? []).length > 0 && (
                <div className="mt-2 space-y-1">
                  <div className="font-mono" style={{ color: '#5a5445' }}>conflicting memories</div>
                  {(meta.gate_debug.conflicting_memories ?? []).map((m, i) => (
                    <div key={i} className="flex items-start gap-2 font-mono">
                      <span style={{ color: '#E0A080' }}>T:{m.trust.toFixed(2)}</span>
                      <span className="line-clamp-1" style={{ color: 'rgba(240,235,225,0.45)' }}>{m.text}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-2 flex items-center gap-3 font-mono" style={{ color: '#5a5445' }}>
                {meta.gate_debug.intent_align != null && <span>intent {meta.gate_debug.intent_align.toFixed(2)}</span>}
                {meta.gate_debug.memory_align != null && <span>memory {meta.gate_debug.memory_align.toFixed(2)}</span>}
                {meta.gate_debug.grounding != null && <span>grounding {meta.gate_debug.grounding.toFixed(2)}</span>}
                {meta.gate_debug.hard_conflicts != null && meta.gate_debug.hard_conflicts > 0 && (
                  <span style={{ color: '#D47058' }}>{meta.gate_debug.hard_conflicts} hard conflict(s)</span>
                )}
              </div>
              {/* Action row — accept claim if a ledger entry exists */}
              <div className="mt-2.5 flex items-center gap-2 pt-2" style={{ borderTop: '1px solid rgba(240,235,225,0.06)' }}>
                {ledgerId ? (
                  gateAccepted ? (
                    <span className="text-[10px] font-medium" style={{ color: '#34d399' }}>✓ Accepted — memory updated</span>
                  ) : (
                    <button
                      onClick={handleAcceptGateClaim}
                      disabled={gateAccepting}
                      className="rounded-full px-2.5 py-1 text-[10px] font-medium transition-all hover:opacity-90 disabled:opacity-40"
                      style={{ border: '1px solid rgba(52,211,153,0.35)', background: 'rgba(52,211,153,0.08)', color: '#34d399' }}
                    >
                      {gateAccepting ? 'Accepting…' : 'My claim is correct — accept it'}
                    </button>
                  )
                ) : (
                  <span className="text-[10px]" style={{ color: '#5a5445' }}>Confidence threshold block — use the thumbs-down to flag a correction</span>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Contradiction mini-graph — animated node-pair when contradiction detected */}
        <AnimatePresence>
          {contradictionDetected && meta?.contradiction_entry && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3 }}
              className="mb-2"
            >
              <ContradictionMiniGraph entry={meta.contradiction_entry} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Contradiction resolution card — shown inline when contradiction detected */}
        <AnimatePresence>
          {contradictionDetected && ledgerId && !contraResolved && (
            <ContradictionResolutionCard
              key={ledgerId}
              ledgerId={ledgerId}
              threadId={props.threadId ?? 'default'}
              contradictionType={(meta as any)?.contradiction_type ?? null}
              summary={(meta as any)?.contradiction_summary ?? null}
              onResolved={() => setContraResolved(true)}
            />
          )}
        </AnimatePresence>

        {/* Pipeline trace — persisted from streaming */}
        {(meta?.pipeline_steps as PipelineStep[] | undefined)?.length ? (
          <div className="mt-3">
            <PipelineCollapse
              steps={meta!.pipeline_steps as PipelineStep[]}
              streaming={false}
            />
          </div>
        ) : (meta?.pipeline_statuses ?? []).length > 0 && (() => {
          // Fallback: legacy flat status strings
          const statuses = [...(meta!.pipeline_statuses ?? [])]
          const memCount = (meta?.retrieved_memories?.length ?? 0) + (meta?.prompt_memories?.length ?? 0)
          if (memCount > 0 && !statuses.some(s => s.match(/\d+ mem/))) {
            statuses.push(`${memCount} memories read`)
          }
          const topMem = (meta?.retrieved_memories as any[])?.[0]
          if (topMem?.text) {
            const memPreview = String(topMem.text).slice(0, 80)
            const trust = typeof topMem.trust === 'number' ? `T:${topMem.trust.toFixed(2)}` : ''
            statuses.push(`${topMem.memory_id ?? ''} ·${trust ? trust + ' ' : ''}${memPreview}`)
          }
          if (gatesFailed && meta?.gate_reason) {
            statuses.push(`gate: ${meta.gate_reason}`)
          }
          return (
            <div className="mt-3">
              <PipelineTrace statuses={statuses} streaming={false} defaultOpen={false} />
            </div>
          )
        })()}

        {/* Cited memories — animated cards with trust visualization */}
        {isAssistant && (meta?.retrieved_memories as any[])?.length > 0 && (() => {
          const mems = (meta!.retrieved_memories as any[]).slice(0, 6)
          const [memOpen, setMemOpen] = useState(false)
          return (
            <div className="mt-2">
              <button
                onClick={() => setMemOpen(!memOpen)}
                className="flex items-center gap-2 text-[11px] font-mono cursor-pointer hover:opacity-80 transition-opacity"
                style={{ color: 'rgba(240,235,225,0.4)', background: 'none', border: 'none', padding: 0 }}
              >
                <span style={{ transform: memOpen ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s', display: 'inline-block' }}>&#9656;</span>
                <span>{mems.length} memories cited</span>
                {/* Mini trust dots preview */}
                <span className="flex gap-0.5 ml-1">
                  {mems.map((m: any, i: number) => {
                    const t = typeof m.trust === 'number' ? m.trust : 0.5
                    return (
                      <span key={i} style={{
                        width: 5, height: 5, borderRadius: '50%', display: 'inline-block',
                        background: t >= 0.7 ? '#34d399' : t >= 0.4 ? '#c9a45c' : 'rgba(240,235,225,0.3)',
                      }} />
                    )
                  })}
                </span>
              </button>
              <AnimatePresence>
                {memOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    style={{ overflow: 'hidden' }}
                  >
                    {/* Mini PCA graph — persistent belief map after generation */}
                    {mems.some((m: any) => m.pca_x != null && m.pca_x !== 0) && (
                      <MiniBeliefMap
                        memories={mems}
                        edges={(meta as any)?.retrieval_edges || []}
                      />
                    )}
                    <div className="mt-2 flex flex-col gap-1.5">
                      {mems.map((mem: any, i: number) => {
                        const trust = typeof mem.trust === 'number' ? mem.trust : 0.5
                        const trustColor = trust >= 0.7 ? '#34d399' : trust >= 0.4 ? '#c9a45c' : 'rgba(240,235,225,0.35)'
                        const trustBg = trust >= 0.7 ? 'rgba(52,211,153,0.06)' : trust >= 0.4 ? 'rgba(201,164,92,0.06)' : 'rgba(240,235,225,0.03)'
                        const kind = String(mem.kind || mem.memory_type || '').replace(/_/g, ' ')
                        const memId = mem.memory_id || mem.id || ''
                        return (
                          <motion.div
                            key={memId || i}
                            initial={{ opacity: 0, x: -12 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.06, duration: 0.15 }}
                            onClick={() => {
                              if (memId && props.onOpenSourceInspector) {
                                props.onOpenSourceInspector(memId)
                              }
                            }}
                            className="flex items-start gap-2 rounded-md px-2.5 py-1.5 text-[11px] transition-colors hover:brightness-125"
                            style={{
                              background: trustBg,
                              border: `1px solid ${trustColor}15`,
                              cursor: memId && props.onOpenSourceInspector ? 'pointer' : 'default',
                            }}
                            title={memId ? 'Click to inspect memory' : undefined}
                          >
                            {/* Trust dot */}
                            <span style={{
                              width: 7, height: 7, borderRadius: '50%', flexShrink: 0, marginTop: 4,
                              background: trustColor,
                              boxShadow: trust >= 0.7 ? `0 0 6px ${trustColor}40` : 'none',
                            }} />
                            {/* Content */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-mono" style={{ color: trustColor, fontSize: 10 }}>
                                  {trust.toFixed(2)}
                                </span>
                                {kind && (
                                  <span style={{
                                    fontSize: 9, color: 'rgba(240,235,225,0.3)',
                                    background: 'rgba(240,235,225,0.04)',
                                    padding: '0 4px', borderRadius: 3,
                                  }}>
                                    {kind}
                                  </span>
                                )}
                                {mem.alias_boost && (
                                  <span style={{
                                    fontSize: 8, color: '#818cf8',
                                    background: 'rgba(129,140,248,0.08)',
                                    padding: '0 4px', borderRadius: 3,
                                  }}>
                                    alias
                                  </span>
                                )}
                              </div>
                              <div className="truncate mt-0.5" style={{ color: 'rgba(240,235,225,0.5)', fontSize: 11 }}>
                                {cleanMemoryText(String(mem.text || '')).slice(0, 140)}
                              </div>
                            </div>
                          </motion.div>
                        )
                      })}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )
        })()}

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
          <div className="mt-3 rounded border border-white/8 bg-white/3 px-3 py-2 text-[11px] text-white/40">
            <span className="font-mono">{prov.id}</span>
            {prov.id && prov.text ? ' · ' : ''}
            <span className="line-clamp-1">{prov.text}</span>
          </div>
        ) : null}

        {/* X-ray mode */}
        {props.xrayMode && meta?.xray && (
          <div className="mt-3 rounded px-3 py-3 text-[11px]" style={{ border: '1px solid rgba(224,160,128,0.15)', background: 'rgba(212,132,92,0.06)' }}>
            <div className="mb-2 font-semibold tracking-wide" style={{ color: '#E0A080' }}>X-RAY</div>
            {(meta.xray.memories_used ?? []).length > 0 && (
              <div className="space-y-1">
                {(meta.xray.memories_used ?? []).map((m, i) => (
                  <div key={i} className="flex items-start gap-2" style={{ color: 'rgba(240,235,225,0.5)' }}>
                    <span className="font-mono flex-shrink-0" style={{ color: '#E0A080' }}>T:{m.trust.toFixed(2)}</span>
                    <span className="line-clamp-1">{m.text}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Rating bar — thumbs up/down with memory citation panel */}
        {isAssistant && meta?.interaction_id && (
          <MessageRatingBar
            msg={{ ...props.msg, rating: localRating ?? undefined, ratingCategory: localRatingCat }}
            threadId={props.threadId}
            onRated={handleRated}
          />
        )}

        {/* Trust delta strip — shows trust movements since this turn (or last rating) */}
        {isAssistant && props.threadId && (
          <TrustDeltaStrip
            threadId={props.threadId}
            sinceTs={ratedAt != null ? ratedAt - 5 : props.msg.createdAt / 1000 - 2}
          />
        )}

        {/* Footer row — compact metadata line */}
        <div className="mt-3 flex items-center gap-3">
          <span className="text-[10px] text-white/20 tabular-nums font-mono">{formatTime(props.msg.createdAt)}</span>

          {/* Generation source pill */}
          {isAssistant && (() => {
            const src = meta?.generation_source || 'local'
            const pill = (() => {
              switch (src) {
                case 'local':
                  return { label: 'Local', bg: 'rgba(52,211,153,0.12)', color: '#34d399', border: 'rgba(52,211,153,0.2)' }
                case 'cloud_openai':
                  return { label: 'GPT-4o', bg: '#1a1a1a', color: '#ffffff', border: 'rgba(255,255,255,0.15)', icon: 'openai' }
                case 'cloud_claude':
                  return { label: 'Claude', bg: '#1a1a1a', color: '#ffffff', border: 'rgba(255,255,255,0.15)', icon: 'claude' }
                case 'cookie_claude':
                case 'agent_loop':
                  return { label: 'Agent Loop', bg: 'rgba(251,146,60,0.12)', color: '#fb923c', border: 'rgba(251,146,60,0.25)', icon: 'claude' }
                case 'cloud_fallback':
                  return { label: 'Fallback: GPT', bg: '#1a1a1a', color: '#ffffff', border: 'rgba(255,255,255,0.15)', icon: 'openai' }
                case 'claude_fallback':
                case 'cloud_fallback_claude':
                  return { label: 'Fallback: Claude', bg: '#1a1a1a', color: '#ffffff', border: 'rgba(255,255,255,0.15)', icon: 'claude' }
                default:
                  if (src.startsWith('bypass_')) {
                    const provider = src.replace('bypass_', '')
                    if (provider.includes('claude')) {
                      return { label: `Bypass: Claude`, bg: '#1a1a1a', color: '#ffffff', border: 'rgba(255,255,255,0.15)', icon: 'claude' }
                    }
                    if (provider.includes('openai') || provider.includes('gpt')) {
                      return { label: `Bypass: GPT`, bg: '#1a1a1a', color: '#ffffff', border: 'rgba(255,255,255,0.15)', icon: 'openai' }
                    }
                    return { label: `Bypass: ${provider}`, bg: 'rgba(251,146,60,0.12)', color: '#fb923c', border: 'rgba(251,146,60,0.2)' }
                  }
                  return { label: src, bg: 'rgba(240,235,225,0.06)', color: 'rgba(240,235,225,0.5)', border: 'rgba(240,235,225,0.1)' }
              }
            })()
            return (
              <span
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
                style={{ background: pill.bg, color: pill.color, border: `1px solid ${pill.border}` }}
                title={`Generation: ${src}`}
              >
                {'icon' in pill && pill.icon === 'claude' && <ClaudeLogo size={10} />}
                {'icon' in pill && pill.icon === 'openai' && <OpenAILogo size={10} color="#ffffff" />}
                {pill.label}
              </span>
            )
          })()}

          {/* Cloud governance pill */}
          {isAssistant && meta?.cloud_governance_used && (
            <span
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
              style={{ background: 'rgba(56,189,248,0.10)', color: '#38bdf8', border: '1px solid rgba(56,189,248,0.18)' }}
              title="Cloud governance services (slot classification, NLI) were used for this response"
            >
              ☁ Governance
            </span>
          )}

          {/* Belief confidence badge */}
          {isAssistant && meta?.belief_confidence != null && meta.belief_confidence > 0 && (
            <span
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-mono tabular-nums"
              style={{
                background: meta.belief_confidence >= 0.7
                  ? 'rgba(52,211,153,0.10)' : meta.belief_confidence >= 0.4
                  ? 'rgba(201,164,92,0.10)' : 'rgba(212,112,88,0.10)',
                color: meta.belief_confidence >= 0.7
                  ? '#34d399' : meta.belief_confidence >= 0.4
                  ? '#c9a45c' : '#D47058',
                border: `1px solid ${meta.belief_confidence >= 0.7
                  ? 'rgba(52,211,153,0.2)' : meta.belief_confidence >= 0.4
                  ? 'rgba(201,164,92,0.2)' : 'rgba(212,112,88,0.2)'}`,
              }}
              title={`Belief confidence: ${(meta.belief_confidence * 100).toFixed(0)}% — how much the system trusts this response based on memory evidence`}
            >
              ◉ {meta.belief_confidence.toFixed(2)}
            </span>
          )}

          {/* Gate check dots — slot/NLI/gap */}
          {isAssistant && meta?.gate_checks && (
            <span className="inline-flex items-center gap-1 text-[9px] font-mono" title="Governance gates: Slot Classify · NLI Critic · Gap Audit">
              {(() => {
                const gc = meta.gate_checks as { slot?: string; nli?: string; gap?: string }
                const dotStyle = (val: string) => {
                  if (!val || val === 'none' || val === 'skip') return { bg: 'rgba(240,235,225,0.15)', color: 'var(--text-faint)' }
                  if (val === 'safe' || val.includes('pass')) return { bg: 'rgba(52,211,153,0.2)', color: '#34d399' }
                  if (val === 'flagged' || val.includes('fail') || val.includes('contradiction')) return { bg: 'rgba(212,112,88,0.2)', color: '#D47058' }
                  if (val.includes('soft')) return { bg: 'rgba(201,164,92,0.2)', color: '#c9a45c' }
                  return { bg: 'rgba(52,211,153,0.15)', color: '#34d399' }
                }
                const gates = [
                  { label: 'S', val: gc.slot || 'none', title: `Slot: ${gc.slot || 'none'}` },
                  { label: 'N', val: gc.nli || 'none', title: `NLI: ${gc.nli || 'none'}` },
                  { label: 'G', val: gc.gap || 'safe', title: `Gap: ${gc.gap || 'safe'}` },
                ]
                return gates.map(g => {
                  const s = dotStyle(g.val)
                  return (
                    <span key={g.label} title={g.title}
                      style={{
                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                        width: 16, height: 16, borderRadius: '50%',
                        background: s.bg, color: s.color, fontSize: 8, fontWeight: 600,
                      }}>
                      {g.label}
                    </span>
                  )
                })
              })()}
            </span>
          )}

          {/* Status badges — condensed */}
          {meta && (
            <div className="flex items-center gap-1.5">
              {gatesFailed && (
                <button
                  onClick={() => setGateFailDrawerOpen(true)}
                  className="rounded-full px-2 py-0.5 text-[10px] font-medium transition-opacity hover:opacity-80"
                  style={{ background: 'rgba(251,113,133,0.15)', color: '#fb7185' }}
                  title={meta?.gate_reason ? `Gate blocked: ${meta.gate_reason}` : 'Click to see why this was blocked'}
                >
                  gate fail{meta?.gate_reason ? ` · ${meta.gate_reason.replace(/_/g, ' ').slice(0, 30)}` : ''} ›
                </button>
              )}
              {contradictionDetected && (
                <button
                  onClick={() => setContradictionDrawerOpen(true)}
                  className="rounded-full px-2 py-0.5 text-[10px] font-medium transition-opacity hover:opacity-80"
                  style={{ background: 'rgba(251,146,60,0.15)', color: '#fb923c' }}
                  title="Open contradiction ledger"
                >
                  contradiction ›
                </button>
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
                  style={{ background: 'rgba(224,160,128,0.18)', color: '#E0A080' }}
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
            className="mt-3 overflow-hidden rounded border border-white/8 bg-black/20 p-3 text-[11px] text-white/50"
          >
            <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 font-mono">
              {responseType && <div><span className="text-white/30">type</span> <span className="text-white/70">{responseType}</span></div>}
              {typeof gatesPassed === 'boolean' && <div><span className="text-white/30">gates</span> <span className={gatesPassed ? 'text-emerald-300' : 'text-amber-300'}>{gatesPassed ? 'pass' : 'fail'}</span></div>}
              {meta.gate_reason && <div className="col-span-2"><span className="text-white/30">reason</span> <span className="text-white/50">{meta.gate_reason}</span></div>}
              {typeof meta.confidence === 'number' && <div><span className="text-white/30">conf</span> <span className="text-white/70">{(meta.confidence * 100).toFixed(0)}%</span></div>}
              {typeof meta.intent_alignment === 'number' && <div><span className="text-white/30">intent</span> <span className="text-white/70">{meta.intent_alignment.toFixed(2)}</span></div>}
              {typeof meta.memory_alignment === 'number' && <div><span className="text-white/30">memory</span> <span className="text-white/70">{meta.memory_alignment.toFixed(2)}</span></div>}
              {typeof meta.unresolved_contradictions_total === 'number' && <div><span className="text-white/30">open</span> <span className="text-white/70">{meta.unresolved_contradictions_total}</span></div>}
              {meta.generation_source && <div><span className="text-white/30">gen</span> <span className="text-white/70">{meta.generation_source}</span></div>}
              {meta.cloud_governance_used && <div><span className="text-white/30">governance</span> <span className="text-sky-300">cloud</span></div>}
              {meta.escalation?.start_tier && <div><span className="text-white/30">escalation</span> <span className="text-white/70">{meta.escalation.start_tier}</span></div>}
              {meta.escalation?.reason && <div className="col-span-2"><span className="text-white/30">esc reason</span> <span className="text-white/50">{meta.escalation.reason}</span></div>}
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

      {/* Contradiction ledger drawer — portal-style, triggered by badge */}
      <ContradictionDrawer
        threadId={props.threadId ?? 'default'}
        open={contradictionDrawerOpen}
        onClose={() => setContradictionDrawerOpen(false)}
      />

      {/* Gate failure drawer — detailed breakdown of why a gate blocked */}
      <GateFailDrawer
        open={gateFailDrawerOpen}
        onClose={() => setGateFailDrawerOpen(false)}
        gateReason={meta?.gate_reason ?? 'unknown'}
        gateDebug={meta?.gate_debug ? {
          slot: meta.gate_debug.slot,
          intent_align: meta.gate_debug.intent_align,
          memory_align: meta.gate_debug.memory_align,
          grounding_score: meta.gate_debug.grounding,
          grounding: meta.gate_debug.grounding,
          hard_conflicts: meta.gate_debug.hard_conflicts,
          open_total: meta.gate_debug.open_total,
          trigger: meta.gate_debug.trigger,
          explanation: meta.gate_debug.explanation,
          stored: meta.gate_debug.stored,
          incoming: meta.gate_debug.incoming,
        } : undefined}
        retrievedMemories={meta?.retrieved_memories}
        contradictionCount={meta?.unresolved_contradictions_total ?? 0}
        onOpenContradictions={() => {
          setGateFailDrawerOpen(false)
          setContradictionDrawerOpen(true)
        }}
      />
    </motion.div>
  )
}
