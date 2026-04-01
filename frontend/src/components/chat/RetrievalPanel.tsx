import { motion, AnimatePresence } from 'framer-motion'
import { TrustBar, type TrustShift } from './TrustBar'

export type RetrievedMemory = {
  id: string
  text: string
  trust: number
  score?: number
}

/**
 * Live retrieval panel — shows retrieved memories with trust bars
 * that animate as trust_shift events arrive.
 *
 * During streaming: fully visible with live-updating bars.
 * After completion: collapses into PipelineCollapse.
 */
export function RetrievalPanel({
  memories,
  trustShifts,
  streaming,
}: {
  memories: RetrievedMemory[]
  trustShifts: TrustShift[]
  streaming?: boolean
}) {
  if (memories.length === 0) return null

  // Build a map of memory_id → latest shift
  const shiftMap = new Map<string, TrustShift>()
  for (const s of trustShifts) {
    shiftMap.set(s.memoryId, s)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className="my-2 space-y-1"
    >
      {memories.map((mem) => {
        const shift = shiftMap.get(mem.id)
        const currentTrust = shift ? shift.to : mem.trust
        const prevTrust = shift ? shift.from : undefined

        return (
          <TrustBar
            key={mem.id}
            trust={currentTrust}
            prevTrust={prevTrust}
            text={mem.text}
            reason={shift?.reason}
          />
        )
      })}

      {streaming && (
        <div className="flex items-center gap-2 text-[10px] font-mono" style={{ color: 'rgba(240,235,225,0.2)' }}>
          <span className="inline-block w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: '#E0A080' }} />
          weighing evidence...
        </div>
      )}
    </motion.div>
  )
}
