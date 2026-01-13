import type { ChatMessage } from '../types'

export type ChatSendRequest = {
  thread_id: string
  message: string
  user_marked_important?: boolean
  mode?: string | null
}

export type RetrievedMemory = {
  text?: string | null
  source?: string | null
  trust?: number | null
  confidence?: number | null
}

export type PromptMemory = {
  text?: string | null
  source?: string | null
  trust?: number | null
  confidence?: number | null
}

export type ChatSendResponse = {
  answer: string
  response_type: string
  gates_passed: boolean
  gate_reason?: string | null
  session_id?: string | null
  metadata?: {
    confidence?: number | null
    intent_alignment?: number | null
    memory_alignment?: number | null
    contradiction_detected?: boolean | null
    unresolved_contradictions_total?: number | null
    unresolved_hard_conflicts?: number | null
    learned_suggestions?: unknown[]
    heuristic_suggestions?: unknown[]
    retrieved_memories?: RetrievedMemory[]
    prompt_memories?: PromptMemory[]
  }
}

function getApiBaseUrl(): string {
  const fromEnv = import.meta.env.VITE_API_BASE_URL
  return (fromEnv ?? 'http://127.0.0.1:8000').replace(/\/$/, '')
}

export async function sendToCrtApi(args: {
  threadId: string
  message: string
  history: ChatMessage[]
}): Promise<ChatSendResponse> {
  const base = getApiBaseUrl()
  const payload: ChatSendRequest = {
    thread_id: args.threadId,
    message: args.message,
  }

  const res = await fetch(`${base}/api/chat/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`CRT API error ${res.status}: ${text || res.statusText}`)
  }

  return (await res.json()) as ChatSendResponse
}
