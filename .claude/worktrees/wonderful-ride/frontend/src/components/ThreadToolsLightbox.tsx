import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'

export function ThreadToolsLightbox(props: {
  open: boolean
  threadId: string
  onClose: () => void
  onExport: () => Promise<void> | void
  onReset: (target: 'memory' | 'ledger' | 'all') => Promise<void> | void
}) {
  const [confirmTarget, setConfirmTarget] = useState<null | 'memory' | 'ledger' | 'all'>(null)

  useEffect(() => {
    if (!props.open) setConfirmTarget(null)
  }, [props.open])

  useEffect(() => {
    if (!props.open) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') props.onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [props.open, props.onClose])

  useEffect(() => {
    if (!props.open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [props.open])

  const confirmLabel = useMemo(() => {
    if (!confirmTarget) return ''
    return confirmTarget === 'all' ? 'Reset memory + ledger' : confirmTarget === 'memory' ? 'Reset memory' : 'Reset ledger'
  }, [confirmTarget])

  return (
    <AnimatePresence>
      {props.open ? (
        <motion.div
          key="thread-tools-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) props.onClose()
          }}
        >
          <motion.div
            initial={{ y: 12, scale: 0.98, opacity: 0 }}
            animate={{ y: 0, scale: 1, opacity: 1 }}
            exit={{ y: 12, scale: 0.98, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="w-full max-w-[560px] overflow-hidden rounded-2xl border border-white/10 bg-[#0B0D12] shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
              <div>
                <div className="text-sm font-semibold text-white">Thread tools</div>
                <div className="mt-1 text-xs text-white/60">Thread: {props.threadId}</div>
              </div>
              <button
                onClick={props.onClose}
                className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/70 hover:bg-white/10"
                title="Close"
              >
                Esc
              </button>
            </div>

            <div className="px-5 py-5">
              <div className="grid grid-cols-1 gap-3">
                <button
                  onClick={() => void props.onExport()}
                  className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-left hover:bg-white/10"
                >
                  <div className="text-sm font-semibold text-white">Download thread export (JSON)</div>
                  <div className="mt-1 text-xs text-white/60">Memories + contradictions for audit/debug.</div>
                </button>

                <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4">
                  <div className="text-sm font-semibold text-rose-100">Danger zone</div>
                  <div className="mt-1 text-xs text-rose-200/80">
                    Reset deletes the SQLite DB files for this thread. This cannot be undone.
                  </div>

                  {confirmTarget ? (
                    <div className="mt-3 flex items-center justify-between gap-2">
                      <div className="text-xs text-rose-100">Confirm: {confirmLabel}</div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setConfirmTarget(null)}
                          className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/80 hover:bg-white/10"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => void props.onReset(confirmTarget)}
                          className="rounded-xl bg-rose-600 px-3 py-2 text-xs font-semibold text-white hover:bg-rose-500"
                        >
                          Yes, reset
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
                      <button
                        onClick={() => setConfirmTarget('memory')}
                        className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/80 hover:bg-white/10"
                      >
                        Reset memory
                      </button>
                      <button
                        onClick={() => setConfirmTarget('ledger')}
                        className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/80 hover:bg-white/10"
                      >
                        Reset ledger
                      </button>
                      <button
                        onClick={() => setConfirmTarget('all')}
                        className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/80 hover:bg-white/10"
                      >
                        Reset all
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
