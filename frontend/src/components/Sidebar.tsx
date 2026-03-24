import { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type { ChatThread, NavId } from '../types'
import type { AuthUser } from '../lib/api'

const COLLAPSED_KEY = 'crt_sidebar_collapsed'

type NavItem = { id: NavId; label: string; icon: string; standalone?: boolean }
type NavSection = { heading: string; items: NavItem[] }

const navSections: NavSection[] = [
  {
    heading: 'Core',
    items: [
      { id: 'chat', label: 'Chat', icon: '✦' },
      { id: 'copilot', label: 'Aether', icon: '◈' },
      { id: 'live', label: 'Live', icon: '◉' },
    ],
  },
  {
    heading: 'Tools',
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: '▦' },
      { id: 'loops', label: 'Loops', icon: 'L' },
      { id: 'journal', label: 'Journal', icon: 'J' },
      { id: 'telemetry', label: 'Telemetry', icon: '⬡' },
      { id: 'jobs', label: 'Jobs', icon: '☷' },
    ],
  },
  {
    heading: 'System',
    items: [
      { id: 'settings', label: 'Settings', icon: '⚙' },
      { id: 'v2', label: 'V2', icon: '▸' },
      { id: 'docs', label: 'Docs', icon: '≣', standalone: true },
    ],
  },
]

