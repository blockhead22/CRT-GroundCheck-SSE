import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'

export function ThreadRenameLightbox(props: {
  open: boolean
  initialTitle: string
  onClose: () => void
  onSubmit: (title: string) => void
}) {
  const [title, setTitle] = useState(props.initialTitle)

  useEffect(() => {
    if (props.open) setTitle(props.initialTitle)
  }, [props.open, props.initialTitle])

  const canSubmit = useMemo(() => title.trim().length > 0, [title])

  return (
    <AnimatePresence initial={false}>
      {props.open ? (
        <motion.div
          key="thread-rename-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] grid place-items-center bg-black/60 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) props.onClose()
          }}
        >
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.98 }}
            transition={{ duration: 0.18 }}
            className="w-full max-w-[520px] rounded-2xl border border-white/10 bg-[#0b0b10]/95 p-4 shadow-card backdrop-blur-xl"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-white">Rename chat</div>
                <div className="mt-1 text-xs text-white/60">This only changes the local thread title.</div>
              </div>
              <button
                onClick={props.onClose}
                className="rounded-xl border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/80 hover:bg-white/10"
                aria-label="Close"
                title="Close"
              >
                ✕
              </button>
            </div>

            <div className="mt-4">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && canSubmit) props.onSubmit(title.trim())
                }}
                placeholder="Thread title"
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none"
                autoFocus
              />
            </div>

            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                onClick={props.onClose}
                className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/80 hover:bg-white/10"
              >
                Cancel
              </button>
              <button
                disabled={!canSubmit}
                onClick={() => props.onSubmit(title.trim())}
                className="rounded-xl bg-violet-600 px-3 py-2 text-xs font-semibold text-white hover:bg-violet-500 disabled:opacity-50"
              >
                Save
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
