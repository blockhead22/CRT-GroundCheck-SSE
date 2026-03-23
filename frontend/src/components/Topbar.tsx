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
    <div
      className="relative flex items-center justify-between px-3 sm:px-5 h-[56px] flex-shrink-0"
      style={{
        zIndex: 100,
        borderBottom: '1px solid rgba(240,235,225,0.06)',
        background: 'rgba(14,13,11,0.8)',
      }}
    >
      {/* Left: Menu + Title */}
      <div className="flex items-center gap-2 sm:gap-3">
        <button
          onClick={props.onToggleSidebarMobile}
          className="rounded p-2 text-base text-white/40 hover:bg-white/[0.06] hover:text-white/60 transition-all"
          aria-label="Toggle menu"
          title="Toggle menu"
        >
          ☰
        </button>
        <div className="flex items-center gap-2.5">
          <div className="text-sm font-semibold text-white/90 font-display tracking-wider">{props.title}</div>
          <span className="hidden rounded-full bg-white/[0.05] px-2 py-0.5 text-[10px] text-white/30 font-mono sm:inline">v1.6</span>
          <span
            title={props.apiBaseUrl ? `API: ${props.apiBaseUrl}` : 'API: (same origin)'}
            className="inline-flex items-center gap-1.5 text-[11px] text-white/35"
          >
            <span className={`h-1.5 w-1.5 rounded-full ${statusColor}`} />
            <span className="hidden xs:inline">{statusLabel}</span>
          </span>
        </div>
      </div>

      {/* Center: Search (hidden on mobile) */}
      <div className="hidden min-w-0 flex-1 justify-center px-4 md:flex">
        <div
          className="flex w-full max-w-[320px] items-center gap-2 rounded px-3.5 py-1.5"
          style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(240,235,225,0.06)' }}
        >
          <span className="text-white/25 text-sm">⌕</span>
          <input
            placeholder="Search"
            className="w-full bg-transparent text-[13px] text-white/70 placeholder:text-white/20 focus:outline-none"
          />
        </div>
      </div>

      {/* Right: User + Settings */}
      <div className="flex items-center gap-3">
        {/* API Base URL input (desktop only) */}
        <div className="hidden items-center gap-2 xl:flex">
          <span className="text-[10px] text-white/20 font-mono tracking-wide">API</span>
          <input
            value={props.apiBaseUrl}
            onChange={(e) => props.onChangeApiBaseUrl(e.target.value)}
            placeholder="(same origin)"
            className="w-[180px] rounded px-3 py-1 text-xs text-white/50 placeholder:text-white/15 focus:outline-none font-mono"
            style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(240,235,225,0.05)' }}
          />
        </div>

        {/* Subtle divider */}
        <div className="hidden xl:block h-4 w-px bg-white/[0.06]" />

        {/* User info (hidden on small screens) */}
        <div className="hidden min-w-0 flex-col items-end sm:flex">
          <div className="max-w-[160px] truncate text-[13px] font-medium text-white/70 lg:max-w-[200px]">{props.userName || 'User'}</div>
        </div>

        {/* User avatar */}
        <div className="relative" style={{ zIndex: 9999 }}>
          <motion.button
            onClick={() => setShowSettings(!showSettings)}
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="grid h-8 w-8 place-items-center rounded-full accent-button text-xs font-semibold text-white transition-all cursor-pointer"
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
