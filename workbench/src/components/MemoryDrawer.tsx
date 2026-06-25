import { AlertOctagon, Check, ChevronRight, History, Search, ShieldX } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, idempotencyKey } from '../api'
import type { SlotDetail, SlotSummary } from '../types'

interface MemoryDrawerProps {
  refreshKey: number
  onMutated: () => void
  preselectedSlotId?: string | null
}

export function MemoryDrawer({ refreshKey, onMutated, preselectedSlotId = null }: MemoryDrawerProps) {
  const [query, setQuery] = useState('')
  const [slots, setSlots] = useState<SlotSummary[]>([])
  const [selected, setSelected] = useState<SlotDetail | null>(null)
  const [correction, setCorrection] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')

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

  if (selected) {
    const confirmable = selected.history.find((item) => item.current && item.source !== 'user_confirmation' && item.source !== 'user_correction')
    return (
      <div className="memory-detail">
        <button className="back-button" onClick={() => setSelected(null)}>← All memory</button>
        <div className="memory-title">
          <div>
            <span>Memory slot</span>
            <h3>{selected.slot_id}</h3>
          </div>
          <span className={`memory-state ${selected.quarantined ? 'quarantined' : selected.conflict ? 'conflict' : 'stable'}`}>
            {selected.quarantined ? 'Quarantined' : selected.conflict ? 'Conflict' : 'Stable'}
          </span>
        </div>
        {notice ? <div className="inline-notice">{notice}</div> : null}
        {preselectedSlotId === selected.slot_id ? (
          <div className="memory-preselected" aria-label="Learner candidate memory target">
            Opened from learner candidate. Review before confirming, correcting, or quarantining.
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
                correction_text: `Workbench correction: ${correction.trim()}`,
              }),
              selected.slot_id,
            )}
          >
            <Check size={15} /> Save confirmed correction
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
            <Check size={15} /> Confirm current candidate
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
            <ShieldX size={15} /> Quarantine slot
          </button>
        </div>
        <div className="history-heading"><History size={15} /> Provenance history</div>
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

  return (
    <div className="memory-browser">
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
