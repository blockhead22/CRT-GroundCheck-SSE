import { Check, MonitorUp } from 'lucide-react'
import type { Health, ModelInfo, RenderProvider, Trace } from '../types'

interface SettingsProps {
  health: Health | null
  models: ModelInfo[]
  model: string
  renderProvider: RenderProvider
  pinned: boolean
  floating: boolean
  trace: Trace | null
  onModel: (model: string) => void
  onRenderProvider: (provider: RenderProvider) => void
  onPinned: (value: boolean) => void
  onFloating: (value: boolean) => void
}

export function SettingsPopover({
  health,
  models,
  model,
  renderProvider,
  pinned,
  floating,
  trace,
  onModel,
  onRenderProvider,
  onPinned,
  onFloating,
}: SettingsProps) {
  const decision = trace?.completion?.route_decision || trace?.route_decision
  const recommendation = decision?.model_recommendation
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
      <label className="field-label" htmlFor="render-provider-select">Answer renderer</label>
      <select
        id="render-provider-select"
        value={renderProvider}
        onChange={(event) => onRenderProvider(event.target.value as RenderProvider)}
      >
        <option value="local">Local model</option>
        <option value="grok_build">Grok 4.5 via Grok CLI (hosted)</option>
      </select>
      <p className={`provider-disclosure ${renderProvider === 'grok_build' ? 'hosted' : ''}`}>
        {renderProvider === 'grok_build'
          ? 'Your governed packet is sent to Grok for rendering. Grok may contribute general knowledge for non-personal questions; Aether keeps retrieval, durable memory, tools, writes, verification, and receipts.'
          : 'Answer wording stays on this machine through Ollama.'}
      </p>
      <button className="toggle-row" onClick={() => onPinned(!pinned)}>
        <span>Always on top</span>
        <span className={`switch ${pinned ? 'on' : ''}`}><Check size={12} /></span>
      </button>
      <button className="toggle-row" onClick={() => onFloating(!floating)}>
        <span>Floating window</span>
        <span className={`switch ${floating ? 'on' : ''}`}><Check size={12} /></span>
      </button>
      <section className="settings-policy" aria-label="Route model policy">
        <div className="settings-policy-head">
          <span>Route model policy</span>
          <strong>{recommendation?.model_selection_changed ? 'switching' : 'read only'}</strong>
        </div>
        {decision && recommendation ? (
          <div className="settings-policy-grid">
            <span>Route</span><strong>{formatValue(decision.selected_route, 'route unavailable')}</strong>
            <span>Current</span><strong>{formatValue(recommendation.current_selected_model)}</strong>
            <span>Recommended</span><strong>{formatValue(recommendation.recommended_model_policy)}</strong>
            <span>Fallback</span><strong>{formatValue(recommendation.fallback_model)}</strong>
            <span>Confidence</span><strong>{formatValue(recommendation.confidence)}</strong>
            <span>Switch</span><strong>{recommendation.model_selection_changed ? 'changed' : 'no automatic switch'}</strong>
          </div>
        ) : (
          <p>No route recommendation for the active turn.</p>
        )}
      </section>
      <div className="service-grid">
        <span>Aether</span><strong>{health?.aether || 'checking'}</strong>
        <span>Ollama</span><strong>{health?.ollama || 'checking'}</strong>
        <span>Codex</span><strong>{health?.codex_available ? 'available' : 'unavailable'}</strong>
      </div>
    </aside>
  )
}

function formatValue(value: string | null | undefined, fallback = 'not specified') {
  return value?.trim() ? value.replaceAll('_', ' ') : fallback
}
