import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { ChatPanel } from './ChatPanel'
import { api, streamChat } from '../api'

vi.mock('../api', () => ({
  api: {
    turns: vi.fn(async () => []),
    trace: vi.fn(),
    escalate: vi.fn(),
    createContinuityOpenLoop: vi.fn(),
    reviewContinuityOpenLoop: vi.fn(),
  },
  idempotencyKey: vi.fn((prefix: string) => `${prefix}-fixed-key`),
  streamChat: vi.fn(),
}))

const mockedStreamChat = vi.mocked(streamChat)
const mockedApi = vi.mocked(api)

function renderPanel(overrides: Partial<ComponentProps<typeof ChatPanel>> = {}) {
  const props = {
    model: 'qwen3:14b',
    renderProvider: 'local' as const,
    conversationId: null,
    conversations: [],
    turns: [],
    codexAvailable: false,
    trace: null,
    onConversation: vi.fn(),
    onNewConversation: vi.fn(),
    onDeleteConversation: vi.fn(),
    onTrace: vi.fn(),
    onOpenTrace: vi.fn(),
    onTurns: vi.fn(),
    ...overrides,
  }
  render(<ChatPanel {...props} />)
  return props
}

function continuityTrace(state: 'inferred_candidate' | 'explicit_open_loop') {
  const evidenceId = state === 'explicit_open_loop'
    ? 'continuity_open_loop:loop-1'
    : 'continuity_candidate:review-worktree'
  return {
    query: '/next',
    status: 'answerable',
    turn_id: 'turn-next',
    conversation_id: 'conv-next',
    model: 'qwen3:14b',
    plan: {
      status: 'complete',
      coverage: 1,
      unresolved_clauses: [],
      clauses: [],
    },
    packets: [],
    continuity_claim_atoms: {
      schema: 'aether.continuity_claim_atoms.v0',
      request_kind: 'next',
      atoms: [{
        atom_id: 'continuity-atom:next',
        section: 'next_candidate',
        proposition: 'Verify the structured next-step action.',
        state,
        evidence_ids: [evidenceId],
      }],
    },
    continuity_packet: {
      schema: 'aether.continuity_pack.v0',
      request_kind: 'next',
      open_loops: state === 'explicit_open_loop' ? [{
        item_id: 'open-loop:loop-1',
        category: 'explicit_open_loop',
        summary: 'Verify the structured next-step action.',
        state: 'unresolved',
        evidence_ids: [evidenceId],
        loop_id: 'loop-1',
        source_type: 'user_explicit',
        revision_hash: 'revision-1',
      }] : [],
    },
    memory_writes: [],
  }
}

const continuityTurn = {
  turn_id: 'turn-next',
  user_message: '/next',
  local_answer: 'Rendered prose must not become the stored summary.',
  model: 'qwen3:14b',
  needs_stronger_model: false,
  created_at: 1,
  completed_at: 2,
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  mockedApi.turns.mockResolvedValue([])
  mockedApi.createContinuityOpenLoop.mockResolvedValue({
    loop_id: 'loop-created',
    project_root: 'D:/AI_round2/aether-core',
    summary: 'Verify the structured next-step action.',
    source_type: 'user_explicit',
    status: 'open',
    idempotency_key: 'create-key',
    created_at: 1,
    updated_at: 1,
    revision_hash: 'revision-created',
  })
  mockedApi.reviewContinuityOpenLoop.mockImplementation(async (_loopId, body) => ({
    loop_id: 'loop-created',
    project_root: 'D:/AI_round2/aether-core',
    summary: 'Verify the structured next-step action.',
    source_type: 'user_explicit',
    status: body.action === 'done' ? 'done' : 'deferred',
    idempotency_key: 'create-key',
    created_at: 1,
    updated_at: 2,
    revision_hash: 'revision-reviewed',
  }))
  mockedApi.trace.mockResolvedValue({
    trace: {
      query: '/resume',
      status: 'answerable',
      turn_id: 'turn-resume',
      conversation_id: 'conv-resume',
      model: 'qwen3:14b',
      generation_model: 'deterministic',
      plan: {
        status: 'complete',
        coverage: 1,
        unresolved_clauses: [],
        clauses: [],
      },
      packets: [],
      public_governance_steps: [{
        schema: 'aether.public_governance_step.v0',
        step_id: 'gov-step-09-answer_fallback',
        index: 9,
        phase: 'answer_fallback',
        status: 'done',
        summary: 'Used deterministic Continuity fallback',
        detail: 'The repaired model answer still failed verification.',
        public: true,
        raw_chain_of_thought: false,
      }],
      memory_writes: [],
    },
  })
  mockedStreamChat.mockImplementation(async (_body, events) => {
    events.onTurn({ turn_id: 'turn-resume', conversation_id: 'conv-resume' })
    events.onTrace({
      query: '/resume',
      status: 'answerable',
      turn_id: 'turn-resume',
      conversation_id: 'conv-resume',
      model: 'qwen3:14b',
      generation_model: 'mistral:latest',
      plan: {
        status: 'complete',
        coverage: 1,
        unresolved_clauses: [],
        clauses: [],
      },
      packets: [],
      public_governance_steps: [],
      memory_writes: [],
    })
    events.onGovernanceStep?.({
      schema: 'aether.public_governance_step.v0',
      step_id: 'gov-step-01-source_check',
      index: 1,
      phase: 'source_check',
      status: 'done',
      summary: 'Checked Continuity sources',
      detail: '3 bounded read-only receipts.',
      public: true,
      raw_chain_of_thought: false,
    })
    events.onToken('Resume answer')
    events.onDone({
      answer: 'Resume answer',
      needs_stronger_model: false,
      memory_writes: [],
      document_write: null,
      tool_runs: [],
      source: 'aether_continuity_model',
      generation_model: 'mistral:latest',
    })
  })
})

