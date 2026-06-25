import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { api } from '../api'
import { buildSupportDraftCandidate } from '../learnDraftPromotion'
import { SupportPatternDrawer } from './SupportPatternDrawer'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return {
    ...actual,
    api: {
      supportPatterns: vi.fn(),
      reviewSupportPattern: vi.fn(),
      importSupportPatterns: vi.fn(),
    },
  }
})

const candidate = {
  candidate_id: 'support-1',
  candidate_type: 'archive_support_pattern' as const,
  category: 'motivation_support',
  candidate_kind: 'support_preference',
  summary: 'Nick may value grounded motivational re-entry.',
  suggested_response_rule: 'Use warm practical re-entry language and end with next steps.',
  risk: 'Do not infer sensitive facts from archive titles.',
  source_signal: 'title_category_count',
  title_category_count: 15,
  status: 'proposed_review' as const,
  review_required: true,
  memory_write_allowed: false,
  confirmed_fact: false,
  created_at: 1,
  updated_at: 1,
  evidence: [{
    evidence_type: 'title_only_example',
    conversation_id: 'conv-1',
    title: 'Dork spiral motivation walking scale check',
    created_at: '2026-01-01T00:00:00+00:00',
  }],
  reviews: [],
  revision_hash: 'support-revision-1',
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.supportPatterns).mockResolvedValue([candidate])
  vi.mocked(api.reviewSupportPattern).mockResolvedValue({})
  vi.mocked(api.importSupportPatterns).mockResolvedValue({ imported_count: 1, candidates: [candidate] })
})

test('renders support-pattern candidates with review boundaries', async () => {
  render(<SupportPatternDrawer />)

  expect(await screen.findByText(candidate.summary)).toBeInTheDocument()
  expect(screen.getByText(candidate.suggested_response_rule)).toBeInTheDocument()
  expect(screen.getByText(candidate.risk)).toBeInTheDocument()
  expect(screen.getByText('not a fact')).toBeInTheDocument()
  expect(screen.getByText(candidate.evidence[0].title)).toBeInTheDocument()
})

test('reviews a support pattern using its revision hash', async () => {
  render(<SupportPatternDrawer />)
  fireEvent.change(await screen.findByLabelText('Review note for support-1'), {
    target: { value: 'Approved as style guidance only.' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Accept' }))

  await waitFor(() => expect(api.reviewSupportPattern).toHaveBeenCalledWith(
    'support-1',
    expect.objectContaining({
      action: 'accept',
      note: 'Approved as style guidance only.',
      revision_hash: 'support-revision-1',
    }),
  ))
})

test('filters support patterns by status', async () => {
  render(<SupportPatternDrawer />)
  fireEvent.click(await screen.findByRole('button', { name: /Accepted/i }))

  await waitFor(() => expect(api.supportPatterns).toHaveBeenLastCalledWith('accepted'))
})

test('shows learner draft as manual support form state without importing it', async () => {
  render(<SupportPatternDrawer draftHandoff={{
    source_candidate_id: 'consolidation_candidate_support',
    source_category: 'support_style_candidate',
    candidate_kind: 'reviewed_support_pattern_candidate',
    summary: 'This turn may contain a reusable support-style preference.',
    proposed_action: 'Route through support-pattern review.',
    risk: 'Do not copy another model voice.',
    draft: {
      category: 'support_style',
      candidate_kind: 'reviewed_support_pattern_candidate',
      suggested_response_rule: 'Use practical re-entry language.',
    },
    evidence: [],
  }} />)

  expect(await screen.findByText(/Nothing has been imported/)).toBeTruthy()
  expect(screen.getByLabelText('Draft support category')).toHaveValue('support_style')
  expect(screen.getByLabelText('Draft support response rule')).toHaveValue('Use practical re-entry language.')
  expect(screen.getByLabelText('Draft support boundary')).toHaveValue('Do not copy another model voice.')
  expect(api.reviewSupportPattern).not.toHaveBeenCalled()
  expect(api.importSupportPatterns).not.toHaveBeenCalled()
})

test('builds a proposed support candidate payload from learner draft without accepting it', () => {
  const draftHandoff = {
    source_candidate_id: 'consolidation_candidate_support',
    source_category: 'support_style_candidate',
    candidate_kind: 'reviewed_support_pattern_candidate',
    summary: 'This turn may contain a reusable support-style preference.',
    proposed_action: 'Route through support-pattern review.',
    risk: 'Do not copy another model voice.',
    draft: {
      category: 'support_style',
      candidate_kind: 'reviewed_support_pattern_candidate',
      suggested_response_rule: 'Use practical re-entry language.',
    },
    evidence: [{
      evidence_type: 'user_turn_excerpt',
      reference_id: 'turn-1',
      summary: 'Nick asked for a warm dork spiral.',
    }],
  }

  expect(buildSupportDraftCandidate(draftHandoff, {
    category: 'support_style',
    candidateKind: 'reviewed_support_pattern_candidate',
    summary: 'This turn may contain a reusable support-style preference.',
    suggestedResponseRule: 'Use practical re-entry language.',
    risk: 'Do not copy another model voice.',
  })).toEqual(expect.objectContaining({
    candidate_id: 'learn_consolidation_candidate_support',
    candidate_type: 'archive_support_pattern',
    category: 'support_style',
    candidate_kind: 'reviewed_support_pattern_candidate',
    summary: 'This turn may contain a reusable support-style preference.',
    suggested_response_rule: 'Use practical re-entry language.',
    risk: 'Do not copy another model voice.',
    source_signal: 'learner_consolidation_candidate',
    title_category_count: 1,
    evidence: [{
      evidence_type: 'user_turn_excerpt',
      conversation_id: 'turn-1',
      title: 'Nick asked for a warm dork spiral.',
    }],
    status: 'proposed_review',
    review_required: true,
    memory_write_allowed: false,
    confirmed_fact: false,
  }))
})
