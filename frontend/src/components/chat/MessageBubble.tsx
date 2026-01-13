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
  const gatesPassed = meta?.gates_passed
  const showMeta = isAssistant && Boolean(meta)

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
                (isBelief ? 'bg-emerald-500/15 text-emerald-200' : 'bg-white/10 text-white/80')
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
          </div>
        ) : null}

        <div className="whitespace-pre-wrap leading-6">{props.msg.text}</div>

        {/* Details moved into the right-side Inspector for less clutter. */}

        <div className={isUser ? 'mt-2 text-right text-[11px] text-white/80' : 'mt-2 text-right text-[11px] text-white/40'}>
          {formatTime(props.msg.createdAt)}
        </div>
      </div>
    </motion.div>
  )
}
