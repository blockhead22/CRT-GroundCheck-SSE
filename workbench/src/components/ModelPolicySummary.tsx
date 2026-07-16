import { Gauge, Shuffle, ShieldCheck } from 'lucide-react'
import type { Trace } from '../types'

export function ModelPolicySummary({ trace }: { trace: Trace | null }) {
  const decision = trace?.completion?.route_decision || trace?.route_decision
  const recommendation = decision?.model_recommendation
  if (!decision || !recommendation) {
    return (
      <div
        aria-hidden="true"
        className="model-policy-summary-placeholder"
        data-testid="model-policy-summary-placeholder"
      />
    )
  }

  return (
    <section className="model-policy-summary" aria-label="Model policy recommendation">
      <div className="model-policy-head">
        <Shuffle size={14} />
        <span>{formatValue(decision.selected_route, 'route unavailable')}</span>
        <strong>{recommendation.model_selection_changed ? 'switching' : 'no auto switch'}</strong>
      </div>
      <div className="model-policy-grid">
        <div>
          <span>Current</span>
          <strong>{formatValue(recommendation.current_selected_model)}</strong>
        </div>
        <div>
          <span>Recommended</span>
          <strong>{formatValue(recommendation.recommended_model_policy)}</strong>
        </div>
        <div>
          <span>Fallback</span>
          <strong>{formatValue(recommendation.fallback_model)}</strong>
        </div>
        <div>
          <span>Confidence</span>
          <strong>{formatValue(recommendation.confidence)}</strong>
        </div>
      </div>
      <div className="model-policy-note">
        <Gauge size={13} />
        <span>{recommendation.latency_caveat || 'No latency note for this route.'}</span>
      </div>
      <div className="model-policy-note evidence">
        <ShieldCheck size={13} />
        <span>{recommendation.evidence_path || 'No recommendation evidence path for this route.'}</span>
      </div>
    </section>
  )
}

function formatValue(value: string | null | undefined, fallback = 'not specified') {
  return value?.trim() ? value.replaceAll('_', ' ') : fallback
}
