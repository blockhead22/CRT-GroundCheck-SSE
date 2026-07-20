import { ArrowRight, CheckCircle2, Clock3, GitBranch, RefreshCcw, Route, ShieldCheck, XCircle } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import type { ConsolidationCandidate, ConsolidationPreview, ReviewDraftHandoff } from '../types'

type CandidateFilter = 'all' | 'task_state' | 'memory' | 'support_patterns' | 'reflections'
type LocalReviewState = 'active' | 'deferred' | 'dismissed'
type ReviewSurface = 'memory' | 'support' | 'reflect'

const FILTERS: Array<{ label: string; value: CandidateFilter }> = [
  { label: 'All', value: 'all' },
  { label: 'Tasks', value: 'task_state' },
  { label: 'Memory', value: 'memory' },
  { label: 'Support', value: 'support_patterns' },
  { label: 'Reflect', value: 'reflections' },
]

function surfaceLabel(surface: string) {
  return surface.replace('_', ' ')
}

function candidateTone(item: ConsolidationCandidate) {
  if (item.review_route?.surface === 'task_state') return 'proposed'
  if (item.category === 'contradiction_review') return 'proposed'
  if (item.category === 'aether_self_improvement') return 'accepted'
  if (item.category === 'support_style_candidate') return 'deferred'
  return ''
}

