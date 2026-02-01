import { motion } from 'framer-motion'

export function Topbar(props: {
  onToggleSidebarMobile: () => void
  title: string
  userName: string
  userEmail: string
  apiStatus: 'checking' | 'connected' | 'disconnected'
  apiBaseUrl: string
  onChangeApiBaseUrl: (v: string) => void
  xrayMode?: boolean
  onToggleXray?: () => void
  onOpenDemoMode?: () => void
  streamingMode?: boolean
  onToggleStreaming?: () => void
}) {
  const initial = (props.userName?.trim()?.[0] || 'U').toUpperCase()
  const statusColor =
    props.apiStatus === 'connected'
      ? 'bg-emerald-400'
      : props.apiStatus === 'disconnected'
        ? 'bg-rose-400'
        : 'bg-amber-300'
  const statusLabel =
    props.apiStatus === 'connected' ? 'Online' : props.apiStatus === 'disconnected' ? 'Offline' : '...'

  return (
    <div className="flex items-center justify-between rounded-[28px] glass-panel px-3 py-2 sm:px-4 sm:py-3">
      {/* Left: Menu + Title */}
      <div className="flex items-center gap-2 sm:gap-3">
        <button
          onClick={props.onToggleSidebarMobile}
          className="rounded-xl border border-white/10 bg-white/5 p-2.5 text-lg text-white/80 hover:bg-white/10 active:bg-white/15"
          aria-label="Toggle menu"
          title="Toggle menu"
        >
          ☰
        </button>
        <div className="flex items-center gap-2">
          <div className="text-sm font-semibold text-white font-display sm:text-base">{props.title}</div>
          <span className="hidden rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-white/60 sm:inline">v1.2</span>
          <span
            title={props.apiBaseUrl ? `API: ${props.apiBaseUrl}` : 'API: (same origin)'}
            className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/70"
          >
            <span className={`h-2 w-2 rounded-full ${statusColor}`} />
            <span className="hidden xs:inline">{statusLabel}</span>
          </span>
        </div>
      </div>

      {/* Center: Search (hidden on mobile) */}
      <div className="hidden min-w-0 flex-1 justify-center px-3 md:flex">
        <div className="flex w-full max-w-[400px] items-center gap-2 rounded-2xl glass-field px-3 py-2">
          <span className="text-white/50">⌕</span>
          <input
            placeholder="Search"
            className="w-full bg-transparent text-sm text-white placeholder:text-white/40 focus:outline-none"
          />
        </div>
      </div>

      {/* Right: User + Settings */}
      <div className="flex items-center gap-2">
        {/* API Base URL input (desktop only) */}
        <div className="hidden items-center gap-2 xl:flex">
          <span className="text-xs text-white/50">API</span>
          <input
            value={props.apiBaseUrl}
            onChange={(e) => props.onChangeApiBaseUrl(e.target.value)}
            placeholder="(same origin)"
            className="w-[180px] rounded-xl glass-field px-3 py-2 text-xs text-white/80 placeholder:text-white/30 focus:outline-none"
          />
        </div>

        {/* User info (hidden on small screens) */}
        <div className="hidden min-w-0 flex-col items-end sm:flex">
          <div className="max-w-[160px] truncate text-sm font-medium text-white/90 lg:max-w-[200px]">{props.userName || 'User'}</div>
          {props.userEmail ? <div className="max-w-[160px] truncate text-xs text-white/50 lg:max-w-[200px]">{props.userEmail}</div> : null}
        </div>

        {/* User avatar */}
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.2 }}
          className="grid h-9 w-9 place-items-center rounded-full accent-button text-sm font-semibold text-white"
        >
          {initial}
        </motion.div>
      </div>
    </div>
  )
}