describe('Continuity Resume action', () => {
  test('sends an explicit hosted wording choice and labels rehydrated Grok output', async () => {
    renderPanel({
      renderProvider: 'grok_build',
      conversationId: 'conv-next',
      turns: [{
        ...continuityTurn,
        render_provider: {
          requested: 'grok_build',
          effective: 'grok_build',
          model: 'grok-4.5',
          status: 'rendered',
          authority: 'aether',
          role: 'wording_only',
        },
      }],
    })

    expect(screen.getByText('Grok 4.5 · hosted wording')).toBeInTheDocument()
    expect(screen.getByText('Hosted Grok answer')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Message Aether'), {
      target: { value: 'Explain this governed packet.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    await waitFor(() => expect(mockedStreamChat).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'Explain this governed packet.',
        render_provider: 'grok_build',
      }),
      expect.any(Object),
    ))
  })

  test('shows a counted verification receipt instead of a blanket checked label', () => {
    renderPanel({
      conversationId: 'conv-next',
      turns: [continuityTurn],
      trace: {
        ...continuityTrace('explicit_open_loop'),
        completion: {
          needs_stronger_model: false,
          verification_summary: {
            schema: 'aether.completion_verification.v0',
            accepted: true,
            all_applicable_checks_passed: true,
            fully_verified: false,
            applicable_dimension_count: 5,
            checked_dimension_count: 4,
            passed_dimension_count: 4,
            failed_dimension_count: 0,
            not_checked_dimension_count: 1,
            dimensions: {},
            raw_chain_of_thought_stored: false,
          },
        },
      },
    })

    expect(screen.getByText('Checked 4/5')).toBeInTheDocument()
    expect(screen.queryByText(/^Checked$/)).not.toBeInTheDocument()
  })

  test('shows the persisted completion receipt after conversation rehydration', () => {
    renderPanel({
      conversationId: 'conv-next',
      turns: [{
        ...continuityTurn,
        completion_verification: {
          schema: 'aether.completion_verification.v0',
          accepted: true,
          all_applicable_checks_passed: true,
          fully_verified: true,
          applicable_dimension_count: 4,
          checked_dimension_count: 4,
          passed_dimension_count: 4,
          failed_dimension_count: 0,
          not_checked_dimension_count: 0,
          dimensions: {},
          raw_chain_of_thought_stored: false,
        },
      }],
      trace: null,
    })

    expect(screen.getByText('Verified 4/4')).toBeInTheDocument()
    expect(screen.queryByText('Checks unavailable')).not.toBeInTheDocument()
  })

  test('sends the exact governed command through the normal chat stream', async () => {
    const props = renderPanel()

    fireEvent.click(screen.getByRole('button', {
      name: 'Resume work from governed evidence',
    }))

    await waitFor(() => expect(mockedStreamChat).toHaveBeenCalledWith(
      {
        message: '/resume',
        conversation_id: undefined,
        model: 'qwen3:14b',
        voice_profile: 'warm',
        render_provider: 'local',
      },
      expect.any(Object),
    ))
    expect(props.onConversation).toHaveBeenCalledWith('conv-resume')
    expect(props.onTrace).toHaveBeenCalledWith(expect.objectContaining({
      turn_id: 'turn-resume',
      memory_writes: [],
    }))
    expect(mockedApi.trace).toHaveBeenCalledWith('turn-resume')
    expect(props.onTrace).toHaveBeenCalledWith(expect.objectContaining({
      public_governance_steps: [expect.objectContaining({
        phase: 'answer_fallback',
        status: 'done',
      })],
    }))
  })

  test('keeps the action icon-only with an explicit tooltip', () => {
    renderPanel()

    const button = screen.getByRole('button', {
      name: 'Resume work from governed evidence',
    })
    expect(button).toHaveAttribute('title', 'Resume work from governed evidence')
    expect(button).toHaveTextContent('')
  })
})

