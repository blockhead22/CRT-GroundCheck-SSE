import { useEffect, useRef, useState, useCallback } from 'react'

type MapPoint = {
  entry_id: number
  x: number
  y: number
  is_belief: boolean
  trust_avg: number | null
  topic_id: number | null
  topic_label: string | null
  query: string
  response_preview: string
  timestamp: number
}

type MapTopic = {
  topic_id: number
  label: string
  centroid_x: number
  centroid_y: number
}

type MapData = {
  points: MapPoint[]
  contradictions: { entry_id_a: number; entry_id_b: number; ledger_id: string }[]
  topics: MapTopic[]
  error?: string
}

// Colors matching the design system
const COLORS = {
  bg: '#141210',
  belief: '#D4845C',
  speech: '#635c50',
  contradiction: '#D47058',
  topicLabel: '#a89d8a',
  topicHull: 'rgba(240,235,225,0.06)',
  grid: 'rgba(240,235,225,0.03)',
  tooltipBg: '#1a1714',
  tooltipBorder: 'rgba(240,235,225,0.12)',
  text: '#F0EBE1',
  textMuted: '#a89d8a',
}

export default function BeliefMapPage({ threadId }: { threadId?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [data, setData] = useState<MapData | null>(null)
  const [tooltip, setTooltip] = useState<{ x: number; y: number; point: MapPoint } | null>(null)
  const [selectedTopic, setSelectedTopic] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Camera state
  const cameraRef = useRef({ offsetX: 0, offsetY: 0, zoom: 1 })
  const dragRef = useRef({ dragging: false, lastX: 0, lastY: 0 })

  const tid = threadId || 'default'

  // Fetch data
  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`/api/variance/embedding-map?thread_id=${tid}`)
      const json = await res.json()
      if (json.error) setError(json.error)
      else setError(null)
      setData(json)
    } catch {
      setError('Failed to fetch embedding map')
    }
  }, [tid])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [fetchData])

  // World → screen coordinate transform
  const worldToScreen = useCallback((wx: number, wy: number, canvas: HTMLCanvasElement) => {
    const cam = cameraRef.current
    const cx = canvas.width / 2
    const cy = canvas.height / 2
    const scale = Math.min(canvas.width, canvas.height) * 0.4 * cam.zoom
    return {
      sx: cx + (wx + cam.offsetX) * scale,
      sy: cy + (-wy + cam.offsetY) * scale, // flip Y
    }
  }, [])

  const screenToWorld = useCallback((sx: number, sy: number, canvas: HTMLCanvasElement) => {
    const cam = cameraRef.current
    const cx = canvas.width / 2
    const cy = canvas.height / 2
    const scale = Math.min(canvas.width, canvas.height) * 0.4 * cam.zoom
    return {
      wx: (sx - cx) / scale - cam.offsetX,
      wy: -((sy - cy) / scale - cam.offsetY),
    }
  }, [])

  // Draw
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !data) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)
    canvas.style.width = `${rect.width}px`
    canvas.style.height = `${rect.height}px`

    // Clear
    ctx.fillStyle = COLORS.bg
    ctx.fillRect(0, 0, rect.width, rect.height)

    if (data.points.length === 0) {
      ctx.fillStyle = COLORS.textMuted
      ctx.font = '14px monospace'
      ctx.textAlign = 'center'
      ctx.fillText('No embedding data yet. Chat with Aether to populate.', rect.width / 2, rect.height / 2)
      return
    }

    // Grid lines
    ctx.strokeStyle = COLORS.grid
    ctx.lineWidth = 1
    for (let g = -1; g <= 1; g += 0.5) {
      const { sx: gx } = worldToScreen(g, 0, canvas)
      const { sy: gy } = worldToScreen(0, g, canvas)
      ctx.beginPath()
      ctx.moveTo(gx, 0)
      ctx.lineTo(gx, rect.height)
      ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(0, gy)
      ctx.lineTo(rect.width, gy)
      ctx.stroke()
    }

    // Contradiction lines
    for (const c of data.contradictions) {
      const a = data.points.find(p => p.entry_id === c.entry_id_a)
      const b = data.points.find(p => p.entry_id === c.entry_id_b)
      if (a && b) {
        const sa = worldToScreen(a.x, a.y, canvas)
        const sb = worldToScreen(b.x, b.y, canvas)
        ctx.strokeStyle = COLORS.contradiction
        ctx.lineWidth = 1.5
        ctx.setLineDash([4, 4])
        ctx.beginPath()
        ctx.moveTo(sa.sx, sa.sy)
        ctx.lineTo(sb.sx, sb.sy)
        ctx.stroke()
        ctx.setLineDash([])
      }
    }

    // Topic labels
    ctx.font = '11px monospace'
    ctx.textAlign = 'center'
    for (const t of data.topics) {
      const { sx, sy } = worldToScreen(t.centroid_x, t.centroid_y, canvas)
      ctx.fillStyle = COLORS.topicLabel
      ctx.globalAlpha = 0.6
      ctx.fillText(t.label || `topic ${t.topic_id}`, sx, sy - 16)
      ctx.globalAlpha = 1.0
    }

    // Points
    for (const p of data.points) {
      const { sx, sy } = worldToScreen(p.x, p.y, canvas)
      const trust = p.trust_avg ?? 0.5
      const radius = 3 + trust * 9 // 3-12px

      const isHighlighted = selectedTopic === null || selectedTopic === p.topic_id
      const alpha = isHighlighted ? 1.0 : 0.15

      ctx.globalAlpha = alpha
      ctx.beginPath()
      ctx.arc(sx, sy, radius, 0, Math.PI * 2)
      ctx.fillStyle = p.is_belief ? COLORS.belief : COLORS.speech
      ctx.fill()

      // Subtle glow for high-trust beliefs
      if (p.is_belief && trust > 0.7) {
        ctx.globalAlpha = alpha * 0.2
        ctx.beginPath()
        ctx.arc(sx, sy, radius + 4, 0, Math.PI * 2)
        ctx.fillStyle = COLORS.belief
        ctx.fill()
      }
      ctx.globalAlpha = 1.0
    }

    // Legend
    const lx = 16
    const ly = rect.height - 50
    ctx.font = '10px monospace'
    ctx.textAlign = 'left'

    ctx.fillStyle = COLORS.belief
    ctx.beginPath()
    ctx.arc(lx, ly, 5, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = COLORS.textMuted
    ctx.fillText('Belief (grounded)', lx + 12, ly + 4)

    ctx.fillStyle = COLORS.speech
    ctx.beginPath()
    ctx.arc(lx, ly + 18, 5, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = COLORS.textMuted
    ctx.fillText('Speech (ungrounded)', lx + 12, ly + 22)

    // Count display
    const beliefs = data.points.filter(p => p.is_belief).length
    const speeches = data.points.length - beliefs
    ctx.fillStyle = COLORS.textMuted
    ctx.font = '10px monospace'
    ctx.textAlign = 'right'
    ctx.fillText(`${data.points.length} points | ${beliefs} beliefs | ${speeches} speech | ${data.topics.length} topics`, rect.width - 16, rect.height - 16)
  }, [data, selectedTopic, worldToScreen])

  // Mouse interactions
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas || !data) return
    const rect = canvas.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top

    // Drag
    if (dragRef.current.dragging) {
      const dx = mx - dragRef.current.lastX
      const dy = my - dragRef.current.lastY
      const scale = Math.min(canvas.width, canvas.height) * 0.4 * cameraRef.current.zoom
      cameraRef.current.offsetX += dx / scale
      cameraRef.current.offsetY += dy / scale
      dragRef.current.lastX = mx
      dragRef.current.lastY = my
      // Force redraw
      setData(prev => prev ? { ...prev } : prev)
      return
    }

    // Hit test
    const dpr = window.devicePixelRatio || 1
    let closest: MapPoint | null = null
    let closestDist = 20 // max pixel distance for hover

    for (const p of data.points) {
      const { sx, sy } = worldToScreen(p.x, p.y, canvas)
      const dist = Math.sqrt((mx * dpr - sx) ** 2 + (my * dpr - sy) ** 2)
      if (dist < closestDist) {
        closestDist = dist
        closest = p
      }
    }

    if (closest) {
      setTooltip({ x: e.clientX, y: e.clientY, point: closest })
    } else {
      setTooltip(null)
    }
  }, [data, worldToScreen])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    dragRef.current = { dragging: true, lastX: e.nativeEvent.offsetX, lastY: e.nativeEvent.offsetY }
  }, [])

  const handleMouseUp = useCallback(() => {
    dragRef.current.dragging = false
  }, [])

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas || !data) return

    const rect = canvas.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    const dpr = window.devicePixelRatio || 1

    for (const p of data.points) {
      const { sx, sy } = worldToScreen(p.x, p.y, canvas)
      const dist = Math.sqrt((mx * dpr - sx) ** 2 + (my * dpr - sy) ** 2)
      if (dist < 20) {
        setSelectedTopic(prev => prev === p.topic_id ? null : p.topic_id)
        return
      }
    }
    setSelectedTopic(null)
  }, [data, worldToScreen])

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    const factor = e.deltaY > 0 ? 0.9 : 1.1
    cameraRef.current.zoom = Math.max(0.2, Math.min(10, cameraRef.current.zoom * factor))
    setData(prev => prev ? { ...prev } : prev)
  }, [])

  // Resize observer
  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const ro = new ResizeObserver(() => {
      setData(prev => prev ? { ...prev } : prev) // trigger redraw
    })
    ro.observe(container)
    return () => ro.disconnect()
  }, [])

  return (
    <div ref={containerRef} className="flex h-full min-h-0 flex-col" style={{ background: COLORS.bg }}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: 'rgba(240,235,225,0.08)' }}>
        <div>
          <h2 className="text-sm font-display" style={{ color: COLORS.text }}>Belief Map</h2>
          <span className="text-[10px] font-mono" style={{ color: COLORS.textMuted }}>
            PCA projection of response embeddings — belief vs speech
          </span>
        </div>
        <div className="flex items-center gap-3">
          {selectedTopic !== null && (
            <button
              onClick={() => setSelectedTopic(null)}
              className="rounded px-2 py-0.5 text-[10px] font-mono"
              style={{ background: 'rgba(212,132,92,0.15)', color: COLORS.belief }}
            >
              clear filter
            </button>
          )}
          <button
            onClick={fetchData}
            className="rounded px-2 py-0.5 text-[10px] font-mono"
            style={{ background: 'rgba(240,235,225,0.06)', color: COLORS.textMuted }}
          >
            refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="px-5 py-2 text-[11px] font-mono" style={{ color: COLORS.contradiction }}>
          {error}
        </div>
      )}

      {/* Canvas */}
      <div className="flex-1 min-h-0 relative">
        <canvas
          ref={canvasRef}
          className="w-full h-full cursor-crosshair"
          onMouseMove={handleMouseMove}
          onMouseDown={handleMouseDown}
          onMouseUp={handleMouseUp}
          onMouseLeave={() => { handleMouseUp(); setTooltip(null) }}
          onClick={handleClick}
          onWheel={handleWheel}
        />

        {/* Tooltip */}
        {tooltip && (
          <div
            className="fixed z-50 pointer-events-none rounded px-3 py-2 max-w-[320px]"
            style={{
              left: tooltip.x + 12,
              top: tooltip.y - 8,
              background: COLORS.tooltipBg,
              border: `1px solid ${COLORS.tooltipBorder}`,
              boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
            }}
          >
            <div className="flex items-center gap-2 mb-1">
              <span
                className="rounded-full px-1.5 py-0.5 text-[9px] font-mono uppercase"
                style={{
                  background: tooltip.point.is_belief ? 'rgba(212,132,92,0.2)' : 'rgba(99,92,80,0.2)',
                  color: tooltip.point.is_belief ? COLORS.belief : COLORS.speech,
                }}
              >
                {tooltip.point.is_belief ? 'belief' : 'speech'}
              </span>
              {tooltip.point.trust_avg != null && (
                <span className="text-[9px] font-mono" style={{ color: COLORS.textMuted }}>
                  trust: {tooltip.point.trust_avg.toFixed(2)}
                </span>
              )}
              {tooltip.point.topic_label && (
                <span className="text-[9px] font-mono" style={{ color: COLORS.belief }}>
                  {tooltip.point.topic_label}
                </span>
              )}
            </div>
            <div className="text-[10px] font-mono mb-1" style={{ color: COLORS.textMuted }}>
              Q: {tooltip.point.query}
            </div>
            <div className="text-[11px]" style={{ color: COLORS.text }}>
              {tooltip.point.response_preview}
            </div>
            <div className="text-[9px] mt-1" style={{ color: COLORS.textMuted }}>
              {new Date(tooltip.point.timestamp * 1000).toLocaleString()}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
