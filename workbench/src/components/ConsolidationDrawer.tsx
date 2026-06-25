import { ArrowRight, GitBranch, RefreshCcw, Route, ShieldCheck } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import type { ConsolidationCandidate, ConsolidationPreview } from '../types'

function surfaceLabel(surface: string) {
  return surface.replace('_', ' ')
}

function candidateTone(item: ConsolidationCandidate) {
  if (item.category === 'contradiction_review') return 'proposed'
  if (item.category === 'aether_self_improvement') return 'accepted'
  if (item.category === 'support_style_candidate') return 'deferred'
  return ''
}

type ReviewSurface = 'memory' | 'support' | 'reflect'

interface ConsolidationDrawerProps {
  onOpenReviewSurface?: (surface: ReviewSurface, options?: { slotId?: string }) => void
}

function routeSurface(surface?: string): ReviewSurface | null {
  if (surface === 'memory') return 'memory'
  if (surface === 'support_patterns') return 'support'
  if (surface === 'reflections') return 'reflect'
  return null
}

function routeLabel(surface: ReviewSurface) {
  if (surface === 'memory') return 'Open Memory'
  if (surface === 'support') return 'Open Support'
  return 'Open Reflect'
}

function draftPreview(item: ConsolidationCandidate) {
  if (!item.review_route?.draft) return ''
  return JSON.stringify({
    endpoint: item.review_route.endpoint || item.review_route.surface,
    adapter_required: Boolean(item.review_route.requires_adapter),
    payload: item.review_route.draft,
  }, null, 2)
}

export function ConsolidationDrawer({ onOpenReviewSurface }: ConsolidationDrawerProps) {
  const [preview, setPreview] = useState<ConsolidationPreview | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    setError('')
    try {
      setPreview(await api.consolidationCandidates())
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not load consolidation candidates.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const counts = useMemo(() => {
    const result = new Map<string, number>()
    for (const item of preview?.candidates || []) {
      const surface = item.review_route?.surface || 'unknown'
      result.set(surface, (result.get(surface) || 0) + 1)
    }
    return [...result.entries()]
  }, [preview])

  if (!preview?.candidates.length && !error) {
    return (
      <div className="drawer-empty">
        <GitBranch size={26} />
        <h3>No learner candidates</h3>
        <p>Recent traces have not produced reviewable consolidation candidates yet.</p>
        <button className="drawer-empty-action" disabled={loading} onClick={() => void load()}>
          <RefreshCcw size={13} />Refresh
        </button>
      </div>
    )
  }

  return (
    <div className="consolidation-browser">
      <div className="reflection-intro">
        Consolidation candidates are preview-only learner suggestions. They do not write memory, support patterns, or reflections.
      </div>
      <div className="consolidation-toolbar">
        <div>
          <span>{preview?.inspected_turn_count || 0}</span>
          <small>turns inspected</small>
        </div>
        {counts.map(([surface, count]) => (
          <div key={surface}>
            <span>{count}</span>
            <small>{surfaceLabel(surface)}</small>
          </div>
        ))}
        <button disabled={loading} onClick={() => void load()}><RefreshCcw size={13} />Refresh</button>
      </div>
      {preview ? (
        <div className="consolidation-safety" aria-label="Consolidation safety">
          <span><ShieldCheck size={12} />{preview.mode.replace('_', ' ')}</span>
          <span>writes {preview.writes_performed ? 'yes' : 'no'}</span>
          <span>memory {preview.memory_ingestion_performed ? 'yes' : 'no'}</span>
          <span>support import {preview.support_pattern_import_performed ? 'yes' : 'no'}</span>
          <span>reflection create {preview.reflection_create_performed ? 'yes' : 'no'}</span>
        </div>
      ) : null}
      {error ? <div className="inline-notice">{error}</div> : null}
      <div className="reflection-list">
        {(preview?.candidates || []).map((item) => (
          <article className={`reflection-card ${candidateTone(item)}`} key={item.candidate_id}>
            {(() => {
              const draft = draftPreview(item)
              return (
                <>
            <div className="reflection-head">
              <span>{item.category.replaceAll('_', ' ')}</span>
              <strong>{surfaceLabel(item.review_route?.surface || 'unknown')}</strong>
            </div>
            <label>Candidate</label>
            <p className="reflection-observation">{item.summary}</p>
            <label>Proposed action</label>
            <p>{item.proposed_action}</p>
            <div className="support-boundary">
              <label>Risk boundary</label>
              <p>{item.risk}</p>
            </div>
            <div className="reflection-meta">
              <span>{item.candidate_kind}</span>
              <span>{item.review_required ? 'review required' : 'no review'}</span>
              <span>{item.memory_write_allowed ? 'memory write allowed' : 'no memory write'}</span>
              <span>{item.confirmed_fact ? 'confirmed fact' : 'not a fact'}</span>
            </div>
            <div className="consolidation-route">
              <Route size={13} />
              <div>
                <label>Review route</label>
                <p>{item.review_route?.action || 'review'} via {item.review_route?.endpoint || item.review_route?.surface || 'review surface'}</p>
                {item.review_route?.slot_id ? <small>{item.review_route.slot_id}</small> : null}
                {item.review_route?.requires_adapter ? <small>adapter required before applying</small> : null}
                {routeSurface(item.review_route?.surface) ? (
                  <button
                    className="consolidation-open-review"
                    onClick={() => onOpenReviewSurface?.(
                      routeSurface(item.review_route?.surface)!,
                      { slotId: item.review_route?.slot_id },
                    )}
                  >
                    <ArrowRight size={12} />
                    {routeLabel(routeSurface(item.review_route?.surface)!)}
                  </button>
                ) : null}
              </div>
            </div>
            {draft ? (
              <div className="consolidation-draft">
                <label>Draft payload</label>
                <p>Preview only. The review drawer still has to adapt and submit this manually.</p>
                <pre>{draft}</pre>
              </div>
            ) : null}
            {item.evidence.length ? (
              <div className="reflection-evidence">
                <label>Evidence</label>
                {item.evidence.map((evidence, index) => (
                  <div key={`${item.candidate_id}-${evidence.reference_id || index}`}>
                    <span>{evidence.summary}</span>
                    <small>{evidence.evidence_type}</small>
                  </div>
                ))}
              </div>
            ) : null}
                </>
              )
            })()}
          </article>
        ))}
      </div>
    </div>
  )
}
