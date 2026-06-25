import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { TraceDrawer } from './TraceDrawer'
import type { Trace } from '../types'

const trace: Trace = {
  query: 'Where do I work and what is my hobby?',
  status: 'blocked',
  turn_id: 'turn_1',
  conversation_id: 'conv_1',
  model: 'qwen2.5:7b-instruct',
  generation_model: 'qwen3:14b',
  character_answer: {
    source: 'aether_character',
    kind: 'self_assessment',
    mode: 'generative_guidance',
    needs_stronger_model: false,
  },
  completion: {
    source: 'aether_character',
    needs_stronger_model: false,
    generation_model: 'qwen3:14b',
    route_decision: {
      selected_route: 'real_use_support',
      candidate_routes: [
        {
          route: 'real_use_support',
          confidence: 0.84,
          reason: 'personal_project_support_or_reentry_prompt',
        },
      ],
      selected_model_policy: 'local_with_support_anchors',
      tool_policy: 'tools_optional',
      repair_policy: 'real_use_anchor_repair_then_fallback',
      escalation_allowed: false,
      escalation_reason: null,
      route_reason: 'personal_project_support_or_reentry_prompt',
      route_confidence: 0.84,
      risk_level: 'low',
      memory_write_allowed: false,
      silent_escalation_allowed: false,
    },
    guidance_kind: 'self_assessment',
    guidance_repaired: false,
    guidance_repair_failed: false,
    depth: {
      mode: 'deep',
      requested: true,
      reason: 'user_requested_depth',
      max_continuations: 1,
      include_approach: true,
      continuation_count: 1,
      depth_satisfied: true,
      continued_reason: 'answer_too_short_for_requested_depth',
      assessment: {
        mode: 'deep',
        requested: true,
        word_count: 242,
        min_words: 180,
        satisfied: true,
        reason: 'depth_minimum_met',
      },
    },
  },
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
      contradiction_disposition: {
        label: 'held',
        confidence: 0.85,
        reason: 'multiple_authoritative_current_values_require_review',
        evidence_state_ids: ['st_1', 'st_2'],
      },
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
  expect(screen.getByLabelText('Contradiction disposition')).toHaveTextContent(
    'held'
  )
  expect(screen.getByLabelText('Contradiction disposition')).toHaveTextContent(
    'multiple authoritative current values require review'
  )
  expect(screen.getByText('100%')).toBeInTheDocument()
  expect(screen.getByText('Context saved')).toBeInTheDocument()
  expect(screen.getByText('aether self')).toBeInTheDocument()
  expect(screen.getByText('A local governed companion.')).toBeInTheDocument()
  const route = screen.getByLabelText('Response route')
  expect(within(route).getByText('aether character')).toBeInTheDocument()
  expect(within(route).getByText('qwen2.5:7b-instruct')).toBeInTheDocument()
  expect(within(route).getByText('qwen3:14b')).toBeInTheDocument()
  expect(within(route).getByText('self assessment')).toBeInTheDocument()
  expect(within(route).getByText('clean')).toBeInTheDocument()
  expect(within(route).getByText('local ok')).toBeInTheDocument()
  const decision = screen.getByLabelText('Route decision')
  expect(within(decision).getByText('Selected route')).toBeInTheDocument()
  expect(within(decision).getByText('real use support')).toBeInTheDocument()
  expect(within(decision).getByText('Model policy')).toBeInTheDocument()
  expect(within(decision).getByText('local with support anchors')).toBeInTheDocument()
  expect(within(decision).getByText('Tool policy')).toBeInTheDocument()
  expect(within(decision).getByText('tools optional')).toBeInTheDocument()
  expect(within(decision).getByText('Repair')).toBeInTheDocument()
  expect(within(decision).getByText('real use anchor repair then fallback')).toBeInTheDocument()
  expect(within(decision).getByText('Risk')).toBeInTheDocument()
  expect(within(decision).getByText('low')).toBeInTheDocument()
  expect(within(decision).getByText('Escalation')).toBeInTheDocument()
  expect(within(decision).getByText('no')).toBeInTheDocument()
  const depth = screen.getByLabelText('Response depth')
  expect(within(depth).getByText('deep')).toBeInTheDocument()
  expect(within(depth).getAllByText('yes')).toHaveLength(2)
  expect(within(depth).getByText('1')).toBeInTheDocument()
  expect(within(depth).getByText('242')).toBeInTheDocument()
  expect(within(depth).getByText('answer too short for requested depth')).toBeInTheDocument()
})

