import { Check, Clock3, RefreshCcw, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, idempotencyKey } from '../api'
import { buildReflectionDraftPayload } from '../learnDraftPromotion'
import type { ReflectionDraftForm } from '../learnDraftPromotion'
import type { Reflection, ReviewDraftHandoff } from '../types'

interface ReflectionDrawerProps {
  draftHandoff?: ReviewDraftHandoff | null
}

export function ReflectionDrawer({ draftHandoff = null }: ReflectionDrawerProps) {
  const [items, setItems] = useState<Reflection[]>([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [revisions, setRevisions] = useState<Record<string, string>>({})
  const [draft, setDraft] = useState<ReflectionDraftForm | null>(null)

  async function load() {
    setError('')
    try {
      setItems(await api.reflections())
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not load reflections.')
    }
  }

  useEffect(() => { void load() }, [])

  useEffect(() => {
    if (!draftHandoff) {
      setDraft(null)
      return
    }
    setDraft({
      subject: String(draftHandoff.draft.subject || 'agent'),
      observation: String(draftHandoff.draft.observation || draftHandoff.summary || ''),
      interpretation: String(draftHandoff.draft.interpretation || ''),
      alternatives: Array.isArray(draftHandoff.draft.alternatives) ? draftHandoff.draft.alternatives.join('\n') : '',
      confidence: String(draftHandoff.draft.confidence ?? '0.45'),
      timeWindow: String(draftHandoff.draft.time_window || 'recent turns'),
      suggestedExperiment: String(draftHandoff.draft.suggested_experiment || draftHandoff.proposed_action || ''),
    })
  }, [draftHandoff])

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

  async function createDraftReflection() {
    if (!draftHandoff || !draft) return
    setBusy(draftHandoff.source_candidate_id)
    setError('')
    setNotice('')
    try {
      await api.createReflection(buildReflectionDraftPayload(draftHandoff, draft))
      setNotice('Created a proposed reflection. It still needs review before it can shape durable behavior.')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not create reflection draft.')
    } finally {
      setBusy('')
    }
  }

  const draftPanel = draftHandoff && draft ? (
    <div className="draft-handoff" aria-label="Learner reflection draft handoff">
      <label>Learner reflection draft</label>
      <p>Manual form state only. Nothing has been created, accepted, or written to memory.</p>
      <input aria-label="Draft reflection subject" value={draft.subject} onChange={(event) => setDraft((current) => current ? { ...current, subject: event.target.value } : current)} />
      <textarea aria-label="Draft reflection observation" value={draft.observation} onChange={(event) => setDraft((current) => current ? { ...current, observation: event.target.value } : current)} />
      <textarea aria-label="Draft reflection interpretation" value={draft.interpretation} onChange={(event) => setDraft((current) => current ? { ...current, interpretation: event.target.value } : current)} />
      <textarea aria-label="Draft reflection alternatives" value={draft.alternatives} onChange={(event) => setDraft((current) => current ? { ...current, alternatives: event.target.value } : current)} />
      <input aria-label="Draft reflection confidence" value={draft.confidence} onChange={(event) => setDraft((current) => current ? { ...current, confidence: event.target.value } : current)} />
      <input aria-label="Draft reflection time window" value={draft.timeWindow} onChange={(event) => setDraft((current) => current ? { ...current, timeWindow: event.target.value } : current)} />
      <textarea aria-label="Draft reflection suggested experiment" value={draft.suggestedExperiment} onChange={(event) => setDraft((current) => current ? { ...current, suggestedExperiment: event.target.value } : current)} />
      <small>Source learner candidate: {draftHandoff.source_candidate_id}</small>
      <button
        type="button"
        className="draft-handoff-action"
        disabled={busy === draftHandoff.source_candidate_id}
        onClick={() => { void createDraftReflection() }}
      >
        <Check size={13} />Create Proposed Reflection
      </button>
    </div>
  ) : null

  if (!items.length && !error) {
    return <div className="drawer-empty"><RefreshCcw size={26} /><h3>No reflections yet</h3><p>Phase 1 stores reviewed hypotheses only. Automatic reflection is intentionally disabled.</p>{draftPanel}</div>
  }

  return (
    <div className="reflection-browser">
      <div className="reflection-intro">Reflections are provisional hypotheses, not personality facts.</div>
      {draftPanel}
      {notice ? <div className="inline-notice success">{notice}</div> : null}
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
