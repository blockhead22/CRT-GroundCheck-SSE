import { Check, Clock3, ShieldAlert, XCircle } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api, idempotencyKey } from '../api'
import type { SupportPattern } from '../types'

type ReviewAction = 'accept' | 'reject' | 'defer'
type StatusFilter = 'all' | SupportPattern['status']

const FILTERS: Array<{ label: string; value: StatusFilter }> = [
  { label: 'All', value: 'all' },
  { label: 'Proposed', value: 'proposed_review' },
  { label: 'Accepted', value: 'accepted' },
  { label: 'Deferred', value: 'deferred' },
  { label: 'Rejected', value: 'rejected' },
]

function statusLabel(status: string) {
  return status.replace('_', ' ')
}

export function SupportPatternDrawer() {
  const [items, setItems] = useState<SupportPattern[]>([])
  const [status, setStatus] = useState<StatusFilter>('all')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notes, setNotes] = useState<Record<string, string>>({})

  async function load(nextStatus = status) {
    setError('')
    try {
      const filter = nextStatus === 'all' ? '' : nextStatus
      setItems(await api.supportPatterns(filter))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not load support patterns.')
    }
  }

  useEffect(() => { void load() }, [])

  async function review(item: SupportPattern, action: ReviewAction) {
    setBusy(item.candidate_id)
    setError('')
    try {
      await api.reviewSupportPattern(item.candidate_id, {
        action,
        note: notes[item.candidate_id] || '',
        revision_hash: item.revision_hash,
        idempotency_key: idempotencyKey(`support-pattern-${action}`),
      })
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Support-pattern review failed.')
    } finally {
      setBusy('')
    }
  }

  const counts = useMemo(() => {
    const result = new Map<string, number>()
    for (const item of items) result.set(item.status, (result.get(item.status) || 0) + 1)
    return result
  }, [items])

  if (!items.length && !error) {
    return (
      <div className="drawer-empty">
        <ShieldAlert size={26} />
        <h3>No support patterns</h3>
        <p>Import archive-derived candidates through the sidecar first. Nothing here becomes memory without review.</p>
      </div>
    )
  }

  return (
    <div className="support-browser">
      <div className="reflection-intro">
        Support patterns are reviewed behavior guidance. They are not confirmed facts and do not write memory.
      </div>
      <div className="support-filter" aria-label="Support pattern status filter">
        {FILTERS.map((filter) => (
          <button
            key={filter.value}
            className={status === filter.value ? 'active' : ''}
            onClick={() => {
              setStatus(filter.value)
              void load(filter.value)
            }}
          >
            {filter.label}
            {filter.value !== 'all' ? <span>{counts.get(filter.value) || 0}</span> : null}
          </button>
        ))}
      </div>
      {error ? <div className="inline-notice">{error}</div> : null}
      <div className="reflection-list">
        {items.map((item) => (
          <article className={`reflection-card ${item.status === 'proposed_review' ? 'proposed' : item.status}`} key={item.candidate_id}>
            <div className="reflection-head">
              <span>{item.category}</span>
              <strong>{statusLabel(item.status)}</strong>
            </div>
            <label>Pattern</label>
            <p className="reflection-observation">{item.summary}</p>
            <label>Accepted behavior</label>
            <p>{item.suggested_response_rule}</p>
            {item.risk ? (
              <div className="support-boundary">
                <label>Boundary</label>
                <p>{item.risk}</p>
              </div>
            ) : null}
            <div className="reflection-meta">
              <span>{item.candidate_kind}</span>
              <span>{item.title_category_count} title signals</span>
              <span>{item.confirmed_fact ? 'fact' : 'not a fact'}</span>
            </div>
            {item.evidence.length ? (
              <div className="reflection-evidence">
                <label>Title-only evidence</label>
                {item.evidence.slice(0, 3).map((evidence, index) => (
                  <div key={`${item.candidate_id}-${evidence.conversation_id || index}`}>
                    <span>{evidence.title || 'Untitled conversation'}</span>
                    <small>{evidence.evidence_type}</small>
                  </div>
                ))}
              </div>
            ) : null}
            {item.status === 'proposed_review' || item.status === 'deferred' ? (
              <div className="reflection-review">
                <textarea
                  aria-label={`Review note for ${item.candidate_id}`}
                  placeholder="Optional review note..."
                  value={notes[item.candidate_id] || ''}
                  onChange={(event) => setNotes((current) => ({ ...current, [item.candidate_id]: event.target.value }))}
                />
                <div className="reflection-actions">
                  <button disabled={busy === item.candidate_id} onClick={() => review(item, 'accept')}><Check size={13} />Accept</button>
                  <button disabled={busy === item.candidate_id} onClick={() => review(item, 'defer')}><Clock3 size={13} />Defer</button>
                  <button className="reject" disabled={busy === item.candidate_id} onClick={() => review(item, 'reject')}><XCircle size={13} />Reject</button>
                </div>
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  )
}
