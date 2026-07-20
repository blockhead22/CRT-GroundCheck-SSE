import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { api } from '../api'
import { ConsolidationDrawer } from './ConsolidationDrawer'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return {
    ...actual,
    api: {
      consolidationCandidates: vi.fn(),
      reviewTaskCandidate: vi.fn(),
    },
  }
})

const preview = {
  mode: 'preview_only' as const,
  writes_performed: false,
  memory_ingestion_performed: false,
  support_pattern_import_performed: false,
  reflection_create_performed: false,
  task_authority_write_performed: false,
  reviewed_task_candidate_count: 0,
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
    review_only: true,
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
    review_only: true,
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
  }, {
    candidate_id: 'consolidation_candidate_archive',
    candidate_type: 'background_consolidation_candidate' as const,
    category: 'archive_evidence_candidate',
    candidate_kind: 'reviewed_archive_evidence_candidate',
    summary: 'Archive/document search found 1 bounded historical evidence hit, led by ChatGPT archive - grounded support.',
    proposed_action: 'Review whether this archive evidence should become a support pattern, reflection, eval prompt, or remain only a trace receipt.',
    risk: 'Do not treat GPT/archive document hits as confirmed memory or clone another assistant voice.',
    review_required: true,
    memory_write_allowed: false,
    confirmed_fact: false,
    review_only: true,
    review_route: {
      surface: 'reflections',
      action: 'draft_archive_evidence_review',
      endpoint: '/v1/reflections',
      requires_adapter: true,
      draft: {
        subject: 'workflow',
        observation: 'Archive/document search found bounded historical evidence: ChatGPT archive - grounded support.',
        interpretation: 'This archive hit may be useful as historical evidence, but it is not confirmed memory.',
        alternatives: ['The archive result may be outdated or merely stylistic.'],
        confidence: 0.5,
        time_window: 'recent archive/document search',
        suggested_experiment: 'Review the source hit before promoting behavior.',
        review_required: true,
        memory_write_allowed: false,
        confirmed_fact: false,
      },
    },
    evidence: [{
      evidence_type: 'chatgpt_archive',
      reference_id: 'doc_archive_1',
      summary: 'ChatGPT archive - grounded support: Historical GPT archive note: Nick asks for grounded, receipt-backed answers. This receipt continues with enough archive-derived context to prove that long evidence rows stay compact by default instead of turning the learner queue into a transcript wall.',
    }, {
      evidence_type: 'safety_contract',
      reference_id: 'archive_document_evidence_candidate',
      summary: 'review_only; archive hits are historical evidence, not confirmed memory; support/reflection writes blocked',
    }],
  }, {
    candidate_id: 'consolidation_candidate_3',
    candidate_type: 'background_consolidation_candidate' as const,
    category: 'aether_self_improvement',
    candidate_kind: 'repair_trace_reflection_candidate',
    summary: 'A repair trace suggests a reusable learner reflection.',
    proposed_action: 'Route through reflection review.',
    risk: 'Do not mutate behavior from one trace without review.',
    review_required: true,
    memory_write_allowed: false,
    confirmed_fact: false,
    review_only: true,
    review_route: {
      surface: 'reflections',
      action: 'draft_reflection_candidate',
      endpoint: '/v1/reflections',
      requires_adapter: true,
      draft: {
        subject: 'agent',
        observation: 'A repair trace suggests a reusable learner reflection.',
        interpretation: 'The response may need a clearer verifier boundary.',
        alternatives: ['This may be a one-off trace issue.'],
        confidence: 0.55,
        time_window: 'recent traces',
        suggested_experiment: 'Watch the next similar answer before changing policy.',
      },
    },
    evidence: [{
      evidence_type: 'trace_repair',
      reference_id: 'turn-3',
      summary: 'Repair trace showed a verifier boundary correction.',
      source_authority: 'trace_verifier',
    }],
  }, {
    candidate_id: 'consolidation_candidate_task',
    candidate_type: 'background_consolidation_candidate' as const,
    category: 'task_authority_candidate',
    candidate_kind: 'reviewed_open_loop_candidate',
    summary: 'Mirus noticed a possible open loop: Edit footage. It has no task authority yet.',
    proposed_action: 'Promote this reviewed action into an explicit open loop.',
    risk: 'The source may be temporary; require explicit promotion.',
    review_required: true,
    memory_write_allowed: false,
    confirmed_fact: false,
    review_only: true,
    review_route: {
      surface: 'task_state',
      action: 'review_task_authority_candidate',
      endpoint: '/v1/consolidation/task-candidates/{candidate_id}/review',
      requires_adapter: false,
      draft: {
        source_candidate_id: 'task_candidate_edit',
        source_turn_id: 'turn-task',
        record_kind: 'open_loop',
        summary: 'Edit footage.',
        category: 'direct_planning_action',
        source_type: 'review_confirmed',
        review_required: true,
        task_authority_write_allowed: false,
        memory_write_allowed: false,
        confirmed_fact: false,
      },
    },
    evidence: [{
      evidence_type: 'mirus_task_intake',
      reference_id: 'turn-task',
      summary: 'I need to edit footage.',
      source_authority: 'user_turn',
    }],
  }],
}

