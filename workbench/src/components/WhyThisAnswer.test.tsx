import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import type { Trace } from '../types'
import {
  WhyThisAnswer,
  buildAnswerFooterLine,
  friendlyChatError,
} from './WhyThisAnswer'

function baseTrace(overrides: Partial<Trace> = {}): Trace {
  return {
    query: 'test',
    status: 'answerable',
    turn_id: 'turn-1',
    conversation_id: 'conv-1',
    model: 'qwen3:14b',
    plan: { status: 'complete', coverage: 1, unresolved_clauses: [], clauses: [] },
    packets: [],
    memory_writes: [],
    ...overrides,
  } as Trace
}

describe('friendlyChatError', () => {
  test('maps network and cancel conflicts to plain English', () => {
    expect(friendlyChatError('Failed to fetch')).toMatch(/sidecar/i)
    expect(friendlyChatError('run is no longer active')).toMatch(/finished/i)
    expect(friendlyChatError('Request failed (409)')).toMatch(/conflicted|finished|stop/i)
  })
})

describe('buildAnswerFooterLine', () => {
  test('nudges open Why when trace is missing', () => {
    expect(buildAnswerFooterLine(null)).toMatch(/Why/i)
  })

  test('mentions personal facts and tools', () => {
    const line = buildAnswerFooterLine(baseTrace({
      packets: [{
        clause_id: 'c1',
        release: 'answerable',
        slot_id: 'user:favorite_color',
        evidence: [{ value: 'orange' } as never],
      } as never],
      tool_runs: [{
        tool_run_id: 't1',
        tool: 'workspace_search',
        status: 'ok',
        output: {
          results: [
            { path: 'D:/AI_round2/aether-core/holden.py' },
            { path: 'D:/AI_round2/aether-core/mirus.py' },
          ],
        },
      } as never],
    }))
    expect(line).toMatch(/personal fact/i)
    expect(line).toMatch(/tool/i)
  })
})

describe('WhyThisAnswer', () => {
  test('shows honesty callout when only project context was used', () => {
    render(
      <WhyThisAnswer
        trace={baseTrace({
          route_decision: { selected_route: 'context_bridge_project' } as never,
          context_bridge: { project: { title: 'Aether' } } as never,
        })}
      />,
    )
    expect(screen.getByText(/Not from your personal profile/i)).toBeInTheDocument()
    expect(screen.getByText(/No personal memory facts/i)).toBeInTheDocument()
  })

  test('links personal facts into Knows when handler is provided', () => {
    const onOpenKnows = vi.fn()
    render(
      <WhyThisAnswer
        onOpenKnows={onOpenKnows}
        trace={baseTrace({
          packets: [{
            clause_id: 'c1',
            release: 'answerable',
            slot_id: 'user:favorite_color',
            evidence: [{ value: 'orange' } as never],
          } as never],
        })}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Review in Knows' }))
    expect(onOpenKnows).toHaveBeenCalledWith('user:favorite_color')
  })

  test('lists tool receipt paths', () => {
    render(
      <WhyThisAnswer
        trace={baseTrace({
          tool_runs: [{
            tool_run_id: 't1',
            tool: 'workspace_search',
            status: 'ok',
            output: {
              results: [
                { path: 'D:/AI_round2/aether-core/aether/sidecar/holden_notes.py' },
              ],
            },
          } as never],
        })}
      />,
    )
    expect(screen.getByText(/workspace search/i)).toBeInTheDocument()
    expect(screen.getByText(/holden_notes\.py/i)).toBeInTheDocument()
  })

  test('shows stopped callout for cancelled runs', () => {
    render(
      <WhyThisAnswer
        trace={baseTrace({
          run_state: { status: 'cancelled' } as never,
        })}
      />,
    )
    expect(screen.getByText(/This run was stopped/i)).toBeInTheDocument()
  })
})
