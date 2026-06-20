import { Check, MonitorUp } from 'lucide-react'
import type { Health, ModelInfo } from '../types'

interface SettingsProps {
  health: Health | null
  models: ModelInfo[]
  model: string
  pinned: boolean
  floating: boolean
  onModel: (model: string) => void
  onPinned: (value: boolean) => void
  onFloating: (value: boolean) => void
}

export function SettingsPopover({
  health,
  models,
  model,
  pinned,
  floating,
  onModel,
  onPinned,
  onFloating,
}: SettingsProps) {
  return (
    <aside className="settings-popover" aria-label="Settings panel">
      <div className="popover-title">
        <MonitorUp size={16} />
        Workbench settings
      </div>
      <label className="field-label" htmlFor="model-select">Local model</label>
      <select id="model-select" value={model} onChange={(event) => onModel(event.target.value)}>
        {models.length ? models.map((item) => (
          <option key={item.name} value={item.name}>{item.name}</option>
        )) : <option value={model}>{model}</option>}
      </select>
      <button className="toggle-row" onClick={() => onPinned(!pinned)}>
        <span>Always on top</span>
        <span className={`switch ${pinned ? 'on' : ''}`}><Check size={12} /></span>
      </button>
      <button className="toggle-row" onClick={() => onFloating(!floating)}>
        <span>Floating window</span>
        <span className={`switch ${floating ? 'on' : ''}`}><Check size={12} /></span>
      </button>
      <div className="service-grid">
        <span>Aether</span><strong>{health?.aether || 'checking'}</strong>
        <span>Ollama</span><strong>{health?.ollama || 'checking'}</strong>
        <span>Codex</span><strong>{health?.codex_available ? 'available' : 'unavailable'}</strong>
      </div>
    </aside>
  )
}
