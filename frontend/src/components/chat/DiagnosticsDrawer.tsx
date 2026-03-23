import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { streamLogs, type LogEntry } from '../../lib/api'

const MAX_LINES = 300
const LEVEL_COLORS: Record<string, string> = {
  DEBUG: 'var(--text-faint)',
  INFO: 'var(--text-muted)',
  WARNING: 'var(--warn)',
  ERROR: 'var(--err)',
  CRITICAL: 'var(--err)',
}

function fmtTs(ts: number): string {
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('en-US', { hour12: false, fractionalSecondDigits: 3 })
}

export function DiagnosticsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [lines, setLines] = useState<LogEntry[]>([])
  const [filter, setFilter] = useState('')
  const [level, setLevel] = useState<'DEBUG' | 'INFO' | 'WARNING'>('INFO')
  const [paused, setPaused] = useState(false)
  const [connected, setConnected] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const pausedRef = useRef(false)
  pausedRef.current = paused

  // Auto-scroll
  useEffect(() => {
    if (!paused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [lines, paused])

  // SSE connection
  useEffect(() => {
    if (!open) return

    const ctrl = streamLogs({
      level,
      onEntry: (entry) => {
        setConnected(true)
        if (!pausedRef.current) {
          setLines((prev) => {
            const next = [...prev, entry]
            return next.length > MAX_LINES ? next.slice(-MAX_LINES) : next
          })
        }
      },
      onError: () => setConnected(false),
    })

    setConnected(true)

    return () => {
      ctrl.abort()
      setConnected(false)
    }
  }, [open, level])

  const filtered = filter
    ? lines.filter((l) => l.msg.toLowerCase().includes(filter.toLowerCase()) || l.logger.toLowerCase().includes(filter.toLowerCase()))
    : lines

  if (!open) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 30, stiffness: 400 }}
        className="fixed bottom-0 left-0 right-0 z-[1200] flex flex-col"
        style={{
          height: '45vh',
          minHeight: '240px',
          maxHeight: '60vh',
          background: 'var(--bg)',
          borderTop: '1px solid var(--border)',
        }}
      >
        {/* Header bar */}
        <div
          className="flex items-center gap-3 px-4 py-1.5 flex-none"
          style={{ borderBottom: '1px solid var(--border-soft)', background: 'var(--surface)' }}
        >
          {/* Status dot */}
          <span
            className="h-1.5 w-1.5 rounded-full flex-none"
            style={{ background: connected ? 'var(--ok)' : 'var(--err)' }}
          />
          <span className="font-mono text-[10px] uppercase tracking-[0.15em] flex-none" style={{ color: 'var(--accent)' }}>
            Diagnostics
          </span>

          {/* Level selector */}
          <div className="flex gap-0.5 ml-2">
            {(['DEBUG', 'INFO', 'WARNING'] as const).map((lv) => (
              <button
                key={lv}
                onClick={() => { setLevel(lv); setLines([]) }}
                className="font-mono text-[9px] uppercase tracking-wider px-2 py-0.5 transition-colors"
                style={{
                  color: level === lv ? 'var(--text)' : 'var(--text-faint)',
                  background: level === lv ? 'var(--surface-3)' : 'transparent',
                  borderRadius: '3px',
                }}
              >
                {lv}
              </button>
            ))}
          </div>

          {/* Filter input */}
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="filter..."
            className="ml-2 flex-1 bg-transparent font-mono text-[11px] text-white/70 placeholder:text-white/20 outline-none"
            style={{ maxWidth: '200px' }}
          />

          <div className="flex-1" />

          {/* Pause / Clear / Close */}
          <button
            onClick={() => setPaused(!paused)}
            className="font-mono text-[9px] uppercase tracking-wider px-2 py-0.5 transition-colors hover:bg-white/[0.06]"
            style={{
              color: paused ? 'var(--warn)' : 'var(--text-faint)',
              borderRadius: '3px',
            }}
          >
            {paused ? 'Paused' : 'Pause'}
          </button>
          <button
            onClick={() => setLines([])}
            className="font-mono text-[9px] uppercase tracking-wider px-2 py-0.5 transition-colors hover:bg-white/[0.06]"
            style={{ color: 'var(--text-faint)', borderRadius: '3px' }}
          >
            Clear
          </button>
          <button
            onClick={onClose}
            className="font-mono text-[9px] uppercase tracking-wider px-2 py-0.5 transition-colors hover:bg-white/[0.06]"
            style={{ color: 'var(--text-faint)', borderRadius: '3px' }}
          >
            Close
          </button>
        </div>

        {/* Log lines */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-auto px-3 py-1 font-mono text-[11px] leading-[1.6]"
          onWheel={() => {
            // If user scrolls up, auto-pause
            if (scrollRef.current) {
              const { scrollTop, scrollHeight, clientHeight } = scrollRef.current
              if (scrollHeight - scrollTop - clientHeight > 40) {
                setPaused(true)
              }
            }
          }}
        >
          {filtered.length === 0 ? (
            <div className="flex items-center justify-center h-full" style={{ color: 'var(--text-faint)' }}>
              {connected ? 'Waiting for log entries...' : 'Connecting...'}
            </div>
          ) : (
            filtered.map((line, i) => (
              <div key={i} className="flex gap-3 py-px hover:bg-white/[0.02] px-1 -mx-1 rounded">
                <span className="flex-none" style={{ color: 'var(--text-faint)', width: '85px' }}>
                  {fmtTs(line.ts)}
                </span>
                <span
                  className="flex-none uppercase text-[9px] font-bold tracking-wider"
                  style={{
                    color: LEVEL_COLORS[line.level] ?? 'var(--text-faint)',
                    width: '50px',
                    lineHeight: '1.6',
                  }}
                >
                  {line.level}
                </span>
                <span className="flex-none" style={{ color: 'var(--text-faint)', width: '140px' }}>
                  {line.logger.length > 20 ? '...' + line.logger.slice(-17) : line.logger}
                </span>
                <span style={{ color: 'var(--text-muted)', wordBreak: 'break-all' }}>
                  {line.msg}
                </span>
              </div>
            ))
          )}
        </div>

        {/* Footer stats */}
        <div
          className="flex items-center gap-4 px-4 py-1 flex-none font-mono text-[9px]"
          style={{ borderTop: '1px solid var(--border-soft)', color: 'var(--text-faint)' }}
        >
          <span>{filtered.length} lines</span>
          {filter && <span>({lines.length} total)</span>}
          <span>level: {level}</span>
          {paused && <span style={{ color: 'var(--warn)' }}>PAUSED — scroll to bottom to resume</span>}
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
