import { motion } from 'framer-motion'
import { useCallback, useEffect, useRef, useState } from 'react'

export function Composer(props: {
  disabled?: boolean
  placeholder?: string
  onSend: (text: string) => void
  onResearch?: (query: string) => void
  researching?: boolean
}) {
  const [text, setText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [focused, setFocused] = useState(false)

  const canSend = text.trim().length > 0

  // Auto-grow textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [text])

  const send = useCallback(() => {
    const t = text.trim()
    if (!t || props.disabled) return
    props.onSend(t)
    setText('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [text, props])

  const research = useCallback(() => {
    const t = text.trim()
    if (!t || !props.onResearch || props.disabled) return
    props.onResearch(t)
    setText('')
  }, [text, props])

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const isDisabled = props.disabled || props.researching

  return (
    <div className="w-full px-4 pb-6 pt-2">
      <div
        className="mx-auto w-full"
        style={{ maxWidth: '760px' }}
      >
        <motion.div
          animate={{
            boxShadow: focused
              ? '0 0 0 1px rgba(201,95,40,0.3), 0 8px 32px rgba(0,0,0,0.4), 0 0 48px rgba(201,95,40,0.06)'
              : '0 2px 12px rgba(0,0,0,0.2), 0 1px 4px rgba(0,0,0,0.15)',
            borderColor: focused
              ? 'rgba(201,95,40,0.25)'
              : 'rgba(240,235,225,0.06)',
          }}
          transition={{ duration: 0.2 }}
          className="relative overflow-hidden rounded-2xl border"
          style={{ background: 'rgba(22,20,16,0.8)', backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)' }}
        >
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            disabled={isDisabled}
            placeholder={props.placeholder ?? 'Message Aether...'}
            rows={1}
            className="w-full resize-none bg-transparent px-5 pb-3 pt-4 text-[15px] leading-relaxed text-white/90 placeholder:text-white/20 focus:outline-none disabled:opacity-50"
            style={{ scrollbarWidth: 'none' }}
            autoComplete="off"
            spellCheck="false"
          />

          {/* Bottom bar with hint + buttons */}
          <div className="flex items-center justify-between px-5 pb-3">
            <div className="text-[10px] text-white/15 font-mono">
              {canSend ? 'Enter to send' : ''}
            </div>
            <div className="flex items-center gap-2">
              {props.onResearch ? (
                <motion.button
                  whileHover={canSend && !isDisabled ? { scale: 1.05 } : undefined}
                  whileTap={canSend && !isDisabled ? { scale: 0.95 } : undefined}
                  onClick={research}
                  disabled={isDisabled || !canSend}
                  title="Deep research"
                  className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/[0.04] text-white/30 transition-all hover:bg-white/[0.08] hover:text-white/60 disabled:cursor-not-allowed disabled:opacity-20"
                >
                  {props.researching ? (
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/20 border-t-white/70" />
                  ) : (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="11" cy="11" r="8" />
                      <line x1="21" y1="21" x2="16.65" y2="16.65" />
                    </svg>
                  )}
                </motion.button>
              ) : null}

              <motion.button
                whileHover={canSend && !isDisabled ? { scale: 1.05 } : undefined}
                whileTap={canSend && !isDisabled ? { scale: 0.95 } : undefined}
                onClick={send}
                disabled={isDisabled || !canSend}
                aria-label="Send"
                className={`flex h-8 w-8 items-center justify-center rounded-xl transition-all ${
                  canSend && !isDisabled
                    ? 'bg-[var(--accent)] text-white hover:opacity-90 shadow-[0_0_16px_rgba(201,95,40,0.35)]'
                    : 'bg-white/[0.04] text-white/15 cursor-not-allowed'
                }`}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </motion.button>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
