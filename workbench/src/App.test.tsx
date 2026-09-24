import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'
import { localRouterFeedbackPreview } from './fixtures/localRouterFeedbackPreview'
import { localRouterRagEvidencePreview } from './fixtures/localRouterRagEvidencePreview'

const health = {
  ok: true,
  aether: 'ready',
  ollama: 'ready',
  model: 'qwen2.5:7b-instruct',
  codex_available: false,
  profile: { id: 'default', storage_scope: 'default_root' },
  substrate: { path: 'test', slots: 2, states: 3, revision_hash: 'rev' },
}

const conversations = [
  {
    conversation_id: 'conv-1',
    title: 'Existing chat',
    created_at: 1,
    updated_at: 2,
  },
]

const trace = {
  query: 'aether, use the gpt logs to fill in the gaps',
  status: 'needs_clarification',
  turn_id: 'turn-old',
  conversation_id: 'conv-1',
  model: 'qwen2.5:7b-instruct',
  generation_model: 'deterministic',
  completion: {
    source: 'aether_meta',
    needs_stronger_model: false,
    generation_model: 'deterministic',
    route_decision: {
      selected_route: 'context_bridge_broad',
      candidate_routes: [{
        route: 'context_bridge_broad',
        confidence: 0.8,
        reason: 'broad_identity_project_or_relationship_context',
      }],
      selected_model_policy: 'local_with_context_bridge',
      tool_policy: 'tools_optional',
      repair_policy: 'context_anchor_repair_then_fallback',
      escalation_allowed: false,
      escalation_reason: null,
      route_reason: 'broad_identity_project_or_relationship_context',
      route_confidence: 0.8,
      risk_level: 'low',
      memory_write_allowed: false,
      silent_escalation_allowed: false,
      model_recommendation: {
        current_selected_model: 'qwen2.5:7b-instruct',
        recommended_model_policy: 'qwen2.5_default_with_context_bridge',
        recommended_model: 'qwen2.5:7b-instruct',
        fallback_model: 'qwen3:14b',
        confidence: 'medium',
        latency_caveat: 'qwen3 is promising for broad support/reflection but slow',
        evidence_path: '.eval-runs\\workbench_eval_20260626_022453.json',
        observational_only: true,
        model_selection_changed: false,
      },
    },
  },
  governance_answer_spine: {
    spine_schema: 'aether.governance_answer_spine.v0',
    source: 'governed_synthesis_lab',
    question_summary: 'Aether should answer with personality without fake intimacy.',
    render_mode: 'governed_spine_model_render',
    tension_packet: {
      packet_id: 'tp_personality_boundary',
      tension_type: 'keep_both',
      sides: [{
        side_id: 'warmth_side',
        label: 'Personality matters',
        claim: 'Aether should feel warmer, more responsive, and less like a canned FAQ.',
        evidence_ids: ['personality_need'],
      }, {
        side_id: 'boundary_side',
        label: 'Fake intimacy is unsafe',
        claim: 'Aether should not fake intimacy, flatter, transplant GPT voice, or turn tone into confirmed truth.',
        evidence_ids: ['intimacy_boundary'],
      }],
      allowed_synthesis: 'Aether can render with warmth when warmth stays grounded in evidence, boundaries, traces, and user correction.',
      forbidden_collapse: 'Do not make Aether either sterile or ungroundedly intimate.',
      trace_summary: 'Governed personality means warmer rendering without surrendering source authority.',
    },
    safety_contract: {
      memory_writes_allowed: false,
      raw_chain_of_thought_stored: false,
      review_required_before_promotion: true,
    },
  },
  plan: {
    status: 'unknown',
    coverage: 0,
    unresolved_clauses: [],
    clauses: [
      {
        clause_id: 'c1',
        text: 'old question',
        status: 'unresolved',
        candidate_slots: [],
        reason_code: 'no_candidate_above_threshold',
      },
    ],
  },
  packets: [],
  tool_runs: [{
    tool_run_id: 'tool_archive_1',
    tool: 'document_search',
    input: { query: 'gpt logs fill gaps' },
    output: {
      results: [{
        title: 'ChatGPT archive - grounded support',
        source_kind: 'chatgpt_archive',
        score: 0.88,
        excerpts: [{
          line: 12,
          text: 'Historical archive hit; bounded evidence, not confirmed memory.',
        }],
      }],
    },
    status: 'completed',
    result_count: 1,
    reason: 'The query asked for saved context, archive logs, or document-backed memory.',
    source: 'deterministic_semantic_tool_router',
  }],
  tool_considerations: [{
    tool: 'document_search',
    status: 'used',
    reason: 'The query asked for saved context, archive logs, or document-backed memory.',
    source: 'deterministic_semantic_tool_router',
  }],
  memory_writes: [{
    slot_id: 'user:favorite_flower',
    state_id: 'state-flower',
    value: 'marigolds',
    created: true,
    authority: 'confirmed',
  }],
  memory_candidates: [{
    slot_id: 'user:favorite_drink',
    summary: 'Favorite drink was mentioned but needs operator review.',
    candidate_kind: 'reviewed_memory_fact_candidate',
    semantic_signal: 'high_ranked_favorite_not_confirmed_single_fact',
    authority: 'unconfirmed',
    review_required: true,
    memory_write_allowed: false,
    confirmed_fact: false,
  }, {
    slot_id: 'user:favorite_flower_reason',
    proposed_value: 'Marigolds may matter because they are orange.',
    summary: 'User connected the favorite flower thread to orange; review before storing this as the durable reason marigolds matter.',
    candidate_kind: 'mirus_contextual_favorite_reason_candidate',
    semantic_signal: 'contextual_reason_for_existing_favorite_not_confirmed_fact',
    authority: 'unconfirmed',
    review_required: true,
    memory_write_allowed: false,
    confirmed_fact: false,
  }],
  task_authority_candidates: [{
    schema: 'aether.task_authority_candidate.v0',
    candidate_id: 'task_candidate_edit',
    record_kind: 'open_loop',
    summary: 'Edit footage.',
    category: 'direct_planning_action',
    confidence: 0.78,
    source: 'mirus_task_intake',
    reference_id: 'turn-old',
    evidence_text: 'I need to edit footage.',
    authority: 'unconfirmed',
    review_required: true,
    review_only: true,
    task_authority_write_allowed: false,
    memory_write_allowed: false,
    confirmed_fact: false,
  }],
  mirus_governed_discovery: {
    schema: 'aether.mirus.governed_discovery.v0',
    enabled: true,
    mode: 'mirus_front_existing_intake_crt_back',
    front_packet: {
      preferred_intent: 'mirus_extract_candidates',
      pending_slot: '',
      candidate_hints: ['user:favorite_drink', 'user:favorite_flower_reason'],
      reasons: ['detected candidate slots: user:favorite_drink, user:favorite_flower_reason'],
    },
    repairs: [
      'added_review_candidate:user:favorite_flower_reason',
    ],
    quality_flags: [],
    logic_graph: {
      nodes: [
        { id: 'input', kind: 'user_turn', label: 'They are both orange. lmao' },
        { id: 'mirus_front', kind: 'front_packet', label: 'mirus_extract_candidates' },
        { id: 'holden_current_intake', kind: 'existing_intake', label: '1 base candidate(s)' },
        { id: 'crt_validator', kind: 'validator', label: 'repair' },
        { id: 'final', kind: 'result', label: '2 review-only candidate(s)' },
      ],
      edges: [
        { from: 'input', to: 'mirus_front', label: 'compress task shape' },
        { from: 'mirus_front', to: 'holden_current_intake', label: 'existing Mirus intake' },
        { from: 'holden_current_intake', to: 'crt_validator', label: 'validate boundaries' },
        { from: 'crt_validator', to: 'final', label: 'release review-only candidates' },
      ],
    },
    safety: {
      memory_write_allowed: false,
      raw_hidden_chain_of_thought_stored: false,
      review_required_before_promotion: true,
    },
  },
}

