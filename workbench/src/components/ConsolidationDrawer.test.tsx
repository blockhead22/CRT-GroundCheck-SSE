import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { api } from '../api'
import { ConsolidationDrawer } from './ConsolidationDrawer'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return {
    ...actual,
    api: {
      consolidationCandidates: vi.fn(),
    },
  }
})

const preview = {
  mode: 'preview_only' as const,
  writes_performed: false,
  memory_ingestion_performed: false,
  support_pattern_import_performed: false,
  reflection_create_performed: false,
  inspected_turn_count: 3,
  candidates: [{
    candidate_id: 'consolidation_candidate_1',
    candidate_type: 'background_consolidation_candidate' as const,
    category: 'contradiction_review',
    candidate_kind: 'contextual_conflict_review',
    summary: 'user:workspace has a contextual contradiction disposition.',
    proposed_action: 'Open memory review for user:workspace.',
    risk: 'Do not expose or select restricted conflicted values without review.',
    review_required: true,
    memory_write_allowed: false,
    confirmed_fact: false,
    review_route: {
      surface: 'memory',
      action: 'open_slot_review',
      endpoint: '/v1/slots/user:workspace',
      slot_id: 'user:workspace',
      disposition_label: 'contextual',
    },
    evidence: [{
      evidence_type: 'trace_packet',
      reference_id: 'turn-1',
      summary: 'user:workspace: contextual; values_may_depend_on_context',
      source_authority: 'trace_conflict',
    }],
  }, {
    candidate_id: 'consolidation_candidate_2',
    candidate_type: 'background_consolidation_candidate' as const,
    category: 'support_style_candidate',
    candidate_kind: 'reviewed_support_pattern_candidate',
    summary: 'This turn may contain reusable support-style preference.',
    proposed_action: 'Route through support-pattern review.',
    risk: 'Do not copy another model voice.',
    review_required: true,
    memory_write_allowed: false,
    confirmed_fact: false,
    review_route: {
      surface: 'support_patterns',
      action: 'draft_support_pattern_candidate',
      endpoint: '/v1/support-patterns/import',
      requires_adapter: true,
      draft: {
        candidate_type: 'background_consolidation_support_pattern',
        category: 'support_style',
        review_required: true,
        memory_write_allowed: false,
        confirmed_fact: false,
      },
    },
    evidence: [],
  }],
}

beforeEach(() => {
  vi.mocked(api.consolidationCandidates).mockClear()
  vi.mocked(api.consolidationCandidates).mockResolvedValue(preview)
})

test('renders preview-only consolidation candidates and safety flags', async () => {
  render(<ConsolidationDrawer />)

  expect(await screen.findByText(preview.candidates[0].summary)).toBeInTheDocument()
  expect(screen.getByText(preview.candidates[1].summary)).toBeInTheDocument()
  expect(screen.getByLabelText('Consolidation safety')).toHaveTextContent('preview only')
  expect(screen.getByLabelText('Consolidation safety')).toHaveTextContent('writes no')
  expect(screen.getByLabelText('Consolidation safety')).toHaveTextContent('session review only')
  expect(screen.getAllByText('no memory write').length).toBeGreaterThan(0)
  expect(screen.getAllByText('not a fact').length).toBeGreaterThan(0)
  expect(screen.getByLabelText('Why consolidation_candidate_1 exists')).toHaveTextContent(
    'user:workspace: contextual; values_may_depend_on_context',
  )
  expect(screen.getByLabelText('Why consolidation_candidate_1 exists')).toHaveTextContent(
    'memory write blocked',
  )
  expect(screen.getByLabelText('Why consolidation_candidate_1 exists')).toHaveTextContent(
    'open_slot_review -> memory',
  )
  expect(screen.getByText('trace_packet / turn-1 / trace_conflict')).toBeInTheDocument()
  expect(screen.getByText(/open_slot_review via \/v1\/slots\/user:workspace/i)).toBeInTheDocument()
  expect(screen.getByText('adapter required before applying')).toBeInTheDocument()
  expect(screen.getByText('Draft payload')).toBeInTheDocument()
  expect(screen.getByText(/background_consolidation_support_pattern/)).toBeInTheDocument()
  expect(screen.getByText(/Preview only. The review drawer still has to adapt and submit this manually./)).toBeInTheDocument()
})

test('filters and triages learner candidates in session only', async () => {
  const onOpenReviewSurface = vi.fn()
  render(<ConsolidationDrawer onOpenReviewSurface={onOpenReviewSurface} />)

  expect(await screen.findByText(preview.candidates[0].summary)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /^Support\s+1$/ }))

  expect(screen.queryByText(preview.candidates[0].summary)).not.toBeInTheDocument()
  expect(screen.getByText(preview.candidates[1].summary)).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Defer Session' }))
  expect(screen.getByText('deferred this session')).toBeInTheDocument()
  expect(onOpenReviewSurface).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole('button', { name: 'Hide Session' }))
  expect(screen.queryByText(preview.candidates[1].summary)).not.toBeInTheDocument()
  expect(screen.getByText('No active learner candidates match this route filter.')).toBeInTheDocument()
  expect(onOpenReviewSurface).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole('button', { name: /^Restore hidden\s+1$/ }))
  expect(screen.getByText(preview.candidates[1].summary)).toBeInTheDocument()
  expect(screen.getByText('active this session')).toBeInTheDocument()
  expect(api.consolidationCandidates).toHaveBeenCalledTimes(1)
})

test('refreshes consolidation preview on demand', async () => {
  render(<ConsolidationDrawer />)

  await screen.findByText(preview.candidates[0].summary)
  fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))

  await waitFor(() => expect(api.consolidationCandidates).toHaveBeenCalledTimes(2))
})

test('opens the mapped review surface without applying the candidate', async () => {
  const onOpenReviewSurface = vi.fn()
  render(<ConsolidationDrawer onOpenReviewSurface={onOpenReviewSurface} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Open Memory' }))
  fireEvent.click(screen.getByRole('button', { name: 'Open Support' }))

  expect(onOpenReviewSurface).toHaveBeenCalledWith('memory', expect.objectContaining({ slotId: 'user:workspace' }))
  expect(onOpenReviewSurface).toHaveBeenCalledWith('support', expect.objectContaining({
    slotId: undefined,
    draftHandoff: expect.objectContaining({
      source_candidate_id: 'consolidation_candidate_2',
      source_category: 'support_style_candidate',
    }),
  }))
})
