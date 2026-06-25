import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { api } from '../api'
import { MemoryDrawer } from './MemoryDrawer'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return {
    ...actual,
    api: {
      slots: vi.fn(),
      slot: vi.fn(),
      correct: vi.fn(),
      confirm: vi.fn(),
      quarantine: vi.fn(),
    },
  }
})

const summary = {
  slot_id: 'user:hobby',
  current_values: ['photography', 'cinematography'],
  conflict: true,
  quarantined: false,
  state_count: 2,
  updated_at: 1,
}

const detail = {
  revision_hash: 'revision-1',
  slot_id: 'user:hobby',
  conflict: true,
  quarantined: false,
  contradiction_disposition: {
    label: 'resolvable',
    confidence: 0.7,
    reason: 'current_values_conflict_but_authority_is_reviewable',
    evidence_state_ids: ['state-1', 'state-2'],
  },
  review: {},
  history: [{
    state_id: 'state-1',
    value: 'photography',
    normalized: 'photography',
    trust: 0.85,
    observed_at: 1,
    temporal_status: 'active',
    source: 'auto_ingest',
    source_text: 'I like photography.',
    current: true,
  }, {
    state_id: 'state-2',
    value: 'cinematography',
    normalized: 'cinematography',
    trust: 0.85,
    observed_at: 2,
    temporal_status: 'active',
    source: 'auto_ingest',
    source_text: 'I like cinematography.',
    current: true,
  }],
}

beforeEach(() => {
  vi.mocked(api.slots).mockResolvedValue({ revision_hash: 'revision-1', slots: [summary] })
  vi.mocked(api.slot).mockResolvedValue(detail)
  vi.mocked(api.correct).mockResolvedValue({})
})

test('opens a slot and writes an explicit correction', async () => {
  const onMutated = vi.fn()
  render(<MemoryDrawer refreshKey={0} onMutated={onMutated} />)
  fireEvent.click(await screen.findByRole('button', { name: /user:hobby/ }))
  expect(await screen.findByLabelText('Memory contradiction disposition')).toHaveTextContent(
    'resolvable'
  )
  expect(screen.getByLabelText('Memory contradiction disposition')).toHaveTextContent(
    'current values conflict but authority is reviewable'
  )
  fireEvent.change(await screen.findByLabelText('Confirmed correction'), {
    target: { value: 'cinematography' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Save confirmed correction' }))

  await waitFor(() => expect(api.correct).toHaveBeenCalledWith(
    'user:hobby',
    expect.objectContaining({
      value: 'cinematography',
      revision_hash: 'revision-1',
    }),
  ))
  expect(onMutated).toHaveBeenCalled()
})
