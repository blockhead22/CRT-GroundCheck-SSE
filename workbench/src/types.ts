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

export interface TracePacket {
  request_id: string
  clause_id: string
  clause_text: string
  planner_slot: string
  slot_id: string
  mode: string
  release: ReleaseDecision
  reason: string
  evidence: Evidence[]
}

export interface Trace {
  query: string
  status: string
  turn_id: string
  conversation_id: string
  model: string
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
  memory_writes?: Array<{
    slot_id: string
    state_id: string
    value: string
    created: boolean
    authority: string
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
export interface ChatEvents {
  onTurn: (data: { turn_id: string; conversation_id: string }) => void
  onTrace: (trace: Trace) => void
  onToken: (text: string) => void
  onDone: (data: {
    answer: string
    needs_stronger_model: boolean
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
