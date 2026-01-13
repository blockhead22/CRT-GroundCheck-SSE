import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef } from 'react'
import type { ChatThread, QuickAction } from '../../types'
import { MessageBubble } from './MessageBubble'
import { Composer } from './Composer'
import { QuickCards } from '../QuickCards'

export function ChatThreadView(props: {
  thread: ChatThread
  typing: boolean
  onSend: (text: string) => void
  quickActions: QuickAction[]
  onPickQuickAction: (a: QuickAction) => void
  selectedMessageId: string | null
  onSelectAssistantMessage: (messageId: string) => void
}) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [props.thread.messages.length, props.typing])

  const empty = props.thread.messages.length === 0

  const hint = useMemo(() => {
    if (!empty) return null
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="w-full max-w-[760px]"
      >
        <div className="text-center">
          <div className="bg-gradient-to-r from-violet-300 via-violet-200 to-white bg-clip-text text-4xl font-semibold text-transparent md:text-5xl">
            Hello Marcus
          </div>
          <div className="mt-2 text-xl font-medium text-white/60 md:text-2xl">How can I help you today?</div>
        </div>
        <div className="mt-10">
          <QuickCards actions={props.quickActions} onPick={props.onPickQuickAction} />
        </div>
      </motion.div>
    )
  }, [empty, props.onPickQuickAction, props.quickActions])

  const selectedMessageId = props.selectedMessageId

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-hidden px-2 py-4 md:px-6">
        <div className="mx-auto flex h-full w-full max-w-[980px] gap-4">
          <div className="min-w-0 flex-1 overflow-auto">
            <div className="flex w-full flex-col gap-3">
              {hint}

              <AnimatePresence initial={false}>
                {props.thread.messages.map((m) => (
                  <div
                    key={m.id}
                    onClick={() => {
                      if (m.role === 'assistant') props.onSelectAssistantMessage(m.id)
                    }}
                    className={
                      m.role === 'assistant'
                        ? 'cursor-pointer rounded-2xl ring-1 ring-transparent hover:ring-white/10'
                        : undefined
                    }
                    title={m.role === 'assistant' ? 'Click to inspect CRT details' : undefined}
                  >
                    <MessageBubble msg={m} selected={m.id === selectedMessageId} />
                  </div>
                ))}
              </AnimatePresence>

              {props.typing ? (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18 }}
                  className="flex justify-start"
                >
                  <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/70 shadow-card">
                    <span className="inline-flex items-center gap-2">
                      <span className="h-2 w-2 animate-pulse rounded-full bg-violet-500" />
                      CRT is thinking…
                    </span>
                  </div>
                </motion.div>
              ) : null}

              <div ref={bottomRef} />
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-white/10 bg-white/5 px-4 py-4 backdrop-blur-xl">
        <div className="mx-auto w-full max-w-[980px]">
          <Composer onSend={props.onSend} />
          <div className="mt-3 text-center text-xs text-white/50">
            Join the CRT community for more insights.{' '}
            <a className="text-violet-300 hover:underline" href="#">
              Join Discord
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
