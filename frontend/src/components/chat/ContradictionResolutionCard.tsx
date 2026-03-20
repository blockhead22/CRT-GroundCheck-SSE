import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { resolveContradiction } from '../../lib/api'

type ContraType = 'TEMPORAL' | 'CONFLICT' | 'REFINEMENT' | 'REVISION' | 'DENIAL' | string

type ResolutionOption = {
  method: string
  label: string
  description: string
  color: string
}

function getOptions(type: ContraType): ResolutionOption[] {
  switch (type?.toUpperCase()) {
    case 'TEMPORAL':
      return [
        { method: 'still_true', label: 'Still true', description: 'Old fact still holds', color: '#34d399' },
        { method: 'no_longer_true', label: 'No longer true', description: 'Newer fact supersedes', color: '#fb923c' },
        { method: 'both_temporal', label: 'Both true (different times)', description: 'Preserve both with timestamps', color: '#818cf8' },
        { method: 'leave_open', label: 'Leave open', description: 'Decide later', color: 'rgba(240,235,225,0.2)' },
      ]
    case 'REFINEMENT':
      return [
        { method: 'accept_refinement', label: 'Accept refinement', description: 'New version is more precise', color: '#34d399' },
        { method: 'keep_original', label: 'Keep original', description: 'Old version was correct', color: '#fb923c' },
        { method: 'leave_open', label: 'Leave open', description: 'Decide later', color: 'rgba(240,235,225,0.2)' },
      ]
    case 'CONFLICT':
    case 'REVISION':
    case 'DENIAL':
    default:
      return [
        { method: 'accept_new', label: 'Keep new', description: 'New memory wins', color: '#34d399' },
        { method: 'keep_old', label: 'Keep old', description: 'Original was right', color: '#fb923c' },
        { method: 'both_wrong', label: 'Both wrong', description: 'Neither is trusted', color: '#fb7185' },
        { method: 'leave_open', label: 'Leave open', description: 'Decide later', color: 'rgba(240,235,225,0.2)' },
      ]
  }
}

export function ContradictionResolutionCard({
  ledgerId,
  threadId,
  contradictionType,
  summary,
  onResolved,
}: {
  ledgerId: string
  threadId: string
  contradictionType?: string | null
  summary?: string | null
  onResolved?: (method: string) => void
}) {
  const [resolving, setResolving] = useState(false)
  const [resolved, setResolved] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const type = contradictionType || 'CONFLICT'
  const options = getOptions(type)

  async function handleResolve(method: string) {
    if (resolving || resolved) return
    setResolving(true)
    setError(null)
    try {
      await resolveContradiction({
        threadId,
        ledgerId,
        method,
        newStatus: method === 'leave_open' ? 'open' : 'resolved',
      })
      setResolved(method)
      onResolved?.(method)
    } catch (e) {
      setError('Resolution failed — try again')
    } finally {
      setResolving(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.18 }}
      className="mt-2 overflow-hidden rounded-xl"
      style={{ border: '1px solid rgba(251,146,60,0.2)', background: 'rgba(251,146,60,0.04)' }}
    >
      <div className="px-3 pt-2.5 pb-2">
        {/* Header */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: '#fb923c' }}>
            Contradiction
          </span>
          <span className="rounded px-1.5 py-0.5 text-[9px] font-mono uppercase" style={{ background: 'rgba(251,146,60,0.12)', color: '#fb923c' }}>
            {type}
          </span>
        </div>

        {summary && (
          <div className="mb-2 text-[11px] leading-relaxed" style={{ color: 'rgba(240,235,225,0.55)' }}>
            {summary}
          </div>
        )}

        {/* Resolution buttons */}
        <AnimatePresence mode="wait">
          {resolved ? (
            <motion.div
              key="done"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-[11px]"
              style={{ color: 'rgba(52,211,153,0.7)' }}
            >
              Resolved: {options.find((o) => o.method === resolved)?.label ?? resolved}
            </motion.div>
          ) : (
            <motion.div key="buttons" className="flex flex-wrap gap-1.5">
              {options.map((opt) => (
                <button
                  key={opt.method}
                  disabled={resolving}
                  onClick={() => handleResolve(opt.method)}
                  title={opt.description}
                  className="rounded-full px-2.5 py-1 text-[10px] font-medium transition-all duration-100 hover:opacity-90 disabled:opacity-40"
                  style={{
                    border: `1px solid ${opt.color}40`,
                    background: `${opt.color}10`,
                    color: opt.color,
                  }}
                >
                  {resolving ? '…' : opt.label}
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {error && (
          <div className="mt-1.5 text-[10px]" style={{ color: '#fb7185' }}>
            {error}
          </div>
        )}
      </div>
    </motion.div>
  )
}
