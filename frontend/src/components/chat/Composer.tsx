import { motion } from 'framer-motion'
import { useMemo, useState } from 'react'

export function Composer(props: {
  disabled?: boolean
  placeholder?: string
  onSend: (text: string) => void
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

  return (
    <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 shadow-card backdrop-blur-xl">
      <input
        value={text}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setText(e.target.value)}
        onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
          if (e.key === 'Enter') send()
        }}
        disabled={props.disabled}
        placeholder={props.placeholder ?? 'Ask something…'}
        className="w-full bg-transparent text-sm text-white placeholder:text-white/40 focus:outline-none disabled:opacity-60"
      />
      <motion.button
        whileHover={canSend ? { scale: 1.03 } : undefined}
        whileTap={canSend ? { scale: 0.98 } : undefined}
        onClick={send}
        disabled={props.disabled || !canSend}
        className="grid h-10 w-10 place-items-center rounded-xl bg-violet-600 text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
        aria-label="Send"
        title="Send"
      >
        ➤
      </motion.button>
    </div>
  )
}
