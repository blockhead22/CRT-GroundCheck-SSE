import { useState } from 'react'
import { motion } from 'framer-motion'
import { UserSettingsPanel } from './UserSettingsPanel'

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
  selectedModel?: string
  onModelChange?: (modelId: string) => void
  onLogout?: () => void
  onOpenSettings?: () => void
}) {
  const [showSettings, setShowSettings] = useState(false)
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
    <div className="relative flex items-center justify-between glass-panel px-3 sm:px-5 h-[80px]" style={{ zIndex: 100 }}>
      {/* Left: Menu + Title */}
      <div className="flex items-center gap-2 sm:gap-3">
        <button
          onClick={props.onToggleSidebarMobile}
          className="rounded bg-white/[0.04] p-2.5 text-lg text-white/50 hover:bg-white/[0.08] hover:text-white/70 active:bg-white/[0.12] transition-all"
          aria-label="Toggle menu"
          title="Toggle menu"
        >
          ☰
        </button>
        <div className="flex items-center gap-2.5">
          <div className="text-sm font-semibold text-white font-display tracking-wider sm:text-base">{props.title}</div>
          <span className="hidden rounded-full bg-white/[0.05] px-2 py-0.5 text-[10px] text-white/30 font-mono sm:inline">v1.2</span>
          <span
            title={props.apiBaseUrl ? `API: ${props.apiBaseUrl}` : 'API: (same origin)'}
            className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.04] px-2.5 py-1 text-[11px] text-white/40"
          >
            <span className={`h-1.5 w-1.5 rounded-full ${statusColor} ${props.apiStatus === 'connected' ? 'shadow-[0_0_6px_rgba(52,211,153,0.5)]' : ''}`} />
            <span className="hidden xs:inline">{statusLabel}</span>
          </span>
        </div>
      </div>

      {/* Center: Search (hidden on mobile) */}
      <div className="hidden min-w-0 flex-1 justify-center px-4 md:flex">
        <div className="flex w-full max-w-[360px] items-center gap-2 rounded glass-field px-4 py-2">
          <span className="text-white/30 text-sm">⌕</span>
          <input
            placeholder="Search"
            className="w-full bg-transparent text-sm text-white/80 placeholder:text-white/25 focus:outline-none"
          />
        </div>
      </div>

      {/* Right: User + Settings */}
      <div className="flex items-center gap-3">
        {/* API Base URL input (desktop only) */}
        <div className="hidden items-center gap-2 xl:flex">
          <span className="text-[10px] text-white/25 font-mono tracking-wide">API</span>
          <input
            value={props.apiBaseUrl}
            onChange={(e) => props.onChangeApiBaseUrl(e.target.value)}
            placeholder="(same origin)"
            className="w-[180px] rounded glass-field px-3 py-1.5 text-xs text-white/60 placeholder:text-white/20 focus:outline-none font-mono"
          />
        </div>

        {/* Subtle divider */}
        <div className="hidden xl:block h-6 w-px bg-white/[0.06]" />

        {/* User info (hidden on small screens) */}
        <div className="hidden min-w-0 flex-col items-end sm:flex">
          <div className="max-w-[160px] truncate text-sm font-medium text-white/80 lg:max-w-[200px]">{props.userName || 'User'}</div>
        </div>

        {/* User avatar */}
        <div className="relative" style={{ zIndex: 9999 }}>
          <motion.button
            onClick={() => setShowSettings(!showSettings)}
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="grid h-9 w-9 place-items-center rounded-full accent-button text-sm font-semibold text-white shadow-[0_0_16px_rgba(212,132,92,0.25)] hover:shadow-[0_0_20px_rgba(212,132,92,0.35)] transition-all cursor-pointer"
            aria-label="User settings"
          >
            {initial}
          </motion.button>

          <UserSettingsPanel
            isOpen={showSettings}
            onClose={() => setShowSettings(false)}
            userName={props.userName}
            userEmail={props.userEmail}
            selectedModel={props.selectedModel}
            onModelChange={(modelId) => {
              props.onModelChange?.(modelId)
              setShowSettings(false)
            }}
            onLogout={props.onLogout}
            onOpenSettings={props.onOpenSettings}
          />
        </div>
      </div>
    </div>
  )
}