beforeEach(() => {
  vi.mocked(api.consolidationCandidates).mockClear()
  vi.mocked(api.consolidationCandidates).mockResolvedValue(preview)
  vi.mocked(api.reviewTaskCandidate).mockClear()
  vi.mocked(api.reviewTaskCandidate).mockResolvedValue({
    review: {
      review_id: 'task-review-1',
      candidate_id: 'consolidation_candidate_task',
      action: 'promote',
      note: 'Promoted explicitly.',
      created_record_kind: 'open_loop',
      created_record_id: 'continuity_loop_1',
      created_at: 1,
    },
    authority_record: { loop_id: 'continuity_loop_1' },
    memory_write_performed: false,
    task_authority_write_performed: true,
  })
})

test('renders preview-only consolidation candidates and safety flags', async () => {
  render(<ConsolidationDrawer />)

  expect(await screen.findByText(preview.candidates[0].summary)).toBeInTheDocument()
  expect(screen.getByText(preview.candidates[1].summary)).toBeInTheDocument()
  expect(screen.getByText(preview.candidates[2].summary)).toBeInTheDocument()
  expect(screen.getByText(preview.candidates[3].summary)).toBeInTheDocument()
  expect(screen.getByText(preview.candidates[4].summary)).toBeInTheDocument()
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
    'review only',
  )
  expect(screen.getByLabelText('Why consolidation_candidate_1 exists')).toHaveTextContent(
    'open_slot_review -> memory',
  )
  expect(screen.getAllByText('review only').length).toBeGreaterThan(0)
  expect(screen.getByText('trace_packet / turn-1 / trace_conflict')).toBeInTheDocument()
  expect(screen.getByText(/open_slot_review via \/v1\/slots\/user:workspace/i)).toBeInTheDocument()
  expect(screen.getAllByText('adapter required before applying')).toHaveLength(3)
  expect(screen.getAllByText('Draft payload')).toHaveLength(4)
  expect(screen.getAllByText(/Preview only. The review drawer still has to adapt and submit this manually./)).toHaveLength(3)
  expect(screen.getByText(/Explicit promotion is required before this reaches task state./)).toBeInTheDocument()
  for (const details of document.querySelectorAll('.consolidation-draft')) {
    expect(details).not.toHaveAttribute('open')
  }
  fireEvent.click(screen.getAllByText('Draft payload')[0])
  expect(screen.getByText(/background_consolidation_support_pattern/)).toBeInTheDocument()
  expect(screen.getByText(/draft_archive_evidence_review via \/v1\/reflections/i)).toBeInTheDocument()
  expect(screen.getByText(/archive hits are historical evidence, not confirmed memory/i)).toBeInTheDocument()
  expect(screen.getByText(/turning the learner queue.../i).closest('details')).not.toHaveAttribute('open')
  expect(screen.getByText(/draft_reflection_candidate via \/v1\/reflections/i)).toBeInTheDocument()
  expect(screen.getAllByText(/repair trace showed a verifier boundary correction/i)).toHaveLength(2)
})

