import { AnimatePresence, motion } from 'framer-motion'
import { useEffect } from 'react'
import type { ChatMessage } from '../types'
import { CrtInspector } from './chat/CrtInspector'

export function InspectorLightbox(props: {
  open: boolean
  message: ChatMessage | null
  onClose: () => void
}) {
  useEffect(() => {
    if (!props.open) return
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prevOverflow
    }
  }, [props.open])

  useEffect(() => {
    if (!props.open) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') props.onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [props.open, props.onClose])

  return (
    <AnimatePresence>
      {props.open ? (
        <motion.div
          key="inspector-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.16 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) props.onClose()
          }}
        >
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.99 }}
            transition={{ duration: 0.18 }}
            className="relative w-full max-w-[820px] overflow-hidden rounded-3xl border border-white/10 bg-[#0b0f16]/80 shadow-[0_20px_70px_rgba(0,0,0,0.65)]"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
              <div>
                <div className="text-sm font-semibold text-white">Inspector</div>
                <div className="mt-0.5 text-xs text-white/50">Click outside or press Esc to close</div>
              </div>
              <button
                onClick={props.onClose}
                className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/80 hover:bg-white/10"
                aria-label="Close inspector"
                title="Close"
              >
                ✕
              </button>
            </div>

            <div className="max-h-[78vh] overflow-auto p-5">
              <CrtInspector message={props.message} onClear={props.onClose} />
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
