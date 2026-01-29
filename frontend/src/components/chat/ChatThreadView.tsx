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
  userName: string
  showSetNameCta?: boolean
  onRequestSetName?: () => void
  selectedMessageId: string | null
  onSelectAssistantMessage: (messageId: string) => void
  onResearch?: (query: string) => void
  researching?: boolean
  onOpenSourceInspector?: (memoryId: string) => void
  onOpenAgentPanel?: (messageId: string) => void
  xrayMode?: boolean
  // Streaming props
  streamingThinking?: string
  streamingResponse?: string
  isThinking?: boolean
  streamPhase?: string | null
}) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [props.thread.messages.length, props.typing, props.streamingThinking, props.streamingResponse])

  const empty = props.thread.messages.length === 0

  const hint = useMemo(() => {
    if (!empty) return null

    const displayName = (props.userName || '').trim() || 'there'
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="w-full max-w-[760px]"
      >
        <div className="text-center">
          <div className="bg-gradient-to-r from-violet-300 via-violet-200 to-white bg-clip-text text-4xl font-semibold text-transparent md:text-5xl">
            Hello {displayName}
          </div>
          <div className="mt-2 text-xl font-medium text-white/60 md:text-2xl">How can I help you today?</div>

          {props.showSetNameCta ? (
            <div className="mt-5 flex justify-center">
              <button
                onClick={props.onRequestSetName}
                className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/80 hover:bg-white/10"
              >
                Set your name
              </button>
            </div>
          ) : null}
        </div>
        <div className="mt-10">
          <QuickCards actions={props.quickActions} onPick={props.onPickQuickAction} />
        </div>
      </motion.div>
    )
  }, [empty, props.onPickQuickAction, props.quickActions, props.userName])

  const selectedMessageId = props.selectedMessageId

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-hidden px-2 py-4 md:px-6">
        <div className="mx-auto flex h-full w-full max-w-[1180px] gap-4">
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
                    <MessageBubble
                      msg={m}
                      threadId={props.thread.id}
                      selected={m.id === selectedMessageId}
                      onOpenSourceInspector={props.onOpenSourceInspector}
                      onOpenAgentPanel={props.onOpenAgentPanel}
                      xrayMode={props.xrayMode}
                    />
                  </div>
                ))}
              </AnimatePresence>

              {/* Streaming thinking display */}
              {props.streamPhase ? (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18 }}
                  className="flex justify-start"
                >
                  <div className="rounded-2xl border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-200 shadow-card">
                    Phase: {props.streamPhase.charAt(0).toUpperCase() + props.streamPhase.slice(1)}
                  </div>
                </motion.div>
              ) : null}

              {props.isThinking && props.streamingThinking ? (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18 }}
                  className="flex justify-start"
                >
                  <div className="max-w-[85%] rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm shadow-card">
                    <div className="mb-2 flex items-center gap-2 text-amber-400">
                      <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
                      <span className="font-medium">Thinking...</span>
                    </div>
                    <div className="max-h-[200px] overflow-y-auto whitespace-pre-wrap text-white/70">
                      {props.streamingThinking}
                    </div>
                  </div>
                </motion.div>
              ) : null}

              {/* Streaming response display */}
              {props.streamingResponse && !props.isThinking ? (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18 }}
                  className="flex justify-start"
                >
                  <div className="max-w-[85%] rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/90 shadow-card">
                    <div className="whitespace-pre-wrap">{props.streamingResponse}</div>
                    <span className="ml-1 inline-block h-4 w-1 animate-pulse bg-violet-500" />
                  </div>
                </motion.div>
              ) : null}

              {/* Simple typing indicator (when not streaming) */}
              {props.typing && !props.streamingThinking && !props.streamingResponse ? (
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
        <div className="mx-auto w-full max-w-[1180px]">
          <Composer
            onSend={props.onSend}
            onResearch={props.onResearch}
            researching={props.researching}
          />
        </div>
      </div>
    </div>
  )
}
