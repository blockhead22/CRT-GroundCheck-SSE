import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'

export function ProfileNameLightbox(props: {
  open: boolean
  initialName?: string
  onClose: () => void
  onSubmit: (name: string) => Promise<void> | void
}) {
  const [name, setName] = useState(props.initialName ?? '')

  useEffect(() => {
    if (props.open) setName(props.initialName ?? '')
  }, [props.open, props.initialName])

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

  const canSubmit = useMemo(() => name.trim().length > 0, [name])

  return (
    <AnimatePresence>
      {props.open ? (
        <motion.div
          key="profile-name-overlay"
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
            className="w-full max-w-[520px] overflow-hidden rounded-2xl border border-white/10 bg-[#0B0D12] shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
              <div>
                <div className="text-sm font-semibold text-white">Set your name</div>
                <div className="mt-1 text-xs text-white/60">This is stored as a CRT fact for this thread.</div>
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
              <label className="text-xs font-semibold tracking-wide text-white/60">Name</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Nick"
                className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm text-white placeholder:text-white/30 focus:outline-none"
                autoFocus
              />

              <div className="mt-5 flex items-center justify-end gap-2">
                <button
                  onClick={props.onClose}
                  className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/80 hover:bg-white/10"
                >
                  Cancel
                </button>
                <button
                  disabled={!canSubmit}
                  onClick={async () => {
                    const trimmed = name.trim()
                    if (!trimmed) return
                    await props.onSubmit(trimmed)
                  }}
                  className={
                    'rounded-xl px-4 py-2 text-sm font-semibold ' +
                    (canSubmit ? 'bg-violet-600 text-white hover:bg-violet-500' : 'bg-white/10 text-white/40')
                  }
                >
                  Save
                </button>
              </div>

              <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-white/60">
                This will send: <span className="font-mono text-white/70">FACT: name = …</span>
              </div>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
