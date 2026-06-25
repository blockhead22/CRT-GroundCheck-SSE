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
  vi.mocked(api.consolidationCandidates).mockResolvedValue(preview)
})

test('renders preview-only consolidation candidates and safety flags', async () => {
  render(<ConsolidationDrawer />)

  expect(await screen.findByText(preview.candidates[0].summary)).toBeInTheDocument()
  expect(screen.getByText(preview.candidates[1].summary)).toBeInTheDocument()
  expect(screen.getByLabelText('Consolidation safety')).toHaveTextContent('preview only')
  expect(screen.getByLabelText('Consolidation safety')).toHaveTextContent('writes no')
  expect(screen.getAllByText('no memory write').length).toBeGreaterThan(0)
  expect(screen.getAllByText('not a fact').length).toBeGreaterThan(0)
  expect(screen.getByText(/open_slot_review via \/v1\/slots\/user:workspace/i)).toBeInTheDocument()
  expect(screen.getByText('adapter required before applying')).toBeInTheDocument()
  expect(screen.getByText('Draft payload')).toBeInTheDocument()
  expect(screen.getByText(/background_consolidation_support_pattern/)).toBeInTheDocument()
  expect(screen.getByText(/Preview only. The review drawer still has to adapt and submit this manually./)).toBeInTheDocument()
})

test('refreshes consolidation preview on demand', async () => {
  render(<ConsolidationDrawer />)

  fireEvent.click(await screen.findByRole('button', { name: 'Refresh' }))

  await waitFor(() => expect(api.consolidationCandidates).toHaveBeenCalledTimes(2))
})

test('opens the mapped review surface without applying the candidate', async () => {
  const onOpenReviewSurface = vi.fn()
  render(<ConsolidationDrawer onOpenReviewSurface={onOpenReviewSurface} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Open Memory' }))
  fireEvent.click(screen.getByRole('button', { name: 'Open Support' }))

  expect(onOpenReviewSurface).toHaveBeenCalledWith('memory', { slotId: 'user:workspace' })
  expect(onOpenReviewSurface).toHaveBeenCalledWith('support', { slotId: undefined })
})