test('filters mixed learner candidates and triages in session only', async () => {
  const onOpenReviewSurface = vi.fn()
  render(<ConsolidationDrawer onOpenReviewSurface={onOpenReviewSurface} />)

  expect(await screen.findByText(preview.candidates[0].summary)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /^Memory\s+1$/ })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /^Support\s+1$/ }))

  expect(screen.queryByText(preview.candidates[0].summary)).not.toBeInTheDocument()
  expect(screen.getByText(preview.candidates[1].summary)).toBeInTheDocument()
  expect(screen.queryByText(preview.candidates[2].summary)).not.toBeInTheDocument()
  expect(screen.queryByText(preview.candidates[3].summary)).not.toBeInTheDocument()
  expect(screen.queryByText(preview.candidates[4].summary)).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /^Reflect\s+2$/ }))
  expect(screen.queryByText(preview.candidates[1].summary)).not.toBeInTheDocument()
  expect(screen.getByText(preview.candidates[2].summary)).toBeInTheDocument()
  expect(screen.getByText(preview.candidates[3].summary)).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /^Support\s+1$/ }))
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

test('explicitly promotes a task candidate and refreshes the review queue', async () => {
  vi.mocked(api.consolidationCandidates)
    .mockResolvedValueOnce(preview)
    .mockResolvedValueOnce({
      ...preview,
      reviewed_task_candidate_count: 1,
      candidates: preview.candidates.filter(
        (item) => item.candidate_id !== 'consolidation_candidate_task',
      ),
    })
  render(<ConsolidationDrawer />)

  await screen.findByText(preview.candidates[4].summary)
  fireEvent.click(screen.getByRole('button', { name: 'Promote to Task State' }))

  await waitFor(() => expect(api.reviewTaskCandidate).toHaveBeenCalledWith(
    'consolidation_candidate_task',
    expect.objectContaining({ action: 'promote' }),
  ))
  expect(await screen.findByText('Promoted to open loop task authority.')).toBeInTheDocument()
  await waitFor(() => expect(
    screen.queryByText(preview.candidates[4].summary),
  ).not.toBeInTheDocument())
})

test('explicitly rejects a task candidate without claiming a task write', async () => {
  vi.mocked(api.reviewTaskCandidate).mockResolvedValueOnce({
    review: {
      review_id: 'task-review-reject',
      candidate_id: 'consolidation_candidate_task',
      action: 'reject',
      note: 'Rejected explicitly.',
      created_record_kind: '',
      created_record_id: '',
      created_at: 1,
    },
    authority_record: null,
    memory_write_performed: false,
    task_authority_write_performed: false,
  })
  vi.mocked(api.consolidationCandidates)
    .mockResolvedValueOnce(preview)
    .mockResolvedValueOnce({
      ...preview,
      reviewed_task_candidate_count: 1,
      candidates: preview.candidates.filter(
        (item) => item.candidate_id !== 'consolidation_candidate_task',
      ),
    })
  render(<ConsolidationDrawer />)

  await screen.findByText(preview.candidates[4].summary)
  fireEvent.click(screen.getByRole('button', { name: 'Reject Candidate' }))

  await waitFor(() => expect(api.reviewTaskCandidate).toHaveBeenCalledWith(
    'consolidation_candidate_task',
    expect.objectContaining({ action: 'reject' }),
  ))
  expect(await screen.findByText(
    'Rejected candidate. No task authority or memory changed.',
  )).toBeInTheDocument()
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
  const reflectButtons = screen.getAllByRole('button', { name: 'Open Reflect' })
  fireEvent.click(reflectButtons[0])
  fireEvent.click(reflectButtons[1])

  expect(onOpenReviewSurface).toHaveBeenCalledWith('memory', expect.objectContaining({ slotId: 'user:workspace' }))
  expect(onOpenReviewSurface).toHaveBeenCalledWith('support', expect.objectContaining({
    slotId: undefined,
    draftHandoff: expect.objectContaining({
      source_candidate_id: 'consolidation_candidate_2',
      source_category: 'support_style_candidate',
    }),
  }))
  expect(onOpenReviewSurface).toHaveBeenCalledWith('reflect', expect.objectContaining({
    slotId: undefined,
    draftHandoff: expect.objectContaining({
      source_candidate_id: 'consolidation_candidate_3',
      source_category: 'aether_self_improvement',
    }),
  }))
  expect(onOpenReviewSurface).toHaveBeenCalledWith('reflect', expect.objectContaining({
    slotId: undefined,
    draftHandoff: expect.objectContaining({
      source_candidate_id: 'consolidation_candidate_archive',
      source_category: 'archive_evidence_candidate',
    }),
  }))
})
