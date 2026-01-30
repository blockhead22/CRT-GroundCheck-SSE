import { useEffect, useMemo, useRef, useState } from 'react'
import { getEffectiveApiBaseUrl } from '../../lib/api'

type LoopEvent = {
  id: string
  text: string
  ts: number
  tone?: 'neutral' | 'info' | 'warn'
}

function formatTime(ts: number): string {
  try {
    return new Date(ts * 1000).toLocaleTimeString()
  } catch (_e) {
    return '--'
  }
}

function summarizeReflection(scorecard: Record<string, unknown>): string {
  const topics = Array.isArray((scorecard as any).top_topics)
    ? (scorecard as any).top_topics.map((t: any) => t?.topic).filter(Boolean).slice(0, 3)
    : []
  const rising = Array.isArray((scorecard as any).topic_trends?.rising)
    ? (scorecard as any).topic_trends.rising.map((t: any) => t?.topic).filter(Boolean).slice(0, 2)
    : []
  const fading = Array.isArray((scorecard as any).topic_trends?.fading)
    ? (scorecard as any).topic_trends.fading.map((t: any) => t?.topic).filter(Boolean).slice(0, 2)
    : []

  const topicText = topics.length ? `topics: ${topics.join(', ')}` : 'topics: --'
  const risingText = rising.length ? `rising: ${rising.join(', ')}` : null
  const fadingText = fading.length ? `fading: ${fading.join(', ')}` : null
  const extra = [risingText, fadingText].filter(Boolean).join(' - ')
  return extra ? `${topicText} - ${extra}` : topicText
}

function summarizePersonality(profile: Record<string, unknown>): string {
  const verbosity = String((profile as any).verbosity || '--')
  const emoji = String((profile as any).emoji || '--')
  const format = String((profile as any).format || '--')
  return `verbosity: ${verbosity} - emoji: ${emoji} - format: ${format}`
}

export function BackgroundLoopInspector(props: { threadId: string | null }) {
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState<LoopEvent[]>([])
  const [lastReflection, setLastReflection] = useState<Record<string, unknown> | null>(null)
  const [lastPersonality, setLastPersonality] = useState<Record<string, unknown> | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [events])

  useEffect(() => {
    if (!props.threadId) return
    const base = getEffectiveApiBaseUrl()
    const url = `${base || ''}/api/loops/stream?thread_id=${encodeURIComponent(props.threadId)}`
    const es = new EventSource(url)

    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false)
    es.onmessage = (evt) => {
      if (!evt.data) return
      try {
        const payload = JSON.parse(evt.data)
        const ts = Number(payload?.scorecard?.updated_at || payload?.profile?.updated_at || payload?.ts || Date.now() / 1000)
        if (payload?.type === 'reflection_scorecard' && payload.scorecard) {
          setLastReflection(payload.scorecard)
          const line = `Reflection updated - ${summarizeReflection(payload.scorecard)}`
          setEvents((prev) => [...prev, { id: `r-${ts}-${prev.length}`, text: line, ts, tone: 'info' }].slice(-10))
          return
        }
        if (payload?.type === 'personality_profile' && payload.profile) {
          setLastPersonality(payload.profile)
          const line = `Personality updated - ${summarizePersonality(payload.profile)}`
          setEvents((prev) => [...prev, { id: `p-${ts}-${prev.length}`, text: line, ts, tone: 'neutral' }].slice(-10))
          return
        }
        if (payload?.type === 'error') {
          const line = `Background loop error: ${payload.error || 'unknown'}`
          setEvents((prev) => [...prev, { id: `e-${ts}-${prev.length}`, text: line, ts, tone: 'warn' }].slice(-10))
        }
      } catch (_e) {
        // ignore parse errors
      }
    }

    return () => {
      es.close()
    }
  }, [props.threadId])

  const lastReflectionTs = useMemo(() => {
    const raw = (lastReflection as any)?.updated_at
    return typeof raw === 'number' ? raw : null
  }, [lastReflection])

  const lastPersonalityTs = useMemo(() => {
    const raw = (lastPersonality as any)?.updated_at
    return typeof raw === 'number' ? raw : null
  }, [lastPersonality])

  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-white">Background Loops</div>
          <div className="mt-0.5 text-[11px] text-white/50">Reflection + personality stream</div>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span className={`h-2 w-2 rounded-full ${connected ? 'bg-emerald-400' : 'bg-white/30'}`} />
          <span className="text-white/60">{connected ? 'Live' : 'Offline'}</span>
        </div>
      </div>

      {!props.threadId ? (
        <div className="mt-3 text-xs text-white/50">Select a thread to see background loop output.</div>
      ) : (
        <>
          <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
            <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-2">
              <div className="text-white/50">Reflection</div>
              <div className="mt-1 text-white/80">
                {lastReflection ? summarizeReflection(lastReflection) : 'Waiting for update...'}
              </div>
              <div className="mt-1 text-[11px] text-white/40">
                Last: {lastReflectionTs ? formatTime(lastReflectionTs) : '--'}
              </div>
            </div>
            <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-2">
              <div className="text-white/50">Personality</div>
              <div className="mt-1 text-white/80">
                {lastPersonality ? summarizePersonality(lastPersonality) : 'Waiting for update...'}
              </div>
              <div className="mt-1 text-[11px] text-white/40">
                Last: {lastPersonalityTs ? formatTime(lastPersonalityTs) : '--'}
              </div>
            </div>
          </div>

          <div className="mt-3 rounded-xl border border-white/10 bg-black/20 px-3 py-2">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-white/40">Stream</div>
            <div
              ref={scrollRef}
              className="mt-2 max-h-[140px] overflow-y-auto pr-1 text-[11px] text-white/70 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
              style={{
                WebkitMaskImage:
                  'linear-gradient(to bottom, rgba(0,0,0,0) 0%, rgba(0,0,0,1) 25%, rgba(0,0,0,1) 80%, rgba(0,0,0,0) 100%)',
                maskImage:
                  'linear-gradient(to bottom, rgba(0,0,0,0) 0%, rgba(0,0,0,1) 25%, rgba(0,0,0,1) 80%, rgba(0,0,0,0) 100%)',
              }}
            >
              {events.length === 0 ? (
                <div className="text-white/40">No background loop events yet.</div>
              ) : (
                <ul className="space-y-1">
                  {events.map((event) => (
                    <li key={event.id} className="flex items-start gap-2">
                      <span
                        className={`mt-1 h-1.5 w-1.5 rounded-full ${
                          event.tone === 'warn' ? 'bg-rose-400' : event.tone === 'info' ? 'bg-sky-400' : 'bg-white/40'
                        }`}
                      />
                      <span className="flex-1">
                        <span className="text-white/40">{formatTime(event.ts)} - </span>
                        {event.text}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
