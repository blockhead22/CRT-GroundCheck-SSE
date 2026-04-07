// Mirror the Streamlit app's primary sections.
export type NavId = 'chat' | 'dashboard' | 'loops' | 'journal' | 'jobs' | 'docs' | 'copilot' | 'live' | 'telemetry' | 'agent-runs' | 'settings' | 'v2' | 'belief-map' | 'beliefs' | 'pipeline-stepper' | 'governance'

export type ChatRole = 'user' | 'assistant'

export type RetrievedMemory = {
  memory_id?: string | null
  text?: string | null
  timestamp?: number | null
  source?: string | null
  trust?: number | null
  confidence?: number | null
  sse_mode?: string | null
  score?: number | null
  kind?: string | null
  pca_x?: number | null
  pca_y?: number | null
}

export type PromptMemory = {
  memory_id?: string | null
  text?: string | null
  source?: string | null
  trust?: number | null
  confidence?: number | null
}

// M3: Research & Evidence Packets
export type Citation = {
  quote_text: string
  source_url: string
  char_offset: number[]
  fetched_at: string
  confidence: number
}

export type EvidencePacket = {
  packet_id: string
  query: string
  summary: string
  citations: Citation[]
  memory_id: string
  citation_count: number
}

// Agent System Types
export type AgentAction = {
  tool: string
  args: Record<string, unknown>
  reasoning?: string | null
}

export type AgentObservation = {
  tool: string
  success: boolean
  result: string | null
  error: string | null
}

export type AgentStep = {
  step_num: number
  thought: string | null
  action: AgentAction | null
  observation: AgentObservation | null
  timestamp: string
}

export type AgentTrace = {
  query: string
  steps: AgentStep[]
  final_answer: string | null
  success: boolean
  error: string | null
  started_at: string
  completed_at: string | null
}

export type CtrMessageMeta = {
  response_type?: string
  gates_passed?: boolean
  gate_reason?: string | null
  session_id?: string | null
  interaction_id?: string | null
  confidence?: number | null
  intent_alignment?: number | null
  memory_alignment?: number | null
  contradiction_detected?: boolean | null
  contradiction_entry?: {
    old_memory_id?: string
    new_memory_id?: string
    old_text?: string
    new_text?: string
    old_trust?: number
    new_trust?: number
    contradiction_type?: string
    resolution_method?: string
  } | null
  unresolved_contradictions_total?: number | null
  unresolved_hard_conflicts?: number | null
  retrieved_memories?: RetrievedMemory[]
  retrieval_edges?: Array<{ from: string; to: string; sim: number }> | null
  prompt_memories?: PromptMemory[]
  learned_suggestions?: unknown[]
  heuristic_suggestions?: unknown[]
  profile_updates?: Array<{
    slot: string
    old: string
    new: string
  }>
  pipeline_statuses?: string[]
  pipeline_steps?: unknown[] // PipelineStep[] — stored as unknown to avoid circular import
  draft_response?: string | null
  tasking?: {
    mode?: string
    passes?: number
    skipped?: string
    interval_seconds?: number
    plan?: {
      notes?: string | null
      tasks?: Array<{
        task_id: string
        goal: string
        acceptance_criteria: string
        status?: string
        summary?: string | null
      }>
    } | null
    coverage?: {
      score?: number
      missing_items?: string[]
      notes?: string | null
    } | null
  } | null
  research_packet?: EvidencePacket | null
  agent_activated?: boolean | null
  agent_answer?: string | null
  agent_trace?: AgentTrace | null
  // Phase 2.2: LLM Claim Tracking
  llm_claims?: Array<{
    slot: string
    value: string
    trust: number
    source: string
  }>
  llm_contradictions?: Array<{
    type: string
    slot: string
    old_value: string
    new_value: string
    disclosure: string
  }>
  llm_disclosures?: string[]
  // Gaslighting detection
  gaslighting_detected?: boolean
  gaslighting_citation?: string
  // Streaming thinking content
  thinking?: string
  // Lazy-load trace ID for thinking content (persists after refresh)
  thinking_trace_id?: string | null
  // Reflection trace ID for directed self-assessment
  reflection_trace_id?: string | null
  reflection_confidence?: number | null
  reflection_label?: string | null  // "high" | "medium" | "low"
  personality_profile?: Record<string, unknown> | null
  reflection_scorecard?: Record<string, unknown> | null
  // Gate debug — structured explanation of why a gate failed
  gate_debug?: {
    trigger?: string | null
    slot?: string | null
    stored?: string | null
    incoming?: string | null
    explanation?: string | null
    intent_align?: number | null
    memory_align?: number | null
    grounding?: number | null
    hard_conflicts?: number | null
    open_total?: number | null
    response_type_pred?: string | null
    conflicting_memories?: Array<{ text: string; trust: number }>
    ledger_id?: string | null
  } | null
  // Generation source (cloud primary mode)
  generation_source?: string | null
  // Escalation decision from backend
  escalation?: {
    start_tier?: string | null
    skip_tiers?: string[] | null
    reason?: string | null
  } | null
  // Whether cloud governance (slot classification, NLI) was used
  cloud_governance_used?: boolean | null
  // Agent loop metadata — whether tools were actually executed
  tools_executed?: boolean | null
  agent_loop?: boolean
  // Cost tracking
  cost_usd?: number
  // Belief confidence — how much the system trusts this response (0-1)
  belief_confidence?: number | null
  // Gate check results — slot classify / NLI critic / gap audit
  gate_checks?: {
    slot?: string
    nli?: string
    gap?: string
    governance_tier?: string
  } | null
  // Reintroduced claims tracking
  reintroduced_claims_count?: number
  xray?: {
    memories_used?: Array<{
      text: string
      trust: number
      confidence: number
      timestamp?: number | null
      reintroduced_claim?: boolean
    }>
    conflicts_detected?: Array<{
      old: string
      new: string
      status: string
    }>
  } | null
  // File references from agent file tools
  referenced_files?: Array<{ path: string; type: 'file' | 'dir' }>
  // Sprint 4 — commitment notification metadata
  notification_type?: string | null
  commitment_id?: string | null
  priority?: string | null
  consequence?: string | null
}

export type MessageRating = 'up' | 'down'

export type ChatMessage = {
  id: string
  role: ChatRole
  text: string
  createdAt: number
  crt?: CtrMessageMeta
  rating?: MessageRating | null
  ratingCategory?: string | null
  isProactive?: boolean
  // Persisted agent thinking strip state for task-route messages
  agentThinking?: import('./components/chat/AgentThinkingStrip').AgentThinkingState | null
}

export type ChatThread = {
  id: string
  title: string
  updatedAt: number
  messages: ChatMessage[]
  unreadCount?: number
  hasProactive?: boolean
  lastProactiveAt?: number | null
}

export type QuickAction = {
  id: string
  icon: string
  title: string
  subtitle: string
  seedPrompt: string
}
