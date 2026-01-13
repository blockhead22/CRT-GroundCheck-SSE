// Mirror the Streamlit app's primary sections.
export type NavId = 'chat' | 'dashboard' | 'docs'

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
