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
  turn_id?: number
  reattempt_after_turn?: number | null
  flag_type?: string
  decision_path?: string[]
  obs?: {
    decision_path?: string[]
    flags?: string[]
    pipeline_statuses?: string[]
    response_mode?: string
    confidence?: number
    gate_reason?: string
    unresolved_hard_conflicts?: number
    reintroduced_claims_count?: number
    product_mode?: string
    generation_provider?: string
    model_route?: {
      route?: string
      provider?: string
      model?: string
      reason?: string
    }
    reflection?: {
      trace_id?: string
      confidence?: number
      label?: string
    }
    critic?: Record<string, unknown>
    tasking?: Record<string, unknown>
  }
}

export function LiveFeedPage() {
  const [events, setEvents] = useState<LiveEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const listRef = useRef<HTMLDivElement | null>(null)
  const seenKeysRef = useRef<Set<string>>(new Set())

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
        const key = [
          parsed.ts_iso || parsed.ts || '',
          parsed.event_type || '',
          parsed.thread_id || '',
          parsed.turn_id ?? '',
          parsed.text || '',
          parsed.gate_reason || '',
          parsed.flag_type || '',
        ].join('|')
        if (seenKeysRef.current.has(key)) return
        seenKeysRef.current.add(key)
        if (seenKeysRef.current.size > 2500) {
          const trimmed = Array.from(seenKeysRef.current).slice(-1800)
          seenKeysRef.current = new Set(trimmed)
        }
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

      <div ref={listRef} className="min-h-0 flex-1 overflow-auto rounded border border-white/10 bg-black/30 p-3 font-mono text-xs">
        {events.length === 0 ? (
          <div className="text-white/50">Waiting for events...</div>
        ) : (
          events.map((e, idx) => {
            const ts = e.ts_iso || (e.ts ? new Date(e.ts * 1000).toISOString() : '')
            const kind = (e.event_type || 'event').toLowerCase()
            const flags = e.obs?.flags ?? []
            const decisionPath = e.decision_path ?? e.obs?.decision_path ?? []
            const reflection = e.obs?.reflection
            const criticVerdict = typeof e.obs?.critic?.verdict === 'string' ? String(e.obs?.critic?.verdict) : null
            return (
              <div key={`${idx}-${ts}`} className="mb-2 border-b border-white/5 pb-2 text-white/90">
                <div className="text-[10px] text-white/50">
                  [{ts}] {kind} {e.thread_id ? `thread=${e.thread_id}` : ''} {e.sender_name ? `sender=${e.sender_name}` : ''}
                  {typeof e.turn_id === 'number' ? ` turn=${e.turn_id}` : ''}
                  {typeof e.reattempt_after_turn === 'number' ? ` reattempt_of=${e.reattempt_after_turn}` : ''}
                </div>
                <div className="whitespace-pre-wrap break-words">{e.text || ''}</div>
                {(e.gate_reason || typeof e.gates_passed === 'boolean') ? (
                  <div className="mt-1 text-[10px] text-white/50">
                    gate={e.gate_reason || 'n/a'} pass={String(Boolean(e.gates_passed))} contra={String(Boolean(e.contradiction_detected))}
                  </div>
                ) : null}
                {e.flag_type ? (
                  <div className="mt-1 text-[10px] text-rose-200/90">flag={e.flag_type}</div>
                ) : null}
                {flags.length > 0 ? (
                  <div className="mt-1 text-[10px] text-amber-200/90">flags={flags.join(', ')}</div>
                ) : null}
                {decisionPath.length > 0 ? (
                  <div className="mt-1 text-[10px] text-cyan-200/90">path={decisionPath.join(' -> ')}</div>
                ) : null}
                {(e.obs?.pipeline_statuses && e.obs.pipeline_statuses.length > 0) ? (
                  <div className="mt-1 text-[10px] text-indigo-200/90">pipeline={e.obs.pipeline_statuses.join(' | ')}</div>
                ) : null}
                {(e.obs?.response_mode || typeof e.obs?.confidence === 'number') ? (
                  <div className="mt-1 text-[10px] text-white/60">
                    mode={e.obs?.response_mode || 'n/a'} conf={typeof e.obs?.confidence === 'number' ? e.obs.confidence.toFixed(2) : 'n/a'}
                  </div>
                ) : null}
                {(e.obs?.product_mode || e.obs?.generation_provider || e.obs?.model_route?.route) ? (
                  <div className="mt-1 text-[10px] text-sky-200/90">
                    product={e.obs?.product_mode || 'n/a'} provider={e.obs?.generation_provider || e.obs?.model_route?.provider || 'n/a'} route={e.obs?.model_route?.route || 'n/a'}
                  </div>
                ) : null}
                {reflection?.trace_id ? (
                  <div className="mt-1 text-[10px] text-emerald-200/90">
                    reflection={reflection.trace_id} label={reflection.label || 'n/a'} conf={typeof reflection.confidence === 'number' ? reflection.confidence.toFixed(2) : 'n/a'}
                  </div>
                ) : null}
                {criticVerdict ? (
                  <div className="mt-1 text-[10px] text-fuchsia-200/90">critic_verdict={criticVerdict}</div>
                ) : null}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