describe('Cross-conversation continuity controls', () => {
  test('rehydrates the source chip and opens the cited conversation', () => {
    const props = renderPanel({
      conversationId: 'conv-destination',
      turns: [{
        ...continuityTurn,
        continuity_alignment_receipt: {
          schema: 'aether.continuity_alignment_receipt.v0',
          status: 'exact',
          retrieval_method: 'exact_id',
          source_conversation_ids: ['conv-source'],
          source_conversations: [{
            conversation_id: 'conv-source',
            title: 'Fictional source thread',
          }],
          candidate_conversations: [],
          destination_conversation_id: 'conv-destination',
          destination_turn_id: 'turn-next',
          cited_turn_ids: ['turn-source'],
          carried_claims: [],
          clarification_required: false,
          profile_memory_write_count: 0,
          archived_conversation_promoted_to_profile_memory: false,
        },
      }],
    })

    expect(screen.getByText('exact cross-chat alignment')).toBeInTheDocument()
    expect(screen.getByText('Fictional source thread')).toBeInTheDocument()
    expect(screen.getByText('Conversation context only · no profile memory written')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', {
      name: 'Open source conversation conv-source',
    }))
    expect(props.onConversation).toHaveBeenCalledWith('conv-source')
  })

  test('starts a new explicitly aligned chat from the selected conversation', async () => {
    const props = renderPanel({ conversationId: 'conv-source' })

    fireEvent.click(screen.getByRole('button', {
      name: 'Continue current chat in a new aligned chat',
    }))

    expect(props.onNewConversation).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(mockedStreamChat).toHaveBeenCalledWith(
      {
        message: (
          'Continue from conversation conv-source and explicitly align this new '
          + 'conversation with it.'
        ),
        conversation_id: undefined,
        model: 'qwen3:14b',
        voice_profile: 'warm',
        render_provider: 'local',
      },
      expect.any(Object),
    ))
  })

  test('lets an ambiguous receipt choose a candidate without a silent selection', async () => {
    const props = renderPanel({
      conversationId: 'conv-destination',
      turns: [{
        ...continuityTurn,
        continuity_alignment_receipt: {
          schema: 'aether.continuity_alignment_receipt.v0',
          status: 'ambiguous',
          retrieval_method: 'semantic',
          source_conversation_ids: [],
          source_conversations: [],
          candidate_conversations: [{
            conversation_id: 'conv-candidate',
            title: 'Candidate source',
            match_kind: 'lexical_fallback',
            score: 0.9,
          }],
          destination_conversation_id: 'conv-destination',
          destination_turn_id: 'turn-next',
          cited_turn_ids: [],
          carried_claims: [],
          clarification_required: true,
          profile_memory_write_count: 0,
          archived_conversation_promoted_to_profile_memory: false,
        },
      }],
    })

    expect(screen.getByText('ambiguous cross-chat alignment')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', {
      name: 'Continue from candidate conversation conv-candidate',
    }))
    expect(props.onNewConversation).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(mockedStreamChat).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining('conversation conv-candidate'),
        conversation_id: undefined,
      }),
      expect.any(Object),
    ))
  })
})

describe('Continuity open-loop actions', () => {
  test('does not write until Pin is clicked and uses the structured atom', async () => {
    renderPanel({
      conversationId: 'conv-next',
      turns: [continuityTurn],
      trace: continuityTrace('inferred_candidate'),
    })

    expect(mockedApi.createContinuityOpenLoop).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Pin as open next step' }))

    await waitFor(() => expect(mockedApi.createContinuityOpenLoop).toHaveBeenCalledWith(
      'Verify the structured next-step action.',
      expect.stringContaining('continuity-pin-turn-next'),
    ))
    expect(mockedApi.createContinuityOpenLoop).not.toHaveBeenCalledWith(
      expect.stringContaining('Rendered prose'),
      expect.any(String),
    )
    expect(await screen.findByText('Pinned as open next step')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mark open next step done' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Defer open next step' })).toBeInTheDocument()
  })

  test('reviews an explicit trace-bound loop with its current revision', async () => {
    renderPanel({
      conversationId: 'conv-next',
      turns: [continuityTurn],
      trace: continuityTrace('explicit_open_loop'),
    })

    expect(mockedApi.reviewContinuityOpenLoop).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Mark open next step done' }))

    await waitFor(() => expect(mockedApi.reviewContinuityOpenLoop).toHaveBeenCalledWith(
      'loop-1',
      expect.objectContaining({
        action: 'done',
        revision_hash: 'revision-1',
        idempotency_key: expect.stringContaining('continuity-done-loop-1'),
      }),
    ))
    expect(await screen.findByText('Marked done')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mark open next step done' })).not.toBeInTheDocument()
  })
})
