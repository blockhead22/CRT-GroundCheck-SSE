import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { api } from '../api'
import { SupportPatternDrawer } from './SupportPatternDrawer'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return {
    ...actual,
    api: {
      supportPatterns: vi.fn(),
      reviewSupportPattern: vi.fn(),
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
  vi.mocked(api.supportPatterns).mockResolvedValue([candidate])
  vi.mocked(api.reviewSupportPattern).mockResolvedValue({})
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
