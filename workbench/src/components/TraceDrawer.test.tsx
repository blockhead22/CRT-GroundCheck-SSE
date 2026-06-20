import { render, screen } from '@testing-library/react'
import { TraceDrawer } from './TraceDrawer'
import type { Trace } from '../types'

const trace: Trace = {
  query: 'Where do I work and what is my hobby?',
  status: 'blocked',
  turn_id: 'turn_1',
  conversation_id: 'conv_1',
  model: 'qwen2.5:7b-instruct',
  plan: {
    status: 'resolved',
    coverage: 1,
    unresolved_clauses: [],
    clauses: [
      { clause_id: 'c1', text: 'Where do I work', status: 'resolved', candidate_slots: ['employer'], reason_code: 'resolved' },
      { clause_id: 'c2', text: 'what is my hobby', status: 'resolved', candidate_slots: ['hobby'], reason_code: 'resolved' },
    ],
  },
  packets: [
    {
      request_id: 'r1', clause_id: 'c1', clause_text: 'Where do I work', planner_slot: 'employer',
      slot_id: 'user:employer', mode: 'current', release: 'conflict', reason: 'distinct_current_values',
      evidence: [],
    },
    {
      request_id: 'r2', clause_id: 'c2', clause_text: 'what is my hobby', planner_slot: 'hobby',
      slot_id: 'user:hobby', mode: 'current', release: 'withhold', reason: 'evidence_not_authoritative_or_safe',
      evidence: [],
    },
  ],
  document_write: {
    document_id: 'doc_1',
    title: 'Nick context',
    created: true,
    chunk_count: 3,
  },
  tool_runs: [{
    tool_run_id: 'tool_1',
    tool: 'aether_self',
    input: { query: 'Who are you?' },
    output: { purpose: 'A local governed companion.' },
    status: 'completed',
  }],
}

test('renders clause-level governance decisions', () => {
  render(<TraceDrawer trace={trace} />)
  expect(screen.getByText('Conflict')).toBeInTheDocument()
  expect(screen.getByText('Withheld')).toBeInTheDocument()
  expect(screen.getByText('user:employer')).toBeInTheDocument()
  expect(screen.getByText('100%')).toBeInTheDocument()
  expect(screen.getByText('Context saved')).toBeInTheDocument()
  expect(screen.getByText('aether self')).toBeInTheDocument()
  expect(screen.getByText('A local governed companion.')).toBeInTheDocument()
})