test('renders route decisions from initial trace metadata for historical traces without completion', () => {
  render(<TraceDrawer trace={{
    ...trace,
    completion: undefined,
    route_decision: {
      selected_route: 'code_tool',
      candidate_routes: [
        {
          route: 'code_tool',
          confidence: 0.9,
          reason: 'repository_code_or_test_question',
        },
      ],
      selected_model_policy: 'tool_first_local_synthesis',
      tool_policy: 'workspace_tools_required_before_synthesis',
      repair_policy: 'repair_with_retrieved_paths_or_escalation_packet',
      escalation_allowed: true,
      escalation_reason: 'focused_tool_evidence_missing',
      route_reason: 'repository_code_or_test_question',
      route_confidence: 0.9,
      risk_level: 'medium',
      memory_write_allowed: false,
      silent_escalation_allowed: false,
    },
  }} />)

  const decision = screen.getByLabelText('Route decision')
  expect(within(decision).getByText('code tool')).toBeInTheDocument()
  expect(within(decision).getByText('tool first local synthesis')).toBeInTheDocument()
  expect(within(decision).getByText('workspace tools required before synthesis')).toBeInTheDocument()
  expect(within(decision).getByText('repair with retrieved paths or escalation packet')).toBeInTheDocument()
  expect(within(decision).getByText('medium')).toBeInTheDocument()
  expect(within(decision).getByText('allowed')).toBeInTheDocument()
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

test('surfaces read-only test recommendation metadata', () => {
  render(<TraceDrawer trace={{
    ...trace,
    tool_runs: [{
      tool_run_id: 'tool_test',
      tool: 'workspace_test_recommend',
      input: { path: 'depth.py' },
      output: {
        path: 'D:\\AI_round2\\aether-core\\aether\\sidecar\\depth.py',
        command: 'python -m pytest tests/test_sidecar_depth.py',
        test_file: 'D:\\AI_round2\\aether-core\\tests\\test_sidecar_depth.py',
        executed: false,
        write_performed: false,
        sha256: 'abc123',
      },
      status: 'completed',
    }],
  }} />)

  const tool = screen.getByLabelText('workspace test recommend metadata')
  expect(screen.getByText('Suggested command: python -m pytest tests/test_sidecar_depth.py')).toBeInTheDocument()
  expect(within(tool).getByText('Command')).toBeInTheDocument()
  expect(within(tool).getByText('python -m pytest tests/test_sidecar_depth.py')).toBeInTheDocument()
  expect(within(tool).getByText('Test file')).toBeInTheDocument()
  expect(within(tool).getByText('D:\\AI_round2\\aether-core\\tests\\test_sidecar_depth.py')).toBeInTheDocument()
  expect(within(tool).getByText('Executed')).toBeInTheDocument()
  expect(within(tool).getByText('no')).toBeInTheDocument()
  expect(within(tool).getByText('Write')).toBeInTheDocument()
  expect(within(tool).getByText('not performed')).toBeInTheDocument()
  expect(within(tool).getByText('Stale hash')).toBeInTheDocument()
  expect(within(tool).getByText('captured')).toBeInTheDocument()
})

test('surfaces governed test result metadata', () => {
  render(<TraceDrawer trace={{
    ...trace,
    tool_runs: [{
      tool_run_id: 'tool_test_run',
      tool: 'workspace_test_run',
      input: { path: 'depth.py' },
      output: {
        path: 'D:\\AI_round2\\aether-core\\aether\\sidecar\\depth.py',
        command: 'python -m pytest tests/test_sidecar_depth.py',
        test_file: 'D:\\AI_round2\\aether-core\\tests\\test_sidecar_depth.py',
        executed: true,
        exit_code: 0,
        passed: true,
        timed_out: false,
        duration_ms: 1234,
        stdout: '============================= test session starts =============================\n1 passed in 0.42s',
        stderr: 'pytest warning sample',
      },
      status: 'completed',
    }],
  }} />)

  const tool = screen.getByLabelText('workspace test run metadata')
  expect(screen.getByText('Suggested command: python -m pytest tests/test_sidecar_depth.py')).toBeInTheDocument()
  expect(within(tool).getByText('Executed')).toBeInTheDocument()
  expect(within(tool).getAllByText('yes')).toHaveLength(2)
  expect(within(tool).getByText('Exit code')).toBeInTheDocument()
  expect(within(tool).getByText('0')).toBeInTheDocument()
  expect(within(tool).getByText('Timed out')).toBeInTheDocument()
  expect(within(tool).getByText('no')).toBeInTheDocument()
  expect(within(tool).getByText('Duration')).toBeInTheDocument()
  expect(within(tool).getByText('1234 ms')).toBeInTheDocument()
  const output = screen.getByLabelText('workspace test run captured output')
  expect(within(output).getByText('stdout')).toBeInTheDocument()
  expect(within(output).getByText(/1 passed in 0\.42s/)).toBeInTheDocument()
  expect(within(output).getByText('stderr')).toBeInTheDocument()
  expect(within(output).getByText('pytest warning sample')).toBeInTheDocument()
})

test('surfaces workspace search excerpts as retrieved snippets', () => {
  render(<TraceDrawer trace={{
    ...trace,
    tool_runs: [{
      tool_run_id: 'tool_search',
      tool: 'workspace_search',
      input: { query: 'TraceDrawer response depth' },
      output: {
        results: [{
          path: 'D:\\AI_round2\\workbench\\src\\components\\TraceDrawer.tsx',
          relative_path: 'workbench/src/components/TraceDrawer.tsx',
          score: 42,
          excerpts: [
            { line: 70, text: '<article className="trace-route" aria-label="Response depth">' },
            { line: 92, text: '<section className="tool-run-list" aria-label="Tool activity">' },
          ],
        }],
      },
      status: 'completed',
    }],
  }} />)

  const snippets = screen.getByLabelText('workspace search retrieved snippets')
  expect(within(snippets).getByText('D:\\AI_round2\\workbench\\src\\components\\TraceDrawer.tsx')).toBeInTheDocument()
  expect(within(snippets).getByText(/70: <article className="trace-route"/)).toBeInTheDocument()
  expect(within(snippets).getByText(/92: <section className="tool-run-list"/)).toBeInTheDocument()
})

test('surfaces workspace read content as a retrieved snippet', () => {
  render(<TraceDrawer trace={{
    ...trace,
    tool_runs: [{
      tool_run_id: 'tool_read',
      tool: 'workspace_read',
      input: { path: 'depth.py' },
      output: {
        path: 'D:\\AI_round2\\aether-core\\aether\\sidecar\\depth.py',
        start_line: 1,
        end_line: 3,
        content: '     1\tdef classify_depth_request(question: str):\n     2\t    text = question.lower()\n     3\t    return DepthPolicy(mode="normal")',
      },
      status: 'completed',
    }],
  }} />)

  const snippets = screen.getByLabelText('workspace read retrieved snippets')
  expect(within(snippets).getByText('read content')).toBeInTheDocument()
  expect(within(snippets).getByText(/def classify_depth_request/)).toBeInTheDocument()
  expect(within(snippets).getByText(/return DepthPolicy/)).toBeInTheDocument()
})

test('surfaces failed tool errors as visible notices', () => {
  render(<TraceDrawer trace={{
    ...trace,
    tool_runs: [{
      tool_run_id: 'tool_failed',
      tool: 'workspace_read',
      input: { path: '..\\outside.txt' },
      output: { error: 'file is outside configured workspaces or does not exist' },
      status: 'failed',
    }],
  }} />)

  expect(screen.getByText('workspace read')).toBeInTheDocument()
  expect(screen.getByText('failed')).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('file is outside configured workspaces or does not exist')
})

test('surfaces non-ready patch reasons as visible notices', () => {
  render(<TraceDrawer trace={{
    ...trace,
    tool_runs: [{
      tool_run_id: 'tool_patch_not_ready',
      tool: 'workspace_patch_propose',
      input: { path: 'app.py' },
      output: {
        path: 'D:\\repo\\app.py',
        ready: false,
        applied: false,
        occurrences: 0,
        error: 'old text must match exactly once',
      },
      status: 'completed',
    }],
  }} />)

  expect(screen.getByText('Patch not ready · old text must match exactly once')).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('old text must match exactly once')
})

test('renders a trace retrieval error', () => {
  render(<TraceDrawer trace={null} error="Trace row was not found." />)
  expect(screen.getByText('Trace unavailable')).toBeInTheDocument()
  expect(screen.getByText('Trace row was not found.')).toBeInTheDocument()
})
