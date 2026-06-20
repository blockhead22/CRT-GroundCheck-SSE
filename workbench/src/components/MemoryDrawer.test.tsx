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
  current_values: ['photography'],
  conflict: false,
  quarantined: false,
  state_count: 1,
  updated_at: 1,
}

const detail = {
  revision_hash: 'revision-1',
  slot_id: 'user:hobby',
  conflict: false,
  quarantined: false,
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
