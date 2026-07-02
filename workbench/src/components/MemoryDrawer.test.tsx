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
  vi.clearAllMocks()
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

test('loads a learner-preselected slot and draft without mutating memory', async () => {
  render(
    <MemoryDrawer
      refreshKey={0}
      preselectedSlotId="user:hobby"
      draftHandoff={{
        source_candidate_id: 'consolidation_candidate_memory',
        source_category: 'memory_fact_candidate',
        candidate_kind: 'reviewed_memory_fact_candidate',
        summary: 'user:hobby has a proposed memory fact from trace evidence.',
        proposed_action: 'Open memory review for user:hobby.',
        risk: 'Do not treat this as memory until reviewed.',
        draft: {
          slot_id: 'user:hobby',
          proposed_value: 'photography',
          summary: 'User says they are focusing on photography again.',
          semantic_signal: 'returned_to_hobby_focus',
          authority: 'unconfirmed',
          confidence: 0.68,
        },
        evidence: [{
          evidence_type: 'trace_user_claim',
          reference_id: 'turn-1',
          summary: 'User says they are focusing on photography again.',
          source_authority: 'user_stated',
        }],
      }}
      onMutated={vi.fn()}
    />,
  )

  expect(await screen.findByText('Opened from learner candidate. Review before confirming, correcting, or quarantining.')).toBeInTheDocument()
  expect(screen.getByLabelText('Learner memory candidate draft')).toHaveTextContent('Trace-proposed memory fact')
  expect(screen.getByLabelText('Learner memory candidate draft')).toHaveTextContent('68%')
  expect(screen.getByLabelText('Learner memory candidate draft')).toHaveTextContent('User says they are focusing on photography again.')
  expect(screen.getByLabelText('Learner memory candidate draft')).toHaveTextContent('photography')
  expect(screen.getByLabelText('Learner memory candidate draft')).toHaveTextContent('returned to hobby focus')
  expect(screen.getByLabelText('Learner memory candidate draft')).toHaveTextContent('unconfirmed')
  fireEvent.click(screen.getByRole('button', { name: 'Use proposed value' }))
  expect(screen.getByLabelText('Confirmed correction')).toHaveValue('photography')
  fireEvent.click(screen.getByRole('button', { name: 'Save confirmed correction' }))
  await waitFor(() => expect(api.correct).toHaveBeenCalledWith(
    'user:hobby',
    expect.objectContaining({
      value: 'photography',
      correction_text: 'Workbench correction from Mirus candidate consolidation_candidate_memory receipt=turn-1: photography',
    }),
  ))
  expect(screen.getByText('trace_user_claim / turn-1 / user_stated')).toBeInTheDocument()
  expect(api.slot).toHaveBeenCalledWith('user:hobby')
  expect(api.confirm).not.toHaveBeenCalled()
  expect(api.quarantine).not.toHaveBeenCalled()
})

test('shows favorite flower reason draft as review-only before correction', async () => {
  vi.mocked(api.slots).mockResolvedValue({
    revision_hash: 'revision-2',
    slots: [{
      slot_id: 'user:favorite_flower_reason',
      current_values: [],
      conflict: false,
      quarantined: false,
      state_count: 0,
      updated_at: 2,
    }],
  })
  vi.mocked(api.slot).mockResolvedValue({
    revision_hash: 'revision-2',
    slot_id: 'user:favorite_flower_reason',
    conflict: false,
    quarantined: false,
    contradiction_disposition: null,
    review: {},
    history: [],
  })

  render(
    <MemoryDrawer
      refreshKey={0}
      preselectedSlotId="user:favorite_flower_reason"
      draftHandoff={{
        source_candidate_id: 'mirus_favorite_flower_reason_turn-orange',
        source_category: 'memory_fact_candidate',
        candidate_kind: 'mirus_contextual_favorite_reason_candidate',
        summary: 'user:favorite_flower_reason has a proposed memory reason from trace evidence.',
        proposed_action: 'Open memory review for user:favorite_flower_reason.',
        risk: 'Do not treat this as memory until reviewed.',
        draft: {
          slot_id: 'user:favorite_flower_reason',
          proposed_value: 'Marigolds may matter because they are orange.',
          summary: 'User connected the favorite flower thread to orange; review before storing this as the durable reason marigolds matter.',
          semantic_signal: 'contextual_reason_for_existing_favorite_not_confirmed_fact',
          authority: 'unconfirmed',
          confidence: 0.58,
        },
        evidence: [{
          evidence_type: 'trace_semantic_signal',
          reference_id: 'turn-orange',
          summary: 'User said “They are both orange” after the marigolds/orange thread.',
          source_authority: 'user_stated_contextual',
        }],
      }}
      onMutated={vi.fn()}
    />,
  )

  const draft = await screen.findByLabelText('Learner memory candidate draft')
  expect(draft).toHaveTextContent('Trace-proposed memory fact')
  expect(draft).toHaveTextContent('58%')
  expect(draft).toHaveTextContent('Marigolds may matter because they are orange.')
  expect(draft).toHaveTextContent('contextual reason for existing favorite not confirmed fact')
  expect(draft).toHaveTextContent('unconfirmed')
  expect(draft).toHaveTextContent('review only')
  expect(api.correct).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole('button', { name: 'Use proposed value' }))
  expect(screen.getByLabelText('Confirmed correction')).toHaveValue(
    'Marigolds may matter because they are orange.',
  )
  fireEvent.click(screen.getByRole('button', { name: 'Save confirmed correction' }))

  await waitFor(() => expect(api.correct).toHaveBeenCalledWith(
    'user:favorite_flower_reason',
    expect.objectContaining({
      value: 'Marigolds may matter because they are orange.',
      correction_text: (
        'Workbench correction from Mirus candidate '
        + 'mirus_favorite_flower_reason_turn-orange receipt=turn-orange: '
        + 'Marigolds may matter because they are orange.'
      ),
    }),
  ))
  expect(api.confirm).not.toHaveBeenCalled()
  expect(api.quarantine).not.toHaveBeenCalled()
})
