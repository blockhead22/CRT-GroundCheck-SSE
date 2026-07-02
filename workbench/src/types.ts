export type ReleaseDecision = 'answerable' | 'withhold' | 'conflict' | 'no_evidence'

export interface Health {
  ok: boolean
  aether: string
  ollama: string
  model: string
  codex_available: boolean
  substrate: {
    path: string
    slots: number
    states: number
    revision_hash: string
  }
}

export interface ModelInfo {
  name: string
  size?: number
  modified_at?: string
}

export interface Evidence {
  state_id: string
  slot_id: string
  value: string
  source_text: string
  source: string
  authority: string
  trust: number
  current: boolean
  observed_at: number
  quality_flags: string[]
}

export interface ContradictionDisposition {
  label: string
  confidence: number
  reason: string
  evidence_state_ids: string[]
}

export interface TracePacket {
  request_id: string
  clause_id: string
  clause_text: string
  planner_slot: string
  slot_id: string
  mode: string
  release: ReleaseDecision
  reason: string
  contradiction_disposition?: ContradictionDisposition | null
  evidence: Evidence[]
}

export interface Trace {
  query: string
  status: string
  turn_id: string
  conversation_id: string
  model: string
  generation_model?: string
  voice_profile?: string
  meta_answer?: { source?: string; intents?: Record<string, boolean> }
  direct_answer?: { source?: string; slot?: string }
  self_description_answer?: { source?: string }
  character_answer?: {
    source?: string
    kind?: string
    mode?: string
    needs_stronger_model?: boolean
  }
  route_decision?: RouteDecision
  governance_answer_spine?: GovernanceAnswerSpine
  public_governance_steps?: PublicGovernanceStep[]
  completion?: {
    source?: string
    needs_stronger_model: boolean
    generation_model?: string
    route_decision?: RouteDecision
    governance_spine_compliance?: GovernanceSpineCompliance
    guidance_kind?: string
    guidance_repaired?: boolean | null
    guidance_repair_failed?: boolean | null
    depth?: DepthCompletion
  }
  depth_policy?: DepthPolicy
  plan: {
    status: string
    coverage: number
    unresolved_clauses: string[]
    clauses: Array<{
      clause_id: string
      text: string
      status: string
      candidate_slots: string[]
      reason_code: string
    }>
  }
  packets: TracePacket[]
  local_router_trace?: Record<string, unknown>
  memory_writes?: Array<{
    slot_id: string
    state_id: string
    value: string
    created: boolean
    authority: string
  }>
  memory_candidates?: Array<{
    schema?: string
    slot_id: string
    proposed_value?: string
    summary?: string
    claim_summary?: string
    candidate_kind?: string
    confidence?: number
    source?: string
    reference_id?: string
    semantic_signal?: string
    authority?: string
    review_required?: boolean
    memory_write_allowed?: boolean
    confirmed_fact?: boolean
  }>
  document_write?: {
    document_id: string
    title: string
    created: boolean
    chunk_count: number
  } | null
  tool_runs?: Array<{
    tool_run_id: string
    tool: string
    input: Record<string, unknown>
    output: Record<string, unknown>
    status: string
  }>
  tool_considerations?: Array<{
    tool: string
    status: string
    reason: string
    source?: string
  }>
}

export interface PublicGovernanceStep {
  schema: string
  step_id: string
  index: number
  phase: string
  status: 'done' | 'skipped' | 'started' | 'failed' | string
  summary: string
  detail: string
  public: boolean
  raw_chain_of_thought: boolean
}

export interface GovernanceAnswerSpine {
  spine_schema: string
  source: string
  question_summary: string
  render_mode: string
  deterministic_source?: string | null
  route?: {
    selected_route?: string
    selected_model_policy?: string
    risk_level?: string
    memory_write_allowed?: boolean
    silent_escalation_allowed?: boolean
  }
  context_scope?: {
    answerable_packet_count?: number
    restricted_packet_count?: number
    has_context_bridge?: boolean
    has_answer_guidance?: boolean
  }
  answerable?: Array<Record<string, unknown>>
  restricted?: Array<Record<string, unknown>>
  render_contract?: string[]
  safety_contract?: {
    memory_writes_allowed?: boolean
    support_pattern_import_allowed?: boolean
    reflection_create_allowed?: boolean
    raw_chain_of_thought_stored?: boolean
    silent_policy_mutation_allowed?: boolean
    review_required_before_promotion?: boolean
  }
}

