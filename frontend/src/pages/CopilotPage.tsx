import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  getCopilotMemories,
  getCopilotProfile,
  getCopilotAccuracy,
  teachCopilot,
  deleteCopilotMemory,
  correctCopilotMemory,
  getCopilotFactChecks,
  resolveFactCheck,
  getTrustDecayConfig,
  runTrustDecay,
  reinforceMemory,
  getSchedulerStatus,
  forceSchedulerTick,
  getCopilotLearningStats,
  getLearningCorrections,
  getInteractionStats,
  triggerRetrain,
  getCopilotSessions,
  searchSessions,
  getCopilotConcepts,
  getCopilotPatterns,
  getCopilotPreferences,
  getTrainingDataStats,
  getPersonalityTimeline,
  getSelfModelState,
  getEpistemicTimeline,
  runLoops,
  getMemoryTrustHistory,
  type CopilotMemory,
  type CopilotMemoriesResponse,
  type CopilotProfile,
  type AccuracyStats,
  type FactCheck,
  type TrustDecayConfig,
  type PersonalityCheckpoint,
  type SelfModelAwareness,
  type EpistemicEvent,
} from '../lib/api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(ts: number): string {
  const diff = Math.floor(Date.now() / 1000) - ts
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`
  return new Date(ts * 1000).toLocaleDateString()
}

function trustColor(trust: number): string {
  if (trust >= 0.7) return 'text-emerald-400'
  if (trust >= 0.4) return 'text-amber-400'
  return 'text-red-400'
}

function trustBg(trust: number): string {
  if (trust >= 0.7) return 'bg-emerald-500/20 border-emerald-500/40'
  if (trust >= 0.4) return 'bg-amber-500/20 border-amber-500/40'
  return 'bg-red-500/20 border-red-500/40'
}

function sourceBadge(source: string): { label: string; className: string } {
  switch (source) {
    case 'inferred':
      return { label: '⚡ Auto', className: 'bg-violet-500/20 text-violet-300 border-violet-500/30' }
    case 'user':
      return { label: '👤 You', className: 'bg-sky-500/20 text-sky-300 border-sky-500/30' }
    case 'document':
      return { label: '📄 Doc', className: 'bg-teal-500/20 text-teal-300 border-teal-500/30' }
    case 'code':
      return { label: '💻 Code', className: 'bg-orange-500/20 text-orange-300 border-orange-500/30' }
    default:
      return { label: source, className: 'bg-white/10 text-white/60 border-white/20' }
  }
}

function categorize(text: string): string {
  const t = text.toLowerCase()
  if (t.includes('name is')) return 'identity'
  if (t.includes('freelanc') || t.includes('work') || t.includes('employ') || t.includes('job')) return 'career'
  if (t.includes('favorite')) return 'favorites'
  if (t.includes('language') || t.includes('code in') || t.includes('python') || t.includes('typescript')) return 'tech'
  if (t.includes('prefer') || t.includes('style') || t.includes('like') || t.includes('love')) return 'preferences'
  if (t.includes('doc') || t.includes('test')) return 'workflow'
  return 'other'
}

const CATEGORY_COLORS: Record<string, string> = {
  identity: '#60a5fa',
  career: '#f59e0b',
  favorites: '#f472b6',
  tech: '#34d399',
  preferences: '#a78bfa',
  workflow: '#fb923c',
  other: '#94a3b8',
}

const CATEGORY_ICONS: Record<string, string> = {
  identity: '👤',
  career: '💼',
  favorites: '⭐',
  tech: '💻',
  preferences: '🎨',
  workflow: '📋',
  other: '📌',
}

// ---------------------------------------------------------------------------
// Toast component
// ---------------------------------------------------------------------------

type Toast = { id: string; text: string; source: string; ts: number }

function ToastStack({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: string) => void }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      <AnimatePresence>
        {toasts.map(t => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, x: 80, scale: 0.9 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 80, scale: 0.9 }}
            className="flex items-start gap-3 rounded border border-violet-500/30 bg-[#1a1a2e]/95 p-3 shadow-lg shadow-violet-500/10 cursor-pointer"
            onClick={() => onDismiss(t.id)}
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-sm bg-violet-500/20">
              <span className="text-sm">🧠</span>
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[10px] uppercase tracking-wider text-violet-400 font-medium">
                System learned
              </div>
              <div className="text-sm text-white/80 mt-0.5 leading-snug">{t.text}</div>
              <div className="mt-1 flex items-center gap-2">
                <span className={`inline-flex items-center rounded-sm border px-1.5 py-0 text-[9px] ${sourceBadge(t.source).className}`}>
                  {sourceBadge(t.source).label}
                </span>
                <span className="text-[9px] text-white/20">{timeAgo(t.ts)}</span>
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Profile Card
// ---------------------------------------------------------------------------

function ProfileCard({ profile }: { profile: CopilotProfile | null }) {
  if (!profile) return null
  return (
    <div className="rounded-sm border border-white/10 bg-gradient-to-br from-violet-500/5 to-sky-500/5 p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-sm bg-violet-500/20 text-2xl">
          🧠
        </div>
        <div>
          <div className="text-lg font-bold text-white">{profile.name || 'Unknown'}</div>
          <div className="text-xs text-white/40">
            {profile.role || 'Role unknown'}{profile.employer ? ` · ${profile.employer}` : ''}
          </div>
        </div>
      </div>

      {profile.languages.length > 0 && (
        <div className="mb-3">
          <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1.5">Languages</div>
          <div className="flex flex-wrap gap-1.5">
            {profile.languages.map(l => (
              <span key={l} className="rounded-sm bg-emerald-500/15 border border-emerald-500/25 px-2 py-0.5 text-xs text-emerald-300">
                {l}
              </span>
            ))}
          </div>
        </div>
      )}

      {Object.keys(profile.preferences).length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1.5">Preferences</div>
          <div className="flex flex-col gap-1">
            {Object.entries(profile.preferences).map(([k, v]) => (
              <div key={k} className="flex items-center gap-2 text-xs">
                <span className="text-white/30">{k.replace(/_/g, ' ')}:</span>
                <span className="text-white/70">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {profile.all_facts.length > 0 && (
        <div className="mt-3">
          <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1.5">All facts</div>
          <ul className="flex flex-col gap-0.5">
            {profile.all_facts.map((f, i) => (
              <li key={i} className="text-xs text-white/50 pl-2 border-l border-white/10">{f}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Teach Form
// ---------------------------------------------------------------------------

function TeachForm({ onTaught, threadId = 'default' }: { onTaught: () => void; threadId?: string }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [success, setSuccess] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const presets = [
    { label: 'Name', template: 'My name is ' },
    { label: 'Language', template: 'I code in ' },
    { label: 'Favorite', template: 'My favorite ' },
    { label: 'Style', template: 'I prefer ' },
    { label: 'Role', template: 'I work as a ' },
  ]

  const handleTeach = async () => {
    if (!text.trim()) return
    setBusy(true)
    try {
      await teachCopilot(text.trim(), undefined, threadId)
      setSuccess(text.trim())
      setText('')
      onTaught()
      setTimeout(() => setSuccess(''), 3000)
    } catch {
      // ignore
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-sm border border-white/10 bg-white/[0.03] p-4">
      <div className="text-xs font-medium uppercase tracking-wider text-white/40 mb-3">
        ✏️ Teach System
      </div>
      <div className="flex flex-wrap gap-1.5 mb-3">
        {presets.map(p => (
          <button
            key={p.label}
            onClick={() => { setText(p.template); inputRef.current?.focus() }}
            className="rounded-sm bg-white/5 border border-white/10 px-2.5 py-1 text-[11px] text-white/50 hover:text-white hover:bg-white/10 transition-all"
          >
            {p.label}
          </button>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          ref={inputRef}
          type="text"
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleTeach()}
          placeholder="Tell the system something about yourself..."
          className="flex-1 rounded border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-white/25 outline-none focus:border-violet-500/50 transition-colors"
        />
        <button
          onClick={handleTeach}
          disabled={!text.trim() || busy}
          className="rounded bg-violet-600 hover:bg-violet-500 disabled:opacity-30 disabled:hover:bg-violet-600 px-5 py-2.5 text-sm font-medium text-white transition-all"
        >
          {busy ? '...' : 'Teach'}
        </button>
      </div>
      <AnimatePresence>
        {success && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2 text-xs text-emerald-400"
          >
            ✓ Learned: &ldquo;{success}&rdquo;
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Memory Graph (stable, no-flicker, HiDPI)
// ---------------------------------------------------------------------------

type GraphNode = {
  x: number; y: number; vx: number; vy: number
  memory: CopilotMemory; cat: string; radius: number
  targetX: number; targetY: number
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

function MemoryGraph({ memories }: { memories: CopilotMemory[] }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [hovered, setHovered] = useState<CopilotMemory | null>(null)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const nodesRef = useRef<GraphNode[]>([])
  const animIdRef = useRef<number>(0)
  const settledRef = useRef(false)
  const frameCountRef = useRef(0)
  const sizeRef = useRef({ w: 800, h: 500 })
  const hoveredIdRef = useRef<string | null>(null)

  // Sync nodes with memories without resetting positions
  useEffect(() => {
    if (!memories.length) { nodesRef.current = []; return }

    const existing = new Map(nodesRef.current.map(n => [n.memory.id, n]))
    const w = sizeRef.current.w
    const h = sizeRef.current.h
    const cats = [...new Set(memories.map(m => categorize(m.text)))]
    const catAngles: Record<string, number> = {}
    cats.forEach((c, i) => { catAngles[c] = (i / cats.length) * Math.PI * 2 - Math.PI / 2 })

    const newNodes: GraphNode[] = memories.map(m => {
      const cat = categorize(m.text)
      const prev = existing.get(m.id)
      if (prev) {
        // Keep position, update data
        prev.memory = m
        prev.cat = cat
        prev.radius = 8 + m.trust * 14
        return prev
      }
      // New node — place near its category cluster
      const angle = catAngles[cat] + (Math.random() - 0.5) * 0.6
      const dist = 100 + Math.random() * 120
      const x = w / 2 + Math.cos(angle) * dist
      const y = h / 2 + Math.sin(angle) * dist
      return { x, y, vx: 0, vy: 0, memory: m, cat, radius: 8 + m.trust * 14, targetX: x, targetY: y }
    })

    nodesRef.current = newNodes
    settledRef.current = false
    frameCountRef.current = 0
  }, [memories])

  // Canvas sizing with HiDPI
  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    const resize = () => {
      const rect = container.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      const w = Math.round(rect.width)
      const h = 500
      sizeRef.current = { w, h }
      canvas.width = w * dpr
      canvas.height = h * dpr
      canvas.style.width = `${w}px`
      canvas.style.height = `${h}px`
      const ctx = canvas.getContext('2d')
      if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      settledRef.current = false
      frameCountRef.current = 0
    }

    resize()
    const obs = new ResizeObserver(resize)
    obs.observe(container)
    return () => obs.disconnect()
  }, [])

  // Animation loop — runs once, reads nodesRef
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const draw = () => {
      const { w, h } = sizeRef.current
      ctx.clearRect(0, 0, w, h)

      const nodes = nodesRef.current
      if (!nodes.length) { animIdRef.current = requestAnimationFrame(draw); return }

      frameCountRef.current++

      // --- Physics (skip after settled) ---
      if (!settledRef.current) {
        // Pre-compute category centroids
        const catCentroids: Record<string, { sx: number; sy: number; count: number }> = {}
        for (const n of nodes) {
          if (!catCentroids[n.cat]) catCentroids[n.cat] = { sx: 0, sy: 0, count: 0 }
          catCentroids[n.cat].sx += n.x
          catCentroids[n.cat].sy += n.y
          catCentroids[n.cat].count++
        }

        let totalMotion = 0
        for (let i = 0; i < nodes.length; i++) {
          const a = nodes[i]
          // Center gravity (weak)
          a.vx += (w / 2 - a.x) * 0.0008
          a.vy += (h / 2 - a.y) * 0.0008

          // Category clustering
          const cc = catCentroids[a.cat]
          const cx = cc.sx / cc.count
          const cy = cc.sy / cc.count
          a.vx += (cx - a.x) * 0.004
          a.vy += (cy - a.y) * 0.004

          // Repulsion
          for (let j = i + 1; j < nodes.length; j++) {
            const b = nodes[j]
            const dx = b.x - a.x
            const dy = b.y - a.y
            const distSq = dx * dx + dy * dy
            const minDist = a.radius + b.radius + 20
            if (distSq < minDist * minDist) {
              const dist = Math.sqrt(distSq) || 1
              const force = (minDist - dist) * 0.025
              const fx = (dx / dist) * force
              const fy = (dy / dist) * force
              a.vx -= fx; a.vy -= fy
              b.vx += fx; b.vy += fy
            }
          }
        }

        for (const n of nodes) {
          n.vx *= 0.88
          n.vy *= 0.88
          n.x += n.vx
          n.y += n.vy
          // Padding from edges
          const pad = n.radius + 30
          n.x = Math.max(pad, Math.min(w - pad, n.x))
          n.y = Math.max(pad + 20, Math.min(h - pad - 30, n.y))
          totalMotion += Math.abs(n.vx) + Math.abs(n.vy)
        }

        // Settle after enough frames and low motion
        if (frameCountRef.current > 200 && totalMotion < 0.5) {
          settledRef.current = true
        }
      }

      // --- Draw edges (same-category, within distance) ---
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          if (nodes[i].cat !== nodes[j].cat) continue
          const dx = nodes[i].x - nodes[j].x
          const dy = nodes[i].y - nodes[j].y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist > 180) continue
          const alpha = Math.max(0.03, 0.15 * (1 - dist / 180))
          const [r, g, b] = hexToRgb(CATEGORY_COLORS[nodes[i].cat] || '#888888')
          ctx.beginPath()
          ctx.strokeStyle = `rgba(${r},${g},${b},${alpha})`
          ctx.lineWidth = 1
          ctx.moveTo(nodes[i].x, nodes[i].y)
          ctx.lineTo(nodes[j].x, nodes[j].y)
          ctx.stroke()
        }
      }

      // --- Draw nodes ---
      const hid = hoveredIdRef.current
      for (const n of nodes) {
        const color = CATEGORY_COLORS[n.cat] || '#888888'
        const [r, g, b] = hexToRgb(color)
        const isHov = n.memory.id === hid

        // Outer glow
        const glowR = n.radius + (isHov ? 12 : 6)
        const glow = ctx.createRadialGradient(n.x, n.y, n.radius * 0.5, n.x, n.y, glowR)
        glow.addColorStop(0, `rgba(${r},${g},${b},${isHov ? 0.25 : 0.12})`)
        glow.addColorStop(1, `rgba(${r},${g},${b},0)`)
        ctx.beginPath()
        ctx.arc(n.x, n.y, glowR, 0, Math.PI * 2)
        ctx.fillStyle = glow
        ctx.fill()

        // Main circle
        const grad = ctx.createRadialGradient(
          n.x - n.radius * 0.3, n.y - n.radius * 0.3, n.radius * 0.1,
          n.x, n.y, n.radius
        )
        grad.addColorStop(0, `rgba(${r},${g},${b},${isHov ? 0.9 : 0.6})`)
        grad.addColorStop(1, `rgba(${r},${g},${b},${isHov ? 0.7 : 0.35})`)
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2)
        ctx.fillStyle = grad
        ctx.fill()

        // Border ring
        ctx.strokeStyle = `rgba(${r},${g},${b},${isHov ? 1 : 0.7})`
        ctx.lineWidth = isHov ? 2.5 : 1.5
        ctx.stroke()

        // Trust indicator dot (small bright dot at center)
        const trustR = Math.max(2, n.radius * 0.25)
        ctx.beginPath()
        ctx.arc(n.x, n.y, trustR, 0, Math.PI * 2)
        ctx.fillStyle = n.memory.trust >= 0.7 ? 'rgba(52,211,153,0.8)' :
                         n.memory.trust >= 0.4 ? 'rgba(251,191,36,0.8)' :
                                                  'rgba(248,113,113,0.8)'
        ctx.fill()
      }

      // --- Category labels ---
      const uniqueCats = [...new Set(nodes.map(n => n.cat))]
      for (const cat of uniqueCats) {
        const catNodes = nodes.filter(n => n.cat === cat)
        const lx = catNodes.reduce((s, n) => s + n.x, 0) / catNodes.length
        const ly = Math.min(...catNodes.map(n => n.y - n.radius)) - 14
        const icon = CATEGORY_ICONS[cat] || ''
        const label = `${icon}  ${cat}`
        const color = CATEGORY_COLORS[cat] || '#888'

        ctx.font = '600 11px Inter, system-ui, sans-serif'
        ctx.textAlign = 'center'
        const tm = ctx.measureText(label)
        const pw = tm.width + 12
        const ph = 18

        // Label pill background
        const [r, g, b] = hexToRgb(color)
        ctx.fillStyle = `rgba(${r},${g},${b},0.12)`
        ctx.beginPath()
        const rx = lx - pw / 2, ry = ly - ph / 2
        ctx.roundRect(rx, ry, pw, ph, 4)
        ctx.fill()

        ctx.fillStyle = color
        ctx.globalAlpha = 0.85
        ctx.fillText(label, lx, ly + 4)
        ctx.globalAlpha = 1
      }

      animIdRef.current = requestAnimationFrame(draw)
    }

    animIdRef.current = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(animIdRef.current)
  }, []) // empty deps — runs once, reads refs

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const scaleX = sizeRef.current.w / rect.width
    const scaleY = sizeRef.current.h / rect.height
    const mx = (e.clientX - rect.left) * scaleX
    const my = (e.clientY - rect.top) * scaleY
    setMousePos({ x: e.clientX, y: e.clientY })

    const hit = nodesRef.current.find(n => {
      const dx = n.x - mx, dy = n.y - my
      return dx * dx + dy * dy < (n.radius + 6) * (n.radius + 6)
    })
    const mem = hit?.memory || null
    hoveredIdRef.current = mem?.id || null
    setHovered(mem)
    // Wake up physics briefly on hover for highlight redraw
    if (mem && settledRef.current) {
      settledRef.current = false
      frameCountRef.current = 195 // will re-settle quickly
    }
  }

  return (
    <div ref={containerRef} className="relative rounded-sm border border-white/10 bg-[#0d0d1a] overflow-hidden">
      <div className="absolute top-3 left-4 text-[10px] uppercase tracking-wider text-white/30 z-10 font-medium">
        Memory Graph — {memories.length} facts
      </div>
      <canvas
        ref={canvasRef}
        className="w-full"
        style={{ height: '500px', cursor: hovered ? 'pointer' : 'default' }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => { setHovered(null); hoveredIdRef.current = null }}
      />
      <div className="absolute bottom-3 left-4 flex flex-wrap gap-3">
        {Object.entries(CATEGORY_COLORS).map(([cat, color]) => (
          <span key={cat} className="flex items-center gap-1.5 text-[10px] text-white/50 font-medium">
            <span className="inline-block h-2.5 w-2.5 rounded-full shadow-sm" style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}40` }} />
            {cat}
          </span>
        ))}
      </div>
      {hovered && (
        <div
          className="fixed z-50 rounded border border-white/15 bg-[#12122a]/95 px-4 py-3 shadow-lg max-w-xs pointer-events-none"
          style={{ left: mousePos.x + 14, top: mousePos.y - 12 }}
        >
          <div className="text-[13px] text-white/90 leading-relaxed">{hovered.text}</div>
          <div className="mt-2 flex items-center gap-3 text-[10px]">
            <span className={`font-semibold ${trustColor(hovered.trust)}`}>
              Trust {(hovered.trust * 100).toFixed(0)}%
            </span>
            <span className="text-white/30">{sourceBadge(hovered.source).label}</span>
            <span className="text-white/25">{timeAgo(hovered.timestamp)}</span>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Accuracy Tracker
// ---------------------------------------------------------------------------

function AccuracyTracker({ accuracy }: { accuracy: AccuracyStats | null }) {
  if (!accuracy) return null
  const pct = Math.round(accuracy.accuracy_rate * 100)
  const gaugeAngle = accuracy.accuracy_rate * 180

  return (
    <div className="rounded-sm border border-white/10 bg-white/[0.03] p-5">
      <div className="text-[10px] uppercase tracking-wider text-white/30 mb-4">📊 Accuracy Tracker</div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 mb-5">
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{pct}%</div>
          <div className="text-[10px] text-white/30">Accuracy</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-amber-400">{accuracy.corrections_made}</div>
          <div className="text-[10px] text-white/30">Corrections</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-red-400">{accuracy.deletions_made}</div>
          <div className="text-[10px] text-white/30">Deletions</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-emerald-400">{accuracy.memories_per_day}</div>
          <div className="text-[10px] text-white/30">Facts/day</div>
        </div>
      </div>

      <div className="flex justify-center mb-5">
        <div className="relative w-40 h-20 overflow-hidden">
          <svg viewBox="0 0 200 110" className="w-full h-full">
            <path
              d="M 20 100 A 80 80 0 0 1 180 100"
              fill="none"
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="12"
              strokeLinecap="round"
            />
            <path
              d="M 20 100 A 80 80 0 0 1 180 100"
              fill="none"
              stroke={pct >= 90 ? '#34d399' : pct >= 70 ? '#fbbf24' : '#f87171'}
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={`${(gaugeAngle / 180) * 251.2} 251.2`}
            />
            <text x="100" y="95" textAnchor="middle" fill="white" fontSize="28" fontWeight="bold">
              {pct}%
            </text>
            <text x="100" y="108" textAnchor="middle" fill="rgba(255,255,255,0.3)" fontSize="10">
              accuracy
            </text>
          </svg>
        </div>
      </div>

      <div className="flex items-center gap-4 justify-center mb-4">
        <div className="flex items-center gap-1.5 text-xs">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-violet-500" />
          <span className="text-white/50">Auto: {accuracy.auto_learned}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-sky-500" />
          <span className="text-white/50">Explicit: {accuracy.explicit}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-white/30">Avg trust: </span>
          <span className={`font-mono font-bold ${trustColor(accuracy.trust_avg)}`}>
            {(accuracy.trust_avg * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {accuracy.learning_velocity.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-white/20 mb-2">Learning Velocity</div>
          <div className="flex items-end gap-1 h-16">
            {accuracy.learning_velocity.map((v, i) => {
              const maxVal = Math.max(...accuracy.learning_velocity.map(x => x.count), 1)
              const barH = Math.max((v.count / maxVal) * 100, 4)
              const autoH = Math.max((v.auto_learned / maxVal) * 100, 0)
              return (
                <div key={i} className="flex flex-1 flex-col items-center gap-0.5 group relative" title={`${v.label}: ${v.count} total, ${v.auto_learned} auto`}>
                  <div className="w-full flex flex-col justify-end" style={{ height: '64px' }}>
                    <div
                      className="w-full rounded-t bg-violet-500/60 transition-all"
                      style={{ height: `${autoH}%` }}
                    />
                    <div
                      className="w-full rounded-b bg-sky-500/40 transition-all"
                      style={{ height: `${Math.max(barH - autoH, 0)}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
          <div className="flex justify-between text-[8px] text-white/15 mt-1">
            <span>{accuracy.learning_velocity[0]?.label}</span>
            <span>{accuracy.learning_velocity[accuracy.learning_velocity.length - 1]?.label}</span>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Fact Checks Panel
// ---------------------------------------------------------------------------

function FactChecksPanel() {
  const [checks, setChecks] = useState<FactCheck[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const data = await getCopilotFactChecks({ limit: 50 })
      setChecks(data)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleResolve = async (id: string) => {
    try {
      await resolveFactCheck(id)
      setChecks(prev => prev.filter(c => c.id !== id))
    } catch { /* ignore */ }
  }

  const severityStyle = (s: string) => {
    if (s === 'critical') return 'bg-red-500/15 text-red-400 border-red-500/30'
    if (s === 'warning') return 'bg-amber-500/15 text-amber-400 border-amber-500/30'
    return 'bg-sky-500/15 text-sky-400 border-sky-500/30'
  }

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-500" /></div>

  if (!checks.length) return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <span className="text-5xl opacity-40">✅</span>
      <div className="mt-3 text-sm text-white/50">No pending fact checks</div>
      <div className="text-xs text-white/25 mt-1">The auto fact-checker will flag contradictions and hallucinations here</div>
    </div>
  )

  return (
    <div className="flex flex-col gap-3">
      <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1">
        {checks.length} pending finding{checks.length !== 1 ? 's' : ''} — sorted by volatility
      </div>
      {checks.map(c => (
        <div key={c.id} className="rounded border border-white/8 bg-white/[0.03] p-4">
          <div className="flex items-start gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <span className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-[10px] font-semibold uppercase ${severityStyle(c.severity)}`}>
                  {c.severity}
                </span>
                {c.volatility > 0 && (
                  <span className="text-[10px] text-white/30 font-mono">
                    V={c.volatility.toFixed(3)}
                  </span>
                )}
                <span className="text-[10px] text-white/20 ml-auto">{c.created_at}</span>
              </div>
              <div className="text-sm text-white/80 leading-relaxed mb-2">{c.finding}</div>
              <div className="text-xs text-white/30 line-clamp-2 italic">
                Response: &ldquo;{c.response_text?.slice(0, 200)}{(c.response_text?.length || 0) > 200 ? '...' : ''}&rdquo;
              </div>
            </div>
            <button
              onClick={() => handleResolve(c.id)}
              className="rounded-sm bg-emerald-500/10 border border-emerald-500/25 px-3 py-1.5 text-xs text-emerald-400 hover:bg-emerald-500/20 transition-all flex-shrink-0"
              title="Mark as resolved"
            >
              ✓ Resolve
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Trust & Decay Panel
// ---------------------------------------------------------------------------

function TrustDecayPanel({ memories, onRefresh }: { memories: CopilotMemory[]; onRefresh: () => void }) {
  const [config, setConfig] = useState<TrustDecayConfig | null>(null)
  const [scheduler, setScheduler] = useState<Record<string, any> | null>(null)
  const [decayResult, setDecayResult] = useState<Record<string, any> | null>(null)
  const [running, setRunning] = useState(false)
  const [reinforcing, setReinforcing] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const [c, s] = await Promise.all([getTrustDecayConfig(), getSchedulerStatus()])
      setConfig(c)
      setScheduler(s)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleRunDecay = async () => {
    setRunning(true)
    try {
      const result = await runTrustDecay()
      setDecayResult(result)
      onRefresh()
    } catch { /* ignore */ }
    finally { setRunning(false) }
  }

  const handleForceTick = async () => {
    setRunning(true)
    try {
      const result = await forceSchedulerTick()
      setDecayResult(result)
      onRefresh()
    } catch { /* ignore */ }
    finally { setRunning(false) }
  }

  const handleReinforce = async (id: string) => {
    setReinforcing(id)
    try {
      await reinforceMemory(id)
      onRefresh()
    } catch { /* ignore */ }
    finally { setReinforcing(null) }
  }

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-500" /></div>

  return (
    <div className="flex flex-col gap-5">
      {/* Config + Scheduler cards */}
      <div className="grid gap-4 lg:grid-cols-2">
        {config && (
          <div className="rounded-sm border border-white/10 bg-white/[0.03] p-5">
            <div className="text-[10px] uppercase tracking-wider text-white/30 mb-4">⚙️ Trust Decay Config</div>
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(config).map(([k, v]) => (
                <div key={k} className="flex flex-col">
                  <span className="text-[10px] text-white/30">{k.replace(/_/g, ' ')}</span>
                  <span className="text-sm font-mono text-white/80">{typeof v === 'number' ? v.toFixed(v < 1 ? 3 : 0) : String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {scheduler && (
          <div className="rounded-sm border border-white/10 bg-white/[0.03] p-5">
            <div className="text-[10px] uppercase tracking-wider text-white/30 mb-4">🔄 Idle Scheduler</div>
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(scheduler).map(([k, v]) => (
                <div key={k} className="flex flex-col">
                  <span className="text-[10px] text-white/30">{k.replace(/_/g, ' ')}</span>
                  <span className="text-sm font-mono text-white/80">
                    {typeof v === 'boolean' ? (
                      <span className={v ? 'text-emerald-400' : 'text-red-400'}>{v ? 'ON' : 'OFF'}</span>
                    ) : String(v)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleRunDecay}
          disabled={running}
          className="rounded bg-violet-600 hover:bg-violet-500 disabled:opacity-40 px-5 py-2.5 text-sm font-medium text-white transition-all"
        >
          {running ? '...' : '⏳ Run Trust Decay Pass'}
        </button>
        <button
          onClick={handleForceTick}
          disabled={running}
          className="rounded bg-white/10 hover:bg-white/15 disabled:opacity-40 border border-white/10 px-5 py-2.5 text-sm text-white/70 transition-all"
        >
          Force Scheduler Tick
        </button>
      </div>

      {/* Decay result */}
      {decayResult && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded border border-emerald-500/20 bg-emerald-500/5 p-4"
        >
          <div className="text-[10px] uppercase tracking-wider text-emerald-400 mb-2">Last Run Result</div>
          <pre className="text-xs text-white/60 font-mono whitespace-pre-wrap overflow-auto max-h-40">
            {JSON.stringify(decayResult, null, 2)}
          </pre>
        </motion.div>
      )}

      {/* Low trust memories — reinforce candidates */}
      {memories.filter(m => m.trust < 0.5).length > 0 && (
        <div className="rounded-sm border border-white/10 bg-white/[0.03] p-5">
          <div className="text-[10px] uppercase tracking-wider text-amber-400/60 mb-3">
            ⚠️ Low-trust memories ({memories.filter(m => m.trust < 0.5).length}) — click to reinforce
          </div>
          <div className="flex flex-col gap-2 max-h-60 overflow-y-auto">
            {memories.filter(m => m.trust < 0.5).sort((a, b) => a.trust - b.trust).map(m => (
              <div key={m.id} className="flex items-center gap-3 rounded-sm bg-white/[0.02] border border-white/5 p-3">
                <span className={`font-mono text-xs font-bold ${trustColor(m.trust)}`}>
                  {(m.trust * 100).toFixed(0)}%
                </span>
                <span className="text-sm text-white/60 flex-1 truncate">{m.text}</span>
                <button
                  onClick={() => handleReinforce(m.id)}
                  disabled={reinforcing === m.id}
                  className="rounded-sm bg-emerald-500/10 border border-emerald-500/25 px-2.5 py-1 text-[11px] text-emerald-400 hover:bg-emerald-500/20 transition-all flex-shrink-0"
                >
                  {reinforcing === m.id ? '...' : '↑ Boost'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sessions Panel
// ---------------------------------------------------------------------------

function SessionsPanel() {
  const [sessions, setSessions] = useState<any[]>([])
  const [searchTopic, setSearchTopic] = useState('')
  const [searching, setSearching] = useState(false)
  const [loading, setLoading] = useState(true)
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await getCopilotSessions({ limit: 30 })
      setSessions(data)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSearch = async () => {
    if (!searchTopic.trim()) { load(); return }
    setSearching(true)
    try {
      const results = await searchSessions(searchTopic.trim(), 30)
      setSessions(results)
    } catch { /* ignore */ }
    finally { setSearching(false) }
  }

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-500" /></div>

  return (
    <div className="flex flex-col gap-4">
      {/* Search */}
      <div className="flex gap-2">
        <input
          type="text"
          value={searchTopic}
          onChange={e => setSearchTopic(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="Search sessions by topic..."
          className="flex-1 rounded border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-white/25 outline-none focus:border-violet-500/50 transition-colors"
        />
        <button
          onClick={handleSearch}
          disabled={searching}
          className="rounded bg-violet-600 hover:bg-violet-500 disabled:opacity-40 px-5 py-2.5 text-sm font-medium text-white transition-all"
        >
          {searching ? '...' : 'Search'}
        </button>
        {searchTopic && (
          <button
            onClick={() => { setSearchTopic(''); load() }}
            className="rounded bg-white/10 hover:bg-white/15 border border-white/10 px-4 py-2.5 text-sm text-white/50 transition-all"
          >
            Clear
          </button>
        )}
      </div>

      {sessions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <span className="text-5xl opacity-40">📂</span>
          <div className="mt-3 text-sm text-white/50">No sessions found</div>
          <div className="text-xs text-white/25 mt-1">Session summaries are created from episodic memory</div>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1">
            {sessions.length} session{sessions.length !== 1 ? 's' : ''}
          </div>
          {sessions.map((s, i) => (
            <div key={i} className="rounded border border-white/8 bg-white/[0.03] overflow-hidden">
              <div
                className="flex items-start gap-3 p-4 cursor-pointer hover:bg-white/[0.02] transition-colors"
                onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
              >
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-sm bg-sky-500/15 text-sm">
                  📋
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-medium text-white/70">
                      {s.thread_id || s.session_id || `Session ${i + 1}`}
                    </span>
                    {s.message_count && (
                      <span className="text-[10px] text-white/25">{s.message_count} messages</span>
                    )}
                    <span className="text-[10px] text-white/20 ml-auto">
                      {s.created_at || s.timestamp ? new Date((s.created_at || s.timestamp) * 1000).toLocaleDateString() : ''}
                    </span>
                  </div>
                  <div className="text-sm text-white/50 line-clamp-2">
                    {s.summary || s.topics?.join(', ') || 'No summary'}
                  </div>
                </div>
                <span className="text-white/20 text-xs mt-1">{expandedIdx === i ? '▲' : '▼'}</span>
              </div>
              {expandedIdx === i && (
                <div className="border-t border-white/5 p-4 bg-white/[0.01]">
                  <pre className="text-xs text-white/50 font-mono whitespace-pre-wrap overflow-auto max-h-60">
                    {JSON.stringify(s, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// CRT Insights Panel (Concepts, Patterns, Learning Stats)
// ---------------------------------------------------------------------------

function CrtInsightsPanel() {
  const [concepts, setConcepts] = useState<any[]>([])
  const [patterns, setPatterns] = useState<any[]>([])
  const [preferences, setPreferences] = useState<any[]>([])
  const [learningStats, setLearningStats] = useState<Record<string, any> | null>(null)
  const [trainingStats, setTrainingStats] = useState<Record<string, any> | null>(null)
  const [interactionStats, setInteractionStats] = useState<Record<string, any> | null>(null)
  const [loading, setLoading] = useState(true)
  const [retraining, setRetraining] = useState(false)
  const [subTab, setSubTab] = useState<'concepts' | 'patterns' | 'learning' | 'training'>('concepts')

  const load = useCallback(async () => {
    try {
      const [con, pat, pref, ls, ts, is] = await Promise.all([
        getCopilotConcepts().catch(() => []),
        getCopilotPatterns().catch(() => []),
        getCopilotPreferences().catch(() => []),
        getCopilotLearningStats().catch(() => null),
        getTrainingDataStats().catch(() => null),
        getInteractionStats(24).catch(() => null),
      ])
      setConcepts(con)
      setPatterns(pat)
      setPreferences(pref)
      setLearningStats(ls)
      setTrainingStats(ts)
      setInteractionStats(is)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleRetrain = async () => {
    setRetraining(true)
    try { await triggerRetrain() } catch { /* ignore */ }
    finally { setRetraining(false); load() }
  }

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-500" /></div>

  const conceptTypes: Record<string, { icon: string; color: string }> = {
    person: { icon: '👤', color: 'text-sky-400' },
    project: { icon: '📦', color: 'text-violet-400' },
    organization: { icon: '🏢', color: 'text-amber-400' },
    topic: { icon: '💡', color: 'text-emerald-400' },
    location: { icon: '📍', color: 'text-rose-400' },
  }

  const subTabItems = [
    { id: 'concepts' as const, label: 'Knowledge Graph', count: concepts.length },
    { id: 'patterns' as const, label: 'Patterns', count: patterns.length },
    { id: 'learning' as const, label: 'Active Learning', count: null },
    { id: 'training' as const, label: 'Training Data', count: null },
  ]

  return (
    <div className="flex flex-col gap-4">
      {/* Sub-tabs */}
      <div className="flex items-center gap-1">
        {subTabItems.map(st => (
          <button
            key={st.id}
            onClick={() => setSubTab(st.id)}
            className={`rounded-sm px-3 py-1.5 text-xs font-medium transition-all ${
              subTab === st.id
                ? 'bg-violet-500/15 text-violet-300 border border-violet-500/30'
                : 'text-white/40 hover:text-white/60 hover:bg-white/5 border border-transparent'
            }`}
          >
            {st.label} {st.count !== null && <span className="text-white/20 ml-1">({st.count})</span>}
          </button>
        ))}
      </div>

      {/* Concepts sub-tab */}
      {subTab === 'concepts' && (
        <div className="flex flex-col gap-4">
          {/* Preferences */}
          {preferences.length > 0 && (
            <div className="rounded-sm border border-white/10 bg-white/[0.03] p-5">
              <div className="text-[10px] uppercase tracking-wider text-white/30 mb-3">🎨 Learned Preferences</div>
              <div className="flex flex-wrap gap-2">
                {preferences.map((p, i) => (
                  <span key={i} className="rounded-sm bg-violet-500/10 border border-violet-500/20 px-3 py-1.5 text-xs text-violet-300">
                    <span className="text-white/30 mr-1">{p.category || 'pref'}:</span>
                    {p.key || p.preference || JSON.stringify(p)}
                    {p.value && <span className="text-white/50 ml-1">= {p.value}</span>}
                    {p.confidence && <span className="text-white/20 ml-1">({(p.confidence * 100).toFixed(0)}%)</span>}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Concepts grid */}
          {concepts.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {concepts.map((c, i) => {
                const ct = conceptTypes[c.concept_type || c.type] || { icon: '🔹', color: 'text-white/60' }
                return (
                  <div key={i} className="rounded border border-white/8 bg-white/[0.03] p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">{ct.icon}</span>
                      <span className={`text-sm font-semibold ${ct.color}`}>
                        {c.name || c.concept_name || 'Unknown'}
                      </span>
                      {c.mention_count && (
                        <span className="ml-auto text-[10px] text-white/25 font-mono">
                          {c.mention_count}× mentioned
                        </span>
                      )}
                    </div>
                    {(c.aliases && c.aliases.length > 0) && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        {c.aliases.map((a: string, ai: number) => (
                          <span key={ai} className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-white/30">
                            {a}
                          </span>
                        ))}
                      </div>
                    )}
                    {c.description && (
                      <div className="text-xs text-white/40 line-clamp-2">{c.description}</div>
                    )}
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-[10px] text-white/20">{c.concept_type || c.type}</span>
                      {c.first_seen && (
                        <span className="text-[10px] text-white/15">
                          since {new Date(c.first_seen * 1000).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <span className="text-5xl opacity-40">🕸</span>
              <div className="mt-3 text-sm text-white/50">No concepts discovered yet</div>
              <div className="text-xs text-white/25 mt-1">Concepts are extracted from conversations over time</div>
            </div>
          )}
        </div>
      )}

      {/* Patterns sub-tab */}
      {subTab === 'patterns' && (
        <div className="flex flex-col gap-3">
          {patterns.length > 0 ? patterns.map((p, i) => (
            <div key={i} className="rounded border border-white/8 bg-white/[0.03] p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] uppercase text-white/30 font-medium">
                  {p.pattern_type || p.type || 'pattern'}
                </span>
                {p.confidence !== undefined && (
                  <div className="flex items-center gap-1 ml-auto">
                    <div className="w-16 h-1.5 rounded-full bg-white/5 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-violet-500/60"
                        style={{ width: `${(p.confidence || 0) * 100}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-white/30 font-mono">
                      {((p.confidence || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                )}
              </div>
              <div className="text-sm text-white/70">{p.description || p.pattern || JSON.stringify(p)}</div>
              {p.examples && (
                <div className="mt-2 text-xs text-white/30 italic">
                  e.g.: {Array.isArray(p.examples) ? p.examples.slice(0, 3).join(' · ') : p.examples}
                </div>
              )}
            </div>
          )) : (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <span className="text-5xl opacity-40">📈</span>
              <div className="mt-3 text-sm text-white/50">No behavioral patterns detected</div>
              <div className="text-xs text-white/25 mt-1">Patterns emerge from repeated interactions</div>
            </div>
          )}
        </div>
      )}

      {/* Active Learning sub-tab */}
      {subTab === 'learning' && (
        <div className="flex flex-col gap-4">
          {/* Interaction stats */}
          {interactionStats && (
            <div className="grid gap-3 sm:grid-cols-3">
              {Object.entries(interactionStats).filter(([k]) => k !== 'period_hours').map(([k, v]) => (
                <div key={k} className="rounded border border-white/10 bg-white/5 p-4">
                  <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1">{k.replace(/_/g, ' ')}</div>
                  <div className="text-xl font-bold text-white">{typeof v === 'number' ? v.toLocaleString() : String(v)}</div>
                </div>
              ))}
            </div>
          )}

          {/* Learning stats detail */}
          {learningStats && (
            <div className="rounded-sm border border-white/10 bg-white/[0.03] p-5">
              <div className="text-[10px] uppercase tracking-wider text-white/30 mb-3">🧠 Active Learning Stats</div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {Object.entries(learningStats).map(([k, v]) => (
                  <div key={k}>
                    <span className="text-[10px] text-white/25">{k.replace(/_/g, ' ')}</span>
                    <div className="text-sm font-mono text-white/70">
                      {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button
            onClick={handleRetrain}
            disabled={retraining}
            className="self-start rounded bg-violet-600 hover:bg-violet-500 disabled:opacity-40 px-5 py-2.5 text-sm font-medium text-white transition-all"
          >
            {retraining ? 'Retraining...' : '🔄 Trigger Model Retrain'}
          </button>
        </div>
      )}

      {/* Training Data sub-tab */}
      {subTab === 'training' && (
        <div className="flex flex-col gap-4">
          {trainingStats ? (
            <div className="rounded-sm border border-white/10 bg-white/[0.03] p-5">
              <div className="text-[10px] uppercase tracking-wider text-white/30 mb-3">📊 Training Data Collection</div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                {Object.entries(trainingStats).map(([k, v]) => (
                  <div key={k} className="flex flex-col">
                    <span className="text-[10px] text-white/30">{k.replace(/_/g, ' ')}</span>
                    <span className="text-lg font-bold text-white">
                      {typeof v === 'number' ? v.toLocaleString() : String(v)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <span className="text-5xl opacity-40">📊</span>
              <div className="mt-3 text-sm text-white/50">No training data available</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Self-Model Slots display
// ---------------------------------------------------------------------------

const SLOT_META: Record<string, { label: string; icon: string; description: string }> = {
  uncertainty_domains: { label: 'Uncertainty Domains', icon: '❓', description: 'Topics where mistakes are frequent' },
  correction_pattern:  { label: 'Correction Pattern',  icon: '↩', description: 'Pattern observed in user corrections' },
  trust_trajectory:    { label: 'Trust Trajectory',    icon: '📈', description: 'How trust has moved recently' },
  known_blindspots:    { label: 'Known Blindspots',    icon: '🕶', description: 'Structural weaknesses' },
  growing_confidence:  { label: 'Growing Confidence',  icon: '✦', description: 'Areas of consistent reinforcement' },
  user_relationship:   { label: 'User Relationship',   icon: '🤝', description: 'Character of the interaction style' },
  response_style:      { label: 'Response Style',      icon: '✏', description: 'Current response calibration' },
}

function SelfModelSlots({ slots }: { slots: SelfModelAwareness }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {Object.entries(SLOT_META).map(([key, meta]) => {
        const value = slots[key]
        return (
          <div key={key} className={`rounded border p-4 transition-all ${value ? 'border-white/12 bg-white/[0.04]' : 'border-white/5 bg-white/[0.01] opacity-50'}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-base">{meta.icon}</span>
              <span className="text-xs font-semibold text-white/70 uppercase tracking-wider">{meta.label}</span>
            </div>
            {value ? (
              <p className="text-sm text-white/80 leading-relaxed">{value}</p>
            ) : (
              <p className="text-xs text-white/25 italic">Not yet assessed</p>
            )}
            <p className="mt-2 text-[10px] text-white/25">{meta.description}</p>
          </div>
        )
      })}
    </div>
  )
}

function PersonalityTimeline({ checkpoints }: { checkpoints: PersonalityCheckpoint[] }) {
  const [expanded, setExpanded] = useState<number | null>(null)

  if (!checkpoints.length) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <span className="text-5xl opacity-30">◈</span>
        <div className="mt-3 text-sm text-white/40">No personality checkpoints yet</div>
        <div className="text-xs text-white/20 mt-1">Checkpoints are written by the heartbeat self-reflection loop</div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1">
        {checkpoints.length} checkpoint{checkpoints.length !== 1 ? 's' : ''} — newest first
      </div>
      {checkpoints.map((cp, i) => {
        const date = new Date(cp.ts * 1000)
        const hasSlots = cp.snapshot && Object.values(cp.snapshot).some(v => v)
        const deltaKeys = cp.delta ? Object.keys(cp.delta) : []
        const isExpanded = expanded === i

        return (
          <div key={cp.id} className="rounded border border-white/8 bg-white/[0.03] overflow-hidden">
            <div
              className="flex items-start gap-3 p-4 cursor-pointer hover:bg-white/[0.02] transition-colors"
              onClick={() => setExpanded(isExpanded ? null : i)}
            >
              <div className="flex-shrink-0 flex flex-col items-center gap-1 pt-0.5">
                <div className={`h-2.5 w-2.5 rounded-full ${i === 0 ? 'bg-violet-400' : 'bg-white/20'}`} />
                {i < checkpoints.length - 1 && <div className="w-px flex-1 bg-white/10 min-h-[16px]" />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-white/60">{date.toLocaleDateString()} {date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  {i === 0 && <span className="rounded-full bg-violet-500/20 border border-violet-500/30 px-2 py-0 text-[9px] text-violet-300">latest</span>}
                  {deltaKeys.length > 0 && (
                    <span className="text-[10px] text-amber-400/70">{deltaKeys.length} change{deltaKeys.length !== 1 ? 's' : ''}</span>
                  )}
                </div>
                {cp.notable_events.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {cp.notable_events.slice(0, 3).map((ev, ei) => (
                      <span key={ei} className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-white/40">{ev}</span>
                    ))}
                    {cp.notable_events.length > 3 && <span className="text-[10px] text-white/20">+{cp.notable_events.length - 3} more</span>}
                  </div>
                )}
                {!cp.notable_events.length && hasSlots && (
                  <div className="text-xs text-white/30 truncate">
                    {Object.entries(cp.snapshot).filter(([,v]) => v).slice(0, 2).map(([k,v]) => `${k}: ${String(v).slice(0, 40)}`).join(' · ')}
                  </div>
                )}
              </div>
              <span className="text-white/20 text-xs flex-shrink-0">{isExpanded ? '▲' : '▼'}</span>
            </div>

            <AnimatePresence>
              {isExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  className="overflow-hidden border-t border-white/5"
                >
                  <div className="p-4 space-y-4">
                    {deltaKeys.length > 0 && (
                      <div>
                        <div className="text-[10px] uppercase tracking-wider text-amber-400/60 mb-2">Changes from previous</div>
                        <div className="space-y-1.5">
                          {deltaKeys.map(k => (
                            <div key={k} className="rounded-sm bg-amber-500/5 border border-amber-500/15 px-3 py-2">
                              <div className="text-[10px] text-amber-400/70 mb-0.5">{SLOT_META[k]?.label || k}</div>
                              <div className="text-xs text-white/60">{String((cp.delta as any)[k])}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-white/25 mb-2">Snapshot</div>
                      <div className="grid gap-2 sm:grid-cols-2">
                        {Object.entries(cp.snapshot).filter(([,v]) => v).map(([k, v]) => (
                          <div key={k} className="rounded-sm bg-white/3 border border-white/5 px-3 py-2">
                            <div className="text-[10px] text-white/30 mb-0.5">{SLOT_META[k]?.label || k}</div>
                            <div className="text-xs text-white/60 line-clamp-3">{String(v)}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )
      })}
    </div>
  )
}

function PersonalityPanel({ threadId }: { threadId: string }) {
  const [slots, setSlots] = useState<SelfModelAwareness>({})
  const [checkpoints, setCheckpoints] = useState<PersonalityCheckpoint[]>([])
  const [traits, setTraits] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)
  const [reflecting, setReflecting] = useState(false)
  const [subTab, setSubTab] = useState<'current' | 'timeline' | 'traits'>('current')

  const load = useCallback(async () => {
    try {
      const [state, timeline] = await Promise.all([
        getSelfModelState(threadId).catch(() => null),
        getPersonalityTimeline(30).catch(() => [] as PersonalityCheckpoint[]),
      ])
      if (state) {
        setSlots(state.self_model_awareness || {})
        setTraits(state.traits || {})
      }
      setCheckpoints(timeline)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [threadId])

  const runReflection = useCallback(async () => {
    setReflecting(true)
    try {
      await runLoops({ thread_id: threadId, mode: 'all' })
      await load()
    } catch { /* ignore */ }
    finally { setReflecting(false) }
  }, [threadId, load])

  useEffect(() => { load() }, [load])

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-500" /></div>

  const subTabs = [
    { id: 'current' as const, label: 'Self-Awareness', icon: '◈' },
    { id: 'timeline' as const, label: 'Timeline', icon: '◷' },
    { id: 'traits' as const, label: 'Adaptive Traits', icon: '⟳' },
  ]

  const filledSlots = Object.values(slots).filter(Boolean).length

  return (
    <div className="flex flex-col gap-4">
      {/* Sub-tab header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          {subTabs.map(st => (
            <button
              key={st.id}
              onClick={() => setSubTab(st.id)}
              className={`rounded-sm px-3 py-1.5 text-xs font-medium transition-all ${
                subTab === st.id
                  ? 'bg-violet-500/15 text-violet-300 border border-violet-500/30'
                  : 'text-white/40 hover:text-white/60 hover:bg-white/5 border border-transparent'
              }`}
            >
              {st.icon} {st.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={runReflection}
            disabled={reflecting}
            className="flex items-center gap-1 rounded-sm border border-violet-500/20 bg-violet-500/5 px-2.5 py-1 text-xs text-violet-400 hover:bg-violet-500/10 disabled:opacity-40 transition-all"
          >
            {reflecting ? <span className="h-3 w-3 animate-spin rounded-full border border-violet-400/40 border-t-violet-400 inline-block" /> : '◈'}
            {reflecting ? 'reflecting…' : 'reflect now'}
          </button>
          <button onClick={load} className="text-xs text-white/30 hover:text-white/60 transition-colors">↻</button>
        </div>
      </div>

      {subTab === 'current' && (
        <div className="space-y-4">
          <div className="flex items-center gap-3 rounded border border-violet-500/20 bg-violet-500/5 px-4 py-3">
            <span className="text-2xl">◈</span>
            <div>
              <div className="text-sm font-medium text-violet-300">Self-Awareness Model</div>
              <div className="text-xs text-white/40">
                {filledSlots}/7 slots populated · updated by heartbeat reflection loop
              </div>
            </div>
            {filledSlots > 0 && (
              <div className="ml-auto flex items-center gap-1">
                {[...Array(7)].map((_, i) => (
                  <div key={i} className={`h-2 w-2 rounded-full ${i < filledSlots ? 'bg-violet-400' : 'bg-white/10'}`} />
                ))}
              </div>
            )}
          </div>
          <SelfModelSlots slots={slots} />
        </div>
      )}

      {subTab === 'timeline' && (
        <PersonalityTimeline checkpoints={checkpoints} />
      )}

      {subTab === 'traits' && (
        <div className="space-y-4">
          <div className="text-xs text-white/30">Adaptive traits inferred from conversation style — updated per-thread automatically.</div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(traits).filter(([,v]) => v != null).map(([key, value]) => (
              <div key={key} className="rounded border border-white/8 bg-white/[0.03] p-4">
                <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1">{key.replace(/_/g, ' ')}</div>
                <div className="text-sm font-medium text-white/80">
                  {typeof value === 'number' ? value.toFixed(3) : String(value)}
                </div>
              </div>
            ))}
            {Object.keys(traits).filter(k => traits[k] != null).length === 0 && (
              <div className="col-span-3 flex flex-col items-center justify-center py-12 text-center">
                <span className="text-4xl opacity-30">⟳</span>
                <div className="mt-3 text-sm text-white/40">No traits calibrated yet</div>
                <div className="text-xs text-white/20 mt-1">Traits adapt from conversation patterns over time</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Epistemic Timeline Panel
// ---------------------------------------------------------------------------

const EVENT_STYLES: Record<string, { dot: string; badge: string }> = {
  gate_fail:             { dot: 'bg-red-500',     badge: 'bg-red-500/15 text-red-400 border-red-500/30' },
  gate_pass:             { dot: 'bg-emerald-500', badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
  feedback_up:           { dot: 'bg-emerald-400', badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  feedback_down:         { dot: 'bg-amber-500',   badge: 'bg-amber-500/15 text-amber-400 border-amber-500/30' },
  trust_delta_batch:     { dot: 'bg-violet-500',  badge: 'bg-violet-500/15 text-violet-400 border-violet-500/30' },
  contradiction_open:    { dot: 'bg-orange-500',  badge: 'bg-orange-500/15 text-orange-400 border-orange-500/30' },
  contradiction_resolved:{ dot: 'bg-sky-500',     badge: 'bg-sky-500/15 text-sky-400 border-sky-500/30' },
  memory_stored:         { dot: 'bg-teal-500',    badge: 'bg-teal-500/15 text-teal-400 border-teal-500/30' },
  reflection_run:        { dot: 'bg-purple-500',  badge: 'bg-purple-500/15 text-purple-400 border-purple-500/30' },
}

function eventStyle(type: string) {
  return EVENT_STYLES[type] || { dot: 'bg-white/30', badge: 'bg-white/10 text-white/50 border-white/20' }
}

function EpistemicEventCard({ ev, expanded, onToggle }: {
  ev: EpistemicEvent
  expanded: boolean
  onToggle: () => void
}) {
  const style = eventStyle(ev.event_type)
  const ts = new Date(ev.ts * 1000)
  const timeStr = ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  const dateStr = ts.toLocaleDateString([], { month: 'short', day: 'numeric' })

  // Extract human-readable detail from payload
  const detail = ev.payload.gate_reason as string
    || ev.payload.category as string
    || ev.payload.reason as string
    || ev.payload.summary as string
    || (ev.payload.mean_delta != null ? `Δ ${(ev.payload.mean_delta as number).toFixed(3)} across ${ev.payload.count} memories` : null)
    || null

  return (
    <div
      className="group cursor-pointer rounded border border-white/8 bg-white/[0.02] px-4 py-3 hover:border-white/15 hover:bg-white/[0.04] transition-all"
      onClick={onToggle}
    >
      <div className="flex items-center gap-3">
        <div className={`h-2 w-2 flex-shrink-0 rounded-full ${style.dot}`} />
        <span className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-[10px] font-semibold ${style.badge}`}>
          {ev.label}
        </span>
        {detail && (
          <span className="text-xs text-white/40 truncate flex-1">{detail}</span>
        )}
        <span className="ml-auto text-[10px] text-white/20 flex-shrink-0">
          {dateStr} {timeStr}
        </span>
        <span className="text-[10px] text-white/20 group-hover:text-white/40 transition-colors">
          {expanded ? '▲' : '▼'}
        </span>
      </div>
      {expanded && (
        <div className="mt-3 pl-5 space-y-2">
          {ev.memory_ids.length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-white/25 mb-1">Memory IDs</div>
              <div className="flex flex-wrap gap-1">
                {ev.memory_ids.map(id => (
                  <span key={id} className="font-mono text-[9px] bg-white/5 border border-white/10 rounded px-1.5 py-0.5 text-white/40">
                    {id}
                  </span>
                ))}
              </div>
            </div>
          )}
          {Object.keys(ev.payload).length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-white/25 mb-1">Payload</div>
              <pre className="text-[10px] text-white/40 bg-white/[0.03] rounded-sm p-2 overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(ev.payload, null, 2)}
              </pre>
            </div>
          )}
          {ev.interaction_id && (
            <div className="text-[10px] text-white/20 font-mono">interaction: {ev.interaction_id}</div>
          )}
        </div>
      )}
    </div>
  )
}

const EVENT_FILTER_OPTIONS = [
  { value: '', label: 'All events' },
  { value: 'gate_fail', label: 'Gate failures' },
  { value: 'gate_pass', label: 'Gate passes' },
  { value: 'feedback_up', label: 'Positive feedback' },
  { value: 'feedback_down', label: 'Negative feedback' },
  { value: 'trust_delta_batch', label: 'Trust updates' },
  { value: 'contradiction_open', label: 'Contradictions' },
  { value: 'memory_stored', label: 'Memory stored' },
]

function EpistemicTimelinePanel({ threadId }: { threadId: string }) {
  const [events, setEvents] = useState<EpistemicEvent[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [offset, setOffset] = useState(0)
  const limit = 50

  const load = useCallback(async (off = 0, ev = filter) => {
    setLoading(true)
    try {
      const res = await getEpistemicTimeline(threadId, {
        limit,
        offset: off,
        eventType: ev || undefined,
      })
      setEvents(res.events)
      setTotal(res.total)
      setOffset(off)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [threadId, filter])

  useEffect(() => { load(0, filter) }, [threadId, filter])

  const handleFilter = (v: string) => {
    setFilter(v)
    setExpandedId(null)
  }

  if (loading && !events.length) {
    return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-500" /></div>
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="text-[10px] uppercase tracking-wider text-white/30">
          {total} event{total !== 1 ? 's' : ''} · thread {threadId.slice(0, 16)}{threadId.length > 16 ? '…' : ''}
        </div>
        <select
          value={filter}
          onChange={e => handleFilter(e.target.value)}
          className="ml-auto rounded-sm border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white outline-none cursor-pointer"
        >
          {EVENT_FILTER_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <button
          onClick={() => load(offset, filter)}
          className="rounded-sm border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/60 hover:text-white hover:bg-white/10 transition-all"
        >
          ↻
        </button>
      </div>

      {events.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <span className="text-5xl opacity-30">◎</span>
          <div className="mt-3 text-sm text-white/40">No events recorded yet</div>
          <div className="text-xs text-white/20 mt-1">Events appear as interactions happen in this thread</div>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-1.5">
            {events.map(ev => (
              <EpistemicEventCard
                key={ev.id}
                ev={ev}
                expanded={expandedId === ev.id}
                onToggle={() => setExpandedId(expandedId === ev.id ? null : ev.id)}
              />
            ))}
          </div>

          {(offset > 0 || total > offset + limit) && (
            <div className="flex items-center justify-center gap-4 pt-2">
              <button
                onClick={() => load(Math.max(0, offset - limit))}
                disabled={offset === 0}
                className="rounded-sm border border-white/10 bg-white/5 px-4 py-1.5 text-xs text-white/60 hover:text-white disabled:opacity-30 transition-all"
              >
                ← Newer
              </button>
              <span className="text-[10px] text-white/30">
                {offset + 1}–{Math.min(offset + limit, total)} of {total}
              </span>
              <button
                onClick={() => load(offset + limit)}
                disabled={offset + limit >= total}
                className="rounded-sm border border-white/10 bg-white/5 px-4 py-1.5 text-xs text-white/60 hover:text-white disabled:opacity-30 transition-all"
              >
                Older →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Stat Card + Trust Bar
// ---------------------------------------------------------------------------

function StatCard({ label, value, sub, accent }: {
  label: string; value: string | number; sub?: string; accent?: string
}) {
  return (
    <div className="flex flex-col gap-1 rounded-sm border border-white/10 bg-white/5 p-4">
      <div className="text-xs font-medium uppercase tracking-wider text-white/40">{label}</div>
      <div className={`text-2xl font-bold ${accent || 'text-white'}`}>{value}</div>
      {sub && <div className="text-xs text-white/40">{sub}</div>}
    </div>
  )
}

function TrustBar({ distribution }: { distribution: Record<string, number> }) {
  const total = Object.values(distribution).reduce((a, b) => a + b, 0)
  if (total === 0) return null
  const segments = [
    { key: 'very_high (0.8-1.0)', color: 'bg-emerald-500', label: 'Very High' },
    { key: 'high (0.6-0.8)', color: 'bg-emerald-400', label: 'High' },
    { key: 'medium (0.3-0.6)', color: 'bg-amber-400', label: 'Medium' },
    { key: 'low (0-0.3)', color: 'bg-red-400', label: 'Low' },
  ]
  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-white/5">
        {segments.map(seg => {
          const count = distribution[seg.key] || 0
          const pct = total > 0 ? (count / total) * 100 : 0
          if (pct === 0) return null
          return (
            <div key={seg.key} className={`${seg.color} transition-all duration-500`} style={{ width: `${pct}%` }} title={`${seg.label}: ${count}`} />
          )
        })}
      </div>
      <div className="flex flex-wrap gap-3 text-xs text-white/50">
        {segments.map(seg => {
          const count = distribution[seg.key] || 0
          if (count === 0) return null
          return (
            <span key={seg.key} className="flex items-center gap-1">
              <span className={`inline-block h-2 w-2 rounded-full ${seg.color}`} />
              {seg.label}: {count}
            </span>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Memory Card
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// MemoryTrustSparkline
// ---------------------------------------------------------------------------

function MemoryTrustSparkline({ memoryId, threadId, currentTrust }: {
  memoryId: string
  threadId: string
  currentTrust: number
}) {
  const [rows, setRows] = useState<import('../lib/api').TrustHistoryRow[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    getMemoryTrustHistory(threadId, memoryId).then(h => {
      if (!cancelled) { setRows(h); setLoaded(true) }
    }).catch(() => setLoaded(true))
    return () => { cancelled = true }
  }, [memoryId, threadId])

  if (!loaded) return <div className="h-8 flex items-center"><span className="text-[10px] text-white/20">loading…</span></div>

  // Always show at least the current trust as a single point
  const points = rows.length > 0
    ? rows.map(r => r.new_trust as number)
    : [currentTrust]

  const W = 120, H = 32, PAD = 2
  const min = Math.min(...points, 0)
  const max = Math.max(...points, 1)
  const range = max - min || 1
  const xs = points.map((_, i) => PAD + (i / Math.max(points.length - 1, 1)) * (W - PAD * 2))
  const ys = points.map(v => H - PAD - ((v - min) / range) * (H - PAD * 2))
  const polyline = xs.map((x, i) => `${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' ')
  const last = points[points.length - 1]
  const trend = points.length > 1 ? last - points[0] : 0
  const lineColor = last >= 0.7 ? '#34d399' : last >= 0.4 ? '#fbbf24' : '#f87171'

  return (
    <div className="flex items-center gap-3">
      <svg width={W} height={H} className="flex-shrink-0 rounded">
        <polyline
          points={polyline}
          fill="none"
          stroke={lineColor}
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          opacity="0.8"
        />
        {/* Current value dot */}
        <circle
          cx={xs[xs.length - 1].toFixed(1)}
          cy={ys[ys.length - 1].toFixed(1)}
          r="2.5"
          fill={lineColor}
        />
      </svg>
      <div className="text-[10px] text-white/30 leading-tight">
        {points.length > 1
          ? <span className={trend > 0.01 ? 'text-emerald-400' : trend < -0.01 ? 'text-red-400' : 'text-white/30'}>
              {trend > 0 ? '↑' : trend < 0 ? '↓' : '→'} {Math.abs(trend * 100).toFixed(0)}% over {points.length} events
            </span>
          : <span>no history yet</span>
        }
      </div>
    </div>
  )
}

function MemoryCard({ memory, expanded, onToggle, onDelete, onCorrect, threadId }: {
  memory: CopilotMemory
  expanded: boolean
  onToggle: () => void
  onDelete: (id: string) => void
  onCorrect: (id: string, text: string) => void
  threadId?: string
}) {
  const src = sourceBadge(memory.source)
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(memory.text)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="group rounded border border-white/8 bg-white/[0.03] hover:bg-white/[0.06] transition-all"
    >
      <div className="flex items-start gap-3 p-4 cursor-pointer" onClick={onToggle}>
        <div className={`mt-0.5 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-sm border ${trustBg(memory.trust)}`}>
          <span className={`text-sm font-bold ${trustColor(memory.trust)}`}>
            {(memory.trust * 100).toFixed(0)}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-[10px] font-medium ${src.className}`}>
              {src.label}
            </span>
            <span className="text-[10px] text-white/30 font-mono">{memory.namespace}</span>
            <span className="text-[10px] rounded-sm px-1.5 py-0 text-white/20" style={{ backgroundColor: (CATEGORY_COLORS[categorize(memory.text)] || '#888') + '20' }}>
              {CATEGORY_ICONS[categorize(memory.text)]} {categorize(memory.text)}
            </span>
            <span className="ml-auto text-[10px] text-white/30">{timeAgo(memory.timestamp)}</span>
          </div>
          <p className="text-sm text-white/80 leading-relaxed">{memory.text}</p>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-white/5"
          >
            <div className="p-4">
              <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4 mb-3">
                <div>
                  <span className="text-white/30">ID</span>
                  <div className="mt-0.5 font-mono text-white/50 break-all text-[10px]">{memory.id}</div>
                </div>
                <div>
                  <span className="text-white/30">Thread</span>
                  <div className="mt-0.5 font-mono text-white/50">{memory.thread_id}</div>
                </div>
                <div>
                  <span className="text-white/30">Trust</span>
                  <div className={`mt-0.5 font-mono font-bold ${trustColor(memory.trust)}`}>{memory.trust.toFixed(2)}</div>
                </div>
                <div>
                  <span className="text-white/30">Stored</span>
                  <div className="mt-0.5 text-white/50 text-[11px]">
                    {memory.created_at || new Date(memory.timestamp * 1000).toLocaleString()}
                  </div>
                </div>
              </div>

              {/* Trust sparkline */}
              <div className="mb-3">
                <div className="text-[10px] text-white/30 uppercase tracking-wider mb-1.5">Trust trajectory</div>
                <MemoryTrustSparkline
                  memoryId={memory.id}
                  threadId={threadId ?? memory.thread_id ?? 'default'}
                  currentTrust={memory.trust}
                />
              </div>

              {editing ? (
                <div className="flex gap-2 mt-2">
                  <input
                    type="text"
                    value={editText}
                    onChange={e => setEditText(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') { onCorrect(memory.id, editText); setEditing(false) }
                      if (e.key === 'Escape') setEditing(false)
                    }}
                    className="flex-1 rounded-sm border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white outline-none focus:border-violet-500/50"
                    autoFocus
                  />
                  <button onClick={() => { onCorrect(memory.id, editText); setEditing(false) }} className="rounded-sm bg-violet-600 px-3 py-1.5 text-xs text-white">Save</button>
                  <button onClick={() => setEditing(false)} className="rounded-sm bg-white/10 px-3 py-1.5 text-xs text-white/50">Cancel</button>
                </div>
              ) : (
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={(e) => { e.stopPropagation(); setEditing(true); setEditText(memory.text) }}
                    className="rounded-sm bg-white/5 border border-white/10 px-3 py-1.5 text-xs text-white/50 hover:text-white hover:bg-white/10 transition-all"
                  >
                    ✏️ Correct
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(memory.id) }}
                    className="rounded-sm bg-red-500/10 border border-red-500/20 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/20 transition-all"
                  >
                    🗑 Delete
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

type SortOrder = 'newest' | 'oldest' | 'trust_high' | 'trust_low'
type Tab = 'memories' | 'profile' | 'graph' | 'accuracy' | 'factchecks' | 'trust' | 'sessions' | 'insights' | 'personality' | 'activity'

const isLocalhost = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname)

export function CopilotPage({ threadId = 'default' }: { threadId?: string }) {
  const [data, setData] = useState<CopilotMemoriesResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [profile, setProfile] = useState<CopilotProfile | null>(null)
  const [accuracy, setAccuracy] = useState<AccuracyStats | null>(null)

  const [nsFilter, setNsFilter] = useState<string>('')
  const [sourceFilter, setSourceFilter] = useState<string>('')
  const [searchQ, setSearchQ] = useState<string>('')
  const [sortOrder, setSortOrder] = useState<SortOrder>('newest')

  const [live, setLive] = useState(true)
  // POLLING FIX: copilot memory poll raised from 2s to 5s
  const [pollInterval] = useState(5000)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())
  const [newCount, setNewCount] = useState(0)
  const prevTotalRef = useRef<number>(0)
  const prevIdsRef = useRef<Set<string>>(new Set())

  const [toasts, setToasts] = useState<Toast[]>([])
  const toastTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('memories')

  const addToast = useCallback((memory: CopilotMemory) => {
    const t: Toast = { id: memory.id, text: memory.text, source: memory.source, ts: memory.timestamp }
    setToasts(prev => [...prev.slice(-4), t])
    const timer = setTimeout(() => {
      setToasts(prev => prev.filter(x => x.id !== t.id))
      toastTimers.current.delete(t.id)
    }, 6000)
    toastTimers.current.set(t.id, timer)
  }, [])

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(x => x.id !== id))
    const timer = toastTimers.current.get(id)
    if (timer) { clearTimeout(timer); toastTimers.current.delete(id) }
  }, [])

  const fetchData = useCallback(async () => {
    try {
      const resp = await getCopilotMemories({
        namespace: nsFilter || undefined,
        source: sourceFilter || undefined,
        search: searchQ || undefined,
        sort: sortOrder,
        limit: 200,
      })
      setData(resp)
      setError(null)
      setLastRefresh(new Date())

      const currentIds = new Set(resp.memories.map(m => m.id))
      if (prevIdsRef.current.size > 0) {
        for (const m of resp.memories) {
          if (!prevIdsRef.current.has(m.id)) {
            addToast(m)
          }
        }
      }
      prevIdsRef.current = currentIds

      if (prevTotalRef.current > 0 && resp.stats.total_memories > prevTotalRef.current) {
        setNewCount(prev => prev + (resp.stats.total_memories - prevTotalRef.current))
      }
      prevTotalRef.current = resp.stats.total_memories
    } catch (e: any) {
      setError(e.message || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }, [nsFilter, sourceFilter, searchQ, sortOrder, addToast])

  const fetchSideData = useCallback(async () => {
    try {
      const [p, a] = await Promise.all([getCopilotProfile(), getCopilotAccuracy()])
      setProfile(p)
      setAccuracy(a)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    setLoading(true)
    fetchData()
    fetchSideData()
  }, [fetchData, fetchSideData])

  useEffect(() => {
    if (live) {
      intervalRef.current = setInterval(() => {
        fetchData()
        fetchSideData()
      }, pollInterval)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [live, pollInterval, fetchData, fetchSideData])

  const handleDelete = async (id: string) => {
    try {
      await deleteCopilotMemory(id)
      fetchData()
      fetchSideData()
    } catch { /* ignore */ }
  }

  const handleCorrect = async (id: string, text: string) => {
    try {
      await correctCopilotMemory(id, text)
      fetchData()
      fetchSideData()
    } catch { /* ignore */ }
  }

  const stats = data?.stats
  const memories = data?.memories || []

  const tabItems: Array<{ id: Tab; label: string; icon: string }> = [
    { id: 'memories', label: 'Memories', icon: '🧠' },
    { id: 'profile', label: 'Profile', icon: '👤' },
    { id: 'graph', label: 'Graph', icon: '🕸' },
    { id: 'accuracy', label: 'Accuracy', icon: '📊' },
    { id: 'factchecks', label: 'Fact Checks', icon: '🔍' },
    { id: 'trust', label: 'Trust & Decay', icon: '⚖️' },
    { id: 'sessions', label: 'Sessions', icon: '📂' },
    { id: 'personality' as const, label: 'Personality', icon: '◈' },
    { id: 'activity' as const, label: 'Activity', icon: '⟳' },
    { id: 'insights' as const, label: 'CRT Insights', icon: '💡' },
  ]

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <ToastStack toasts={toasts} onDismiss={dismissToast} />

      <div className="flex flex-col gap-4 border-b border-white/10 p-4 sm:p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white font-display">Aether</h1>
            <p className="mt-0.5 text-xs text-white/40">
              Epistemic state — memory, trust, personality, and what the system knows about itself
            </p>
          </div>

          <div className="flex items-center gap-3">
            {newCount > 0 && (
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="rounded-full bg-violet-500/20 border border-violet-500/40 px-2 py-0.5 text-xs text-violet-300"
              >
                +{newCount} new
              </motion.span>
            )}
            <div className="flex items-center gap-2 rounded border border-white/10 bg-white/5 px-3 py-1.5">
              <button onClick={() => setLive(v => !v)} className="flex items-center gap-1.5 text-xs">
                <span className={`inline-block h-2 w-2 rounded-full ${live ? 'bg-emerald-400 animate-pulse' : 'bg-white/20'}`} />
                <span className={live ? 'text-emerald-400' : 'text-white/40'}>{live ? 'Live' : 'Paused'}</span>
              </button>
              <span className="mx-1 h-4 w-px bg-white/10" />
              <button onClick={() => { setLoading(true); fetchData(); fetchSideData() }} className="text-xs text-white/40 hover:text-white transition-colors" title="Refresh now">↻</button>
            </div>
            <span className="text-[10px] text-white/20">{lastRefresh.toLocaleTimeString()}</span>
          </div>
        </div>

        {stats && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            <StatCard label="Total" value={stats.total_memories} accent="text-white" />
            <StatCard label="Auto-learned" value={stats.auto_learned_count}
              sub={stats.total_memories > 0 ? `${Math.round((stats.auto_learned_count / stats.total_memories) * 100)}%` : undefined}
              accent="text-violet-400" />
            <StatCard label="Explicit" value={stats.explicit_count} accent="text-sky-400" />
            <StatCard label="Namespaces" value={stats.namespaces.length} sub={stats.namespaces.slice(0, 3).join(', ')} />
            <StatCard label="Accuracy" value={accuracy ? `${Math.round(accuracy.accuracy_rate * 100)}%` : '—'} accent="text-emerald-400" />
            <div className="col-span-2 sm:col-span-4 lg:col-span-1">
              <div className="flex flex-col gap-1 rounded-sm border border-white/10 bg-white/5 p-4">
                <div className="text-xs font-medium uppercase tracking-wider text-white/40">Trust</div>
                <div className="mt-1"><TrustBar distribution={stats.trust_distribution} /></div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-1 border-b border-white/5 px-4 py-2 sm:px-6">
        {tabItems.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`rounded-sm px-3 py-1.5 text-xs font-medium transition-all ${
              tab === t.id
                ? 'bg-violet-500/15 text-violet-300 border border-violet-500/30'
                : 'text-white/40 hover:text-white/60 hover:bg-white/5 border border-transparent'
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">
        {tab === 'memories' && (
          <div className="flex flex-col gap-0">
            <div className="flex flex-wrap items-center gap-2 border-b border-white/5 px-4 py-3 sm:px-6">
              <input type="text" placeholder="Search..." value={searchQ} onChange={e => setSearchQ(e.target.value)}
                className="rounded-sm border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white placeholder-white/30 outline-none focus:border-violet-500/50 w-40" />
              <select value={nsFilter} onChange={e => setNsFilter(e.target.value)}
                className="rounded-sm border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white outline-none cursor-pointer">
                <option value="">All NS</option>
                {(stats?.namespaces || []).map(ns => <option key={ns} value={ns}>{ns}</option>)}
              </select>
              <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}
                className="rounded-sm border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white outline-none cursor-pointer">
                <option value="">All Sources</option>
                <option value="inferred">⚡ Auto</option>
                <option value="user">👤 Explicit</option>
                <option value="document">📄 Doc</option>
                <option value="code">💻 Code</option>
              </select>
              <select value={sortOrder} onChange={e => setSortOrder(e.target.value as SortOrder)}
                className="rounded-sm border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white outline-none cursor-pointer">
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
                <option value="trust_high">High trust</option>
                <option value="trust_low">Low trust</option>
              </select>
              <span className="ml-auto text-xs text-white/30">{data ? `${data.total} memories` : '...'}</span>
            </div>

            <div className="px-4 py-3 sm:px-6">
              <TeachForm onTaught={() => { fetchData(); fetchSideData() }} threadId={threadId} />
            </div>

            <div className="px-4 py-2 sm:px-6">
              {loading && !data ? (
                <div className="flex items-center justify-center py-20">
                  <div className="flex flex-col items-center gap-3">
                    <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-500" />
                    <span className="text-sm text-white/40">Loading...</span>
                  </div>
                </div>
              ) : error ? (
                <div className="flex items-center justify-center py-20">
                  <div className="rounded-sm border border-red-500/20 bg-red-500/5 p-8 text-center">
                    <span className="text-4xl">⚠️</span>
                    <div className="mt-2 text-sm text-red-400">{error}</div>
                    <button onClick={() => { setLoading(true); fetchData() }} className="mt-3 rounded-sm bg-white/10 px-4 py-2 text-xs text-white">Retry</button>
                  </div>
                </div>
              ) : memories.length === 0 ? (
                <div className="flex items-center justify-center py-16 text-center">
                  <div>
                    <span className="text-5xl opacity-40">🧠</span>
                    <div className="mt-2 text-sm text-white/40">No memories yet</div>
                    <div className="text-xs text-white/20 max-w-sm mt-1">Use the Teach form above or chat to get started</div>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  <AnimatePresence mode="popLayout">
                    {memories.map(m => (
                      <MemoryCard
                        key={m.id}
                        memory={m}
                        expanded={expandedId === m.id}
                        onToggle={() => setExpandedId(expandedId === m.id ? null : m.id)}
                        onDelete={handleDelete}
                        onCorrect={handleCorrect}
                        threadId={threadId}
                      />
                    ))}
                  </AnimatePresence>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === 'profile' && (
          <div className="grid gap-4 p-4 sm:p-6 lg:grid-cols-2">
            <ProfileCard profile={profile} />
            <TeachForm onTaught={() => { fetchData(); fetchSideData() }} />
          </div>
        )}

        {tab === 'graph' && (
          <div className="p-4 sm:p-6">
            <MemoryGraph memories={memories} />
          </div>
        )}

        {tab === 'accuracy' && (
          <div className="p-4 sm:p-6">
            <AccuracyTracker accuracy={accuracy} />
          </div>
        )}

        {tab === 'factchecks' && (
          <div className="p-4 sm:p-6">
            <FactChecksPanel />
          </div>
        )}

        {tab === 'trust' && (
          <div className="p-4 sm:p-6">
            <TrustDecayPanel memories={memories} onRefresh={() => { fetchData(); fetchSideData() }} />
          </div>
        )}

        {tab === 'sessions' && (
          <div className="p-4 sm:p-6">
            <SessionsPanel />
          </div>
        )}

        {tab === 'personality' && (
          <div className="p-4 sm:p-6">
            <PersonalityPanel threadId={threadId} />
          </div>
        )}

        {tab === 'activity' && (
          <div className="p-4 sm:p-6">
            <EpistemicTimelinePanel threadId={threadId} />
          </div>
        )}

        {tab === 'insights' && (
          <div className="p-4 sm:p-6">
            <CrtInsightsPanel />
          </div>
        )}
      </div>
    </div>
  )
}
