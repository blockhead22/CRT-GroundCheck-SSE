import { AlertOctagon, Check, ChevronRight, History, Search, ShieldX } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api, idempotencyKey } from '../api'
import type { Health, ReviewDraftHandoff, SlotDetail, SlotSummary } from '../types'
import { humanSlotLabel, memoryGroupForSlot, type UiMode } from '../uiMode'

interface MemoryDrawerProps {
  refreshKey: number
  onMutated: () => void
  uiMode?: UiMode
  preselectedSlotId?: string | null
  draftHandoff?: ReviewDraftHandoff | null
  health?: Health | null
}

function memoryDraftValue(draftHandoff: ReviewDraftHandoff) {
  const summary = String(draftHandoff.draft.summary || draftHandoff.summary || '')
  const proposedValue = String(draftHandoff.draft.proposed_value || '')
  const semanticSignal = String(draftHandoff.draft.semantic_signal || '')
  const authority = String(draftHandoff.draft.authority || 'unconfirmed')
  const confidence = draftHandoff.draft.confidence
  return {
    slotId: String(draftHandoff.draft.slot_id || ''),
    proposedValue,
    summary,
    semanticSignal,
    authority,
    confidence: typeof confidence === 'number' ? confidence : null,
  }
}

export function MemoryDrawer({
  refreshKey,
  onMutated,
  uiMode = 'simple',
  preselectedSlotId = null,
  draftHandoff = null,
  health = null,
}: MemoryDrawerProps) {
  const [query, setQuery] = useState('')
  const [slots, setSlots] = useState<SlotSummary[]>([])
  const [selected, setSelected] = useState<SlotDetail | null>(null)
  const [correction, setCorrection] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const isSimple = uiMode === 'simple'
  const profileReceipt = health ? (
    <div
      className="memory-profile-receipt"
      aria-label="Active memory profile"
      title={health.substrate.path}
    >
      <span>Personal profile</span>
      <strong>{health.profile.id}</strong>
      <span>{health.substrate.slots} facts</span>
    </div>
  ) : null

  const grouped = useMemo(() => {
    const groups: Record<'identity' | 'favorites' | 'work' | 'other', SlotSummary[]> = {
      identity: [],
      favorites: [],
      work: [],
      other: [],
    }
    for (const slot of slots) {
      groups[memoryGroupForSlot(slot.slot_id)].push(slot)
    }
    return groups
  }, [slots])

  useEffect(() => {
    let active = true
    const timer = window.setTimeout(() => {
      api.slots(query).then((data) => {
        if (active) setSlots(data.slots)
      }).catch((error) => active && setNotice(error.message))
    }, 140)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [query, refreshKey])

  useEffect(() => {
    if (preselectedSlotId) void loadSlot(preselectedSlotId)
  }, [preselectedSlotId])

  async function loadSlot(slotId: string) {
    setNotice('')
    setCorrection('')
    try {
      setSelected(await api.slot(slotId))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Memory detail failed to load.')
    }
  }

  async function mutate(action: () => Promise<unknown>, slotId: string) {
    setBusy(true)
    setNotice('')
    try {
      await action()
      setSelected(await api.slot(slotId))
      setCorrection('')
      setNotice('Memory updated.')
      onMutated()
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Memory update failed.')
    } finally {
      setBusy(false)
    }
  }

  function correctionSourceText(value: string, draft: ReviewDraftHandoff | null) {
    const cleanValue = value.trim()
    if (!draft) return `Workbench correction: ${cleanValue}`
    const receipt = draft.evidence[0]
    const receiptRef = receipt?.reference_id ? ` receipt=${receipt.reference_id}` : ''
    return (
      `Workbench correction from Mirus candidate ${draft.source_candidate_id}`
      + `${receiptRef}: ${cleanValue}`
    )
  }

  if (selected) {
    const confirmable = selected.history.find((item) => item.current && item.source !== 'user_confirmation' && item.source !== 'user_correction')
    const memoryDraft = draftHandoff ? memoryDraftValue(draftHandoff) : null
    const activeMemoryDraftHandoff = memoryDraft?.slotId === selected.slot_id ? draftHandoff : null
    return (
      <div className="memory-detail">
        {profileReceipt}
        <button className="back-button" onClick={() => setSelected(null)}>← All memory</button>
        <div className="memory-title">
          <div>
            <span>{isSimple ? 'What Aether knows' : 'Memory slot'}</span>
            <h3>{isSimple ? humanSlotLabel(selected.slot_id) : selected.slot_id}</h3>
            {isSimple ? <small className="memory-slot-id">{selected.slot_id}</small> : null}
          </div>
          <span className={`memory-state ${selected.quarantined ? 'quarantined' : selected.conflict ? 'conflict' : 'stable'}`}>
            {selected.quarantined ? 'Needs review' : selected.conflict ? 'Conflict' : 'Confirmed'}
          </span>
        </div>
        {notice ? <div className="inline-notice">{notice}</div> : null}
        {preselectedSlotId === selected.slot_id ? (
          <div className="memory-preselected" aria-label="Learner candidate memory target">
            Opened from learner candidate. Review before confirming, correcting, or quarantining.
          </div>
        ) : null}
        {memoryDraft && activeMemoryDraftHandoff ? (
          <div className="memory-draft" aria-label="Learner memory candidate draft">
            <div className="memory-draft-head">
              <span>Trace-proposed memory fact</span>
              <strong>{memoryDraft.confidence === null ? 'review' : `${Math.round(memoryDraft.confidence * 100)}%`}</strong>
            </div>
            <p>{memoryDraft.summary}</p>
            {memoryDraft.proposedValue ? (
              <div className="memory-draft-proposed">
                <label>Proposed value</label>
                <strong>{memoryDraft.proposedValue}</strong>
                <button
                  disabled={busy}
                  onClick={() => setCorrection(memoryDraft.proposedValue)}
                >
                  Use proposed value
                </button>
              </div>
            ) : null}
            <div className="memory-draft-meta">
              <span>{activeMemoryDraftHandoff.source_candidate_id}</span>
              <span>{activeMemoryDraftHandoff.candidate_kind}</span>
              {memoryDraft.semanticSignal ? <span>{memoryDraft.semanticSignal.replaceAll('_', ' ')}</span> : null}
              <span>{memoryDraft.authority}</span>
              <span>review only</span>
            </div>
            {activeMemoryDraftHandoff.evidence.length ? (
              <div className="memory-draft-evidence">
                {activeMemoryDraftHandoff.evidence.map((evidence, index) => (
                  <div key={`${activeMemoryDraftHandoff.source_candidate_id}-${evidence.reference_id || index}`}>
                    <span>{evidence.summary}</span>
                    <small>{[evidence.evidence_type, evidence.reference_id, evidence.source_authority].filter(Boolean).join(' / ')}</small>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        {selected.contradiction_disposition ? (
          <div className="memory-disposition" aria-label="Memory contradiction disposition">
            <span>Contradiction disposition</span>
            <strong>{selected.contradiction_disposition.label.replaceAll('_', ' ')}</strong>
            <p>
              {selected.contradiction_disposition.reason.replaceAll('_', ' ')}
              {' '}
              ({Math.round(selected.contradiction_disposition.confidence * 100)}%)
            </p>
          </div>
        ) : null}
        <div className="correction-box">
          <label htmlFor="correction">Confirmed correction</label>
          <textarea
            id="correction"
            value={correction}
            onChange={(event) => setCorrection(event.target.value)}
            placeholder="Enter the value that should be treated as true…"
          />
          <button
            className="primary-action"
            disabled={!correction.trim() || busy}
            onClick={() => mutate(
              () => api.correct(selected.slot_id, {
                value: correction.trim(),
                revision_hash: selected.revision_hash,
                idempotency_key: idempotencyKey('correct'),
                correction_text: correctionSourceText(
                  correction,
                  activeMemoryDraftHandoff || null,
                ),
              }),
              selected.slot_id,
            )}
          >
            <Check size={15} /> {isSimple ? 'Save as true' : 'Save confirmed correction'}
          </button>
        </div>
        <div className="memory-actions">
          <button
            disabled={!confirmable || busy}
            onClick={() => confirmable && mutate(
              () => api.confirm(selected.slot_id, {
                state_id: confirmable.state_id,
                revision_hash: selected.revision_hash,
                idempotency_key: idempotencyKey('confirm'),
                confirmation_text: 'Confirmed in Aether Workbench.',
              }),
              selected.slot_id,
            )}
          >
            <Check size={15} /> {isSimple ? 'Confirm this value' : 'Confirm current candidate'}
          </button>
          <button
            className="danger-action"
            disabled={busy}
            onClick={() => mutate(
              () => api.quarantine(selected.slot_id, {
                revision_hash: selected.revision_hash,
                idempotency_key: idempotencyKey('quarantine'),
                reason: 'Quarantined from Aether Workbench after user review.',
              }),
              selected.slot_id,
            )}
          >
            <ShieldX size={15} /> {isSimple ? 'Mark not trusted' : 'Quarantine slot'}
          </button>
        </div>
        <div className="history-heading"><History size={15} /> {isSimple ? 'History' : 'Provenance history'}</div>
        <div className="history-list">
          {selected.history.map((item) => (
            <article className={`history-item ${item.current ? 'current' : ''}`} key={item.state_id}>
              <div className="history-value">
                <strong>{item.value}</strong>
                {item.current ? <span>current</span> : null}
              </div>
              <p>{item.source_text || 'No source excerpt recorded.'}</p>
              <small>{item.source} · {item.temporal_status} · {new Date(item.observed_at * 1000).toLocaleString()}</small>
            </article>
          ))}
        </div>
      </div>
    )
  }

  if (isSimple) {
    const sections: Array<{ key: keyof typeof grouped; title: string }> = [
      { key: 'identity', title: 'You' },
      { key: 'favorites', title: 'Favorites' },
      { key: 'work', title: 'Work & projects' },
      { key: 'other', title: 'Other' },
    ]
    return (
      <div className="memory-browser memory-profile">
        {profileReceipt}
        <p className="memory-profile-lead">
          Facts Aether is allowed to use about you. Confirm or correct anything wrong.
        </p>
        <label className="search-box">
          <Search size={15} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search what Aether knows…" />
        </label>
        {notice ? <div className="inline-notice">{notice}</div> : null}
        {sections.map((section) => {
          const items = grouped[section.key]
          if (!items.length) return null
          return (
            <div className="memory-profile-section" key={section.key}>
              <h4>{section.title}</h4>
              <div className="memory-card-grid">
                {items.map((slot) => (
                  <button
                    type="button"
                    className={`memory-card ${slot.quarantined ? 'quarantined' : slot.conflict ? 'conflict' : 'stable'}`}
                    key={slot.slot_id}
                    onClick={() => loadSlot(slot.slot_id)}
                  >
                    <span className="memory-card-label">{humanSlotLabel(slot.slot_id)}</span>
                    <strong className="memory-card-value">
                      {slot.current_values.join(' · ') || 'No value yet'}
                    </strong>
                    <span className="memory-card-status">
                      {slot.quarantined ? 'Needs review' : slot.conflict ? 'Conflict' : 'OK'}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )
        })}
        {!slots.length ? (
          <div className="drawer-empty compact">
            <p>Nothing stored yet. Tell Aether a preference in chat, then confirm it here if you want it kept.</p>
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <div className="memory-browser">
      {profileReceipt}
      <label className="search-box">
        <Search size={15} />
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search memory slots…" />
      </label>
      {notice ? <div className="inline-notice">{notice}</div> : null}
      <div className="slot-list">
        {slots.map((slot) => (
          <button className="slot-row" key={slot.slot_id} onClick={() => loadSlot(slot.slot_id)}>
            <span className={`slot-icon ${slot.quarantined ? 'quarantined' : slot.conflict ? 'conflict' : ''}`}>
              {slot.quarantined || slot.conflict ? <AlertOctagon size={15} /> : <Check size={15} />}
            </span>
            <span className="slot-copy">
              <strong>{slot.slot_id}</strong>
              <span>{slot.current_values.join(' · ') || 'No current value'} · {slot.state_count} states</span>
            </span>
            <ChevronRight size={15} />
          </button>
        ))}
        {!slots.length ? <div className="drawer-empty compact"><p>No matching memory slots.</p></div> : null}
      </div>
    </div>
  )
}
