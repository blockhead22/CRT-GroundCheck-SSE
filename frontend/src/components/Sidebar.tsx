import { AnimatePresence, motion } from 'framer-motion'
import type { ChatThread, NavId } from '../types'

const nav: Array<{ id: NavId; label: string; icon: string }> = [
  { id: 'chat', label: 'Chat', icon: '✦' },
  { id: 'dashboard', label: 'Dashboard', icon: '▦' },
  { id: 'loops', label: 'Loops', icon: 'L' },
  { id: 'showcase', label: 'Showcase', icon: '✨' },
  { id: 'jobs', label: 'Jobs', icon: '☷' },
  { id: 'docs', label: 'Docs', icon: '≣' },
]

export function Sidebar(props: {
  open: boolean
  onClose: () => void
  navActive: NavId
  onNav: (id: NavId) => void
  search: string
  onSearch: (v: string) => void
  threads: ChatThread[]
  selectedThreadId: string | null
  onSelectThread: (id: string) => void
  onNewThread: () => void
  onDeleteThread: (id: string) => void
  onRequestRenameThread: (id: string) => void
}) {
  return (
    <AnimatePresence initial={false}>
      {props.open && (
        <motion.aside
          key="sidebar"
          initial={{ x: -16, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: -16, opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="hidden h-full w-[290px] flex-none lg:flex"
        >
          <div className="flex h-full w-full flex-col rounded-2xl border border-white/10 bg-white/5 shadow-soft backdrop-blur-xl">
            <div className="flex items-center justify-between px-4 py-4">
              <div className="flex items-center gap-2">
                <div className="grid h-9 w-9 place-items-center rounded-xl bg-violet-600 text-white shadow">
                  <span className="text-sm font-semibold">Q</span>
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">CRT</div>
                  <div className="text-xs text-white/60">AI Chat Helper</div>
                </div>
              </div>
              <button
                onClick={props.onClose}
                className="rounded-xl border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/70 hover:bg-white/10"
                aria-label="Collapse sidebar"
                title="Collapse"
              >
                ⟨
              </button>
            </div>

            <div className="px-4">
              <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                <span className="text-white/50">⌕</span>
                <input
                  value={props.search}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => props.onSearch(e.target.value)}
                  placeholder="Search chat"
                  className="w-full bg-transparent text-sm text-white placeholder:text-white/40 focus:outline-none"
                />
              </div>
            </div>

            <div className="mt-4 px-2">
              <div className="px-3 pb-2 text-xs font-semibold tracking-wide text-white/60">Navigation</div>
              <div className="flex flex-col gap-1">
                {nav.map((item) => {
                  const isActive = item.id === props.navActive
                  return (
                    <button
                      key={item.id}
                      onClick={() => props.onNav(item.id)}
                      className={
                        'group flex items-center gap-3 rounded-xl px-3 py-2 text-left text-sm transition ' +
                        (isActive ? 'bg-white/10 text-white' : 'text-white/80 hover:bg-white/10')
                      }
                    >
                      <span
                        className={
                          'grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/5 text-xs ' +
                          (isActive ? 'text-violet-200' : 'text-white/50')
                        }
                      >
                        {item.icon}
                      </span>
                      <span className="font-medium">{item.label}</span>
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="mt-4 px-4">
              <div className="flex items-center justify-between">
                <div className="text-xs font-semibold tracking-wide text-white/60">Recent chats</div>
                <button onClick={props.onNewThread} className="text-xs text-white/70 hover:underline">
                  New
                </button>
              </div>

              <div className="mt-2 flex flex-col gap-2">
                {props.threads
                  .filter((t) => (props.search ? t.title.toLowerCase().includes(props.search.toLowerCase()) : true))
                  .slice(0, 8)
                  .map((t) => {
                    const selected = t.id === props.selectedThreadId
                    return (
                      <motion.button
                        whileHover={{ y: -1 }}
                        whileTap={{ scale: 0.99 }}
                        key={t.id}
                        onClick={() => props.onSelectThread(t.id)}
                        className={
                          'group rounded-xl border border-white/10 px-3 py-2 text-left ' +
                          (selected ? 'bg-white/10' : 'bg-white/5 hover:bg-white/10')
                        }
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-medium text-white">{t.title}</div>
                          </div>
                          <div className="flex flex-none items-center gap-1 opacity-0 transition group-hover:opacity-100">
                            <button
                              onClick={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                props.onRequestRenameThread(t.id)
                              }}
                              className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/70 hover:bg-white/10"
                              aria-label="Rename chat"
                              title="Rename"
                            >
                              ✎
                            </button>
                            <button
                              onClick={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                props.onDeleteThread(t.id)
                              }}
                              className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/70 hover:bg-white/10"
                              aria-label="Delete chat"
                              title="Delete"
                            >
                              ✕
                            </button>
                          </div>
                        </div>
                        <div className="text-xs text-white/50">Updated {new Date(t.updatedAt).toLocaleDateString()}</div>
                      </motion.button>
                    )
                  })}
              </div>
            </div>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
