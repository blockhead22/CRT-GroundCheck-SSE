import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { getTrustDelta, type TrustDeltaItem } from '../../lib/api'

function TrustPill({ item }: { item: TrustDeltaItem }) {
  const isUp = item.delta > 0
  const isDown = item.delta < 0
  const color = isUp ? '#34d399' : isDown ? '#fb7185' : 'rgba(240,235,225,0.3)'
  const sign = isUp ? '+' : ''

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85, y: 4 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="group/pill relative flex items-center gap-1.5 rounded-lg px-2 py-1 cursor-default"
      style={{ border: `1px solid ${color}25`, background: `${color}08` }}
      title={item.reason || undefined}
    >
      <span className="font-mono text-[10px] flex-shrink-0" style={{ color }}>
        {sign}{(item.delta * 100).toFixed(0)}%
      </span>
      <span className="line-clamp-1 max-w-[140px] text-[10px]" style={{ color: 'rgba(240,235,225,0.4)' }}>
        {item.text_preview || item.memory_id.slice(0, 12) + '…'}
      </span>
      {/* Hover tooltip with full trust values */}
      <div
        className="pointer-events-none absolute bottom-full left-0 mb-1 hidden rounded-lg px-2 py-1.5 text-[10px] whitespace-nowrap group-hover/pill:block z-50"
        style={{ background: 'rgba(18,17,16,0.95)', border: '1px solid rgba(240,235,225,0.08)', color: 'rgba(240,235,225,0.7)' }}
      >
        <span className="font-mono">{item.old_trust.toFixed(3)} → {item.new_trust.toFixed(3)}</span>
        {item.reason && <div className="mt-0.5" style={{ color: 'rgba(240,235,225,0.4)' }}>{item.reason}</div>}
      </div>
    </motion.div>
  )
}

export function TrustDeltaStrip({
  threadId,
  sinceTs,
}: {
  threadId: string
  sinceTs: number
}) {
  const [items, setItems] = useState<TrustDeltaItem[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    let mounted = true
    async function load() {
      try {
        const data = await getTrustDelta({ threadId, sinceTs, limit: 20 })
        if (mounted) setItems(data.filter((d) => Math.abs(d.delta) > 0.001))
      } catch {
        // silently ignore — strip is informational
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [threadId, sinceTs])

  if (loading || items.length === 0) return null

  const visible = expanded ? items : items.slice(0, 3)
  const hidden = items.length - 3

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      transition={{ duration: 0.2, delay: 0.3 }}
      className="mt-2 overflow-hidden"
    >
      <div className="flex items-center gap-1 mb-1.5">
        <span className="text-[9px] uppercase tracking-widest" style={{ color: 'rgba(240,235,225,0.2)' }}>
          trust moved
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <AnimatePresence>
          {visible.map((item) => (
            <TrustPill key={item.memory_id + item.timestamp} item={item} />
          ))}
        </AnimatePresence>
        {!expanded && hidden > 0 && (
          <button
            onClick={() => setExpanded(true)}
            className="rounded-lg px-2 py-1 text-[10px] transition-opacity hover:opacity-70"
            style={{ border: '1px solid rgba(240,235,225,0.08)', background: 'rgba(240,235,225,0.03)', color: 'rgba(240,235,225,0.3)' }}
          >
            +{hidden} more
          </button>
        )}
      </div>
    </motion.div>
  )
}
