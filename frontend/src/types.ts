// Mirror the Streamlit app's primary sections.
export type NavId = 'chat' | 'dashboard' | 'jobs' | 'docs' | 'showcase'

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
  confidence?: number | null
  intent_alignment?: number | null
  memory_alignment?: number | null
  contradiction_detected?: boolean | null
  unresolved_contradictions_total?: number | null
  unresolved_hard_conflicts?: number | null
  retrieved_memories?: RetrievedMemory[]
  prompt_memories?: PromptMemory[]
  learned_suggestions?: unknown[]
  heuristic_suggestions?: unknown[]
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
}

export type ChatMessage = {
  id: string
  role: ChatRole
  text: string
  createdAt: number
  crt?: CtrMessageMeta
}

export type ChatThread = {
  id: string
  title: string
  updatedAt: number
  messages: ChatMessage[]
}

export type QuickAction = {
  id: string
  icon: string
  title: string
  subtitle: string
  seedPrompt: string
}
