import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { api } from '../api'
import { ReflectionDrawer } from './ReflectionDrawer'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return {
    ...actual,
    api: {
      reflections: vi.fn(),
      reviewReflection: vi.fn(),
    },
  }
})

const reflection = {
  reflection_id: 'reflection-1',
  subject: 'workflow' as const,
  observation: 'Three tasks were postponed while their next actions were unclear.',
  interpretation: 'Ambiguity may be increasing friction.',
  alternatives: ['The tasks may simply be lower priority.'],
  confidence: 0.62,
  time_window: 'past 7 days',
  suggested_experiment: 'Define one concrete next action for three days.',
  status: 'proposed' as const,
  created_at: 1,
  updated_at: 1,
  revision_hash: 'revision-1',
  evidence: [{
    evidence_id: 'evidence-1',
    evidence_type: 'action_outcome',
    reference_id: 'action-1',
    summary: 'Task postponed without a defined next action.',
    created_at: 1,
  }],
  reviews: [],
}

beforeEach(() => {
  vi.mocked(api.reflections).mockResolvedValue([reflection])
  vi.mocked(api.reviewReflection).mockResolvedValue({})
})

test('separates observation, interpretation, alternatives, and evidence', async () => {
  render(<ReflectionDrawer />)
  expect(await screen.findByText(reflection.observation)).toBeInTheDocument()
  expect(screen.getByText(reflection.interpretation)).toBeInTheDocument()
  expect(screen.getByText(reflection.alternatives[0])).toBeInTheDocument()
  expect(screen.getByText(reflection.evidence[0].summary)).toBeInTheDocument()
})

test('reviews a reflection using its revision hash', async () => {
  render(<ReflectionDrawer />)
  fireEvent.change(await screen.findByLabelText('Review note for reflection-1'), {
    target: { value: 'Priority changed; this pattern is wrong.' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Reject' }))

  await waitFor(() => expect(api.reviewReflection).toHaveBeenCalledWith(
    'reflection-1',
    expect.objectContaining({
      action: 'reject',
      note: 'Priority changed; this pattern is wrong.',
      revision_hash: 'revision-1',
    }),
  ))
})
