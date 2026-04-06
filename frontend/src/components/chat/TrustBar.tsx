import { motion } from 'framer-motion'
import { cleanMemoryText } from '../../lib/memoryUtils'

export type TrustShift = {
  memoryId: string
  from: number
  to: number
  reason?: string
  text?: string
}

/**
 * Animated horizontal trust bar for a single memory.
 *
 * Shows trust score, bar fill, optional delta arrow, and truncated memory text.
 */
export function TrustBar({
  trust,
  prevTrust,
  text,
  reason,
  compact,
}: {
  trust: number
  prevTrust?: number
  text?: string
  reason?: string
  compact?: boolean
}) {
  const pct = Math.min(Math.max(trust, 0), 1) * 100
  const shifted = prevTrust != null && Math.abs(trust - prevTrust) > 0.005
  const delta = shifted ? trust - prevTrust! : 0

  // Color based on trust level
  const barColor =
    trust >= 0.8 ? '#34d399'
    : trust >= 0.5 ? '#E0A080'
    : trust >= 0.3 ? '#d4a84b'
    : '#D47058'

  const deltaColor = delta > 0 ? '#34d399' : '#D47058'

  return (
    <div className={`flex items-center gap-2 ${compact ? 'text-[10px]' : 'text-[11px]'} font-mono`}>
      {/* Trust score */}
      <span className="flex-shrink-0 w-[3.5em] text-right" style={{ color: barColor }}>
        T:{trust.toFixed(2)}
      </span>

      {/* Bar */}
      <div className="flex-1 h-[6px] rounded-full overflow-hidden" style={{ background: 'rgba(240,235,225,0.06)', maxWidth: compact ? '80px' : '120px' }}>
        <motion.div
          className="h-full rounded-full"
          style={{ background: barColor }}
          initial={{ width: prevTrust != null ? `${prevTrust * 100}%` : `${pct}%` }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>

      {/* Delta arrow */}
      {shifted && (
        <motion.span
          initial={{ opacity: 0, x: -4 }}
          animate={{ opacity: 1, x: 0 }}
          className="flex-shrink-0"
          style={{ color: deltaColor }}
        >
          {delta > 0 ? '\u25B2' : '\u25BC'}
        </motion.span>
      )}

      {/* Memory text preview */}
      {text && (
        <span
          className="truncate flex-1"
          style={{ color: 'rgba(240,235,225,0.35)' }}
          title={text}
        >
          {(() => { const c = cleanMemoryText(text); return c.length > 60 ? c.slice(0, 60) + '\u2026' : c })()}
        </span>
      )}

      {/* Reason tag */}
      {reason && shifted && (
        <span className="flex-shrink-0" style={{ color: 'rgba(240,235,225,0.2)' }}>
          {'\u2190'} {reason}
        </span>
      )}
    </div>
  )
}
