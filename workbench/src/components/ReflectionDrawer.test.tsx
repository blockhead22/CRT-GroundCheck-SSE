import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { api } from '../api'
import { buildReflectionDraftPayload } from '../learnDraftPromotion'
import { ReflectionDrawer } from './ReflectionDrawer'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return {
    ...actual,
    api: {
      reflections: vi.fn(),
      reviewReflection: vi.fn(),
      createReflection: vi.fn(),
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
  vi.clearAllMocks()
  vi.mocked(api.reflections).mockResolvedValue([reflection])
  vi.mocked(api.reviewReflection).mockResolvedValue({})
  vi.mocked(api.createReflection).mockResolvedValue(reflection)
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

test('shows learner draft as manual reflection form state without creating it', async () => {
  render(<ReflectionDrawer draftHandoff={{
    source_candidate_id: 'consolidation_candidate_reflection',
    source_category: 'aether_self_improvement',
    candidate_kind: 'reflection_candidate',
    summary: 'A recent answer may reveal an Aether behavior improvement worth reviewing.',
    proposed_action: 'Create a reviewed reflection only if it repeats.',
    risk: 'Do not convert one thin answer into a permanent behavior rule.',
    draft: {
      subject: 'agent',
      observation: 'A recent answer may reveal a behavior improvement.',
      confidence: 0.45,
      time_window: 'recent turns',
      suggested_experiment: 'Review similar traces before accepting.',
    },
    evidence: [],
  }} />)

  expect(await screen.findByLabelText('Draft reflection subject')).toHaveValue('agent')
  expect(screen.getByLabelText('Draft reflection observation')).toHaveValue('A recent answer may reveal a behavior improvement.')
  expect(screen.getByLabelText('Draft reflection suggested experiment')).toHaveValue('Review similar traces before accepting.')
  expect(api.reviewReflection).not.toHaveBeenCalled()
  expect(api.createReflection).not.toHaveBeenCalled()
})

test('builds a proposed reflection payload from learner draft without accepting it', () => {
  const draftHandoff = {
    source_candidate_id: 'consolidation_candidate_reflection',
    source_category: 'aether_self_improvement',
    candidate_kind: 'reflection_candidate',
    summary: 'A recent answer may reveal an Aether behavior improvement worth reviewing.',
    proposed_action: 'Create a reviewed reflection only if it repeats.',
    risk: 'Do not convert one thin answer into a permanent behavior rule.',
    draft: {
      subject: 'agent',
      observation: 'A recent answer may reveal a behavior improvement.',
      interpretation: 'The answer may show a repeatable repair.',
      alternatives: ['It may be a one-off prompt artifact.'],
      confidence: 0.45,
      time_window: 'recent turns',
      suggested_experiment: 'Review similar traces before accepting.',
    },
    evidence: [{
      evidence_type: 'trace_route',
      reference_id: 'turn-2',
      summary: 'real-use guidance repair',
    }],
  }

  expect(buildReflectionDraftPayload(draftHandoff, {
    subject: 'agent',
    observation: 'A recent answer may reveal a behavior improvement.',
    interpretation: 'The answer may show a repeatable repair.',
    alternatives: 'It may be a one-off prompt artifact.',
    confidence: '0.45',
    timeWindow: 'recent turns',
    suggestedExperiment: 'Review similar traces before accepting.',
  })).toEqual(expect.objectContaining({
    subject: 'agent',
    observation: 'A recent answer may reveal a behavior improvement.',
    interpretation: 'The answer may show a repeatable repair.',
    alternatives: ['It may be a one-off prompt artifact.'],
    confidence: 0.45,
    time_window: 'recent turns',
    suggested_experiment: 'Review similar traces before accepting.',
    evidence: expect.arrayContaining([
      expect.objectContaining({
        evidence_type: 'trace_route',
        reference_id: 'turn-2',
        summary: 'real-use guidance repair',
      }),
      expect.objectContaining({
        evidence_type: 'learner_risk_boundary',
        reference_id: 'consolidation_candidate_reflection',
        summary: 'Do not convert one thin answer into a permanent behavior rule.',
      }),
    ]),
  }))
})
