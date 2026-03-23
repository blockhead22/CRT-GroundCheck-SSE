import { motion, AnimatePresence } from 'framer-motion'
import { useCallback, useEffect, useRef, useState } from 'react'
import { getCloudSettings, updateCloudSettings } from '../../lib/api'

type GenerationMode = 'local' | 'cloud_openai' | 'cloud_claude'

const MODEL_OPTIONS: { value: GenerationMode; label: string; shortLabel: string; icon: React.ReactNode }[] = [
  {
    value: 'local',
    label: 'Local (qwen3:14b)',
    shortLabel: 'Local',
    icon: (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
        <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
        <line x1="6" y1="6" x2="6.01" y2="6" />
        <line x1="6" y1="18" x2="6.01" y2="18" />
      </svg>
    ),
  },
  {
    value: 'cloud_openai',
    label: 'GPT-4o Mini',
    shortLabel: 'GPT-4o',
    icon: (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2L2 7l10 5 10-5-10-5z" />
        <path d="M2 17l10 5 10-5" />
        <path d="M2 12l10 5 10-5" />
      </svg>
    ),
  },
  {
    value: 'cloud_claude',
    label: 'Claude Sonnet',
    shortLabel: 'Claude',
    icon: (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M8 14s1.5 2 4 2 4-2 4-2" />
        <line x1="9" y1="9" x2="9.01" y2="9" />
        <line x1="15" y1="9" x2="15.01" y2="9" />
      </svg>
    ),
  },
]

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
  const [generationMode, setGenerationMode] = useState<GenerationMode>('local')
  const [modelSelectorOpen, setModelSelectorOpen] = useState(false)
  const [settingsLoaded, setSettingsLoaded] = useState(false)
  const selectorRef = useRef<HTMLDivElement>(null)

  const canSend = text.trim().length > 0

  // Load current generation mode from settings on mount
  useEffect(() => {
    getCloudSettings()
      .then((settings) => {
        const mode = settings.generation_mode as GenerationMode
        if (mode && ['local', 'cloud_openai', 'cloud_claude'].includes(mode)) {
          setGenerationMode(mode)
        }
        setSettingsLoaded(true)
      })
      .catch(() => {
        setSettingsLoaded(true)
      })
  }, [])

  // Close selector on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (selectorRef.current && !selectorRef.current.contains(e.target as Node)) {
        setModelSelectorOpen(false)
      }
    }
    if (modelSelectorOpen) {
      document.addEventListener('mousedown', handleClick)
      return () => document.removeEventListener('mousedown', handleClick)
    }
  }, [modelSelectorOpen])

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

  async function handleModelSelect(mode: GenerationMode) {
    setGenerationMode(mode)
    setModelSelectorOpen(false)
    try {
      await updateCloudSettings({ generation_mode: mode })
    } catch (err) {
      console.warn('[Composer] Failed to persist generation mode:', err)
    }
  }

  const isDisabled = props.disabled || props.researching
  const activeModel = MODEL_OPTIONS.find((m) => m.value === generationMode) ?? MODEL_OPTIONS[0]

  return (
    <div className="w-full px-4 pb-6 pt-2">
      <div
        className="mx-auto w-full"
        style={{ maxWidth: '760px' }}
      >
        {/* Model selector pill - above the input */}
        <div className="mb-2 flex items-center justify-start" ref={selectorRef}>
          <div className="relative">
            <button
              onClick={() => setModelSelectorOpen(!modelSelectorOpen)}
              className="flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-medium transition-all hover:bg-white/[0.06]"
              style={{
                borderColor: 'rgba(240,235,225,0.08)',
                background: 'rgba(22,20,16,0.6)',
                color: 'rgba(240,235,225,0.5)',
              }}
            >
              <span className="flex items-center gap-1.5">
                {generationMode !== 'local' && (
                  <span style={{ color: 'rgba(201,95,40,0.7)' }}>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
                    </svg>
                  </span>
                )}
                {activeModel.icon}
                <span>{activeModel.shortLabel}</span>
              </span>
              <svg
                width="8" height="8" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"
                className="ml-0.5 opacity-40"
                style={{ transform: modelSelectorOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }}
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>

            <AnimatePresence>
              {modelSelectorOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -4, scale: 0.95 }}
                  transition={{ duration: 0.12 }}
                  className="absolute left-0 top-full z-50 mt-1 min-w-[180px] overflow-hidden rounded-xl border"
                  style={{
                    borderColor: 'rgba(240,235,225,0.08)',
                    background: 'rgba(18,16,12,0.95)',
                    backdropFilter: 'blur(20px)',
                    WebkitBackdropFilter: 'blur(20px)',
                    boxShadow: '0 8px 32px rgba(0,0,0,0.5), 0 2px 8px rgba(0,0,0,0.3)',
                  }}
                >
                  {MODEL_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => handleModelSelect(opt.value)}
                      className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-[12px] transition-colors hover:bg-white/[0.06]"
                      style={{
                        color: generationMode === opt.value ? 'rgba(201,95,40,0.9)' : 'rgba(240,235,225,0.6)',
                      }}
                    >
                      <span className="flex-shrink-0">{opt.icon}</span>
                      <span className="flex-1 font-medium">{opt.label}</span>
                      {generationMode === opt.value && (
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      )}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Main input container */}
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
          className="relative overflow-hidden border"
          style={{
            background: 'rgba(22,20,16,0.8)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            borderRadius: '24px',
          }}
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
                  <path d="M5 12h14" />
                  <path d="M12 5l7 7-7 7" />
                </svg>
              </motion.button>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
