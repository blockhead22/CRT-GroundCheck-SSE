import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { getTrustDelta, type TrustDeltaItem } from '../../lib/api'
import { cleanMemoryText } from '../../lib/memoryUtils'

/** Extract a short label from memory text — slot name or first few words */
function shortLabel(item: TrustDeltaItem): string {
  const raw = item.text_preview || ''
  const cleaned = cleanMemoryText(raw)

  // Try to extract a slot-like label: "favorite_color = orange" → "favorite_color"
  const slotMatch = cleaned.match(/^(\w[\w_]+)\s*[=:]/)
  if (slotMatch) return slotMatch[1].replace(/_/g, ' ')

  // Try to extract "My X is Y" → "X"
  const myMatch = cleaned.match(/^(?:my|your|the)\s+(.{3,20}?)(?:\s+is|\s+are|[.,])/i)
  if (myMatch) return myMatch[1].trim()

  // Fallback: first 20 chars
  return cleaned.slice(0, 20) || item.memory_id.slice(0, 8)
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

  // Sort by absolute delta descending — most significant shifts first
  const sorted = [...items].sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
  const visible = expanded ? sorted : sorted.slice(0, 4)
  const hidden = sorted.length - 4

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2, delay: 0.3 }}
      className="mt-1.5"
    >
      <div
        className="flex items-center gap-1 flex-wrap font-mono text-[10px] leading-relaxed"
        style={{ color: 'rgba(240,235,225,0.3)' }}
      >
        <span style={{ color: 'rgba(240,235,225,0.15)', fontSize: 9 }} className="uppercase tracking-widest mr-0.5">
          trust
        </span>
        {visible.map((item, i) => {
          const isUp = item.delta > 0
          const color = isUp ? '#34d399' : '#fb7185'
          const sign = isUp ? '↑' : '↓'
          const label = shortLabel(item)
          return (
            <span key={item.memory_id + item.timestamp} className="inline-flex items-center gap-0.5 cursor-default group/delta relative">
              {i > 0 && <span style={{ color: 'rgba(240,235,225,0.1)' }}> · </span>}
              <span style={{ color }}>{sign}</span>
              <span style={{ color: 'rgba(240,235,225,0.35)' }}>{label}</span>
              <span style={{ color }} className="tabular-nums">{isUp ? '+' : ''}{(item.delta * 100).toFixed(1)}%</span>
              {/* Hover tooltip */}
              <span
                className="pointer-events-none absolute bottom-full left-0 mb-1 hidden rounded px-2 py-1 whitespace-nowrap group-hover/delta:block z-50"
                style={{ background: 'rgba(18,17,16,0.95)', border: '1px solid rgba(240,235,225,0.08)', color: 'rgba(240,235,225,0.6)', fontSize: 9 }}
              >
                {item.old_trust.toFixed(3)} → {item.new_trust.toFixed(3)}
                {item.reason && <span className="ml-1" style={{ color: 'rgba(240,235,225,0.3)' }}>({item.reason})</span>}
              </span>
            </span>
          )
        })}
        {!expanded && hidden > 0 && (
          <button
            onClick={() => setExpanded(true)}
            className="hover:opacity-70 transition-opacity"
            style={{ color: 'rgba(240,235,225,0.2)' }}
          >
            +{hidden} more
          </button>
        )}
      </div>
    </motion.div>
  )
}