const turns = [
  {
    turn_id: 'turn-old',
    user_message: 'old question',
    local_answer: 'old answer',
    model: 'qwen2.5:7b-instruct',
    needs_stronger_model: false,
    created_at: 1,
  },
]

const slotDetail = {
  revision_hash: 'revision-1',
  slot_id: 'user:workspace',
  conflict: true,
  quarantined: false,
  contradiction_disposition: {
    label: 'contextual',
    confidence: 0.7,
    reason: 'values_may_depend_on_context',
    evidence_state_ids: ['state-1', 'state-2'],
  },
  review: {},
  history: [{
    state_id: 'state-1',
    value: 'shop',
    normalized: 'shop',
    trust: 0.8,
    observed_at: 1,
    temporal_status: 'active',
    source: 'auto_ingest',
    source_text: 'I am heading to the shop.',
    current: true,
  }],
}

let consolidationPreview: Record<string, unknown>

beforeEach(() => {
  localStorage.clear()
  // Existing App tests assert Lab chrome (Trace, voice, route grid).
  // Lab chrome tests: mark migration done so intentional Lab sticks.
  localStorage.setItem('aether.uiMode.simpleDefault.v1', '1')
  localStorage.setItem('aether.uiMode', 'lab')
  vi.restoreAllMocks()
  consolidationPreview = {
    mode: 'preview_only',
    writes_performed: false,
    memory_ingestion_performed: false,
    support_pattern_import_performed: false,
    reflection_create_performed: false,
    inspected_turn_count: 0,
    candidates: [],
  }
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/health')) return new Response(JSON.stringify(health), { status: 200 })
    if (url.endsWith('/v1/models')) return new Response(JSON.stringify({ models: [{ name: health.model }] }), { status: 200 })
    if (url.endsWith('/v1/settings/tool-approval')) {
      return new Response(
        JSON.stringify({
          schema: 'aether.tool_approval_policy.v0',
          auto_approve_exact_patch_apply: false,
          updated_at: null,
        }),
        { status: 200 },
      )
    }
    if (url.endsWith('/v1/conversations')) return new Response(JSON.stringify({ conversations }), { status: 200 })
    if (url.endsWith('/v1/conversations/conv-1/turns')) return new Response(JSON.stringify({ turns }), { status: 200 })
    if (url.endsWith('/v1/traces/turn-old')) return new Response(JSON.stringify({ trace }), { status: 200 })
    if (url.includes('/v1/slots/user%3Aworkspace')) return new Response(JSON.stringify(slotDetail), { status: 200 })
    if (url.includes('/v1/slots')) return new Response(JSON.stringify({ revision_hash: 'rev', slots: [] }), { status: 200 })
    if (url.includes('/v1/support-patterns')) return new Response(JSON.stringify({ candidates: [] }), { status: 200 })
    if (url.includes('/v1/reflections')) return new Response(JSON.stringify({ reflections: [] }), { status: 200 })
    if (url.includes('/v1/consolidation/candidates')) return new Response(JSON.stringify(consolidationPreview), { status: 200 })
    return new Response(JSON.stringify({ turns: [] }), { status: 200 })
  }))
})

