import { useEffect, useMemo, useRef, useState } from 'react'
import { getEffectiveApiBaseUrl } from '../lib/api'

type LiveEvent = {
  ts?: number
  ts_iso?: string
  event_type?: string
  text?: string
  thread_id?: string
  sender_name?: string
  gate_reason?: string
  gates_passed?: boolean
  contradiction_detected?: boolean
}

export function LiveFeedPage() {
  const [events, setEvents] = useState<LiveEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const listRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const base = getEffectiveApiBaseUrl().replace(/\/$/, '')
    const url = `${base}/api/telegram/live/stream?max_initial_lines=200&poll_interval=1.0`
    const es = new EventSource(url)
    es.onopen = () => setConnected(true)
    es.onerror = () => {
      setConnected(false)
      setErrors((prev) => [...prev.slice(-4), 'stream connection error'])
    }
    es.onmessage = (evt) => {
      try {
        const parsed = JSON.parse(evt.data) as LiveEvent
        if ((parsed.event_type || '').toLowerCase() === 'heartbeat') return
        setEvents((prev) => [...prev.slice(-499), parsed])
      } catch {
        setErrors((prev) => [...prev.slice(-4), 'bad event payload'])
      }
    }
    return () => es.close()
  }, [])

  useEffect(() => {
    if (!listRef.current) return
    listRef.current.scrollTop = listRef.current.scrollHeight
  }, [events.length])

  const statusText = useMemo(() => (connected ? 'Connected' : 'Disconnected'), [connected])

  return (
    <div className="flex h-full flex-col gap-4 overflow-hidden p-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-white">Live Output</div>
          <div className="mt-1 text-sm text-white/60">
            Real-time Telegram inbound/outbound stream with trailing history.
          </div>
        </div>
        <div className={`rounded px-3 py-1 text-xs ${connected ? 'bg-emerald-500/20 text-emerald-200' : 'bg-amber-500/20 text-amber-200'}`}>
          {statusText}
        </div>
      </div>

      {errors.length > 0 ? (
        <div className="rounded border border-amber-400/30 bg-amber-500/10 p-2 text-xs text-amber-100">
          {errors[errors.length - 1]}
        </div>
      ) : null}

      <div ref={listRef} className="min-h-0 flex-1 overflow-auto rounded-xl border border-white/10 bg-black/30 p-3 font-mono text-xs">
        {events.length === 0 ? (
          <div className="text-white/50">Waiting for events...</div>
        ) : (
          events.map((e, idx) => {
            const ts = e.ts_iso || (e.ts ? new Date(e.ts * 1000).toISOString() : '')
            const kind = (e.event_type || 'event').toLowerCase()
            return (
              <div key={`${idx}-${ts}`} className="mb-2 border-b border-white/5 pb-2 text-white/90">
                <div className="text-[10px] text-white/50">
                  [{ts}] {kind} {e.thread_id ? `thread=${e.thread_id}` : ''} {e.sender_name ? `sender=${e.sender_name}` : ''}
                </div>
                <div className="whitespace-pre-wrap break-words">{e.text || ''}</div>
                {(e.gate_reason || typeof e.gates_passed === 'boolean') ? (
                  <div className="mt-1 text-[10px] text-white/50">
                    gate={e.gate_reason || 'n/a'} pass={String(Boolean(e.gates_passed))} contra={String(Boolean(e.contradiction_detected))}
                  </div>
                ) : null}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

