import { AnimatePresence, motion } from 'framer-motion'
import { useMemo, useState } from 'react'
import type { ChatMessage, ChatThread } from '../types'
import { CrtInspector } from './chat/CrtInspector'

type TabId = 'history' | 'inspector'

export function RightPanel(props: {
  threads: ChatThread[]
  selectedThreadId: string | null
  onSelectThread: (id: string) => void
  selectedMessage: ChatMessage | null
  onClearSelection: () => void
}) {
  const [tab, setTab] = useState<TabId>('history')

  // Auto-switch to inspector when a message gets selected.
  useMemo(() => {
    if (props.selectedMessage) setTab('inspector')
    return null
  }, [props.selectedMessage])

  return (
    <div className="flex h-[calc(100vh-3rem)] w-[340px] flex-none flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/5 shadow-soft backdrop-blur-xl">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div className="text-sm font-semibold text-white">{tab === 'history' ? 'History' : 'Inspector'}</div>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] text-white/70">6/50</span>
        </div>
      </div>

      <div className="flex items-center gap-2 px-4 py-3">
        <button
          onClick={() => setTab('history')}
          className={
            'rounded-xl px-3 py-1.5 text-xs font-semibold ' +
            (tab === 'history' ? 'bg-violet-600 text-white' : 'bg-white/5 text-white/80 hover:bg-white/10')
          }
        >
          History
        </button>
        <button
          onClick={() => setTab('inspector')}
          className={
            'rounded-xl px-3 py-1.5 text-xs font-semibold ' +
            (tab === 'inspector' ? 'bg-violet-600 text-white' : 'bg-white/5 text-white/80 hover:bg-white/10')
          }
        >
          Inspector
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-auto px-4 pb-4">
        <AnimatePresence mode="wait" initial={false}>
          {tab === 'history' ? (
            <motion.div
              key="history"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              transition={{ duration: 0.16 }}
              className="space-y-2"
            >
              {props.threads.slice(0, 10).map((t) => {
                const selected = t.id === props.selectedThreadId
                return (
                  <button
                    key={t.id}
                    onClick={() => props.onSelectThread(t.id)}
                    className={
                      'w-full rounded-2xl border px-3 py-3 text-left transition ' +
                      (selected
                        ? 'border-violet-500/60 bg-violet-500/10'
                        : 'border-white/10 bg-white/5 hover:bg-white/10')
                    }
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 grid h-5 w-5 place-items-center rounded-md border border-white/10 bg-white/5">
                        <span className={selected ? 'text-violet-300' : 'text-white/40'}>✓</span>
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold text-white">{t.title}</div>
                        <div className="mt-0.5 line-clamp-2 text-xs text-white/60">
                          {t.messages.slice(-1)[0]?.text ?? 'New thread'}
                        </div>
                      </div>
                    </div>
                  </button>
                )
              })}

              <div className="pt-2">
                <button className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/80 hover:bg-white/10">
                  Clear history
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="inspector"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              transition={{ duration: 0.16 }}
            >
              <CrtInspector
                message={props.selectedMessage}
                onClear={props.onClearSelection}
                threadId={props.selectedThreadId ?? null}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