test('opens the trace drawer and expands the desktop window', async () => {
  render(<App />)
  await screen.findByText('On this PC')
  fireEvent.click(screen.getByRole('button', { name: 'Trace' }))
  expect(screen.getByLabelText('trace drawer')).toBeInTheDocument()
  expect(window.aetherDesktop?.setExpanded).toHaveBeenCalledWith(true)
})

test('keeps the empty-chat composer in its grid row when no policy summary is active', async () => {
  const { container } = render(<App />)
  await screen.findByText('On this PC')

  expect(container.querySelector('.model-policy-summary-placeholder')).toBeInTheDocument()
  expect(screen.queryByLabelText('Model policy recommendation')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Message Aether')).toBeInTheDocument()
  expect(screen.getByLabelText('Aether voice')).toHaveValue('warm')
  expect(screen.getByText('Talk to your governed memory.')).toBeInTheDocument()
})

test('shows Codex availability in settings', async () => {
  render(<App />)
  await screen.findByText('On this PC')
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
  await waitFor(() => expect(screen.getByText('unavailable')).toBeInTheDocument())
  expect(screen.getByLabelText('Route model policy')).toHaveTextContent('read only')
  expect(screen.getByText('No route recommendation for the active turn.')).toBeInTheDocument()
})

test('makes hosted rendering an explicit disclosed setting', async () => {
  render(<App />)
  await screen.findByText('On this PC')
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))

  const provider = screen.getByLabelText('Answer renderer')
  expect(provider).toHaveValue('local')
  expect(screen.getByText('Answer wording stays on this machine through Ollama.')).toBeInTheDocument()

  fireEvent.change(provider, { target: { value: 'grok_build' } })
  expect(provider).toHaveValue('grok_build')
  expect(screen.getByText(/governed packet is sent to Grok for rendering/)).toBeInTheDocument()
  expect(screen.getByText(/may contribute general knowledge for non-personal questions/)).toBeInTheDocument()
  await waitFor(() => expect(localStorage.getItem('aether.renderProvider')).toBe('grok_build'))
})

