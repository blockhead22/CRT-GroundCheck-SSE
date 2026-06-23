import { Check, Clock3, RefreshCcw, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, idempotencyKey } from '../api'
import type { Reflection } from '../types'

export function ReflectionDrawer() {
  const [items, setItems] = useState<Reflection[]>([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [revisions, setRevisions] = useState<Record<string, string>>({})

  async function load() {
    setError('')
    try {
      setItems(await api.reflections())
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not load reflections.')
    }
  }

  useEffect(() => { void load() }, [])

  async function review(item: Reflection, action: 'accept' | 'reject' | 'defer' | 'revise') {
    setBusy(item.reflection_id)
    setError('')
    try {
      const observation = revisions[item.reflection_id]?.trim()
      await api.reviewReflection(item.reflection_id, {
        action,
        note: notes[item.reflection_id] || '',
        revision_hash: item.revision_hash,
        idempotency_key: idempotencyKey(`reflection-${action}`),
        ...(action === 'revise' ? {
          revision: {
            subject: item.subject,
            observation: observation || item.observation,
            interpretation: item.interpretation,
            alternatives: item.alternatives,
            confidence: item.confidence,
            time_window: item.time_window,
            suggested_experiment: item.suggested_experiment,
            evidence: item.evidence,
          },
        } : {}),
      })
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Reflection review failed.')
    } finally {
      setBusy('')
    }
  }

  if (!items.length && !error) {
    return <div className="drawer-empty"><RefreshCcw size={26} /><h3>No reflections yet</h3><p>Phase 1 stores reviewed hypotheses only. Automatic reflection is intentionally disabled.</p></div>
  }

  return (
    <div className="reflection-browser">
      <div className="reflection-intro">Reflections are provisional hypotheses, not personality facts.</div>
      {error ? <div className="inline-notice">{error}</div> : null}
      <div className="reflection-list">
        {items.map((item) => (
          <article className={`reflection-card ${item.status}`} key={item.reflection_id}>
            <div className="reflection-head">
              <span>{item.subject}</span>
              <strong>{item.status}</strong>
            </div>
            <label>Observation</label>
            <p className="reflection-observation">{item.observation}</p>
            {item.interpretation ? <><label>Possible interpretation</label><p>{item.interpretation}</p></> : null}
            {item.alternatives.length ? <><label>Alternative explanations</label><ul>{item.alternatives.map((alternative) => <li key={alternative}>{alternative}</li>)}</ul></> : null}
            <div className="reflection-meta"><span>{Math.round(item.confidence * 100)}% confidence</span><span>{item.time_window}</span></div>
            {item.evidence.length ? <div className="reflection-evidence"><label>Evidence</label>{item.evidence.map((evidence) => <div key={evidence.evidence_id}><span>{evidence.summary}</span><small>{evidence.evidence_type}</small></div>)}</div> : null}
            {item.suggested_experiment ? <div className="reflection-experiment"><label>Suggested experiment</label><p>{item.suggested_experiment}</p></div> : null}
            {item.status === 'proposed' || item.status === 'deferred' ? (
              <div className="reflection-review">
                <textarea aria-label={`Review note for ${item.reflection_id}`} placeholder="Optional review note…" value={notes[item.reflection_id] || ''} onChange={(event) => setNotes((current) => ({ ...current, [item.reflection_id]: event.target.value }))} />
                <textarea aria-label={`Revised observation for ${item.reflection_id}`} placeholder="Revise the observation before choosing Revise…" value={revisions[item.reflection_id] || ''} onChange={(event) => setRevisions((current) => ({ ...current, [item.reflection_id]: event.target.value }))} />
                <div className="reflection-actions">
                  <button disabled={busy === item.reflection_id} onClick={() => review(item, 'accept')}><Check size={13} />Accept</button>
                  <button disabled={busy === item.reflection_id} onClick={() => review(item, 'defer')}><Clock3 size={13} />Defer</button>
                  <button disabled={busy === item.reflection_id} onClick={() => review(item, 'revise')}><RefreshCcw size={13} />Revise</button>
                  <button className="reject" disabled={busy === item.reflection_id} onClick={() => review(item, 'reject')}><XCircle size={13} />Reject</button>
                </div>
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  )
}