interface ConsolidationDrawerProps {
  onOpenReviewSurface?: (surface: ReviewSurface, options?: { slotId?: string; draftHandoff?: ReviewDraftHandoff }) => void
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

function draftHandoff(item: ConsolidationCandidate): ReviewDraftHandoff | undefined {
  if (!item.review_route?.draft) return undefined
  return {
    source_candidate_id: item.candidate_id,
    source_category: item.category,
    candidate_kind: item.candidate_kind,
    summary: item.summary,
    proposed_action: item.proposed_action,
    risk: item.risk,
    draft: item.review_route.draft,
    evidence: item.evidence,
  }
}

function firstReceipt(item: ConsolidationCandidate) {
  return item.evidence[0]?.summary ? compactText(item.evidence[0].summary) : 'No trace receipt attached to this candidate.'
}

function reviewBoundary(item: ConsolidationCandidate) {
  const flags = []
  if (isReviewOnly(item)) flags.push('review only')
  flags.push(item.review_required ? 'review required' : 'review not required')
  flags.push(item.memory_write_allowed ? 'memory write allowed' : 'memory write blocked')
  flags.push(item.confirmed_fact ? 'confirmed fact' : 'not confirmed fact')
  return flags.join(' / ')
}

function isReviewOnly(item: ConsolidationCandidate) {
  return item.review_only ?? (
    item.review_required
    && item.memory_write_allowed === false
    && item.confirmed_fact === false
  )
}

function isTaskStateCandidate(item: ConsolidationCandidate) {
  return item.review_route?.surface === 'task_state'
}

function reviewDestination(item: ConsolidationCandidate) {
  const action = item.review_route?.action || 'review'
  const surface = surfaceLabel(item.review_route?.surface || 'unknown')
  return `${action} -> ${surface}`
}

function evidenceMeta(evidence: ConsolidationCandidate['evidence'][number]) {
  const parts = [evidence.evidence_type]
  if (evidence.reference_id) parts.push(evidence.reference_id)
  if (evidence.source_authority) parts.push(evidence.source_authority)
  return parts.join(' / ')
}

function compactText(value: string, maxLength = 180) {
  const normalized = value.replace(/\s+/g, ' ').trim()
  if (normalized.length <= maxLength) return normalized
  return `${normalized.slice(0, maxLength - 1).trimEnd()}...`
}

export function ConsolidationDrawer({ onOpenReviewSurface }: ConsolidationDrawerProps) {
  const [preview, setPreview] = useState<ConsolidationPreview | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState<CandidateFilter>('all')
  const [localReview, setLocalReview] = useState<Record<string, LocalReviewState>>({})
  const [reviewing, setReviewing] = useState<Record<string, boolean>>({})
  const [reviewNotice, setReviewNotice] = useState('')

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

  const candidates = preview?.candidates || []

  const counts = useMemo(() => {
    const result = new Map<string, number>()
    for (const item of candidates) {
      const surface = item.review_route?.surface || 'unknown'
      result.set(surface, (result.get(surface) || 0) + 1)
    }
    return [...result.entries()]
  }, [candidates])

  const queueStats = useMemo(() => {
    const stats = { active: 0, deferred: 0, dismissed: 0, routed: 0, adapterRequired: 0 }
    for (const item of candidates) {
      const state = localReview[item.candidate_id] || 'active'
      if (state === 'dismissed') stats.dismissed += 1
      else if (state === 'deferred') stats.deferred += 1
      else stats.active += 1
      if (routeSurface(item.review_route?.surface)) stats.routed += 1
      if (item.review_route?.requires_adapter) stats.adapterRequired += 1
    }
    return stats
  }, [candidates, localReview])

  const visibleCandidates = useMemo(() => candidates.filter((item) => {
    if (localReview[item.candidate_id] === 'dismissed') return false
    return filter === 'all' || item.review_route?.surface === filter
  }), [candidates, filter, localReview])

  function setCandidateState(candidateId: string, state: LocalReviewState) {
    setLocalReview((current) => ({ ...current, [candidateId]: state }))
  }

  function restoreHidden() {
    setLocalReview((current) => Object.fromEntries(
      Object.entries(current).filter(([, state]) => state !== 'dismissed'),
    ))
  }

  async function reviewTaskCandidate(
    item: ConsolidationCandidate,
    action: 'promote' | 'reject',
  ) {
    setReviewing((current) => ({ ...current, [item.candidate_id]: true }))
    setError('')
    setReviewNotice('')
    try {
      const result = await api.reviewTaskCandidate(item.candidate_id, {
        action,
        note: action === 'promote'
          ? 'Promoted explicitly from the Workbench learner review queue.'
          : 'Rejected explicitly from the Workbench learner review queue.',
        idempotency_key: `task-candidate-${action}-${crypto.randomUUID()}`,
      })
      setReviewNotice(action === 'promote'
        ? `Promoted to ${result.review.created_record_kind.replace('_', ' ')} task authority.`
        : 'Rejected candidate. No task authority or memory changed.')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not review task candidate.')
    } finally {
      setReviewing((current) => {
        const next = { ...current }
        delete next[item.candidate_id]
        return next
      })
    }
  }

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
        Consolidation candidates are preview-only learner suggestions. Task candidates change task state only after explicit promotion; they never write memory.
      </div>
      <div className="consolidation-toolbar">
        <div>
          <span>{preview?.inspected_turn_count || 0}</span>
          <small>turns inspected</small>
        </div>
        <div>
          <span>{queueStats.active}</span>
          <small>active queue</small>
        </div>
        <div>
          <span>{queueStats.deferred}</span>
          <small>deferred</small>
        </div>
        <div>
          <span>{queueStats.routed}</span>
          <small>routable</small>
        </div>
        {counts.map(([surface, count]) => (
          <div key={surface}>
            <span>{count}</span>
            <small>{surfaceLabel(surface)}</small>
          </div>
        ))}
        <button disabled={loading} onClick={() => void load()}><RefreshCcw size={13} />Refresh</button>
      </div>
      <div className="consolidation-filter" aria-label="Learner candidate route filter">
        {FILTERS.map((item) => (
          <button
            key={item.value}
            className={filter === item.value ? 'active' : ''}
            onClick={() => setFilter(item.value)}
          >
            {item.label}
            {item.value !== 'all' ? <span>{counts.find(([surface]) => surface === item.value)?.[1] || 0}</span> : null}
          </button>
        ))}
        {queueStats.dismissed ? (
          <button className="restore" onClick={restoreHidden}>
            Restore hidden <span>{queueStats.dismissed}</span>
          </button>
        ) : null}
      </div>
      {preview ? (
        <div className="consolidation-safety" aria-label="Consolidation safety">
          <span><ShieldCheck size={12} />{preview.mode.replace('_', ' ')}</span>
          <span>writes {preview.writes_performed ? 'yes' : 'no'}</span>
          <span>memory {preview.memory_ingestion_performed ? 'yes' : 'no'}</span>
          <span>support import {preview.support_pattern_import_performed ? 'yes' : 'no'}</span>
          <span>reflection create {preview.reflection_create_performed ? 'yes' : 'no'}</span>
          <span>task authority {preview.task_authority_write_performed ? 'yes' : 'no'}</span>
          <span>session review only</span>
          {queueStats.adapterRequired ? <span>{queueStats.adapterRequired} adapter draft</span> : null}
        </div>
      ) : null}
      {error ? <div className="inline-notice">{error}</div> : null}
      {reviewNotice ? <div className="inline-notice success">{reviewNotice}</div> : null}
      <div className="reflection-list">
        {visibleCandidates.map((item) => (
          <article className={`reflection-card ${candidateTone(item)}`} key={item.candidate_id}>
            {(() => {
              const draft = draftPreview(item)
              const state = localReview[item.candidate_id] || 'active'
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
            <div className="consolidation-why" aria-label={`Why ${item.candidate_id} exists`}>
              <div>
                <label>Receipt</label>
                <p>{firstReceipt(item)}</p>
              </div>
              <div>
                <label>Boundary</label>
                <p>{reviewBoundary(item)}</p>
              </div>
              <div>
                <label>Review</label>
                <p>{reviewDestination(item)}</p>
              </div>
            </div>
            <div className="reflection-meta">
              <span>{item.candidate_kind}</span>
              {isReviewOnly(item) ? <span>review only</span> : null}
              <span>{item.review_required ? 'review required' : 'no review'}</span>
              <span>{item.memory_write_allowed ? 'memory write allowed' : 'no memory write'}</span>
              <span>{item.confirmed_fact ? 'confirmed fact' : 'not a fact'}</span>
              <span>{state} this session</span>
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
                      {
                        slotId: item.review_route?.slot_id,
                        draftHandoff: draftHandoff(item),
                      },
                    )}
                  >
                    <ArrowRight size={12} />
                    {routeLabel(routeSurface(item.review_route?.surface)!)}
                  </button>
                ) : null}
              </div>
            </div>
            {draft ? (
              <details className="consolidation-draft">
                <summary>Draft payload</summary>
                <p>{isTaskStateCandidate(item)
                  ? 'Preview only. Explicit promotion is required before this reaches task state.'
                  : 'Preview only. The review drawer still has to adapt and submit this manually.'}</p>
                <pre>{draft}</pre>
              </details>
            ) : null}
            {item.evidence.length ? (
              <div className="reflection-evidence">
                <label>Evidence</label>
                {item.evidence.map((evidence, index) => {
                  const compactSummary = compactText(evidence.summary)
                  const isLongSummary = compactSummary !== evidence.summary
                  return (
                    <div key={`${item.candidate_id}-${evidence.reference_id || index}`}>
                      {isLongSummary ? (
                        <details className="reflection-evidence-detail">
                          <summary>{compactSummary}</summary>
                          <p>{evidence.summary}</p>
                        </details>
                      ) : (
                        <span>{compactSummary}</span>
                      )}
                      <small>{evidenceMeta(evidence)}</small>
                    </div>
                  )
                })}
              </div>
            ) : null}
            <div className="consolidation-review-actions" aria-label={`Learner review controls for ${item.candidate_id}`}>
              {state === 'deferred' ? (
                <button onClick={() => setCandidateState(item.candidate_id, 'active')}>
                  <RefreshCcw size={12} />Return to Queue
                </button>
              ) : (
                <button onClick={() => setCandidateState(item.candidate_id, 'deferred')}>
                  <Clock3 size={12} />Defer Session
                </button>
              )}
              {isTaskStateCandidate(item) ? (
                <>
                  <button
                    className="accept"
                    disabled={Boolean(reviewing[item.candidate_id])}
                    onClick={() => void reviewTaskCandidate(item, 'promote')}
                  >
                    <CheckCircle2 size={12} />Promote to Task State
                  </button>
                  <button
                    className="reject"
                    disabled={Boolean(reviewing[item.candidate_id])}
                    onClick={() => void reviewTaskCandidate(item, 'reject')}
                  >
                    <XCircle size={12} />Reject Candidate
                  </button>
                </>
              ) : (
                <button className="reject" onClick={() => setCandidateState(item.candidate_id, 'dismissed')}>
                  <XCircle size={12} />Hide Session
                </button>
              )}
            </div>
                </>
              )
            })()}
          </article>
        ))}
        {preview && !visibleCandidates.length ? (
          <div className="drawer-empty compact">
            <p>No active learner candidates match this route filter.</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}