test('defaults floating on and persists window chrome across restarts', async () => {
  // First run (no stored keys): floating defaults on for QoL.
  const first = render(<App />)
  await screen.findByText('On this PC')
  expect(screen.getByRole('button', { name: 'Dock window' })).toBeInTheDocument()
  expect(window.aetherDesktop?.setFloating).toHaveBeenCalledWith(true)
  expect(window.aetherDesktop?.setAlwaysOnTop).toHaveBeenCalledWith(true)
  await waitFor(() => expect(localStorage.getItem('aether.window.floating')).toBe('true'))
  await waitFor(() => expect(localStorage.getItem('aether.window.pinned')).toBe('true'))

  fireEvent.click(screen.getByRole('button', { name: 'Dock window' }))
  await waitFor(() => expect(localStorage.getItem('aether.window.floating')).toBe('false'))
  expect(screen.getByRole('button', { name: 'Float window' })).toBeInTheDocument()
  first.unmount()

  vi.mocked(window.aetherDesktop!.setFloating).mockClear()
  vi.mocked(window.aetherDesktop!.setAlwaysOnTop).mockClear()

  // Restart: restore docked (false) preference.
  render(<App />)
  await screen.findByText('On this PC')
  expect(screen.getByRole('button', { name: 'Float window' })).toBeInTheDocument()
  expect(window.aetherDesktop?.setFloating).toHaveBeenCalledWith(false)
  expect(window.aetherDesktop?.setAlwaysOnTop).toHaveBeenCalledWith(true)
})

test('opens the reflect drawer from bottom navigation', async () => {
  render(<App />)
  await screen.findByText('On this PC')
  fireEvent.click(screen.getByRole('button', { name: 'Reflect' }))
  expect(screen.getByLabelText('reflect drawer')).toBeInTheDocument()
  expect(screen.getByText('Reflection review')).toBeInTheDocument()
  expect(window.aetherDesktop?.setExpanded).toHaveBeenCalledWith(true)
})

test('opens the support-pattern review drawer from bottom navigation', async () => {
  render(<App />)
  await screen.findByText('On this PC')
  fireEvent.click(screen.getByRole('button', { name: 'Support' }))
  expect(screen.getByLabelText('support drawer')).toBeInTheDocument()
  expect(screen.getByText('Support review')).toBeInTheDocument()
  expect(window.aetherDesktop?.setExpanded).toHaveBeenCalledWith(true)
})

test('opens the learner preview drawer from bottom navigation', async () => {
  render(<App />)
  await screen.findByText('On this PC')
  fireEvent.click(screen.getByRole('button', { name: 'Learn' }))
  expect(screen.getByLabelText('learn drawer')).toBeInTheDocument()
  expect(screen.getByText('Learner preview')).toBeInTheDocument()
  await screen.findByText('No learner candidates')
  expect(window.aetherDesktop?.setExpanded).toHaveBeenCalledWith(true)
})

