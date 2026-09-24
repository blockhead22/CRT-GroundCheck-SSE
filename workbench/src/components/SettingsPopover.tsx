import { Check, MonitorUp } from 'lucide-react'
import type { Health, ModelInfo, RenderProvider, Trace } from '../types'
import type { UiMode } from '../uiMode'

interface SettingsProps {
  health: Health | null
  models: ModelInfo[]
  model: string
  renderProvider: RenderProvider
  uiMode: UiMode
  pinned: boolean
  floating: boolean
  autoApproveExactPatchApply: boolean
  trace: Trace | null
  onModel: (model: string) => void
  onRenderProvider: (provider: RenderProvider) => void
  onUiMode: (mode: UiMode) => void
  onPinned: (value: boolean) => void
  onFloating: (value: boolean) => void
  onAutoApproveExactPatchApply: (value: boolean) => void
}

export function SettingsPopover({
  health,
  models,
  model,
  renderProvider,
  uiMode,
  pinned,
  floating,
  autoApproveExactPatchApply,
  trace,
  onModel,
  onRenderProvider,
  onUiMode,
  onPinned,
  onFloating,
  onAutoApproveExactPatchApply,
}: SettingsProps) {
  const decision = trace?.completion?.route_decision || trace?.route_decision
  const recommendation = decision?.model_recommendation
  return (
    <aside className="settings-popover" aria-label="Settings panel">
      <div className="popover-title">
        <MonitorUp size={16} />
        Workbench settings
      </div>
      <label className="field-label" htmlFor="ui-mode-select">Interface</label>
      <select
        id="ui-mode-select"
        value={uiMode}
        onChange={(event) => onUiMode(event.target.value as UiMode)}
      >
        <option value="simple">Simple (recommended) — chat, Why, Knows</option>
        <option value="lab">Lab only — Process dumps, Learn, Reflect</option>
      </select>
      <p className="provider-disclosure">
        {uiMode === 'simple'
          ? 'Default product mode. Tap the green line under an answer (or Why) for a plain summary. Lab stays under More if you need it.'
          : 'Lab is for debugging. Process and full traces are noisy — switch back to Simple for everyday use.'}
      </p>
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
        <option value="grok_build">Grok via Grok CLI (hosted)</option>
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
      <button
        className="toggle-row"
        onClick={() => onAutoApproveExactPatchApply(!autoApproveExactPatchApply)}
      >
        <span>Auto-approve exact patches</span>
        <span className={`switch ${autoApproveExactPatchApply ? 'on' : ''}`}><Check size={12} /></span>
      </button>
      <p className="provider-disclosure">
        When on, ready exact file patches apply immediately after proposal.
        Default remains manual approve. Only exact hash-bound patches qualify.
      </p>
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