export interface GovernanceSpineCompliance {
  schema: string
  checked: boolean
  passed: boolean
  flags: string[]
  restricted_clause_count: number
  restricted_value_leak: boolean
  missing_restricted_boundary: boolean
  unauthorized_memory_write_claim: boolean
  answer_length: number
  stored_restricted_values: boolean
  raw_chain_of_thought_stored: boolean
}

export interface LocalRouterRagEvidenceReview {
  kind: 'local_router_rag_evidence_review'
  source: 'local_router_rag_suite' | string
  pack?: string
  pack_path?: string
  result_path?: string
  case_count: number
  baseline_to_beat: 'scaffolded_rag' | string
  baselines: Record<string, {
    answer_pass_count: number
    answer_pass_rate: number
    answer_avg_score: number | null
    trace_pass_count: number
    trace_pass_rate: number
    trace_avg_score: number | null
    repair_count: number
    fallback_count: number
    failure_count: number
    failures_by_task_type: Record<string, number>
  }>
  governed_delta_vs_scaffolded_rag: {
    answer_pass_delta: number
    answer_avg_score_delta: number | null
    trace_complete: boolean
  }
  review_flags: string[]
  failure_summary: Record<string, Record<string, number>>
  safety_contract: {
    promotion_status: 'review_only' | string
    memory_writes_allowed: boolean
    raw_chain_of_thought_stored: boolean
    silent_policy_mutation_allowed: boolean
    review_required_before_promotion: boolean
  }
  next_review: string
}

export interface RouteCandidate {
  route: string
  confidence: number
  reason: string
}

export interface RouteDecision {
  selected_route: string
  candidate_routes: RouteCandidate[]
  selected_model_policy: string
  tool_policy: string
  repair_policy: string
  escalation_allowed: boolean
  escalation_reason?: string | null
  route_reason: string
  route_confidence: number
  risk_level: string
  memory_write_allowed: boolean
  silent_escalation_allowed: boolean
  model_recommendation?: {
    current_selected_model: string
    recommended_model_policy: string
    recommended_model: string
    fallback_model: string
    confidence: string
    latency_caveat: string
    evidence_path: string
    observational_only: boolean
    model_selection_changed: boolean
  }
}

export interface DepthPolicy {
  mode: string
  requested: boolean
  reason: string
  max_continuations: number
  include_approach: boolean
  guidance?: string
}

export interface DepthCompletion extends DepthPolicy {
  continuation_count: number
  depth_satisfied: boolean
  continued_reason: string
  assessment?: {
    mode: string
    requested: boolean
    word_count: number
    min_words: number
    satisfied: boolean
    reason: string
  }
}

export interface PatchApplyReceipt {
  receipt_id: string
  tool_run_id: string
  path: string
  before_sha256: string
  after_sha256: string
  patch: string
  idempotent_replay: boolean
}

export interface Turn {
  turn_id: string
  user_message: string
  local_answer: string
  model: string
  needs_stronger_model: boolean
  created_at: number
  completed_at?: number
}

export interface Conversation {
  conversation_id: string
  title: string
  created_at: number
  updated_at: number
}

export interface SlotSummary {
  slot_id: string
  current_values: string[]
  conflict: boolean
  quarantined: boolean
  state_count: number
  updated_at: number
}

export interface SlotHistory {
  state_id: string
  value: string
  normalized: string
  trust: number
  observed_at: number
  temporal_status: string
  source: string
  source_text: string
  superseded_by?: string
  current: boolean
}

export interface SlotDetail {
  revision_hash: string
  slot_id: string
  conflict: boolean
  quarantined: boolean
  contradiction_disposition?: ContradictionDisposition | null
  history: SlotHistory[]
  review: unknown
}


