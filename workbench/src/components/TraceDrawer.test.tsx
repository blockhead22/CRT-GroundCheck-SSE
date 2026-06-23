import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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

test('makes patch previews visibly non-applied', () => {
  render(<TraceDrawer trace={{
    ...trace,
    tool_runs: [{
      tool_run_id: 'tool_patch',
      tool: 'workspace_patch_propose',
      input: { path: 'app.py' },
      output: {
        path: 'D:\\repo\\app.py',
        ready: true,
        applied: false,
        patch: '-old\n+new\n',
      },
      status: 'completed',
    }],
  }} />)

  expect(screen.getByText('workspace patch propose')).toBeInTheDocument()
  expect(screen.getByText(/Patch preview ready · not applied/)).toBeInTheDocument()
})

test('requires a visible approval click before applying a patch', async () => {
  const onApplyPatch = vi.fn(async () => ({
    receipt_id: 'receipt_1',
    tool_run_id: 'tool_patch',
    path: 'D:\\repo\\app.py',
    before_sha256: 'before',
    after_sha256: 'after',
    patch: '-old\n+new\n',
    idempotent_replay: false,
  }))
  render(<TraceDrawer
    trace={{
      ...trace,
      tool_runs: [{
        tool_run_id: 'tool_patch',
        tool: 'workspace_patch_propose',
        input: { path: 'app.py' },
        output: {
          path: 'D:\\repo\\app.py',
          ready: true,
          applied: false,
          patch: '-old\n+new\n',
        },
        status: 'completed',
      }],
    }}
    onApplyPatch={onApplyPatch}
  />)

  expect(onApplyPatch).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Approve exact patch' }))
  await waitFor(() => expect(onApplyPatch).toHaveBeenCalledWith('tool_patch'))
})
