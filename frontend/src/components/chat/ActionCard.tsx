import { motion, AnimatePresence } from 'framer-motion'
import { useState } from 'react'

/** Derive quick-reply options from the checkpoint message text or metadata */
function deriveOptions(
  text: string,
  meta?: Record<string, unknown>,
): { label: string; value: string }[] {
  // If metadata provides explicit suggested_actions, use those
  const suggested = meta?.suggested_actions as
    | { label: string; value: string }[]
    | undefined
  if (Array.isArray(suggested) && suggested.length > 0) {
    return suggested
  }

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

/** Colorize a diff line for display */
function DiffLine({ line }: { line: string }) {
  let color = 'rgba(240,235,225,0.6)'
  if (line.startsWith('+') && !line.startsWith('+++')) {
    color = 'rgba(80,200,120,0.9)'
  } else if (line.startsWith('-') && !line.startsWith('---')) {
    color = 'rgba(240,80,80,0.9)'
  } else if (line.startsWith('@@')) {
    color = 'rgba(130,170,255,0.8)'
  }
  return <div style={{ color }}>{line || '\u00A0'}</div>
}

export function ActionCard(props: {
  checkpointMessage: string
  checkpointMeta?: Record<string, unknown>
  onRespond: (text: string) => void
  onDismiss?: () => void
}) {
  // ask_user checkpoints need a typed reply, not yes/no buttons — open text mode immediately
  const isAskUser = props.checkpointMeta?.checkpoint_tier === 'ask_user' || props.checkpointMeta?.loop_suspended === true
  const [customMode, setCustomMode] = useState(isAskUser)
  const [customText, setCustomText] = useState('')
  const options = isAskUser ? [] : deriveOptions(props.checkpointMessage, props.checkpointMeta)

  const meta = props.checkpointMeta
  const diffPreview = (meta?.diff_preview as string) || ''
  const command = (meta?.command as string) || ''
  const targetPath = (meta?.target_path as string) || ''

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
        className="relative rounded-lg border px-4 py-3"
        style={{
          background: 'rgba(22,20,16,0.85)',
          borderColor: 'rgba(212,132,92,0.2)',
          boxShadow: '0 -4px 24px rgba(0,0,0,0.25), 0 0 48px rgba(212,132,92,0.04)',
        }}
      >
        {/* Dismiss / close button */}
        {props.onDismiss && (
          <button
            onClick={props.onDismiss}
            className="absolute top-2 right-2 flex h-5 w-5 items-center justify-center rounded transition-colors hover:bg-white/[0.1]"
            style={{ color: 'rgba(240,235,225,0.3)' }}
            title="Dismiss"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
        {/* ask_user label — shown when agent loop paused with a question */}
        {isAskUser && (
          <div className="mb-2 flex items-center gap-1.5 text-[11px] font-mono" style={{ color: 'rgba(212,132,92,0.6)' }}>
            <span>◆</span>
            <span className="tracking-widest uppercase text-[10px]">waiting for your reply</span>
          </div>
        )}

        {/* Screenshot preview for desktop actions */}
        {(meta?.screenshot_b64 as string) && (
          <div className="mb-3">
            <img
              src={`data:image/jpeg;base64,${meta?.screenshot_b64 as string}`}
              alt="Current desktop state"
              className="rounded border w-full"
              style={{
                borderColor: 'rgba(240,235,225,0.1)',
                maxHeight: '300px',
                objectFit: 'contain',
              }}
            />
            {(meta?.target_description as string) && (
              <div
                className="mt-1 text-[11px]"
                style={{ color: 'rgba(212,132,92,0.8)' }}
              >
                Target: {meta?.target_description as string}
              </div>
            )}
          </div>
        )}

        {/* Diff preview for file write actions */}
        {diffPreview && (
          <div className="mb-3">
            {targetPath && (
              <div
                className="mb-1.5 text-[12px] font-mono"
                style={{ color: 'rgba(240,235,225,0.5)' }}
              >
                {targetPath}
              </div>
            )}
            <pre
              className="overflow-x-auto rounded border p-2 text-[11px] font-mono leading-[1.4]"
              style={{
                background: 'rgba(0,0,0,0.3)',
                borderColor: 'rgba(240,235,225,0.06)',
                maxHeight: '240px',
                overflowY: 'auto',
              }}
            >
              {diffPreview.split('\n').map((line, i) => (
                <DiffLine key={i} line={line} />
              ))}
            </pre>
          </div>
        )}

        {/* Command preview for shell/git actions */}
        {command && !diffPreview && (
          <div className="mb-3">
            <code
              className="block rounded border px-3 py-2 text-[12px] font-mono"
              style={{
                background: 'rgba(0,0,0,0.3)',
                borderColor: 'rgba(240,235,225,0.06)',
                color: 'rgba(240,235,225,0.8)',
              }}
            >
              $ {command}
            </code>
          </div>
        )}

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
