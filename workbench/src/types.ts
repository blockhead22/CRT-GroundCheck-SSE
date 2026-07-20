export type ReleaseDecision = 'answerable' | 'withhold' | 'conflict' | 'no_evidence'

export type RenderProvider = 'local' | 'grok_build'

export interface RenderProviderReceipt {
  schema?: string
  requested: RenderProvider
  effective: RenderProvider
  model?: string
  fallback_applied?: boolean
  status?: string
  authority?: 'aether' | string
  role?: 'governed_renderer' | 'wording_only' | 'none' | string
}

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
  schema?: string
  query: string
  status: string
  planner?: {
    schema?: string
    scope?: string
    applicable: boolean
    status: string
    coverage?: number | null
    raw_coverage?: number | null
    reason?: string
  }
  coverage?: {
    schema?: string
    scope?: string
    status: string
    applicable?: number
    checked?: number
    passed?: number
    failed?: number
    not_checked?: number
    fully_verified?: boolean
  }
  result?: {
    schema?: string
    status: string
    accepted?: boolean | null
    answer_released?: boolean
    boundary_message_released?: boolean
    source?: string
    needs_stronger_model?: boolean
    fully_verified?: boolean
    raw_chain_of_thought_stored?: boolean
  }
  turn_id: string
  conversation_id: string
  model: string
  generation_model?: string
  voice_profile?: string
  external_renderer?: {
    requested_provider?: RenderProvider
    effective_provider?: RenderProvider
    request_source?: string
    requested?: boolean
    eligible?: boolean
    selected?: boolean
    status?: string
    model?: string
    effective_model?: string
    attempts?: number
    latency_s?: number
    fallback_applied?: boolean
    tools_allowed?: boolean
    writes_allowed?: boolean
    authority?: string
    role?: string
  }
  runtime_model_identity?: {
    schema?: string
    governing_system?: string
    effective_provider?: RenderProvider
    provider_display?: string
    model?: string
    maker?: string
    location?: 'local' | 'hosted' | string
    invoked?: boolean
    authority?: string
    renderer_role?: string
    independent_retrieval?: boolean
    tools_allowed?: boolean
    writes_allowed?: boolean
  }
  meta_answer?: { source?: string; intents?: Record<string, boolean> }
  direct_answer?: { source?: string; slot?: string }
  self_description_answer?: { source?: string }
  character_answer?: {
    source?: string
    kind?: string
    mode?: string
    needs_stronger_model?: boolean
    critic_repair_contract?: CharacterCriticRepairContract
  }
  route_decision?: RouteDecision
  governance_answer_spine?: GovernanceAnswerSpine
  public_governance_steps?: PublicGovernanceStep[]
  continuity_claim_atoms?: {
    schema: string
    request_kind: string
    atoms: ContinuityClaimAtom[]
  }
  continuity_packet?: {
    schema: string
    request_kind: string
    open_loops?: ContinuityOpenLoopItem[]
  }
  cross_conversation_context?: {
    schema: string
    requested: boolean
    retrieval_method: string
    status: string
    source_conversation_ids: string[]
    source_title?: string
    candidates?: Array<{
      conversation_id: string
      title: string
      match_kind: string
      score: number
      matching_turn_ids: string[]
    }>
    turns?: Array<{
      turn_id: string
      user: { text: string; authority: string }
      assistant: {
        text: string
        authority: string
        included: boolean
        exclusion_reason: string
      }
    }>
  }
  continuity_alignment_receipt?: ContinuityAlignmentReceipt
  task_continuation_packet?: TaskContinuationPacket
  task_continuation_receipt?: TaskContinuationReceipt
  mirus_governed_discovery?: MirusGovernedDiscovery | null
  completion?: {
    source?: string
    needs_stronger_model: boolean
    generation_model?: string
    render_provider?: RenderProviderReceipt
    route_decision?: RouteDecision
    governance_spine_compliance?: GovernanceSpineCompliance
    verification_summary?: CompletionVerification
    guidance_kind?: string
    guidance_repaired?: boolean | null
    guidance_repair_failed?: boolean | null
    character_critic_repair?: CharacterCriticRepair
    depth?: DepthCompletion
    continuity_alignment_receipt?: ContinuityAlignmentReceipt
    task_continuation_receipt?: TaskContinuationReceipt
    answer_released?: boolean
    boundary_message_released?: boolean
    public_answer?: string
    rejected_source?: string
    verification_rejection?: {
      schema?: string
      failed_dimensions?: string[]
      raw_rejected_draft_stored?: boolean
      raw_rejected_draft_released?: boolean
    }
  }
  depth_policy?: DepthPolicy
  plan?: {
    status: string
    coverage: number
    coverage_applicable?: boolean
    applicable?: boolean
    scope?: string
    unresolved_clauses: string[]
    clauses: Array<{
      clause_id: string
      text: string
      status: string
      candidate_slots: string[]
      reason_code: string
    }>
  }
  packets?: TracePacket[]
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
  task_authority_candidates?: Array<{
    schema: string
    candidate_id: string
    record_kind: 'open_loop' | 'constraint'
    summary: string
    category: string
    confidence: number
    source: string
    reference_id: string
    evidence_text: string
    authority: 'unconfirmed' | string
    review_required: boolean
    review_only: boolean
    task_authority_write_allowed: boolean
    memory_write_allowed: boolean
    confirmed_fact: boolean
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

export interface ContinuityClaimAtom {
  atom_id: string
  section: 'where' | 'changed' | 'next_candidate' | string
  proposition: string
  state: 'observed' | 'inferred_candidate' | 'explicit_open_loop' | string
  evidence_ids: string[]
}

export interface ContinuityOpenLoopItem {
  item_id: string
  category: string
  summary: string
  state: string
  evidence_ids: string[]
  loop_id: string
  source_type: string
  revision_hash: string
  observed_at?: number
}

export interface ContinuityOpenLoop {
  loop_id: string
  project_root: string
  summary: string
  source_type: 'user_explicit' | 'review_confirmed' | string
  status: 'open' | 'done' | 'deferred' | string
  idempotency_key: string
  created_at: number
  updated_at: number
  revision_hash: string
}

export interface TaskContinuationStateItem {
  loop_id: string
  summary: string
  source_type: string
  status: string
  revision_hash: string
  updated_at: number
}

export interface TaskContinuationSelection {
  loop_id: string
  revision_hash: string
}

export interface TaskContinuationArtifact {
  artifact_id: string
  label: string
  locator: string
  artifact_kind: string
  source_type: string
  status: string
  revision_hash: string
  updated_at: number
}

export interface TaskContinuationConstraint {
  constraint_id: string
  statement: string
  constraint_kind: string
  source_type: string
  status: string
  revision_hash: string
  updated_at: number
}

export interface TaskContinuationPacket {
  schema: string
  requested: boolean
  status: string
  request_kind: string
  project_root: string
  pending_steps: TaskContinuationStateItem[]
  completed_steps: TaskContinuationStateItem[]
  deferred_steps: TaskContinuationStateItem[]
  artifacts?: TaskContinuationArtifact[]
  active_constraints?: TaskContinuationConstraint[]
  revoked_constraints?: TaskContinuationConstraint[]
  selection?: {
    requested: boolean
    mode: string
    validated: boolean
    failure_reason: string
    requested_loop_id: string
    expected_revision_hash: string
  }
  selected_loop_id: string
  selected_loop_revision_hash?: string
  next_action: string
  next_action_authorized: boolean
  automatic_execution_allowed: boolean
  workspace_tool_use_allowed: boolean
  durable_writes_allowed: boolean
  profile_memory_write_allowed: boolean
}

export interface TaskContinuationReceipt {
  schema: string
  status: string
  selection_requested?: boolean
  selection_mode?: string
  selection_validated?: boolean
  selection_failure_reason?: string
  selected_loop_id: string
  selected_loop_revision_hash?: string
  artifact_count?: number
  active_constraint_count?: number
  revoked_constraint_count?: number
  next_action_authorized: boolean
  automatic_execution_allowed: boolean
  workspace_tool_use_allowed: boolean
  durable_write_count: number
  profile_memory_write_count: number
}

export interface CharacterCriticFinding {
  phase?: string
  dimension?: string
  status?: string
  note?: string
}

export interface CharacterCriticRepairContract {
  schema?: string
  mode?: string
  review_only?: boolean
  memory_writes?: boolean
  support_reflection_writes?: boolean
  policy_mutation?: boolean
  kind?: string
  required_dimensions?: string[]
  forbidden_patterns?: string[]
  hard_gates?: string[]
}

export interface CharacterCriticRepair {
  schema?: string
  contract?: CharacterCriticRepairContract
  pre_repair_findings?: CharacterCriticFinding[]
  post_repair_findings?: CharacterCriticFinding[]
  repair_triggered_by?: string[]
  review_only?: boolean
  memory_writes?: boolean
  support_reflection_writes?: boolean
  policy_mutation?: boolean
}

export interface MirusGovernedDiscovery {
  schema: string
  enabled: boolean
  mode: string
  front_packet?: {
    preferred_intent?: string
    pending_slot?: string
    candidate_hints?: string[]
    reasons?: string[]
  }
  repairs?: string[]
  quality_flags?: string[]
  logic_graph?: {
    nodes?: Array<{
      id: string
      kind?: string
      label?: string
      data?: Record<string, unknown>
    }>
    edges?: Array<{
      from: string
      to: string
      label?: string
    }>
  }
  safety?: Record<string, unknown>
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
  tension_packet?: {
    packet_id: string
    tension_type: string
    sides: Array<{
      side_id: string
      label: string
      claim: string
      evidence_ids?: string[]
    }>
    allowed_synthesis: string
    forbidden_collapse: string
    trace_summary: string
  } | null
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

export type CompletionVerificationStatus =
  | 'passed'
  | 'failed'
  | 'not_checked'
  | 'not_applicable'

export interface CompletionVerificationDimension {
  status: CompletionVerificationStatus
  checked: boolean
  passed: boolean | null
  reason: string
  flags?: string[]
}

export interface CompletionVerification {
  schema: string
  accepted: boolean
  all_applicable_checks_passed: boolean
  fully_verified: boolean
  applicable_dimension_count: number
  checked_dimension_count: number
  passed_dimension_count: number
  failed_dimension_count: number
  release_blocking_failed_dimension_count?: number
  not_checked_dimension_count: number
  dimensions: Record<string, CompletionVerificationDimension>
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
    recommended_model_policy?: string
    recommended_model?: string
    fallback_model?: string
    confidence?: string
    latency_caveat?: string
    evidence_path?: string
    observational_only?: boolean
    model_selection_changed?: boolean
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

export interface ContinuityAlignmentReceipt {
  schema: string
  status: 'exact' | 'partial' | 'ambiguous' | 'blocked' | string
  retrieval_method: string
  source_conversation_ids: string[]
  source_conversations?: Array<{
    conversation_id: string
    title: string
  }>
  candidate_conversations?: Array<{
    conversation_id: string
    title: string
    match_kind: string
    score: number
  }>
  destination_conversation_id: string
  destination_turn_id: string
  cited_turn_ids: string[]
  carried_claims: Array<Record<string, unknown>>
  clarification_required: boolean
  profile_memory_write_count: number
  archived_conversation_promoted_to_profile_memory: boolean
}

export interface Turn {
  turn_id: string
  user_message: string
  local_answer: string
  model: string
  needs_stronger_model: boolean
  created_at: number
  completed_at?: number
  generation_model?: string
  render_provider?: RenderProviderReceipt
  completion_verification?: CompletionVerification
  continuity_alignment_receipt?: ContinuityAlignmentReceipt
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
  task_authority_write_performed?: boolean
  reviewed_task_candidate_count?: number
  inspected_turn_count: number
  candidates: ConsolidationCandidate[]
}

export interface TaskCandidateReviewResponse {
  review: {
    review_id: string
    candidate_id: string
    action: 'promote' | 'reject'
    note: string
    created_record_kind: 'open_loop' | 'constraint' | ''
    created_record_id: string
    created_at: number
  }
  authority_record: Record<string, unknown> | null
  memory_write_performed: boolean
  task_authority_write_performed: boolean
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
    character_critic_repair?: CharacterCriticRepair
    depth?: DepthCompletion
    memory_writes?: Array<{ slot_id: string; value: string }>
    document_write?: { document_id: string; title: string; chunk_count: number } | null
    tool_runs?: Array<{ tool: string; status: string }>
  }) => void
  onError: (message: string) => void
}

export interface DesktopBridge {
  apiBase: string
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