// Flat list for mobile grid
const navFlat: NavItem[] = navSections.flatMap((s) => s.items)

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
  pinnedThreadIds?: string[]
  onTogglePinThread?: (id: string) => void
  isMobile?: boolean
  // API settings for mobile
  apiStatus?: 'checking' | 'connected' | 'disconnected'
  apiBaseUrl?: string
  onChangeApiBaseUrl?: (v: string) => void
  // Auth
  authUser?: AuthUser | null
  onLogout?: () => void
  onShowLogin?: () => void
}) {
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>(() => {
    try {
      const raw = localStorage.getItem(COLLAPSED_KEY)
      return raw ? JSON.parse(raw) : {}
    } catch { return {} }
  })

  useEffect(() => {
    try { localStorage.setItem(COLLAPSED_KEY, JSON.stringify(collapsedSections)) } catch {}
  }, [collapsedSections])

  const toggleSection = (heading: string) => {
    setCollapsedSections((prev) => ({ ...prev, [heading]: !prev[heading] }))
  }

  const pinnedIds = props.pinnedThreadIds ?? []
  const isPinned = (id: string) => pinnedIds.includes(id)

  const handleNavClick = (id: NavId, standalone?: boolean) => {
    if (standalone) {
      window.location.href = `/${id}`
      return
    }
    props.onNav(id)
    if (props.isMobile) props.onClose()
  }

  const handleThreadSelect = (id: string) => {
    props.onSelectThread(id)
    if (props.isMobile) props.onClose()
  }

  const sidebarContent = (
    <div className="flex h-full w-full flex-col glass-panel">
      <div className="flex items-center justify-between px-4 py-4">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded accent-button text-white shadow-[0_0_20px_rgba(212,132,92,0.3)]">
            <span className="text-sm font-bold tracking-wide">Q</span>
          </div>
          <div>
            <div className="text-base font-semibold text-white font-display tracking-wider">CRT</div>
            <div className="text-[11px] text-white/40 tracking-wide">Aether Intelligence</div>
          </div>
        </div>
        <button
          onClick={props.onClose}
          className="rounded bg-white/[0.04] px-2 py-1 text-xs text-white/40 hover:bg-white/[0.08] hover:text-white/60 transition-all"
          aria-label="Close sidebar"
          title="Close"
        >
          {props.isMobile ? '✕' : '⟨'}
        </button>
      </div>

      <div className="mt-2 px-2 overflow-y-auto flex-1">
        {/* Desktop: Grouped sections with docs-style headers */}
        {!props.isMobile && (
          <div className="flex flex-col">
            {navSections.map((section) => {
              const isCollapsed = !!collapsedSections[section.heading]
              return (
                <div key={section.heading} className="mb-4">
                  <button
                    onClick={() => toggleSection(section.heading)}
                    className="flex w-full items-center gap-1.5 px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider hover:opacity-80 transition-opacity"
                    style={{ color: '#E0A080' }}
                  >
                    <motion.span
                      animate={{ rotate: isCollapsed ? -90 : 0 }}
                      transition={{ duration: 0.15 }}
                      className="inline-block text-[9px]"
                    >
                      ▾
                    </motion.span>
                    {section.heading}
                  </button>
                  <AnimatePresence initial={false}>
                    {!isCollapsed && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.15 }}
                        className="overflow-hidden"
                      >
                        <div className="flex flex-col gap-px">
                          {section.items.map((item) => {
                            const isActive = item.id === props.navActive
                            return (
                              <button
                                key={item.id}
                                onClick={() => handleNavClick(item.id, item.standalone)}
                                className={
                                  'group relative flex items-center gap-3 rounded-r-lg px-3 py-2 text-left text-[13px] transition-all duration-200 ' +
                                  (isActive
                                    ? 'text-white/90 bg-white/[0.06]'
                                    : 'text-white/45 hover:text-white/70 hover:bg-white/[0.03]')
                                }
                                style={isActive ? { borderLeft: '2px solid #D4845C', marginLeft: '-1px' } : { marginLeft: '1px' }}
                              >
                                <span
                                  className={
                                    'text-xs transition-all duration-200 ' +
                                    (isActive ? 'text-[#E0A080]' : 'text-white/30 group-hover:text-white/50')
                                  }
                                >
                                  {item.icon}
                                </span>
                                <span className="font-medium">{item.label}</span>
                              </button>
                            )
                          })}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )
            })}
          </div>
        )}

        {/* Mobile: Grid layout for quick access */}
        {props.isMobile && (
          <div className="grid grid-cols-4 gap-2 px-1">
            {navFlat.map((item) => {
              const isActive = item.id === props.navActive
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item.id, item.standalone)}
                  className={
                    'flex flex-col items-center justify-center gap-1 rounded p-3 text-center transition ' +
                    (isActive ? 'bg-white/15 text-white' : 'bg-white/5 text-white/70 hover:bg-white/10 active:bg-white/15')
                  }
                >
                  <span
                    className={
                      'grid h-10 w-10 place-items-center rounded border border-white/10 bg-white/5 text-base ' +
                      (isActive ? 'text-violet-200' : 'text-white/50')
                    }
                  >
                    {item.icon}
                  </span>
                  <span className="text-[10px] font-medium">{item.label}</span>
                </button>
              )
            })}
          </div>
        )}

        {/* Pinned chats */}
        {(() => {
          const pinned = props.threads.filter((t) => isPinned(t.id) && (props.search ? t.title.toLowerCase().includes(props.search.toLowerCase()) : true))
          if (pinned.length === 0) return null
          return (
            <div className="mt-2 px-2" style={{ borderTop: '1px solid rgba(240,235,225,0.05)', paddingTop: '12px' }}>
              <div
                className="text-[11px] font-semibold uppercase tracking-wider px-1 mb-2"
                style={{ color: '#D4845C' }}
              >
                Pinned
              </div>
              <div className="flex flex-col gap-px">
                {pinned.map((t) => {
                  const selected = t.id === props.selectedThreadId
                  return (
                    <motion.div
                      whileTap={{ scale: 0.98 }}
                      key={t.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => handleThreadSelect(t.id)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleThreadSelect(t.id) }}
                      className={
                        'group cursor-pointer rounded-r-lg px-3 py-2.5 text-left transition-all duration-200 ' +
                        (selected
                          ? 'text-white/90 bg-white/[0.06]'
                          : 'text-white/35 hover:text-white/60 hover:bg-white/[0.03]')
                      }
                      style={selected ? { borderLeft: '2px solid #D4845C', marginLeft: '-1px' } : { marginLeft: '1px' }}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="text-[10px] text-[#D4845C]/60">📌</span>
                            <span className="truncate text-[13px] font-medium">{t.title}</span>
                          </div>
                          <div className="text-[11px] text-white/25 mt-0.5 pl-[18px]">Updated {new Date(t.updatedAt).toLocaleDateString()}</div>
                        </div>
                        <div className={`flex flex-none items-center gap-1 ${props.isMobile ? 'opacity-100' : 'opacity-0 transition-opacity duration-200 group-hover:opacity-100'}`}>
                          <button
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); props.onTogglePinThread?.(t.id) }}
                            className="rounded p-1.5 text-[11px] text-[#D4845C]/60 hover:bg-white/[0.06] hover:text-[#D4845C] transition-colors"
                            aria-label="Unpin chat"
                            title="Unpin"
                          >
                            📌
                          </button>
                          <button
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); props.onRequestRenameThread(t.id) }}
                            className="rounded p-1.5 text-[11px] text-white/30 hover:bg-white/[0.06] hover:text-white/50 transition-colors"
                            aria-label="Rename chat"
                            title="Rename"
                          >
                            ✎
                          </button>
                          <button
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); props.onDeleteThread(t.id) }}
                            className="rounded p-1.5 text-[11px] text-white/30 hover:bg-white/[0.06] hover:text-white/50 transition-colors"
                            aria-label="Delete chat"
                            title="Delete"
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  )
                })}
              </div>
            </div>
          )
        })()}

        {/* Recent chats (excludes pinned) */}
        <div className="mt-2 px-2" style={{ borderTop: '1px solid rgba(240,235,225,0.05)', paddingTop: '12px' }}>
          <div className="flex items-center justify-between mb-2">
            <div
              className="text-[11px] font-semibold uppercase tracking-wider px-1"
              style={{ color: '#5a5445' }}
            >
              Recent chats
            </div>
            <button
              onClick={() => {
                props.onNewThread()
                if (props.isMobile) props.onClose()
              }}
              className="rounded px-2.5 py-1 text-[11px] text-white/40 hover:text-white/60 hover:bg-white/[0.04] transition-all"
            >
              + New
            </button>
          </div>

          <div className="flex flex-col gap-px pb-4">
            {props.threads
              .filter((t) => !isPinned(t.id) && (props.search ? t.title.toLowerCase().includes(props.search.toLowerCase()) : true))
              .slice(0, props.isMobile ? 5 : 8)
              .map((t) => {
                const selected = t.id === props.selectedThreadId
                return (
                  <motion.div
                    whileTap={{ scale: 0.98 }}
                    key={t.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => handleThreadSelect(t.id)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleThreadSelect(t.id) }}
                    className={
                      'group cursor-pointer rounded-r-lg px-3 py-2.5 text-left transition-all duration-200 ' +
                      (selected
                        ? 'text-white/90 bg-white/[0.06]'
                        : 'text-white/35 hover:text-white/60 hover:bg-white/[0.03]')
                    }
                    style={selected ? { borderLeft: '2px solid #D4845C', marginLeft: '-1px' } : { marginLeft: '1px' }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[13px] font-medium">{t.title}</div>
                        <div className="text-[11px] text-white/25 mt-0.5">Updated {new Date(t.updatedAt).toLocaleDateString()}</div>
                      </div>
                      <div className={`flex flex-none items-center gap-1 ${props.isMobile ? 'opacity-100' : 'opacity-0 transition-opacity duration-200 group-hover:opacity-100'}`}>
                        <button
                          onClick={(e) => { e.preventDefault(); e.stopPropagation(); props.onTogglePinThread?.(t.id) }}
                          className="rounded p-1.5 text-[11px] text-white/30 hover:bg-white/[0.06] hover:text-white/50 transition-colors"
                          aria-label="Pin chat"
                          title="Pin"
                        >
                          📌
                        </button>
                        <button
                          onClick={(e) => { e.preventDefault(); e.stopPropagation(); props.onRequestRenameThread(t.id) }}
                          className="rounded p-1.5 text-[11px] text-white/30 hover:bg-white/[0.06] hover:text-white/50 transition-colors"
                          aria-label="Rename chat"
                          title="Rename"
                        >
                          ✎
                        </button>
                        <button
                          onClick={(e) => { e.preventDefault(); e.stopPropagation(); props.onDeleteThread(t.id) }}
                          className="rounded p-1.5 text-[11px] text-white/30 hover:bg-white/[0.06] hover:text-white/50 transition-colors"
                          aria-label="Delete chat"
                          title="Delete"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  </motion.div>
                )
              })}
          </div>
        </div>
      </div>
    </div>
  )

  // If this is already the mobile version, just render the content directly
  if (props.isMobile) {
    return sidebarContent
  }

  return (
    <AnimatePresence initial={false}>
      {props.open && (
        <>
          {/* Desktop sidebar */}
          <motion.aside
            key="sidebar-desktop"
            initial={{ x: -16, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -16, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="hidden h-full w-[290px] flex-none lg:flex"
          >
            {sidebarContent}
          </motion.aside>

          {/* Mobile drawer overlay */}
          <motion.div
            key="sidebar-mobile-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-black/60 lg:hidden"
            onClick={props.onClose}
          />

          {/* Mobile drawer */}
          <motion.aside
            key="sidebar-mobile"
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="fixed inset-y-0 left-0 z-50 w-[85vw] max-w-[320px] p-3 lg:hidden"
          >
            {/* Render content directly instead of recursive Sidebar call */}
            <div className="flex h-full w-full flex-col glass-panel">
              <div className="flex items-center justify-between px-4 py-4">
                <div className="flex items-center gap-2">
                  <div className="grid h-9 w-9 place-items-center rounded accent-button text-white">
                    <span className="text-sm font-semibold">Q</span>
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-white font-display">CRT</div>
                    <div className="text-xs text-white/60">AI Chat Helper</div>
                  </div>
                </div>
                <button
                  onClick={props.onClose}
                  className="rounded border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/70 hover:bg-white/10"
                  aria-label="Close sidebar"
                  title="Close"
                >
                  ✕
                </button>
              </div>

              <div className="px-4">
                <div className="flex items-center gap-2 rounded glass-field px-3 py-2">
                  <span className="text-white/50">⌕</span>
                  <input
                    value={props.search}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => props.onSearch(e.target.value)}
                    placeholder="Search chat"
                    className="w-full bg-transparent text-sm text-white placeholder:text-white/40 focus:outline-none"
                  />
                </div>
              </div>

              <div className="mt-4 px-2 overflow-y-auto flex-1">
                <div className="px-3 pb-2 text-xs font-semibold tracking-wide text-white/60">Navigation</div>
                {/* Mobile: Grid layout for quick access */}
                <div className="grid grid-cols-4 gap-2 px-1">
                  {navFlat.map((item) => {
                    const isActive = item.id === props.navActive
                    return (
                      <button
                        key={item.id}
                        onClick={() => handleNavClick(item.id, item.standalone)}
                        className={
                          'flex flex-col items-center justify-center gap-1 rounded p-3 text-center transition ' +
                          (isActive ? 'bg-white/15 text-white' : 'bg-white/5 text-white/70 hover:bg-white/10 active:bg-white/15')
                        }
                      >
                        <span
                          className={
                            'grid h-10 w-10 place-items-center rounded border border-white/10 bg-white/5 text-base ' +
                            (isActive ? 'text-violet-200' : 'text-white/50')
                          }
                        >
                          {item.icon}
                        </span>
                        <span className="text-[10px] font-medium">{item.label}</span>
                      </button>
                    )
                  })}
                </div>

                {/* User Account Section for Mobile */}
                <div className="mt-4 px-2">
                  <div className="text-xs font-semibold tracking-wide text-white/60 mb-2">Account</div>
                  <div className="rounded border border-white/10 bg-white/5 p-3">
                    {props.authUser ? (
                      <div className="space-y-3">
                        <div className="flex items-center gap-3">
                          <div className="grid h-10 w-10 place-items-center rounded-full accent-button text-sm font-semibold text-white">
                            {(props.authUser.display_name?.[0] || props.authUser.username[0] || 'U').toUpperCase()}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-white truncate">{props.authUser.display_name || props.authUser.username}</div>
                            <div className="text-xs text-white/50">@{props.authUser.username}</div>
                          </div>
                        </div>
                        <button
                          onClick={() => {
                            props.onLogout?.()
                            props.onClose()
                          }}
                          className="w-full rounded bg-white/10 px-3 py-2 text-xs text-white/70 hover:bg-white/15 active:bg-white/20"
                        >
                          Logout
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <p className="text-xs text-white/50">Login to sync chats across devices</p>
                        <button
                          onClick={() => {
                            props.onShowLogin?.()
                            props.onClose()
                          }}
                          className="w-full rounded accent-button px-3 py-2 text-xs font-medium text-white"
                        >
                          Login / Register
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* API Settings for Mobile */}
              <div className="mt-4 px-2">
                <div className="text-xs font-semibold tracking-wide text-white/60 mb-2">API Settings</div>
                <div className="rounded border border-white/10 bg-white/5 p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`h-2 w-2 rounded-full ${
                      props.apiStatus === 'connected' ? 'bg-emerald-400' :
                      props.apiStatus === 'disconnected' ? 'bg-rose-400' : 'bg-amber-300'
                    }`} />
                    <span className="text-xs text-white/70">
                      {props.apiStatus === 'connected' ? 'Connected' :
                       props.apiStatus === 'disconnected' ? 'Disconnected' : 'Checking...'}
                    </span>
                  </div>
                  <input
                    value={props.apiBaseUrl || ''}
                    onChange={(e) => props.onChangeApiBaseUrl?.(e.target.value)}
                    placeholder="API URL (e.g. http://192.168.1.91:8123)"
                    className="w-full rounded glass-field px-3 py-2 text-xs text-white/80 placeholder:text-white/30 focus:outline-none"
                  />
                </div>
              </div>

              <div className="mt-4 px-2">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-semibold tracking-wide text-white/60">Recent chats</div>
                    <button 
                      onClick={() => {
                        props.onNewThread()
                        props.onClose()
                      }} 
                      className="rounded bg-white/10 px-3 py-1 text-xs text-white/70 hover:bg-white/15 active:bg-white/20"
                    >
                      + New
                    </button>
                  </div>

                  <div className="mt-2 flex flex-col gap-2 pb-4">
                    {props.threads
                      .filter((t) => (props.search ? t.title.toLowerCase().includes(props.search.toLowerCase()) : true))
                      .slice(0, 5)
                      .map((t) => {
                        const selected = t.id === props.selectedThreadId
                        return (
                          <motion.div
                            whileTap={{ scale: 0.98 }}
                            key={t.id}
                            role="button"
                            tabIndex={0}
                            onClick={() => handleThreadSelect(t.id)}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleThreadSelect(t.id) }}
                            className={
                              'group cursor-pointer rounded border border-white/10 px-3 py-3 text-left active:bg-white/15 ' +
                              (selected ? 'bg-white/10' : 'bg-white/5 hover:bg-white/10')
                            }
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div className="min-w-0 flex-1">
                                <div className="truncate text-sm font-medium text-white">{t.title}</div>
                                <div className="text-xs text-white/50 mt-0.5">Updated {new Date(t.updatedAt).toLocaleDateString()}</div>
                              </div>
                              <div className="flex flex-none items-center gap-1">
                                <button
                                  onClick={(e) => {
                                    e.preventDefault()
                                    e.stopPropagation()
                                    props.onRequestRenameThread(t.id)
                                  }}
                                  className="rounded border border-white/10 bg-white/5 p-2 text-[11px] text-white/70 hover:bg-white/10 active:bg-white/15"
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
                                  className="rounded border border-white/10 bg-white/5 p-2 text-[11px] text-white/70 hover:bg-white/10 active:bg-white/15"
                                  aria-label="Delete chat"
                                  title="Delete"
                                >
                                  ✕
                                </button>
                              </div>
                            </div>
                          </motion.div>
                        )
                      })}
                  </div>
                </div>
              </div>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