test('opens a learner candidate review surface without applying it', async () => {
  consolidationPreview = {
    mode: 'preview_only',
    writes_performed: false,
    memory_ingestion_performed: false,
    support_pattern_import_performed: false,
    reflection_create_performed: false,
    inspected_turn_count: 1,
    candidates: [{
      candidate_id: 'consolidation_candidate_support',
      candidate_type: 'background_consolidation_candidate',
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
          category: 'support_style',
          candidate_kind: 'reviewed_support_pattern_candidate',
          suggested_response_rule: 'Use practical re-entry language.',
        },
      },
      evidence: [],
    }],
  }
  render(<App />)
  await screen.findByText('On this PC')
  fireEvent.click(screen.getByRole('button', { name: 'Learn' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Open Support' }))

  expect(screen.getByLabelText('support drawer')).toBeInTheDocument()
  expect(screen.getByText('Support review')).toBeInTheDocument()
  expect(await screen.findByText(/Manual form state only. Nothing has been imported/)).toBeInTheDocument()
  expect(screen.getByLabelText('Draft support response rule')).toHaveValue('Use practical re-entry language.')
  expect(window.aetherDesktop?.setExpanded).toHaveBeenCalledWith(true)
})

test('opens a learner reflection candidate as manual draft form state', async () => {
  consolidationPreview = {
    mode: 'preview_only',
    writes_performed: false,
    memory_ingestion_performed: false,
    support_pattern_import_performed: false,
    reflection_create_performed: false,
    inspected_turn_count: 1,
    candidates: [{
      candidate_id: 'consolidation_candidate_reflection',
      candidate_type: 'background_consolidation_candidate',
      category: 'aether_self_improvement',
      candidate_kind: 'reflection_candidate',
      summary: 'A recent answer may reveal an Aether behavior improvement worth reviewing.',
      proposed_action: 'Create a reviewed reflection only if it repeats.',
      risk: 'Do not convert one thin answer into a permanent behavior rule.',
      review_required: true,
      memory_write_allowed: false,
      confirmed_fact: false,
      review_route: {
        surface: 'reflections',
        action: 'draft_create_reflection',
        endpoint: '/v1/reflections',
        draft: {
          subject: 'agent',
          observation: 'A recent answer may reveal a behavior improvement.',
          confidence: 0.45,
          time_window: 'recent turns',
          suggested_experiment: 'Review similar traces before accepting.',
        },
      },
      evidence: [],
    }],
  }
  render(<App />)
  await screen.findByText('On this PC')
  fireEvent.click(screen.getByRole('button', { name: 'Learn' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Open Reflect' }))

  expect(screen.getByLabelText('reflect drawer')).toBeInTheDocument()
  expect(await screen.findByText(/Manual form state only. Nothing has been created/)).toBeInTheDocument()
  expect(screen.getByLabelText('Draft reflection observation')).toHaveValue('A recent answer may reveal a behavior improvement.')
})

test('renders local-router feedback ledger candidates in learner review surfaces', async () => {
  consolidationPreview = localRouterFeedbackPreview as unknown as Record<string, unknown>
  render(<App />)
  await screen.findByText('On this PC')

  fireEvent.click(screen.getByRole('button', { name: 'Learn' }))

  expect(await screen.findByText('5 replay rows needed fallback routing.')).toBeInTheDocument()
  expect(screen.getByText('architecture_process had 5 rows with weaker receipt coverage.')).toBeInTheDocument()
  expect(screen.getByLabelText('Consolidation safety')).toHaveTextContent('preview only')
  expect(screen.getByLabelText('Consolidation safety')).toHaveTextContent('writes no')
  expect(screen.getByLabelText('Consolidation safety')).toHaveTextContent('4 adapter draft')
  expect(screen.getByRole('button', { name: /^Support\s+3$/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /^Reflect\s+1$/ })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /^Support\s+3$/ }))
  fireEvent.click(screen.getAllByRole('button', { name: 'Open Support' })[0])

  expect(screen.getByLabelText('support drawer')).toBeInTheDocument()
  expect(await screen.findByText(/Manual form state only. Nothing has been imported/)).toBeInTheDocument()
  expect(screen.getByLabelText('Draft support category')).toHaveValue('local_router_feedback')
  expect(screen.getByLabelText('Draft support response rule')).toHaveValue(
    'Ask for concrete receipts or narrow the claim before rendering broad synthesis.',
  )

  fireEvent.click(screen.getByRole('button', { name: 'Learn' }))
  fireEvent.click(await screen.findByRole('button', { name: /^Reflect\s+1$/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Open Reflect' }))

  expect(screen.getByLabelText('reflect drawer')).toBeInTheDocument()
  expect(await screen.findByText(/Manual form state only. Nothing has been created/)).toBeInTheDocument()
  expect(screen.getByLabelText('Draft reflection subject')).toHaveValue('local_router_fallback_usage')
  expect(screen.getByLabelText('Draft reflection time window')).toHaveValue('local-router curated replay v1')
})

test('renders local-router RAG evidence as a review-only learner candidate', async () => {
  consolidationPreview = localRouterRagEvidencePreview as unknown as Record<string, unknown>
  render(<App />)
  await screen.findByText('On this PC')

  fireEvent.click(screen.getByRole('button', { name: 'Learn' }))

  expect(await screen.findByText('Adversarial v2: governed passed 6/6 with trace 6/6; scaffolded RAG passed 5/6.')).toBeInTheDocument()
  expect(screen.getByLabelText('Consolidation safety')).toHaveTextContent('preview only')
  expect(screen.getByLabelText('Consolidation safety')).toHaveTextContent('writes no')
  expect(screen.getByLabelText('Consolidation safety')).toHaveTextContent('1 adapter draft')
  expect(screen.getByText(/Small holdout and perfect governed score require caution/)).toBeInTheDocument()
  expect(screen.getByText(/review_only; memory writes blocked/)).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Open Reflect' }))

  expect(screen.getByLabelText('reflect drawer')).toBeInTheDocument()
  expect(await screen.findByText(/Manual form state only. Nothing has been created/)).toBeInTheDocument()
  expect(screen.getByLabelText('Draft reflection subject')).toHaveValue('agent')
  expect(screen.getByLabelText('Draft reflection observation')).toHaveValue(
    'In adversarial v2, governed Aether passed 6/6 with trace 6/6 while scaffolded RAG passed 5/6.',
  )
  expect(screen.getByLabelText('Draft reflection time window')).toHaveValue('local-router RAG adversarial v2 holdout')
})

test('opens a learner contradiction candidate directly on its memory slot', async () => {
  consolidationPreview = {
    mode: 'preview_only',
    writes_performed: false,
    memory_ingestion_performed: false,
    support_pattern_import_performed: false,
    reflection_create_performed: false,
    inspected_turn_count: 1,
    candidates: [{
      candidate_id: 'consolidation_candidate_memory',
      candidate_type: 'background_consolidation_candidate',
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
      evidence: [],
    }],
  }
  render(<App />)
  await screen.findByText('On this PC')
  fireEvent.click(screen.getByRole('button', { name: 'Learn' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Open Memory' }))

  expect(await screen.findByLabelText('memory drawer')).toBeInTheDocument()
  expect(await screen.findByText('user:workspace')).toBeInTheDocument()
  expect(screen.getByText('Opened from learner candidate. Review before confirming, correcting, or quarantining.')).toBeInTheDocument()
})

test('opens a trace-proposed memory fact draft without applying it', async () => {
  consolidationPreview = {
    mode: 'preview_only',
    writes_performed: false,
    memory_ingestion_performed: false,
    support_pattern_import_performed: false,
    reflection_create_performed: false,
    inspected_turn_count: 1,
    candidates: [{
      candidate_id: 'consolidation_candidate_memory_fact',
      candidate_type: 'background_consolidation_candidate',
      category: 'memory_fact_candidate',
      candidate_kind: 'reviewed_memory_fact_candidate',
      summary: 'user:workspace has a proposed memory fact from trace evidence.',
      proposed_action: 'Open memory review for user:workspace.',
      risk: 'Do not treat a trace-proposed fact as current memory until reviewed.',
      review_required: true,
      memory_write_allowed: false,
      confirmed_fact: false,
      review_route: {
        surface: 'memory',
        action: 'draft_memory_fact_candidate',
        endpoint: '/v1/slots/user:workspace',
        slot_id: 'user:workspace',
        requires_adapter: true,
        draft: {
          slot_id: 'user:workspace',
          summary: 'User says the shop is the current workspace.',
          confidence: 0.68,
        },
      },
      evidence: [{
        evidence_type: 'trace_user_claim',
        reference_id: 'turn-1',
        summary: 'User says the shop is the current workspace.',
        source_authority: 'user_stated',
      }],
    }],
  }
  render(<App />)
  await screen.findByText('On this PC')
  fireEvent.click(screen.getByRole('button', { name: 'Learn' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Open Memory' }))

  expect(await screen.findByLabelText('memory drawer')).toBeInTheDocument()
  expect(await screen.findByLabelText('Learner memory candidate draft')).toHaveTextContent(
    'User says the shop is the current workspace.',
  )
  expect(screen.getByLabelText('Learner memory candidate draft')).toHaveTextContent('review only')
  expect(screen.getByText('trace_user_claim / turn-1 / user_stated')).toBeInTheDocument()
})

test('starts a new chat without deleting durable knowledge', async () => {
  localStorage.setItem('aether.currentConversation', 'conv-1')
  render(<App />)
  await screen.findByDisplayValue('Existing chat')
  fireEvent.click(screen.getByRole('button', { name: 'New chat' }))
  expect(screen.getByRole('combobox', { name: 'Conversation' })).toHaveValue('')
  expect(localStorage.getItem('aether.currentConversation')).toBeNull()
})

test('deletes only the current chat after explicit confirmation', async () => {
  localStorage.setItem('aether.currentConversation', 'conv-1')
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const fetchMock = vi.mocked(fetch)
  render(<App />)
  await screen.findByDisplayValue('Existing chat')
  fireEvent.click(screen.getByRole('button', { name: 'Delete current chat' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/v1/conversations/conv-1'),
    expect.objectContaining({ method: 'DELETE' }),
  ))
  expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('memory'))
})

test('opens a historical turn trace from the assistant answer', async () => {
  localStorage.setItem('aether.currentConversation', 'conv-1')
  const fetchMock = vi.mocked(fetch)
  render(<App />)
  await screen.findByText('old answer')

  fireEvent.click(screen.getByRole('button', { name: 'Open trace for turn turn-old' }))

  await screen.findByLabelText('trace drawer')
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/v1/traces/turn-old'),
    expect.anything(),
  ))
  const route = screen.getByLabelText('Response route')
  expect(route).toHaveTextContent('aether meta')
  expect(route).toHaveTextContent('deterministic')
})

test('opens an inline process receipt from a historical assistant answer', async () => {
  localStorage.setItem('aether.currentConversation', 'conv-1')
  const fetchMock = vi.mocked(fetch)
  render(<App />)
  await screen.findByText('old answer')

  fireEvent.click(screen.getByRole('button', { name: 'Toggle process for turn turn-old' }))

  const thinking = await screen.findByLabelText('Answer process')
  expect(thinking).toHaveTextContent('How this answer formed')
  expect(thinking).toHaveTextContent('Governance receipts')
  expect(thinking).toHaveTextContent('Mirus front packet: mirus extract candidates')
  expect(thinking).toHaveTextContent('Candidate hints: user:favorite_drink, user:favorite_flower_reason')
  expect(thinking).toHaveTextContent('Logic graph: input -> mirus_front -> holden_current_intake -> crt_validator -> final')
  expect(thinking).toHaveTextContent('CRT repair: added review candidate:user:favorite flower reason')
  expect(thinking).toHaveTextContent('Mirus candidate: high ranked favorite not confirmed single fact')
  expect(thinking).toHaveTextContent('Task candidate (open loop): Edit footage.')
  expect(thinking).toHaveTextContent('Selected route: context bridge broad')
  expect(thinking).toHaveTextContent('Model policy: local with context bridge')
  expect(thinking).toHaveTextContent('Repair policy: context anchor repair then fallback')
  expect(thinking).toHaveTextContent('Held Tension')
  expect(thinking).toHaveTextContent('Packet type: keep both')
  expect(thinking).toHaveTextContent('Side A: Personality matters - Aether should feel warmer, more responsive, and less like a canned FAQ.')
  expect(thinking).toHaveTextContent('Side B: Fake intimacy is unsafe - Aether should not fake intimacy, flatter, transplant GPT voice, or turn tone into confirmed truth.')
  expect(thinking).toHaveTextContent('Allowed synthesis: Aether can render with warmth when warmth stays grounded in evidence, boundaries, traces, and user correction.')
  expect(thinking).toHaveTextContent('Forbidden collapse: Do not make Aether either sterile or ungroundedly intimate.')
  expect(thinking).toHaveTextContent('Trace preview: Governed personality means warmer rendering without surrendering source authority.')
  expect(thinking).toHaveTextContent('Recommended model: qwen2.5:7b-instruct (medium)')
  expect(thinking).toHaveTextContent('Fallback model: qwen3:14b')
  expect(thinking).toHaveTextContent('Stored user:favorite_flower: confirmed')
  expect(thinking).toHaveTextContent('Review-only memory candidate user:favorite_drink')
  expect(thinking).toHaveTextContent('Review-only memory candidate user:favorite_flower_reason')
  expect(thinking).toHaveTextContent('document search: completed')
  expect(thinking).toHaveTextContent('document search used: The query asked for saved context, archive logs, or document-backed memory.')
  expect(thinking).toHaveTextContent('Verifier')
  expect(thinking).toHaveTextContent('Memory writes: blocked')
  expect(thinking).toHaveTextContent('Silent escalation: blocked')
  expect(thinking).toHaveTextContent('Learning')
  expect(thinking).toHaveTextContent('Review candidate: user:favorite_drink (unconfirmed, review required, write blocked)')
  expect(thinking).toHaveTextContent('Review candidate: user:favorite_flower_reason (unconfirmed, review required, write blocked)')
  expect(thinking).toHaveTextContent('Task review candidate: Edit footage. (review required, task write blocked)')
  expect(thinking).toHaveTextContent('Model recommendation stayed observational')
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/v1/traces/turn-old'),
    expect.anything(),
  ))
})

test('keeps model recommendation out of chat and inside the trace drawer', async () => {
  localStorage.setItem('aether.currentConversation', 'conv-1')
  render(<App />)
  await screen.findByText('old answer')

  fireEvent.click(screen.getByRole('button', { name: 'Open trace for turn turn-old' }))

  expect(screen.queryByLabelText('Model policy recommendation')).not.toBeInTheDocument()
  const decision = await screen.findByLabelText('Route decision')
  expect(decision).toHaveTextContent('context bridge broad')
  expect(decision).toHaveTextContent('qwen2.5:7b-instruct')
  expect(decision).toHaveTextContent('qwen2.5 default with context bridge')
  expect(decision).toHaveTextContent('qwen3:14b')
  expect(decision).toHaveTextContent('medium')
  expect(decision).toHaveTextContent('workbench_eval_20260626_022453.json')
})

test('shows read-only route model policy in settings after opening a trace', async () => {
  localStorage.setItem('aether.currentConversation', 'conv-1')
  render(<App />)
  await screen.findByText('old answer')

  fireEvent.click(screen.getByRole('button', { name: 'Open trace for turn turn-old' }))
  await screen.findByLabelText('Route decision')
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))

  const policy = await screen.findByLabelText('Route model policy')
  expect(policy).toHaveTextContent('read only')
  expect(policy).toHaveTextContent('context bridge broad')
  expect(policy).toHaveTextContent('qwen2.5:7b-instruct')
  expect(policy).toHaveTextContent('qwen2.5 default with context bridge')
  expect(policy).toHaveTextContent('qwen3:14b')
  expect(policy).toHaveTextContent('no automatic switch')
})


test('refreshes the open memory list and total count after a chat writes a fact', async () => {
  const fallback = vi.mocked(fetch).getMockImplementation()!
  let completed = false
  vi.mocked(fetch).mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/health')) {
      return new Response(JSON.stringify({
        ...health, substrate: { ...health.substrate, slots: completed ? 1 : 0 },
      }), { status: 200 })
    }
    if (url.includes('/v1/slots')) {
      return new Response(JSON.stringify({ revision_hash: 'after-write', slots: completed ? [{
        slot_id: 'user:name', current_values: ['Mara'], conflict: false,
        quarantined: false, state_count: 1, updated_at: 2,
      }] : [] }), { status: 200 })
    }
    if (url.endsWith('/v1/chat/stream')) {
      completed = true
      return new Response(
        'event: turn\ndata: {"turn_id":"turn-new","conversation_id":"conv-1"}\n\n'
        + 'event: done\ndata: {"needs_stronger_model":false,"memory_writes":[{"slot_id":"user:name"}]}\n\n',
        { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
      )
    }
    return fallback(input, init)
  })
  render(<App />)
  await screen.findByText('On this PC')
  fireEvent.click(screen.getByRole('button', { name: 'Memory' }))
  expect(await screen.findByLabelText('Active memory profile')).toHaveTextContent('0 facts')
  fireEvent.change(screen.getByLabelText('Message Aether'), { target: { value: 'My name is Mara.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
  await waitFor(() => expect(screen.getByLabelText('Active memory profile')).toHaveTextContent('1 facts'))
  expect(await screen.findByRole('button', { name: /user:name.*Mara/ })).toBeInTheDocument()
})
