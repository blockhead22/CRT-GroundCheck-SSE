import { Minus, PanelLeft, Pin, PinOff, Settings2, X } from 'lucide-react'

interface HeaderProps {
  connected: boolean
  pinned: boolean
  floating: boolean
  onTogglePinned: () => void
  onToggleFloating: () => void
  onToggleSettings: () => void
}

export function Header({
  connected,
  pinned,
  floating,
  onTogglePinned,
  onToggleFloating,
  onToggleSettings,
}: HeaderProps) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark">Æ</span>
        <span>AETHER</span>
      </div>
      <div className="window-tools">
        <span
          className={`connection ${connected ? 'online' : 'offline'}`}
          title={connected
            ? 'Sidecar connected on this PC'
            : 'Sidecar offline — start the Aether sidecar to chat'}
        >
          <span className="status-dot" />
          {connected ? 'On this PC' : 'Sidecar offline'}
        </span>
        <button
          aria-label={floating ? 'Dock window' : 'Float window'}
          title={floating ? 'Dock window and reserve desktop space' : 'Float window'}
          onClick={onToggleFloating}
        >
          <PanelLeft size={15} />
        </button>
        <button aria-label={pinned ? 'Disable always on top' : 'Enable always on top'} onClick={onTogglePinned}>
          {pinned ? <Pin size={15} /> : <PinOff size={15} />}
        </button>
        <button aria-label="Settings" onClick={onToggleSettings}>
          <Settings2 size={15} />
        </button>
        <button aria-label="Minimize" onClick={() => window.aetherDesktop?.minimize()}>
          <Minus size={15} />
        </button>
        <button aria-label="Hide Aether" onClick={() => window.aetherDesktop?.close()}>
          <X size={15} />
        </button>
      </div>
    </header>
  )
}
