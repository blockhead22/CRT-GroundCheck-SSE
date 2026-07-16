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