export interface ReflectionEvidence {
  evidence_id: string
  evidence_type: string
  reference_id: string
  summary: string
  observed_at?: number
  created_at: number
}

export interface Reflection {
  reflection_id: string
  subject: 'agent' | 'user' | 'workflow' | 'project'
  observation: string
  interpretation: string
  alternatives: string[]
  confidence: number
  time_window: string
  suggested_experiment: string
  status: 'proposed' | 'accepted' | 'rejected' | 'deferred' | 'expired' | 'superseded'
  supersedes_id?: string
  superseded_by?: string
  created_at: number
  updated_at: number
  evidence: ReflectionEvidence[]
  reviews: Array<{
    review_id: string
    action: string
    note: string
    result_reflection_id?: string
    created_at: number
  }>
  revision_hash: string
}

export interface SupportPattern {
  candidate_id: string
  candidate_type: 'archive_support_pattern'
  category: string
  candidate_kind: string
  summary: string
  suggested_response_rule: string
  risk: string
  source_signal: string
  title_category_count: number
  status: 'proposed_review' | 'accepted' | 'rejected' | 'deferred'
  review_required: boolean
  memory_write_allowed: boolean
  confirmed_fact: boolean
  created_at: number
  updated_at: number
  evidence: Array<{
    evidence_type: string
    conversation_id: string
    title: string
    created_at?: string
  }>
  reviews: Array<{
    review_id: string
    action: string
    note: string
    created_at: number
  }>
  revision_hash: string
}

export interface ConsolidationCandidate {
  candidate_id: string
  candidate_type: 'background_consolidation_candidate'
  category: string
  candidate_kind: string
  summary: string
  proposed_action: string
  risk: string
  review_required: boolean
  memory_write_allowed: boolean
  confirmed_fact: boolean
  review_only?: boolean
  review_route: {
    surface: 'memory' | 'support_patterns' | 'reflections' | string
    action: string
    endpoint?: string
    slot_id?: string
    disposition_label?: string
    requires_adapter?: boolean
    draft?: Record<string, unknown>
  }
  evidence: Array<{
    evidence_type: string
    reference_id: string
    summary: string
    observed_at?: number | null
    source_authority?: string | null
  }>
}

export interface ReviewDraftHandoff {
  source_candidate_id: string
  source_category: string
  candidate_kind: string
  summary: string
  proposed_action: string
  risk: string
  draft: Record<string, unknown>
  evidence: Array<{
    evidence_type: string
    reference_id: string
    summary: string
    observed_at?: number | null
    source_authority?: string | null
  }>
}

export interface ConsolidationPreview {
  mode: 'preview_only'
  writes_performed: boolean
  memory_ingestion_performed: boolean
  support_pattern_import_performed: boolean
  reflection_create_performed: boolean
  inspected_turn_count: number
  candidates: ConsolidationCandidate[]
}
export interface ChatEvents {
  onTurn: (data: { turn_id: string; conversation_id: string }) => void
  onTrace: (trace: Trace) => void
  onGovernanceStep?: (step: PublicGovernanceStep) => void
  onToken: (text: string) => void
  onDone: (data: {
    answer: string
    needs_stronger_model: boolean
    source?: string
    generation_model?: string
    guidance_source?: string
    guidance_kind?: string
    guidance_repaired?: boolean | null
    guidance_repair_failed?: boolean | null
    depth?: DepthCompletion
    memory_writes?: Array<{ slot_id: string; value: string }>
    document_write?: { document_id: string; title: string; chunk_count: number } | null
    tool_runs?: Array<{ tool: string; status: string }>
  }) => void
  onError: (message: string) => void
}

export interface DesktopBridge {
  setExpanded: (value: boolean) => Promise<unknown>
  setFloating: (value: boolean) => Promise<boolean>
  setAlwaysOnTop: (value: boolean) => Promise<boolean>
  minimize: () => void
  close: () => void
  onSidecarStatus: (callback: (status: string) => void) => () => void
}

declare global {
  interface Window {
    aetherDesktop?: DesktopBridge
  }
}
