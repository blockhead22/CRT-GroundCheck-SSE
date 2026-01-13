import { motion } from 'framer-motion'
import type { ChatMessage } from '../../types'
import { formatTime } from '../../lib/time'

function pct01(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const clamped = Math.max(0, Math.min(1, v))
  return `${Math.round(clamped * 100)}%`
}

export function MessageBubble(props: { msg: ChatMessage; selected?: boolean }) {
  const isUser = props.msg.role === 'user'
  const meta = props.msg.crt
  const isAssistant = !isUser

  const responseType = (meta?.response_type ?? '').toLowerCase()
  const isBelief = responseType === 'belief'
  const isExplanation = responseType === 'explanation'
  const gatesPassed = meta?.gates_passed
  const showMeta = isAssistant && Boolean(meta)

  const grounding = (() => {
    if (!isAssistant || !meta) return null
    const pm: any[] = (meta as any).prompt_memories ?? []
    const rm: any[] = (meta as any).retrieved_memories ?? []

    const hasSystemRetrieved = rm.some((m) => String(m?.source || '').toLowerCase() === 'system')
    const hasFallbackRetrieved = rm.some((m) => String(m?.source || '').toLowerCase() === 'fallback')
    const hasNonAuditableRetrieved = rm.some((m) => {
      const s = String(m?.source || '').toLowerCase()
      return s && s !== 'user' && s !== 'external'
    })

    const factLines = pm.filter((m) => String(m?.text || '').trim().toLowerCase().startsWith('fact:'))
    const badFactSource = factLines.some((m) => {
      const s = String(m?.source || '').toLowerCase()
      return s && s !== 'user'
    })

    const responseType = String((meta as any).response_type || '').toLowerCase()
    const isExplanation = responseType === 'explanation'
    const hasDocCitation = pm.some((m) => String(m?.memory_id || '').toLowerCase().startsWith('doc:'))

    if (badFactSource || hasSystemRetrieved || hasFallbackRetrieved) {
      return { level: 'bad', reason: 'Non-auditable sources present (system/fallback or non-user FACT lines).' }
    }
    if (isExplanation && !hasDocCitation) {
      return { level: 'weak', reason: 'Explanation without doc citations.' }
    }
    if (hasNonAuditableRetrieved) {
      return { level: 'weak', reason: 'Retrieved memories include non-user sources.' }
    }
    return { level: 'ok', reason: 'Grounded in user/external memories or doc citations.' }
  })()

  const prov = (() => {
    if (!isAssistant || !meta || !(isBelief || isExplanation)) return null
    const pm = meta.prompt_memories ?? []
    const rm = meta.retrieved_memories ?? []
    const best =
      pm.find((m: any) => String(m?.memory_id || '').toLowerCase().startsWith('doc:')) ||
      pm.find((m) => (m.text || '').trim().toLowerCase().startsWith('fact:')) ||
      pm[0] ||
      rm[0]
    const text = (best?.text || '').trim()
    const id = (best as any)?.memory_id ? String((best as any).memory_id) : ''
    if (!text && !id) return null
    return { id, text }
  })()

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      className={isUser ? 'flex justify-end' : 'flex justify-start'}
    >
      <div
        className={
          'max-w-[80%] rounded-2xl px-4 py-3 text-sm shadow-card md:max-w-[70%] ' +
          (isUser
            ? 'bg-violet-600 text-white'
            : 'bg-white/5 text-white border border-white/10') +
          (props.selected ? ' ring-2 ring-violet-500/60' : '')
        }
      >
        {showMeta ? (
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span
              className={
                'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ' +
                (isBelief
                  ? 'bg-emerald-500/15 text-emerald-200'
                  : isExplanation
                    ? 'bg-sky-500/15 text-sky-200'
                    : 'bg-white/10 text-white/80')
              }
              title="CRT response type"
            >
              {isBelief ? 'BELIEF' : (responseType || 'SPEECH').toUpperCase()}
            </span>

            {typeof gatesPassed === 'boolean' ? (
              <span
                className={
                  'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ' +
                  (gatesPassed ? 'bg-emerald-500/15 text-emerald-200' : 'bg-amber-500/15 text-amber-200')
                }
                title={
                  gatesPassed
                    ? 'Reconstruction gates passed'
                    : `Reconstruction gates failed${meta?.gate_reason ? `: ${meta.gate_reason}` : ''}`
                }
              >
                {gatesPassed ? 'GATES: PASS' : 'GATES: FAIL'}
              </span>
            ) : null}

            {meta?.contradiction_detected ? (
              <span
                className="inline-flex items-center rounded-full bg-rose-500/15 px-2 py-0.5 text-[11px] font-medium text-rose-200"
                title="A contradiction was detected and recorded"
              >
                CONTRADICTION
              </span>
            ) : null}

            {grounding ? (
              <span
                className={
                  'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ' +
                  (grounding.level === 'ok'
                    ? 'bg-emerald-500/15 text-emerald-200'
                    : grounding.level === 'bad'
                      ? 'bg-rose-500/15 text-rose-200'
                      : 'bg-amber-500/15 text-amber-200')
                }
                title={grounding.reason}
              >
                {grounding.level === 'ok' ? 'GROUNDING: OK' : grounding.level === 'bad' ? 'GROUNDING: BAD' : 'GROUNDING: WEAK'}
              </span>
            ) : null}
          </div>
        ) : null}

        <div className="whitespace-pre-wrap leading-6">{props.msg.text}</div>

        {prov ? (
          <div className="mt-3 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-[11px] text-white/60">
            <div className="font-semibold tracking-wide text-white/50">{isExplanation ? 'CITATIONS' : 'PROVENANCE'}</div>
            <div className="mt-1 line-clamp-2 whitespace-pre-wrap text-white/70">
              {prov.id ? <span className="font-mono text-white/60">{prov.id}</span> : null}
              {prov.id && prov.text ? <span className="text-white/40"> · </span> : null}
              {prov.text || '—'}
            </div>
          </div>
        ) : null}

        <div className={isUser ? 'mt-2 text-right text-[11px] text-white/80' : 'mt-2 text-right text-[11px] text-white/40'}>
          {formatTime(props.msg.createdAt)}
        </div>
      </div>
    </motion.div>
  )
}
