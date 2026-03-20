import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { listOpenContradictions, resolveContradiction, type ContradictionListItem } from '../../lib/api'

const TYPE_LABEL: Record<string, string> = {
  TEMPORAL: 'Temporal',
  CONFLICT: 'Conflict',
  REFINEMENT: 'Refinement',
  REVISION: 'Revision',
  DENIAL: 'Denial',
}

const TYPE_COLOR: Record<string, string> = {
  TEMPORAL: '#818cf8',
  CONFLICT: '#fb7185',
  REFINEMENT: '#fb923c',
  REVISION: '#facc15',
  DENIAL: '#f43f5e',
}

function ResolutionRow({ item, threadId, onResolved }: {
  item: ContradictionListItem
  threadId: string
  onResolved: (ledgerId: string) => void
}) {
  const [resolving, setResolving] = useState(false)
  const [resolved, setResolved] = useState(false)

  const type = (item.contradiction_type || 'CONFLICT').toUpperCase()
  const color = TYPE_COLOR[type] ?? '#fb923c'

  async function resolve(method: string, status = 'resolved') {
    if (resolving || resolved) return
    setResolving(true)
    try {
      await resolveContradiction({ threadId, ledgerId: item.ledger_id, method, newStatus: status })
      setResolved(true)
      onResolved(item.ledger_id)
    } catch {
      // show nothing — non-critical
    } finally {
      setResolving(false)
    }
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: resolved ? 0.3 : 1, x: 0 }}
      transition={{ duration: 0.18 }}
      className="rounded-xl p-3"
      style={{ border: '1px solid rgba(240,235,225,0.06)', background: 'rgba(240,235,225,0.02)' }}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <span className="rounded px-1.5 py-0.5 text-[9px] font-mono uppercase" style={{ background: `${color}15`, color }}>
          {TYPE_LABEL[type] ?? type}
        </span>
        <span className="text-[10px] font-mono" style={{ color: 'rgba(240,235,225,0.25)' }}>
          drift {item.drift_mean?.toFixed(2) ?? '—'}
        </span>
        {item.affects_slots && (
          <span className="text-[10px]" style={{ color: 'rgba(240,235,225,0.2)' }}>· {item.affects_slots}</span>
        )}
      </div>

      {item.summary && (
        <div className="mb-2 text-[11px] leading-relaxed" style={{ color: 'rgba(240,235,225,0.6)' }}>
          {item.summary}
        </div>
      )}

      {resolved ? (
        <div className="text-[10px]" style={{ color: 'rgba(52,211,153,0.6)' }}>Resolved</div>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {type === 'TEMPORAL' ? (
            <>
              <QuickBtn label="Still true" onClick={() => resolve('still_true')} color="#34d399" disabled={resolving} />
              <QuickBtn label="No longer true" onClick={() => resolve('no_longer_true')} color="#fb923c" disabled={resolving} />
              <QuickBtn label="Both temporal" onClick={() => resolve('both_temporal')} color="#818cf8" disabled={resolving} />
            </>
          ) : type === 'REFINEMENT' ? (
            <>
              <QuickBtn label="Accept" onClick={() => resolve('accept_refinement')} color="#34d399" disabled={resolving} />
              <QuickBtn label="Keep original" onClick={() => resolve('keep_original')} color="#fb923c" disabled={resolving} />
            </>
          ) : (
            <>
              <QuickBtn label="Keep new" onClick={() => resolve('accept_new')} color="#34d399" disabled={resolving} />
              <QuickBtn label="Keep old" onClick={() => resolve('keep_old')} color="#fb923c" disabled={resolving} />
              <QuickBtn label="Both wrong" onClick={() => resolve('both_wrong')} color="#fb7185" disabled={resolving} />
            </>
          )}
          <QuickBtn label="Leave open" onClick={() => resolve('leave_open', 'open')} color="rgba(240,235,225,0.2)" disabled={resolving} />
        </div>
      )}
    </motion.div>
  )
}

function QuickBtn({ label, onClick, color, disabled }: { label: string; onClick: () => void; color: string; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="rounded-full px-2.5 py-0.5 text-[10px] font-medium transition-opacity hover:opacity-80 disabled:opacity-40"
      style={{ border: `1px solid ${color}40`, background: `${color}10`, color }}
    >
      {label}
    </button>
  )
}

export function ContradictionDrawer({
  threadId,
  open,
  onClose,
}: {
  threadId: string
  open: boolean
  onClose: () => void
}) {
  const [items, setItems] = useState<ContradictionListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set())
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    listOpenContradictions(threadId, 50)
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [open, threadId])

  function handleResolved(ledgerId: string) {
    setResolvedIds((prev) => new Set([...prev, ledgerId]))
  }

  const visible = items.filter((i) => !resolvedIds.has(i.ledger_id))

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            ref={overlayRef}
            className="fixed inset-0 z-40"
            style={{ background: 'rgba(10,9,8,0.5)' }}
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.div
            key="drawer"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="fixed right-0 top-0 bottom-0 z-50 flex flex-col"
            style={{
              width: 'min(420px, 90vw)',
              background: 'rgba(18,17,16,0.97)',
              borderLeft: '1px solid rgba(240,235,225,0.07)',
              backdropFilter: 'blur(24px)',
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid rgba(240,235,225,0.06)' }}>
              <div>
                <div className="text-sm font-medium text-white/80">Contradiction Ledger</div>
                {!loading && (
                  <div className="text-[11px]" style={{ color: 'rgba(240,235,225,0.3)' }}>
                    {visible.length} open · {resolvedIds.size} resolved this session
                  </div>
                )}
              </div>
              <button
                onClick={onClose}
                className="rounded-lg px-2 py-1 text-[11px] transition-opacity hover:opacity-70"
                style={{ color: 'rgba(240,235,225,0.3)', border: '1px solid rgba(240,235,225,0.08)' }}
              >
                close
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
              {loading ? (
                <div className="py-8 text-center text-[12px]" style={{ color: 'rgba(240,235,225,0.2)' }}>
                  Loading…
                </div>
              ) : visible.length === 0 ? (
                <div className="py-8 text-center text-[12px]" style={{ color: 'rgba(240,235,225,0.25)' }}>
                  {resolvedIds.size > 0 ? 'All contradictions resolved this session.' : 'No open contradictions.'}
                </div>
              ) : (
                visible.map((item) => (
                  <ResolutionRow
                    key={item.ledger_id}
                    item={item}
                    threadId={threadId}
                    onResolved={handleResolved}
                  />
                ))
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
