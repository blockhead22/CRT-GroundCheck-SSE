import type {
  ChatEvents,
  Health,
  ModelInfo,
  SlotDetail,
  SlotSummary,
  Trace,
  Turn,
} from './types'

const API_BASE = import.meta.env.VITE_AETHER_API_BASE || 'http://127.0.0.1:8765'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.detail || `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/health'),
  models: async () => (await request<{ models: ModelInfo[] }>('/v1/models')).models,
  conversations: () => request<{ conversations: Array<{ conversation_id: string; title: string }> }>('/v1/conversations'),
  turns: async (conversationId: string) =>
    (await request<{ turns: Turn[] }>(`/v1/conversations/${encodeURIComponent(conversationId)}/turns`)).turns,
  slots: async (query = '') =>
    request<{ revision_hash: string; slots: SlotSummary[] }>(
      `/v1/slots${query ? `?query=${encodeURIComponent(query)}` : ''}`,
    ),
  slot: (slotId: string) => request<SlotDetail>(`/v1/slots/${encodeURIComponent(slotId)}`),
  trace: (turnId: string) => request<{ trace: Trace } & Record<string, unknown>>(`/v1/traces/${turnId}`),
  confirm: (slotId: string, body: Record<string, string>) =>
    request(`/v1/slots/${encodeURIComponent(slotId)}/confirm`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  correct: (slotId: string, body: Record<string, string>) =>
    request(`/v1/slots/${encodeURIComponent(slotId)}/correct`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  quarantine: (slotId: string, body: Record<string, string>) =>
    request(`/v1/slots/${encodeURIComponent(slotId)}/quarantine`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  escalate: (turnId: string, reason: string) =>
    request<{ answer: string; escalation_id: string }>('/v1/escalations', {
      method: 'POST',
      body: JSON.stringify({ turn_id: turnId, reason }),
    }),
  documents: () => request<{ documents: Array<{
    document_id: string
    title: string
    source_kind: string
    chars: number
    chunk_count: number
    updated_at: number
  }> }>('/v1/documents'),
}

function dispatchEvent(block: string, events: ChatEvents) {
  let eventName = ''
  let data = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) eventName = line.slice(6).trim()
    if (line.startsWith('data:')) data += line.slice(5).trim()
  }
  if (!eventName || !data) return
  const payload = JSON.parse(data)
  if (eventName === 'turn') events.onTurn(payload)
  else if (eventName === 'trace') events.onTrace(payload)
  else if (eventName === 'token') events.onToken(payload.text)
  else if (eventName === 'done') events.onDone(payload)
  else if (eventName === 'error') events.onError(payload.message)
}

export async function streamChat(
  body: { message: string; conversation_id?: string; model: string },
  events: ChatEvents,
) {
  const response = await fetch(`${API_BASE}/v1/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok || !response.body) throw new Error(`Chat failed (${response.status})`)

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done }).replace(/\r\n/g, '\n')
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''
    for (const block of blocks) dispatchEvent(block, events)
    if (done) break
  }
  if (buffer.trim()) dispatchEvent(buffer, events)
}

export function idempotencyKey(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`
}
