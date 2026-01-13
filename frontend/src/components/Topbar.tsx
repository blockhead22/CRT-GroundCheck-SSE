import { motion } from 'framer-motion'

export function Topbar(props: {
  onToggleSidebarMobile: () => void
  title: string
  userName: string
  userEmail: string
  apiStatus: 'checking' | 'connected' | 'disconnected'
  apiBaseUrl: string
  onChangeApiBaseUrl: (v: string) => void
}) {
  const initial = (props.userName?.trim()?.[0] || 'U').toUpperCase()
  const statusColor =
    props.apiStatus === 'connected'
      ? 'bg-emerald-400'
      : props.apiStatus === 'disconnected'
        ? 'bg-rose-400'
        : 'bg-amber-300'
  const statusLabel =
    props.apiStatus === 'connected' ? 'API: Online' : props.apiStatus === 'disconnected' ? 'API: Offline' : 'API: Checking'

  return (
    <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3 shadow-soft backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <button
          onClick={props.onToggleSidebarMobile}
          className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white/80 hover:bg-white/10 lg:hidden"
          aria-label="Toggle sidebar"
          title="Toggle sidebar"
        >
          ☰
        </button>
        <div className="flex items-center gap-2">
          <div className="text-sm font-semibold text-white">{props.title}</div>
          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/60">v1.2</span>
          <span
            title={props.apiBaseUrl ? `Base: ${props.apiBaseUrl}` : 'Base: (same origin / dev proxy)'}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/70"
          >
            <span className={`h-2 w-2 rounded-full ${statusColor}`} />
            {statusLabel}
          </span>
        </div>
      </div>

      <div className="flex min-w-0 flex-1 justify-center px-3">
        <div className="flex w-full max-w-[520px] items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
          <span className="text-white/50">⌕</span>
          <input
            placeholder="Search"
            className="w-full bg-transparent text-sm text-white placeholder:text-white/40 focus:outline-none"
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="hidden items-center gap-2 lg:flex">
          <span className="text-xs text-white/50">API base</span>
          <input
            value={props.apiBaseUrl}
            onChange={(e) => props.onChangeApiBaseUrl(e.target.value)}
            placeholder="(same origin)"
            className="w-[220px] rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/80 placeholder:text-white/30 focus:outline-none"
          />
        </div>
        <button className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white/70 hover:bg-white/10" title="Notifications">
          🔔
        </button>
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.2 }}
          className="grid h-9 w-9 place-items-center rounded-full bg-violet-600 text-sm font-semibold text-white"
        >
          {initial}
        </motion.div>
      </div>
    </div>
  )
}
