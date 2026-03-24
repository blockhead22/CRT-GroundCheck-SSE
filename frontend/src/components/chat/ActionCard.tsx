import { motion, AnimatePresence } from 'framer-motion'
import { useState } from 'react'

/** Derive quick-reply options from the checkpoint message text */
function deriveOptions(text: string): { label: string; value: string }[] {
  const lower = (text || '').toLowerCase()

  // Permission / go-ahead patterns → action-oriented buttons
  if (
    /\bgo ahead\b/.test(lower) ||
    /\bshould I\b/.test(lower) ||
    /\bshall I\b/.test(lower) ||
    /\bproceed\b/.test(lower) ||
    /\bwant me to\b/.test(lower) ||
    /\bok to\b/.test(lower) ||
    /\bcan I\b/.test(lower) ||
    /\bquery\b/.test(lower) ||
    /\bfetch\b/.test(lower) ||
    /\bexecute\b/.test(lower)
  ) {
    return [
      { label: 'Yes, go ahead', value: 'Yes, go ahead' },
      { label: 'No, skip it', value: 'No, skip it' },
    ]
  }

  return [
    { label: 'Yes', value: 'Yes' },
    { label: 'No', value: 'No' },
  ]
}

export function ActionCard(props: {
  checkpointMessage: string
  checkpointMeta?: Record<string, unknown>
  onRespond: (text: string) => void
}) {
  const [customMode, setCustomMode] = useState(false)
  const [customText, setCustomText] = useState('')
  const options = deriveOptions(props.checkpointMessage)

  function sendCustom() {
    const t = customText.trim()
    if (!t) return
    props.onRespond(t)
    setCustomText('')
    setCustomMode(false)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.97 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="mx-auto w-full px-4"
      style={{ maxWidth: '760px' }}
    >
      <div
        className="rounded-lg border px-4 py-3"
        style={{
          background: 'rgba(22,20,16,0.85)',
          borderColor: 'rgba(212,132,92,0.2)',
          boxShadow: '0 -4px 24px rgba(0,0,0,0.25), 0 0 48px rgba(212,132,92,0.04)',
        }}
      >
        {/* Quick reply buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          {options.map((opt) => (
            <motion.button
              key={opt.value}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => props.onRespond(opt.value)}
              className="rounded-full border px-4 py-1.5 text-[13px] font-medium transition-colors hover:bg-white/[0.08]"
              style={{
                borderColor: 'rgba(212,132,92,0.3)',
                color: 'rgba(240,235,225,0.8)',
                background: 'rgba(212,132,92,0.08)',
              }}
            >
              {opt.label}
            </motion.button>
          ))}

          {/* Custom reply toggle / input */}
          <AnimatePresence mode="wait">
            {!customMode ? (
              <motion.button
                key="toggle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => setCustomMode(true)}
                className="rounded-full border px-3 py-1.5 text-[13px] transition-colors hover:bg-white/[0.06]"
                style={{
                  borderColor: 'rgba(240,235,225,0.08)',
                  color: 'rgba(240,235,225,0.4)',
                }}
              >
                Other...
              </motion.button>
            ) : (
              <motion.div
                key="input"
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.15 }}
                className="flex items-center gap-1.5 overflow-hidden"
              >
                <input
                  autoFocus
                  value={customText}
                  onChange={(e) => setCustomText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') sendCustom()
                    if (e.key === 'Escape') { setCustomMode(false); setCustomText('') }
                  }}
                  placeholder="Type a response..."
                  className="rounded-full border bg-transparent px-3 py-1.5 text-[13px] text-white/80 placeholder:text-white/20 focus:outline-none"
                  style={{
                    borderColor: 'rgba(212,132,92,0.25)',
                    minWidth: '160px',
                  }}
                />
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={sendCustom}
                  disabled={!customText.trim()}
                  className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full transition-all"
                  style={{
                    background: customText.trim() ? 'rgba(212,132,92,0.9)' : 'rgba(212,132,92,0.2)',
                    color: customText.trim() ? '#fff' : 'rgba(255,255,255,0.3)',
                  }}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14" />
                    <path d="M12 5l7 7-7 7" />
                  </svg>
                </motion.button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  )
}
