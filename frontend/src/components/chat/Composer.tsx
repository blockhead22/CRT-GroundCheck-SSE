import { motion } from 'framer-motion'
import { useMemo, useState } from 'react'

export function Composer(props: {
  disabled?: boolean
  placeholder?: string
  onSend: (text: string) => void
  onResearch?: (query: string) => void
  researching?: boolean
}) {
  const [text, setText] = useState('')

  const canSend = useMemo(() => {
    const t = text.trim()
    return Boolean(t)
  }, [text])

  function send() {
    const t = text.trim()
    if (!t) return
    props.onSend(t)
    setText('')
  }

  function research() {
    const t = text.trim()
    if (!t || !props.onResearch) return
    props.onResearch(t)
    setText('')
  }

  return (
    <div className="flex items-center gap-2 sm:gap-3 rounded-2xl glass-card px-3 py-2 sm:px-4 sm:py-3">
      <input
        value={text}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setText(e.target.value)}
        onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
          if (e.key === 'Enter') send()
        }}
        disabled={props.disabled || props.researching}
        placeholder={props.placeholder ?? 'Ask something…'}
        className="w-full min-w-0 bg-transparent text-sm sm:text-base text-white placeholder:text-white/40 focus:outline-none disabled:opacity-60"
        autoComplete="off"
        autoCorrect="off"
        spellCheck="false"
      />
      {props.onResearch ? (
        <motion.button
          whileHover={canSend && !props.researching ? { scale: 1.03 } : undefined}
          whileTap={canSend && !props.researching ? { scale: 0.95 } : undefined}
          onClick={research}
          disabled={props.disabled || !canSend || props.researching}
          className="grid h-11 w-11 sm:h-10 sm:w-10 flex-none place-items-center rounded-xl bg-sky-500 text-white hover:bg-sky-400 active:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Research"
          title="Research this topic"
        >
          {props.researching ? (
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          ) : (
            '🔍'
          )}
        </motion.button>
      ) : null}
      <motion.button
        whileHover={canSend && !props.researching ? { scale: 1.03 } : undefined}
        whileTap={canSend && !props.researching ? { scale: 0.95 } : undefined}
        onClick={send}
        disabled={props.disabled || !canSend || props.researching}
        className="grid h-11 w-11 sm:h-10 sm:w-10 flex-none place-items-center rounded-xl accent-button text-white hover:brightness-110 active:brightness-90 disabled:cursor-not-allowed disabled:opacity-50"
        aria-label="Send"
        title="Send"
      >
        ➤
      </motion.button>
    </div>
  )
}
