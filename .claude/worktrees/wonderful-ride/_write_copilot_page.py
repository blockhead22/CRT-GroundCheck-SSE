# -*- coding: utf-8 -*-
"""Write CopilotPage.tsx with proper emojis"""
import pathlib

p = pathlib.Path(r'd:\AI_round2\frontend\src\pages\CopilotPage.tsx')

# Use actual Unicode chars directly
brain = '\U0001F9E0'    # brain
bust = '\U0001F464'     # bust
doc = '\U0001F4C4'      # document
laptop = '\U0001F4BB'   # laptop
case_ = '\U0001F4BC'    # briefcase
palette = '\U0001F3A8'  # palette
clip = '\U0001F4CB'     # clipboard
pin = '\U0001F4CC'      # pushpin
chart = '\U0001F4CA'    # chart
web = '\U0001F578'      # spider web
trash = '\U0001F5D1'    # trash
zap = '\u26A1'          # lightning
star = '\u2B50'         # star
pencil = '\u270F\uFE0F' # pencil
warn = '\u26A0\uFE0F'   # warning
check = '\u2713'        # check
dash = '\u2014'         # em dash
reload_ = '\u21BB'      # reload
dot = '\u00B7'          # middle dot

content = f"""import {{ useCallback, useEffect, useRef, useState }} from 'react'
import {{ motion, AnimatePresence }} from 'framer-motion'
import {{
  getCopilotMemories,
  getCopilotProfile,
  getCopilotAccuracy,
  teachCopilot,
  deleteCopilotMemory,
  correctCopilotMemory,
  type CopilotMemory,
  type CopilotStats,
  type CopilotMemoriesResponse,
  type CopilotProfile,
  type AccuracyStats,
}} from '../lib/api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(ts: number): string {{
  const diff = Math.floor(Date.now() / 1000) - ts
  if (diff < 60) return `${{diff}}s ago`
  if (diff < 3600) return `${{Math.floor(diff / 60)}}m ago`
  if (diff < 86400) return `${{Math.floor(diff / 3600)}}h ago`
  if (diff < 604800) return `${{Math.floor(diff / 86400)}}d ago`
  return new Date(ts * 1000).toLocaleDateString()
}}

function trustColor(trust: number): string {{
  if (trust >= 0.7) return 'text-emerald-400'
  if (trust >= 0.4) return 'text-amber-400'
  return 'text-red-400'
}}

function trustBg(trust: number): string {{
  if (trust >= 0.7) return 'bg-emerald-500/20 border-emerald-500/40'
  if (trust >= 0.4) return 'bg-amber-500/20 border-amber-500/40'
  return 'bg-red-500/20 border-red-500/40'
}}

function sourceBadge(source: string): {{ label: string; className: string }} {{
  switch (source) {{
    case 'inferred':
      return {{ label: '{zap} Auto', className: 'bg-violet-500/20 text-violet-300 border-violet-500/30' }}
    case 'user':
      return {{ label: '{bust} You', className: 'bg-sky-500/20 text-sky-300 border-sky-500/30' }}
    case 'document':
      return {{ label: '{doc} Doc', className: 'bg-teal-500/20 text-teal-300 border-teal-500/30' }}
    case 'code':
      return {{ label: '{laptop} Code', className: 'bg-orange-500/20 text-orange-300 border-orange-500/30' }}
    default:
      return {{ label: source, className: 'bg-white/10 text-white/60 border-white/20' }}
  }}
}}

function categorize(text: string): string {{
  const t = text.toLowerCase()
  if (t.includes('name is')) return 'identity'
  if (t.includes('freelanc') || t.includes('work') || t.includes('employ') || t.includes('job')) return 'career'
  if (t.includes('favorite')) return 'favorites'
  if (t.includes('language') || t.includes('code in') || t.includes('python') || t.includes('typescript')) return 'tech'
  if (t.includes('prefer') || t.includes('style') || t.includes('like') || t.includes('love')) return 'preferences'
  if (t.includes('doc') || t.includes('test')) return 'workflow'
  return 'other'
}}

const CATEGORY_COLORS: Record<string, string> = {{
  identity: '#60a5fa',
  career: '#f59e0b',
  favorites: '#f472b6',
  tech: '#34d399',
  preferences: '#a78bfa',
  workflow: '#fb923c',
  other: '#94a3b8',
}}

const CATEGORY_ICONS: Record<string, string> = {{
  identity: '{bust}',
  career: '{case_}',
  favorites: '{star}',
  tech: '{laptop}',
  preferences: '{palette}',
  workflow: '{clip}',
  other: '{pin}',
}}

// ---------------------------------------------------------------------------
// Toast component
// ---------------------------------------------------------------------------

type Toast = {{ id: string; text: string; source: string; ts: number }}

function ToastStack({{ toasts, onDismiss }}: {{ toasts: Toast[]; onDismiss: (id: string) => void }}) {{
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      <AnimatePresence>
        {{toasts.map(t => (
          <motion.div
            key={{t.id}}
            initial={{{{ opacity: 0, x: 80, scale: 0.9 }}}}
            animate={{{{ opacity: 1, x: 0, scale: 1 }}}}
            exit={{{{ opacity: 0, x: 80, scale: 0.9 }}}}
            className="flex items-start gap-3 rounded-xl border border-violet-500/30 bg-[#1a1a2e]/95 backdrop-blur-xl p-3 shadow-2xl shadow-violet-500/10 cursor-pointer"
            onClick={{() => onDismiss(t.id)}}
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/20">
              <span className="text-sm">{brain}</span>
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[10px] uppercase tracking-wider text-violet-400 font-medium">
                Copilot learned
              </div>
              <div className="text-sm text-white/80 mt-0.5 leading-snug">{{t.text}}</div>
              <div className="mt-1 flex items-center gap-2">
                <span className={{`inline-flex items-center rounded-md border px-1.5 py-0 text-[9px] ${{sourceBadge(t.source).className}}`}}>
                  {{sourceBadge(t.source).label}}
                </span>
                <span className="text-[9px] text-white/20">{{timeAgo(t.ts)}}</span>
              </div>
            </div>
          </motion.div>
        ))}}
      </AnimatePresence>
    </div>
  )
}}

// ---------------------------------------------------------------------------
// Profile Card
// ---------------------------------------------------------------------------

function ProfileCard({{ profile }}: {{ profile: CopilotProfile | null }}) {{
  if (!profile) return null
  return (
    <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-violet-500/5 to-sky-500/5 p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-500/20 text-2xl">
          {brain}
        </div>
        <div>
          <div className="text-lg font-bold text-white">{{profile.name || 'Unknown'}}</div>
          <div className="text-xs text-white/40">
            {{profile.role || 'Role unknown'}}{{profile.employer ? ` {dot} ${{profile.employer}}` : ''}}
          </div>
        </div>
      </div>

      {{profile.languages.length > 0 && (
        <div className="mb-3">
          <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1.5">Languages</div>
          <div className="flex flex-wrap gap-1.5">
            {{profile.languages.map(l => (
              <span key={{l}} className="rounded-md bg-emerald-500/15 border border-emerald-500/25 px-2 py-0.5 text-xs text-emerald-300">
                {{l}}
              </span>
            ))}}
          </div>
        </div>
      )}}

      {{Object.keys(profile.preferences).length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1.5">Preferences</div>
          <div className="flex flex-col gap-1">
            {{Object.entries(profile.preferences).map(([k, v]) => (
              <div key={{k}} className="flex items-center gap-2 text-xs">
                <span className="text-white/30">{{k.replace(/_/g, ' ')}}:</span>
                <span className="text-white/70">{{v}}</span>
              </div>
            ))}}
          </div>
        </div>
      )}}

      {{profile.all_facts.length > 0 && (
        <div className="mt-3">
          <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1.5">All facts</div>
          <ul className="flex flex-col gap-0.5">
            {{profile.all_facts.map((f, i) => (
              <li key={{i}} className="text-xs text-white/50 pl-2 border-l border-white/10">{{f}}</li>
            ))}}
          </ul>
        </div>
      )}}
    </div>
  )
}}

// ---------------------------------------------------------------------------
// Teach Form
// ---------------------------------------------------------------------------

function TeachForm({{ onTaught }}: {{ onTaught: () => void }}) {{
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [success, setSuccess] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const presets = [
    {{ label: 'Name', template: 'My name is ' }},
    {{ label: 'Language', template: 'I code in ' }},
    {{ label: 'Favorite', template: 'My favorite ' }},
    {{ label: 'Style', template: 'I prefer ' }},
    {{ label: 'Role', template: 'I work as a ' }},
  ]

  const handleTeach = async () => {{
    if (!text.trim()) return
    setBusy(true)
    try {{
      await teachCopilot(text.trim())
      setSuccess(text.trim())
      setText('')
      onTaught()
      setTimeout(() => setSuccess(''), 3000)
    }} catch {{
      // ignore
    }} finally {{
      setBusy(false)
    }}
  }}

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <div className="text-xs font-medium uppercase tracking-wider text-white/40 mb-3">
        {pencil} Teach Copilot
      </div>
      <div className="flex flex-wrap gap-1.5 mb-3">
        {{presets.map(p => (
          <button
            key={{p.label}}
            onClick={{() => {{ setText(p.template); inputRef.current?.focus() }}}}
            className="rounded-lg bg-white/5 border border-white/10 px-2.5 py-1 text-[11px] text-white/50 hover:text-white hover:bg-white/10 transition-all"
          >
            {{p.label}}
          </button>
        ))}}
      </div>
      <div className="flex gap-2">
        <input
          ref={{inputRef}}
          type="text"
          value={{text}}
          onChange={{e => setText(e.target.value)}}
          onKeyDown={{e => e.key === 'Enter' && handleTeach()}}
          placeholder="Tell Copilot something about yourself..."
          className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-white/25 outline-none focus:border-violet-500/50 transition-colors"
        />
        <button
          onClick={{handleTeach}}
          disabled={{!text.trim() || busy}}
          className="rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-30 disabled:hover:bg-violet-600 px-5 py-2.5 text-sm font-medium text-white transition-all"
        >
          {{busy ? '...' : 'Teach'}}
        </button>
      </div>
      <AnimatePresence>
        {{success && (
          <motion.div
            initial={{{{ opacity: 0, height: 0 }}}}
            animate={{{{ opacity: 1, height: 'auto' }}}}
            exit={{{{ opacity: 0, height: 0 }}}}
            className="mt-2 text-xs text-emerald-400"
          >
            {check} Learned: &ldquo;{{success}}&rdquo;
          </motion.div>
        )}}
      </AnimatePresence>
    </div>
  )
}}

// ---------------------------------------------------------------------------
// Memory Graph
// ---------------------------------------------------------------------------

function MemoryGraph({{ memories }}: {{ memories: CopilotMemory[] }}) {{
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [hovered, setHovered] = useState<CopilotMemory | null>(null)
  const [mousePos, setMousePos] = useState({{ x: 0, y: 0 }})
  const nodesRef = useRef<Array<{{
    x: number; y: number; vx: number; vy: number;
    memory: CopilotMemory; cat: string; radius: number
  }}>>([])

  useEffect(() => {{
    if (!memories.length) return
    const cats = [...new Set(memories.map(m => categorize(m.text)))]
    const catAngles: Record<string, number> = {{}}
    cats.forEach((c, i) => {{ catAngles[c] = (i / cats.length) * Math.PI * 2 }})

    nodesRef.current = memories.map(m => {{
      const cat = categorize(m.text)
      const angle = catAngles[cat] + (Math.random() - 0.5) * 0.8
      const dist = 80 + Math.random() * 100
      return {{
        x: 250 + Math.cos(angle) * dist,
        y: 200 + Math.sin(angle) * dist,
        vx: 0, vy: 0,
        memory: m,
        cat,
        radius: 6 + m.trust * 10,
      }}
    }})
  }}, [memories])

  useEffect(() => {{
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animId: number
    const draw = () => {{
      const w = canvas.width
      const h = canvas.height
      ctx.clearRect(0, 0, w, h)

      const nodes = nodesRef.current
      if (!nodes.length) {{ animId = requestAnimationFrame(draw); return }}

      for (let i = 0; i < nodes.length; i++) {{
        const a = nodes[i]
        a.vx += (w / 2 - a.x) * 0.001
        a.vy += (h / 2 - a.y) * 0.001
        const catNodes = nodes.filter(n => n.cat === a.cat)
        const cx = catNodes.reduce((s, n) => s + n.x, 0) / catNodes.length
        const cy = catNodes.reduce((s, n) => s + n.y, 0) / catNodes.length
        a.vx += (cx - a.x) * 0.003
        a.vy += (cy - a.y) * 0.003

        for (let j = i + 1; j < nodes.length; j++) {{
          const b = nodes[j]
          const dx = b.x - a.x
          const dy = b.y - a.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          if (dist < 60) {{
            const force = (60 - dist) * 0.02
            const fx = (dx / dist) * force
            const fy = (dy / dist) * force
            a.vx -= fx; a.vy -= fy
            b.vx += fx; b.vy += fy
          }}
        }}
      }}

      for (const n of nodes) {{
        n.vx *= 0.92; n.vy *= 0.92
        n.x += n.vx; n.y += n.vy
        n.x = Math.max(n.radius, Math.min(w - n.radius, n.x))
        n.y = Math.max(n.radius, Math.min(h - n.radius, n.y))
      }}

      ctx.globalAlpha = 0.08
      for (let i = 0; i < nodes.length; i++) {{
        for (let j = i + 1; j < nodes.length; j++) {{
          if (nodes[i].cat === nodes[j].cat) {{
            const dist = Math.sqrt(
              (nodes[i].x - nodes[j].x) ** 2 + (nodes[i].y - nodes[j].y) ** 2
            )
            if (dist < 150) {{
              ctx.beginPath()
              ctx.strokeStyle = CATEGORY_COLORS[nodes[i].cat] || '#888'
              ctx.lineWidth = 1
              ctx.moveTo(nodes[i].x, nodes[i].y)
              ctx.lineTo(nodes[j].x, nodes[j].y)
              ctx.stroke()
            }}
          }}
        }}
      }}

      ctx.globalAlpha = 1
      for (const n of nodes) {{
        const color = CATEGORY_COLORS[n.cat] || '#888'
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.radius + 4, 0, Math.PI * 2)
        ctx.fillStyle = color + '15'
        ctx.fill()
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2)
        ctx.fillStyle = color + '60'
        ctx.fill()
        ctx.strokeStyle = color
        ctx.lineWidth = 1.5
        ctx.stroke()
      }}

      const uniqueCats = [...new Set(nodes.map(n => n.cat))]
      for (const cat of uniqueCats) {{
        const catNodes = nodes.filter(n => n.cat === cat)
        const lx = catNodes.reduce((s, n) => s + n.x, 0) / catNodes.length
        const ly = catNodes.reduce((s, n) => s + n.y, 0) / catNodes.length
        ctx.font = '10px sans-serif'
        ctx.fillStyle = CATEGORY_COLORS[cat] || '#888'
        ctx.globalAlpha = 0.6
        ctx.textAlign = 'center'
        ctx.fillText(`${{CATEGORY_ICONS[cat] || ''}} ${{cat}}`, lx, ly - 25)
        ctx.globalAlpha = 1
      }}

      animId = requestAnimationFrame(draw)
    }}

    draw()
    return () => cancelAnimationFrame(animId)
  }}, [memories])

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {{
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    setMousePos({{ x: e.clientX, y: e.clientY }})
    const hit = nodesRef.current.find(n => {{
      const d = Math.sqrt((n.x - mx) ** 2 + (n.y - my) ** 2)
      return d < n.radius + 4
    }})
    setHovered(hit?.memory || null)
  }}

  return (
    <div className="relative rounded-2xl border border-white/10 bg-white/[0.02] overflow-hidden">
      <div className="absolute top-3 left-4 text-[10px] uppercase tracking-wider text-white/30 z-10">
        Memory Graph {dash} {{memories.length}} facts
      </div>
      <canvas
        ref={{canvasRef}}
        width={{500}}
        height={{400}}
        className="w-full h-[400px]"
        onMouseMove={{handleMouseMove}}
        onMouseLeave={{() => setHovered(null)}}
        style={{{{ cursor: hovered ? 'pointer' : 'default' }}}}
      />
      <div className="absolute bottom-3 left-4 flex flex-wrap gap-2">
        {{Object.entries(CATEGORY_COLORS).map(([cat, color]) => (
          <span key={{cat}} className="flex items-center gap-1 text-[9px] text-white/40">
            <span className="inline-block h-2 w-2 rounded-full" style={{{{ backgroundColor: color }}}} />
            {{cat}}
          </span>
        ))}}
      </div>
      {{hovered && (
        <div
          className="fixed z-50 rounded-lg border border-white/20 bg-[#1a1a2e]/95 backdrop-blur-xl px-3 py-2 shadow-xl max-w-xs pointer-events-none"
          style={{{{ left: mousePos.x + 12, top: mousePos.y - 10 }}}}
        >
          <div className="text-xs text-white/80">{{hovered.text}}</div>
          <div className="mt-1 flex items-center gap-2 text-[9px]">
            <span className={{trustColor(hovered.trust)}}>Trust: {{(hovered.trust * 100).toFixed(0)}}%</span>
            <span className="text-white/30">{{hovered.source}}</span>
            <span className="text-white/30">{{timeAgo(hovered.timestamp)}}</span>
          </div>
        </div>
      )}}
    </div>
  )
}}

// ---------------------------------------------------------------------------
// Accuracy Tracker
// ---------------------------------------------------------------------------

function AccuracyTracker({{ accuracy }}: {{ accuracy: AccuracyStats | null }}) {{
  if (!accuracy) return null
  const pct = Math.round(accuracy.accuracy_rate * 100)
  const gaugeAngle = accuracy.accuracy_rate * 180

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
      <div className="text-[10px] uppercase tracking-wider text-white/30 mb-4">{chart} Accuracy Tracker</div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 mb-5">
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{{pct}}%</div>
          <div className="text-[10px] text-white/30">Accuracy</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-amber-400">{{accuracy.corrections_made}}</div>
          <div className="text-[10px] text-white/30">Corrections</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-red-400">{{accuracy.deletions_made}}</div>
          <div className="text-[10px] text-white/30">Deletions</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-emerald-400">{{accuracy.memories_per_day}}</div>
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
              stroke={{pct >= 90 ? '#34d399' : pct >= 70 ? '#fbbf24' : '#f87171'}}
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={{`${{(gaugeAngle / 180) * 251.2}} 251.2`}}
            />
            <text x="100" y="95" textAnchor="middle" fill="white" fontSize="28" fontWeight="bold">
              {{pct}}%
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
          <span className="text-white/50">Auto: {{accuracy.auto_learned}}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-sky-500" />
          <span className="text-white/50">Explicit: {{accuracy.explicit}}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-white/30">Avg trust: </span>
          <span className={{`font-mono font-bold ${{trustColor(accuracy.trust_avg)}}`}}>
            {{(accuracy.trust_avg * 100).toFixed(0)}}%
          </span>
        </div>
      </div>

      {{accuracy.learning_velocity.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-white/20 mb-2">Learning Velocity</div>
          <div className="flex items-end gap-1 h-16">
            {{accuracy.learning_velocity.map((v, i) => {{
              const maxVal = Math.max(...accuracy.learning_velocity.map(x => x.count), 1)
              const barH = Math.max((v.count / maxVal) * 100, 4)
              const autoH = Math.max((v.auto_learned / maxVal) * 100, 0)
              return (
                <div key={{i}} className="flex flex-1 flex-col items-center gap-0.5 group relative" title={{`${{v.label}}: ${{v.count}} total, ${{v.auto_learned}} auto`}}>
                  <div className="w-full flex flex-col justify-end" style={{{{ height: '64px' }}}}>
                    <div
                      className="w-full rounded-t bg-violet-500/60 transition-all"
                      style={{{{ height: `${{autoH}}%` }}}}
                    />
                    <div
                      className="w-full rounded-b bg-sky-500/40 transition-all"
                      style={{{{ height: `${{Math.max(barH - autoH, 0)}}%` }}}}
                    />
                  </div>
                </div>
              )
            }})}}
          </div>
          <div className="flex justify-between text-[8px] text-white/15 mt-1">
            <span>{{accuracy.learning_velocity[0]?.label}}</span>
            <span>{{accuracy.learning_velocity[accuracy.learning_velocity.length - 1]?.label}}</span>
          </div>
        </div>
      )}}
    </div>
  )
}}

// ---------------------------------------------------------------------------
// Stat Card + Trust Bar
// ---------------------------------------------------------------------------

function StatCard({{ label, value, sub, accent }}: {{
  label: string; value: string | number; sub?: string; accent?: string
}}) {{
  return (
    <div className="flex flex-col gap-1 rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="text-xs font-medium uppercase tracking-wider text-white/40">{{label}}</div>
      <div className={{`text-2xl font-bold ${{accent || 'text-white'}}`}}>{{value}}</div>
      {{sub && <div className="text-xs text-white/40">{{sub}}</div>}}
    </div>
  )
}}

function TrustBar({{ distribution }}: {{ distribution: Record<string, number> }}) {{
  const total = Object.values(distribution).reduce((a, b) => a + b, 0)
  if (total === 0) return null
  const segments = [
    {{ key: 'very_high (0.8-1.0)', color: 'bg-emerald-500', label: 'Very High' }},
    {{ key: 'high (0.6-0.8)', color: 'bg-emerald-400', label: 'High' }},
    {{ key: 'medium (0.3-0.6)', color: 'bg-amber-400', label: 'Medium' }},
    {{ key: 'low (0-0.3)', color: 'bg-red-400', label: 'Low' }},
  ]
  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-white/5">
        {{segments.map(seg => {{
          const count = distribution[seg.key] || 0
          const pct = total > 0 ? (count / total) * 100 : 0
          if (pct === 0) return null
          return (
            <div key={{seg.key}} className={{`${{seg.color}} transition-all duration-500`}} style={{{{ width: `${{pct}}%` }}}} title={{`${{seg.label}}: ${{count}}`}} />
          )
        }})}}
      </div>
      <div className="flex flex-wrap gap-3 text-xs text-white/50">
        {{segments.map(seg => {{
          const count = distribution[seg.key] || 0
          if (count === 0) return null
          return (
            <span key={{seg.key}} className="flex items-center gap-1">
              <span className={{`inline-block h-2 w-2 rounded-full ${{seg.color}}`}} />
              {{seg.label}}: {{count}}
            </span>
          )
        }})}}
      </div>
    </div>
  )
}}

// ---------------------------------------------------------------------------
// Memory Card
// ---------------------------------------------------------------------------

function MemoryCard({{ memory, expanded, onToggle, onDelete, onCorrect }}: {{
  memory: CopilotMemory
  expanded: boolean
  onToggle: () => void
  onDelete: (id: string) => void
  onCorrect: (id: string, text: string) => void
}}) {{
  const src = sourceBadge(memory.source)
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(memory.text)

  return (
    <motion.div
      layout
      initial={{{{ opacity: 0, y: 8 }}}}
      animate={{{{ opacity: 1, y: 0 }}}}
      exit={{{{ opacity: 0, y: -8 }}}}
      className="group rounded-xl border border-white/8 bg-white/[0.03] hover:bg-white/[0.06] transition-all"
    >
      <div className="flex items-start gap-3 p-4 cursor-pointer" onClick={{onToggle}}>
        <div className={{`mt-0.5 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border ${{trustBg(memory.trust)}}`}}>
          <span className={{`text-sm font-bold ${{trustColor(memory.trust)}}`}}>
            {{(memory.trust * 100).toFixed(0)}}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={{`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-medium ${{src.className}}`}}>
              {{src.label}}
            </span>
            <span className="text-[10px] text-white/30 font-mono">{{memory.namespace}}</span>
            <span className="text-[10px] rounded-md px-1.5 py-0 text-white/20" style={{{{ backgroundColor: (CATEGORY_COLORS[categorize(memory.text)] || '#888') + '20' }}}}>
              {{CATEGORY_ICONS[categorize(memory.text)]}} {{categorize(memory.text)}}
            </span>
            <span className="ml-auto text-[10px] text-white/30">{{timeAgo(memory.timestamp)}}</span>
          </div>
          <p className="text-sm text-white/80 leading-relaxed">{{memory.text}}</p>
        </div>
      </div>

      <AnimatePresence>
        {{expanded && (
          <motion.div
            initial={{{{ height: 0, opacity: 0 }}}}
            animate={{{{ height: 'auto', opacity: 1 }}}}
            exit={{{{ height: 0, opacity: 0 }}}}
            className="overflow-hidden border-t border-white/5"
          >
            <div className="p-4">
              <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4 mb-3">
                <div>
                  <span className="text-white/30">ID</span>
                  <div className="mt-0.5 font-mono text-white/50 break-all text-[10px]">{{memory.id}}</div>
                </div>
                <div>
                  <span className="text-white/30">Thread</span>
                  <div className="mt-0.5 font-mono text-white/50">{{memory.thread_id}}</div>
                </div>
                <div>
                  <span className="text-white/30">Trust</span>
                  <div className={{`mt-0.5 font-mono font-bold ${{trustColor(memory.trust)}}`}}>{{memory.trust.toFixed(2)}}</div>
                </div>
                <div>
                  <span className="text-white/30">Stored</span>
                  <div className="mt-0.5 text-white/50 text-[11px]">
                    {{memory.created_at || new Date(memory.timestamp * 1000).toLocaleString()}}
                  </div>
                </div>
              </div>

              {{editing ? (
                <div className="flex gap-2 mt-2">
                  <input
                    type="text"
                    value={{editText}}
                    onChange={{e => setEditText(e.target.value)}}
                    onKeyDown={{e => {{
                      if (e.key === 'Enter') {{ onCorrect(memory.id, editText); setEditing(false) }}
                      if (e.key === 'Escape') setEditing(false)
                    }}}}
                    className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white outline-none focus:border-violet-500/50"
                    autoFocus
                  />
                  <button onClick={{() => {{ onCorrect(memory.id, editText); setEditing(false) }}}} className="rounded-lg bg-violet-600 px-3 py-1.5 text-xs text-white">Save</button>
                  <button onClick={{() => setEditing(false)}} className="rounded-lg bg-white/10 px-3 py-1.5 text-xs text-white/50">Cancel</button>
                </div>
              ) : (
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={{(e) => {{ e.stopPropagation(); setEditing(true); setEditText(memory.text) }}}}
                    className="rounded-lg bg-white/5 border border-white/10 px-3 py-1.5 text-xs text-white/50 hover:text-white hover:bg-white/10 transition-all"
                  >
                    {pencil} Correct
                  </button>
                  <button
                    onClick={{(e) => {{ e.stopPropagation(); onDelete(memory.id) }}}}
                    className="rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/20 transition-all"
                  >
                    {trash} Delete
                  </button>
                </div>
              )}}
            </div>
          </motion.div>
        )}}
      </AnimatePresence>
    </motion.div>
  )
}}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

type SortOrder = 'newest' | 'oldest' | 'trust_high' | 'trust_low'
type Tab = 'memories' | 'profile' | 'graph' | 'accuracy'

export function CopilotPage() {{
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
  const [pollInterval] = useState(2000)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())
  const [newCount, setNewCount] = useState(0)
  const prevTotalRef = useRef<number>(0)
  const prevIdsRef = useRef<Set<string>>(new Set())

  const [toasts, setToasts] = useState<Toast[]>([])
  const toastTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('memories')

  const addToast = useCallback((memory: CopilotMemory) => {{
    const t: Toast = {{ id: memory.id, text: memory.text, source: memory.source, ts: memory.timestamp }}
    setToasts(prev => [...prev.slice(-4), t])
    const timer = setTimeout(() => {{
      setToasts(prev => prev.filter(x => x.id !== t.id))
      toastTimers.current.delete(t.id)
    }}, 6000)
    toastTimers.current.set(t.id, timer)
  }}, [])

  const dismissToast = useCallback((id: string) => {{
    setToasts(prev => prev.filter(x => x.id !== id))
    const timer = toastTimers.current.get(id)
    if (timer) {{ clearTimeout(timer); toastTimers.current.delete(id) }}
  }}, [])

  const fetchData = useCallback(async () => {{
    try {{
      const resp = await getCopilotMemories({{
        namespace: nsFilter || undefined,
        source: sourceFilter || undefined,
        search: searchQ || undefined,
        sort: sortOrder,
        limit: 200,
      }})
      setData(resp)
      setError(null)
      setLastRefresh(new Date())

      const currentIds = new Set(resp.memories.map(m => m.id))
      if (prevIdsRef.current.size > 0) {{
        for (const m of resp.memories) {{
          if (!prevIdsRef.current.has(m.id)) {{
            addToast(m)
          }}
        }}
      }}
      prevIdsRef.current = currentIds

      if (prevTotalRef.current > 0 && resp.stats.total_memories > prevTotalRef.current) {{
        setNewCount(prev => prev + (resp.stats.total_memories - prevTotalRef.current))
      }}
      prevTotalRef.current = resp.stats.total_memories
    }} catch (e: any) {{
      setError(e.message || 'Failed to load data')
    }} finally {{
      setLoading(false)
    }}
  }}, [nsFilter, sourceFilter, searchQ, sortOrder, addToast])

  const fetchSideData = useCallback(async () => {{
    try {{
      const [p, a] = await Promise.all([getCopilotProfile(), getCopilotAccuracy()])
      setProfile(p)
      setAccuracy(a)
    }} catch {{ /* ignore */ }}
  }}, [])

  useEffect(() => {{
    setLoading(true)
    fetchData()
    fetchSideData()
  }}, [fetchData, fetchSideData])

  useEffect(() => {{
    if (live) {{
      intervalRef.current = setInterval(() => {{
        fetchData()
        fetchSideData()
      }}, pollInterval)
    }}
    return () => {{ if (intervalRef.current) clearInterval(intervalRef.current) }}
  }}, [live, pollInterval, fetchData, fetchSideData])

  const handleDelete = async (id: string) => {{
    try {{
      await deleteCopilotMemory(id)
      fetchData()
      fetchSideData()
    }} catch {{ /* ignore */ }}
  }}

  const handleCorrect = async (id: string, text: string) => {{
    try {{
      await correctCopilotMemory(id, text)
      fetchData()
      fetchSideData()
    }} catch {{ /* ignore */ }}
  }}

  const stats = data?.stats
  const memories = data?.memories || []

  const tabItems: Array<{{ id: Tab; label: string; icon: string }}> = [
    {{ id: 'memories', label: 'Memories', icon: '{brain}' }},
    {{ id: 'profile', label: 'Profile', icon: '{bust}' }},
    {{ id: 'graph', label: 'Graph', icon: '{web}' }},
    {{ id: 'accuracy', label: 'Accuracy', icon: '{chart}' }},
  ]

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <ToastStack toasts={{toasts}} onDismiss={{dismissToast}} />

      <div className="flex flex-col gap-4 border-b border-white/10 p-4 sm:p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white font-display">Copilot Interactions</h1>
            <p className="mt-0.5 text-xs text-white/40">
              Live view {dash} what Copilot knows, learns, and gets wrong
            </p>
          </div>

          <div className="flex items-center gap-3">
            {{newCount > 0 && (
              <motion.span
                initial={{{{ scale: 0 }}}}
                animate={{{{ scale: 1 }}}}
                className="rounded-full bg-violet-500/20 border border-violet-500/40 px-2 py-0.5 text-xs text-violet-300"
              >
                +{{newCount}} new
              </motion.span>
            )}}
            <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5">
              <button onClick={{() => setLive(v => !v)}} className="flex items-center gap-1.5 text-xs">
                <span className={{`inline-block h-2 w-2 rounded-full ${{live ? 'bg-emerald-400 animate-pulse' : 'bg-white/20'}}`}} />
                <span className={{live ? 'text-emerald-400' : 'text-white/40'}}>{{live ? 'Live' : 'Paused'}}</span>
              </button>
              <span className="mx-1 h-4 w-px bg-white/10" />
              <button onClick={{() => {{ setLoading(true); fetchData(); fetchSideData() }}}} className="text-xs text-white/40 hover:text-white transition-colors" title="Refresh now">{reload_}</button>
            </div>
            <span className="text-[10px] text-white/20">{{lastRefresh.toLocaleTimeString()}}</span>
          </div>
        </div>

        {{stats && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            <StatCard label="Total" value={{stats.total_memories}} accent="text-white" />
            <StatCard label="Auto-learned" value={{stats.auto_learned_count}}
              sub={{stats.total_memories > 0 ? `${{Math.round((stats.auto_learned_count / stats.total_memories) * 100)}}%` : undefined}}
              accent="text-violet-400" />
            <StatCard label="Explicit" value={{stats.explicit_count}} accent="text-sky-400" />
            <StatCard label="Namespaces" value={{stats.namespaces.length}} sub={{stats.namespaces.slice(0, 3).join(', ')}} />
            <StatCard label="Accuracy" value={{accuracy ? `${{Math.round(accuracy.accuracy_rate * 100)}}%` : '{dash}'}} accent="text-emerald-400" />
            <div className="col-span-2 sm:col-span-4 lg:col-span-1">
              <div className="flex flex-col gap-1 rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-xs font-medium uppercase tracking-wider text-white/40">Trust</div>
                <div className="mt-1"><TrustBar distribution={{stats.trust_distribution}} /></div>
              </div>
            </div>
          </div>
        )}}
      </div>

      <div className="flex items-center gap-1 border-b border-white/5 px-4 py-2 sm:px-6">
        {{tabItems.map(t => (
          <button
            key={{t.id}}
            onClick={{() => setTab(t.id)}}
            className={{`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${{
              tab === t.id
                ? 'bg-violet-500/15 text-violet-300 border border-violet-500/30'
                : 'text-white/40 hover:text-white/60 hover:bg-white/5 border border-transparent'
            }}`}}
          >
            {{t.icon}} {{t.label}}
          </button>
        ))}}
      </div>

      <div className="flex-1 overflow-y-auto">
        {{tab === 'memories' && (
          <div className="flex flex-col gap-0">
            <div className="flex flex-wrap items-center gap-2 border-b border-white/5 px-4 py-3 sm:px-6">
              <input type="text" placeholder="Search..." value={{searchQ}} onChange={{e => setSearchQ(e.target.value)}}
                className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white placeholder-white/30 outline-none focus:border-violet-500/50 w-40" />
              <select value={{nsFilter}} onChange={{e => setNsFilter(e.target.value)}}
                className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white outline-none cursor-pointer">
                <option value="">All NS</option>
                {{(stats?.namespaces || []).map(ns => <option key={{ns}} value={{ns}}>{{ns}}</option>)}}
              </select>
              <select value={{sourceFilter}} onChange={{e => setSourceFilter(e.target.value)}}
                className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white outline-none cursor-pointer">
                <option value="">All Sources</option>
                <option value="inferred">{zap} Auto</option>
                <option value="user">{bust} Explicit</option>
                <option value="document">{doc} Doc</option>
                <option value="code">{laptop} Code</option>
              </select>
              <select value={{sortOrder}} onChange={{e => setSortOrder(e.target.value as SortOrder)}}
                className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white outline-none cursor-pointer">
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
                <option value="trust_high">High trust</option>
                <option value="trust_low">Low trust</option>
              </select>
              <span className="ml-auto text-xs text-white/30">{{data ? `${{data.total}} memories` : '...'}}</span>
            </div>

            <div className="px-4 py-3 sm:px-6">
              <TeachForm onTaught={{() => {{ fetchData(); fetchSideData() }}}} />
            </div>

            <div className="px-4 py-2 sm:px-6">
              {{loading && !data ? (
                <div className="flex items-center justify-center py-20">
                  <div className="flex flex-col items-center gap-3">
                    <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-500" />
                    <span className="text-sm text-white/40">Loading...</span>
                  </div>
                </div>
              ) : error ? (
                <div className="flex items-center justify-center py-20">
                  <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-8 text-center">
                    <span className="text-4xl">{warn}</span>
                    <div className="mt-2 text-sm text-red-400">{{error}}</div>
                    <button onClick={{() => {{ setLoading(true); fetchData() }}}} className="mt-3 rounded-lg bg-white/10 px-4 py-2 text-xs text-white">Retry</button>
                  </div>
                </div>
              ) : memories.length === 0 ? (
                <div className="flex items-center justify-center py-16 text-center">
                  <div>
                    <span className="text-5xl opacity-40">{brain}</span>
                    <div className="mt-2 text-sm text-white/40">No memories yet</div>
                    <div className="text-xs text-white/20 max-w-sm mt-1">Use the Teach form above or chat with Copilot to get started</div>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  <AnimatePresence mode="popLayout">
                    {{memories.map(m => (
                      <MemoryCard
                        key={{m.id}}
                        memory={{m}}
                        expanded={{expandedId === m.id}}
                        onToggle={{() => setExpandedId(expandedId === m.id ? null : m.id)}}
                        onDelete={{handleDelete}}
                        onCorrect={{handleCorrect}}
                      />
                    ))}}
                  </AnimatePresence>
                </div>
              )}}
            </div>
          </div>
        )}}

        {{tab === 'profile' && (
          <div className="grid gap-4 p-4 sm:p-6 lg:grid-cols-2">
            <ProfileCard profile={{profile}} />
            <TeachForm onTaught={{() => {{ fetchData(); fetchSideData() }}}} />
          </div>
        )}}

        {{tab === 'graph' && (
          <div className="p-4 sm:p-6">
            <MemoryGraph memories={{memories}} />
          </div>
        )}}

        {{tab === 'accuracy' && (
          <div className="p-4 sm:p-6">
            <AccuracyTracker accuracy={{accuracy}} />
          </div>
        )}}
      </div>
    </div>
  )
}}
"""

p.write_text(content, encoding='utf-8')
lines = content.count('\n')
print(f"Written {lines} lines, {len(content)} bytes")
