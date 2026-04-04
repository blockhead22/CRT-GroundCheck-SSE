import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import type { ContradictionListItem } from '../../lib/api'

interface ContradictionLedgerProps {
  open: boolean
  onClose: () => void
  contradictions: ContradictionListItem[]
  onExport?: () => void
}

export function ContradictionLedger(props: ContradictionLedgerProps) {
  const [filter, setFilter] = useState<'all' | 'disclosed' | 'pending'>('all')

  const filteredContradictions = props.contradictions.filter((c) => {
    if (filter === 'all') return true
    if (filter === 'disclosed') return c.status === 'disclosed'
    if (filter === 'pending') return c.status !== 'disclosed'
    return true
  })

  if (!props.open) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="fixed right-0 top-0 z-[1200] flex h-screen w-full max-w-xl flex-col border-l border-white/10 bg-gray-900/95 shadow-2xl backdrop-blur-xl"
      >
        {/* Header */}
        <div className="border-b border-white/10 bg-gradient-to-r from-violet-600/10 to-purple-600/10 p-6">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-violet-600/20 text-2xl">
                🔍
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">Contradiction Ledger</h2>
                <p className="text-sm text-white/60">Real-time audit trail</p>
              </div>
            </div>
            <button
              onClick={props.onClose}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-white/60 transition hover:bg-white/10 hover:text-white"
              aria-label="Close ledger"
            >
              ✕
            </button>
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl bg-white/5 p-3 text-center">
              <div className="text-2xl font-bold text-white">{props.contradictions.length}</div>
              <div className="text-xs text-white/60">Total</div>
            </div>
            <div className="rounded-xl bg-green-500/10 p-3 text-center">
              <div className="text-2xl font-bold text-green-400">
                {props.contradictions.filter((c) => c.status === 'disclosed').length}
              </div>
              <div className="text-xs text-green-300">Disclosed</div>
            </div>
            <div className="rounded-xl bg-orange-500/10 p-3 text-center">
              <div className="text-2xl font-bold text-orange-400">
                {props.contradictions.filter((c) => c.status !== 'disclosed').length}
              </div>
              <div className="text-xs text-orange-300">Pending</div>
            </div>
          </div>

          {/* Filter Buttons */}
          <div className="mt-4 flex gap-2">
            <button
              onClick={() => setFilter('all')}
              className={`flex-1 rounded-lg px-3 py-2 text-xs font-medium transition ${
                filter === 'all'
                  ? 'bg-violet-600 text-white'
                  : 'border border-white/10 bg-white/5 text-white/60 hover:bg-white/10'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilter('disclosed')}
              className={`flex-1 rounded-lg px-3 py-2 text-xs font-medium transition ${
                filter === 'disclosed'
                  ? 'bg-green-600 text-white'
                  : 'border border-white/10 bg-white/5 text-white/60 hover:bg-white/10'
              }`}
            >
              Disclosed
            </button>
            <button
              onClick={() => setFilter('pending')}
              className={`flex-1 rounded-lg px-3 py-2 text-xs font-medium transition ${
                filter === 'pending'
                  ? 'bg-orange-600 text-white'
                  : 'border border-white/10 bg-white/5 text-white/60 hover:bg-white/10'
              }`}
            >
              Pending
            </button>
          </div>
        </div>

        {/* Ledger Entries */}
        <div className="flex-1 overflow-auto p-6">
          {filteredContradictions.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="mb-4 text-6xl opacity-20">📝</div>
              <div className="text-lg font-medium text-white/60">No contradictions found</div>
              <div className="mt-2 text-sm text-white/40">
                {filter === 'all'
                  ? 'Start chatting to see contradictions appear here'
                  : `No ${filter} contradictions yet`}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <AnimatePresence>
                {filteredContradictions.map((c, index) => (
                  <motion.div
                    key={c.contradiction_id || index}
                    initial={{ opacity: 0, x: 30 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -30 }}
                    transition={{ delay: index * 0.05 }}
                    className="animate-ledgerEntryAppear rounded-2xl border border-white/10 bg-white/5 p-4 shadow-lg backdrop-blur-sm"
                  >
                    {/* Entry Header */}
                    <div className="mb-3 flex items-start justify-between">
                      <div>
                        <div className="mb-1 font-mono text-xs text-white/50">
                          {c.contradiction_id || `#c${String(index + 1).padStart(3, '0')}`}
                        </div>
                        <div className="text-sm font-semibold text-white">Slot: {c.slot}</div>
                      </div>
                      <div
                        className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                          c.status === 'disclosed'
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-orange-500/20 text-orange-400'
                        }`}
                      >
                        {c.status === 'disclosed' ? '✓ DISCLOSED' : '⚠ PENDING'}
                      </div>
                    </div>

                    {/* Values */}
                    <div className="mb-3 space-y-2 rounded-xl bg-black/30 p-3">
                      <div className="border-l-4 border-red-500 pl-3">
                        <div className="mb-1 text-xs text-white/50">Old Value:</div>
                        <div className="text-sm text-white/90">{c.old_value}</div>
                        {c.old_trust != null && (
                          <div className="mt-1 flex items-center gap-2">
                            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-white/10">
                              <div
                                className="h-full bg-red-500"
                                style={{ width: `${Math.round(c.old_trust * 100)}%` }}
                              />
                            </div>
                            <span className="text-xs text-white/50">Trust: {(c.old_trust * 100).toFixed(0)}%</span>
                          </div>
                        )}
                      </div>

                      <div className="border-l-4 border-green-500 pl-3">
                        <div className="mb-1 text-xs text-white/50">New Value:</div>
                        <div className="text-sm text-white/90">{c.new_value}</div>
                        {c.new_trust != null && (
                          <div className="mt-1 flex items-center gap-2">
                            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-white/10">
                              <div
                                className="h-full bg-green-500"
                                style={{ width: `${Math.round(c.new_trust * 100)}%` }}
                              />
                            </div>
                            <span className="text-xs text-white/50">Trust: {(c.new_trust * 100).toFixed(0)}%</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Metadata */}
                    <div className="flex flex-wrap gap-2 text-xs text-white/50">
                      {c.detected_at && <span>Detected: {new Date(c.detected_at).toLocaleDateString()}</span>}
                      {c.policy && (
                        <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-violet-300">{c.policy}</span>
                      )}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        {filteredContradictions.length > 0 && (
          <div className="border-t border-white/10 bg-black/20 p-4">
            <div className="flex gap-3">
              {props.onExport && (
                <button
                  onClick={props.onExport}
                  className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-white/80 transition hover:bg-white/10"
                >
                  📄 Export Ledger
                </button>
              )}
              <button
                onClick={props.onClose}
                className="flex-1 rounded-xl bg-gradient-to-r from-violet-600 to-purple-600 px-4 py-3 text-sm font-semibold text-white transition hover:brightness-110"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  )
}

// Badge component for showing contradiction count
export function ContradictionBadge(props: { count: number; onClick: () => void }) {
  if (props.count === 0) return null

  return (
    <motion.button
      initial={{ scale: 0 }}
      animate={{ scale: 1 }}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={props.onClick}
      className="flex items-center gap-2 rounded-full border border-orange-500/30 bg-orange-500/10 px-3 py-1.5 text-sm font-medium text-orange-300 shadow-lg transition hover:bg-orange-500/20"
    >
      <span className="animate-pulseGlow">⚠️</span>
      <span>{props.count} Contradiction{props.count !== 1 ? 's' : ''}</span>
    </motion.button>
  )
}
