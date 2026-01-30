import { useEffect, useMemo, useRef, useState } from 'react'
import { getEffectiveApiBaseUrl, runLoops } from '../../lib/api'

type LoopEvent = {
  id: string
  text: string
  ts: number
  tone?: 'neutral' | 'info' | 'warn'
}

const MAX_EVENTS = 400

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
  const manualRaw = typeof (scorecard as any).manual_prompt === 'string' ? (scorecard as any).manual_prompt.trim() : ''
  const manual = manualRaw ? `note: ${manualRaw.slice(0, 80)}` : null
  const parts = [extra ? `${topicText} - ${extra}` : topicText, manual].filter(Boolean).join(' - ')
  return parts
}

function summarizePersonality(profile: Record<string, unknown>): string {
  const verbosity = String((profile as any).verbosity || '--')
  const emoji = String((profile as any).emoji || '--')
  const format = String((profile as any).format || '--')
  const manualRaw = typeof (profile as any).manual_prompt === 'string' ? (profile as any).manual_prompt.trim() : ''
  const manual = manualRaw ? `note: ${manualRaw.slice(0, 80)}` : null
  return [`verbosity: ${verbosity} - emoji: ${emoji} - format: ${format}`, manual].filter(Boolean).join(' - ')
}

export function BackgroundLoopInspector(props: { threadId: string | null }) {
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState<LoopEvent[]>([])
  const [lastReflection, setLastReflection] = useState<Record<string, unknown> | null>(null)
  const [lastPersonality, setLastPersonality] = useState<Record<string, unknown> | null>(null)
  const [prompt, setPrompt] = useState('')
  const [mode, setMode] = useState<'both' | 'reflection' | 'personality'>('both')
  const [status, setStatus] = useState<{ state: 'idle' | 'running' | 'success' | 'error'; message?: string }>({
    state: 'idle',
  })
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
          setEvents((prev) => [...prev, { id: `r-${ts}-${prev.length}`, text: line, ts, tone: 'info' }].slice(-MAX_EVENTS))
          return
        }
        if (payload?.type === 'personality_profile' && payload.profile) {
          setLastPersonality(payload.profile)
          const line = `Personality updated - ${summarizePersonality(payload.profile)}`
          setEvents((prev) => [...prev, { id: `p-${ts}-${prev.length}`, text: line, ts, tone: 'neutral' }].slice(-MAX_EVENTS))
          return
        }
        if (payload?.type === 'heartbeat') {
          const line = 'heartbeat'
          setEvents((prev) => [...prev, { id: `h-${ts}-${prev.length}`, text: line, ts, tone: 'neutral' }].slice(-MAX_EVENTS))
          return
        }
        if (payload?.type === 'error') {
          const line = `Background loop error: ${payload.error || 'unknown'}`
          setEvents((prev) => [...prev, { id: `e-${ts}-${prev.length}`, text: line, ts, tone: 'warn' }].slice(-MAX_EVENTS))
        }
      } catch (_e) {
        // ignore parse errors
      }
    }

    return () => {
      es.close()
    }
  }, [props.threadId])

  async function handleRun() {
    if (!props.threadId) return
    setStatus({ state: 'running' })
    try {
      const res = await runLoops({
        thread_id: props.threadId,
        mode,
        prompt: prompt.trim() ? prompt.trim() : null,
      })
      const ran = res.ran?.length ? res.ran.join(', ') : 'loops'
      setStatus({ state: 'success', message: `Triggered: ${ran}` })
      setPrompt('')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setStatus({ state: 'error', message: msg })
    }
  }

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

      <div className="mt-3 rounded-xl border border-white/10 bg-black/20">
        <div className="px-3 pt-2 text-[11px] font-semibold uppercase tracking-wide text-white/40">Stream</div>
        <div
          ref={scrollRef}
          className="mt-2 max-h-[1400px] overflow-y-auto px-3 pb-3 text-[11px] text-white/70"
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
        <div className="border-t border-white/10 px-3 py-2">
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as typeof mode)}
              className="h-9 rounded-lg border border-white/10 bg-black/30 px-2 text-[11px] text-white/80 focus:outline-none"
            >
              <option value="both">Both</option>
              <option value="reflection">Reflection</option>
              <option value="personality">Personality</option>
            </select>
            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  void handleRun()
                }
              }}
              placeholder="Prompt note..."
              className="h-9 min-w-[220px] flex-1 rounded-lg border border-white/10 bg-black/30 px-3 text-[11px] text-white/80 placeholder:text-white/40 focus:outline-none"
            />
            <button
              onClick={handleRun}
              disabled={status.state === 'running'}
              className="h-9 rounded-lg border border-white/10 bg-white/10 px-3 text-[11px] font-semibold text-white/80 hover:bg-white/15 disabled:opacity-50"
            >
              {status.state === 'running' ? 'Running...' : 'Run'}
            </button>
          </div>
          {status.state !== 'idle' ? (
            <div
              className={
                'mt-1 text-[11px] ' +
                (status.state === 'error' ? 'text-rose-300' : status.state === 'success' ? 'text-emerald-300' : 'text-white/60')
              }
            >
              {status.message || (status.state === 'running' ? 'Triggering loop run...' : '')}
            </div>
          ) : null}
        </div>
      </div>
        </>
      )}
    </div>
  )
}
