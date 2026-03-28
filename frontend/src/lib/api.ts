import type { ChatMessage } from '../types'

export type ChatSendRequest = {
  thread_id: string
  message: string
  user_marked_important?: boolean
  mode?: string | null
  phase_mode?: boolean
}

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

export type ChatFeedbackRequest = {
  interaction_id: string
  thread_id: string
  thumbs_up: boolean
  category?: 'hallucination' | 'wrong_fact' | 'tone' | 'other' | null
  comment?: string | null
  memory_ids_cited?: string[]
}

export type ChatFeedbackResponse = {
  ok: boolean
  interaction_id: string
  thumbs_up: boolean
  memories_affected: Array<{ memory_id: string; old_trust: number; new_trust: number }>
}

export type ChatSendResponse = {
  answer: string
  response_type: string
  gates_passed: boolean
  gate_reason?: string | null
  session_id?: string | null
  metadata?: {
    interaction_id?: string | null
    confidence?: number | null
    intent_alignment?: number | null
    memory_alignment?: number | null
    contradiction_detected?: boolean | null
    unresolved_contradictions_total?: number | null
    unresolved_hard_conflicts?: number | null
    learned_suggestions?: unknown[]
    heuristic_suggestions?: unknown[]
    profile_updates?: Array<{
      slot: string
      old: string
      new: string
    }>
    pipeline_statuses?: string[]
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
      }
      coverage?: {
        score?: number
        missing_items?: string[]
        notes?: string | null
      }
    }
    retrieved_memories?: RetrievedMemory[]
    prompt_memories?: PromptMemory[]
    agent_activated?: boolean | null
    agent_answer?: string | null
    agent_trace?: {
      query: string
      steps: Array<{
        step_num: number
        thought: string | null
        action: {
          tool: string
          args: Record<string, unknown>
          reasoning?: string | null
        } | null
        observation: {
          tool: string
          success: boolean
          result: string | null
          error: string | null
        } | null
        timestamp: string
      }>
      final_answer: string | null
      success: boolean
      error: string | null
      started_at: string
      completed_at: string | null
    } | null
    xray?: {
      memories_used?: Array<{
        text: string
        trust: number
        confidence: number
        timestamp?: number | null
      }>
      conflicts_detected?: Array<{
        old: string
        new: string
        status: string
      }>
    } | null
  }
}

export type LoopRunRequest = {
  thread_id: string
  mode?: 'reflection' | 'personality' | 'both' | 'heartbeat' | 'all'
  prompt?: string | null
}

export type LoopRunResponse = {
  ok: boolean
  thread_id: string
  ran: string[]
  reflection_scorecard?: Record<string, unknown> | null
  personality_profile?: Record<string, unknown> | null
  self_model?: Record<string, string | null> | null
  open_contradictions?: number | null
}

export type ReflectionJournalEntry = {
  id: number
  thread_id: string
  created_at: number
  entry_type: string
  title: string
  body: string
  meta?: Record<string, unknown> | null
}

export type JournalSettings = {
  thread_id: string
  auto_reply_enabled: boolean
  auto_reply_enabled_override?: boolean | null
  auto_reply_chance: number
  auto_reply_min_seconds: number
  auto_reply_interval_seconds: number
}

export type JournalReplyResponse = {
  ok: boolean
  entry: ReflectionJournalEntry
  auto_reply_created: boolean
}

function getApiBaseUrlInternal(): string {
  const fromEnv = import.meta.env.VITE_API_BASE_URL
  let fromStorage = typeof window !== 'undefined' ? window.localStorage.getItem('crt_api_base_url') : null
  
  // Calculate what the fallback should be based on current hostname
  let fallback = ''
  if (typeof window !== 'undefined') {
    // Always use port 8123 for the API
    const hostname = window.location.hostname
    fallback = `http://${hostname}:8123`
  }
  
  // Clear stale localStorage values that don't match current host context
  if (fromStorage && typeof window !== 'undefined') {
    const hostname = window.location.hostname
    const isExternalAccess = hostname !== 'localhost' && hostname !== '127.0.0.1'
    const storageIsLoopback = fromStorage.includes('127.0.0.1') || fromStorage.includes('localhost')
    if (isExternalAccess && storageIsLoopback) {
      // Clear stale loopback URL when accessing externally
      window.localStorage.removeItem('crt_api_base_url')
      fromStorage = null
    }
  }
  
  const base = (fromStorage && fromStorage.trim()) || (fromEnv && String(fromEnv).trim()) || fallback
  return base.replace(/\/$/, '')
}

export function getEffectiveApiBaseUrl(): string {
  return getApiBaseUrlInternal()
}

export function setEffectiveApiBaseUrl(baseUrl: string): void {
  if (typeof window === 'undefined') return
  const clean = (baseUrl || '').trim().replace(/\/$/, '')
  if (!clean) {
    window.localStorage.removeItem('crt_api_base_url')
  } else {
    window.localStorage.setItem('crt_api_base_url', clean)
  }
}

export async function sendToCrtApi(args: {
  threadId: string
  message: string
  history: ChatMessage[]
}): Promise<ChatSendResponse> {
  const base = getApiBaseUrlInternal()
  const payload: ChatSendRequest = {
    thread_id: args.threadId,
    message: args.message,
  }

  let res: Response
  try {
    const token = getAuthToken()
    res = await fetch(`${base}/api/chat/send`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
    })
  } catch (_e) {
    const at = base ? base : '(same origin)'
    throw new Error(`CRT API unreachable at ${at}. Is the backend running?`)
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`CRT API error ${res.status}: ${text || res.statusText}`)
  }

  return (await res.json()) as ChatSendResponse
}

export async function runLoops(args: LoopRunRequest): Promise<LoopRunResponse> {
  const base = getApiBaseUrlInternal()
  const payload: LoopRunRequest = {
    thread_id: args.thread_id,
    mode: args.mode ?? 'both',
    prompt: args.prompt ?? null,
  }

  let res: Response
  try {
    res = await fetch(`${base}/api/loops/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch (_e) {
    const at = base ? base : '(same origin)'
    throw new Error(`CRT API unreachable at ${at}. Is the backend running?`)
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`CRT API error ${res.status}: ${text || res.statusText}`)
  }

  return (await res.json()) as LoopRunResponse
}

export async function getReflectionJournal(args: {
  threadId: string
  limit?: number
}): Promise<{ entries: ReflectionJournalEntry[]; count: number }> {
  const base = getApiBaseUrlInternal()
  const limit = typeof args.limit === 'number' ? args.limit : 50
  let res: Response
  try {
    res = await fetch(`${base}/api/reflection/journal/${encodeURIComponent(args.threadId)}?limit=${limit}`)
  } catch (_e) {
    const at = base ? base : '(same origin)'
    throw new Error(`CRT API unreachable at ${at}. Is the backend running?`)
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`CRT API error ${res.status}: ${text || res.statusText}`)
  }

  return (await res.json()) as { entries: ReflectionJournalEntry[]; count: number }
}

export async function getJournalSettings(args: { threadId: string }): Promise<JournalSettings> {
  const base = getApiBaseUrlInternal()
  let res: Response
  try {
    res = await fetch(`${base}/api/journal/settings?thread_id=${encodeURIComponent(args.threadId)}`)
  } catch (_e) {
    const at = base ? base : '(same origin)'
    throw new Error(`CRT API unreachable at ${at}. Is the backend running?`)
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`CRT API error ${res.status}: ${text || res.statusText}`)
  }

  return (await res.json()) as JournalSettings
}

export async function setJournalSettings(args: {
  threadId: string
  autoReplyEnabled: boolean
}): Promise<JournalSettings> {
  const base = getApiBaseUrlInternal()
  const payload = {
    thread_id: args.threadId,
    auto_reply_enabled: args.autoReplyEnabled,
  }

  let res: Response
  try {
    res = await fetch(`${base}/api/journal/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch (_e) {
    const at = base ? base : '(same origin)'
    throw new Error(`CRT API unreachable at ${at}. Is the backend running?`)
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`CRT API error ${res.status}: ${text || res.statusText}`)
  }

  return (await res.json()) as JournalSettings
}

export async function postJournalReply(args: {
  threadId: string
  replyTo: number
  body: string
  title?: string
  author?: string
}): Promise<JournalReplyResponse> {
  const base = getApiBaseUrlInternal()
  const payload = {
    thread_id: args.threadId,
    reply_to: args.replyTo,
    body: args.body,
    title: args.title,
    author: args.author,
  }

  let res: Response
  try {
    res = await fetch(`${base}/api/reflection/journal/reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch (_e) {
    const at = base ? base : '(same origin)'
    throw new Error(`CRT API unreachable at ${at}. Is the backend running?`)
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`CRT API error ${res.status}: ${text || res.statusText}`)
  }

  return (await res.json()) as JournalReplyResponse
}

// Streaming event types from /api/chat/stream
export type StreamEventType =
  | 'status'
  | 'intent_preview'
  | 'intent_classified'
  | 'plan_ready'
  | 'tool_start'
  | 'tool_result'
  | 'validate_result'
  | 'task_done'
  | 'task_acknowledged'
  | 'orchestration_start'
  | 'subtask_start'
  | 'subtask_done'
  | 'orchestration_done'
  | 'agent_checkpoint'
  | 'task_cancelled'
  | 'agent_thinking_token'
  | 'thinking_start'
  | 'thinking_token'
  | 'thinking'
  | 'thinking_end'
  | 'phase_start'
  | 'phase_end'
  | 'token'
  | 'correction'
  | 'stream_checkpoint'
  | 'stream_stopped'
  | 'plan_proposal'
  | 'plan_update'
  | 'plan_complete'
  | 'agent_loop_start'
  | 'agent_loop_complete'
  | 'done'
  | 'error'

export type AgentStep = {
  step_index: number
  tool_name: string
  input: Record<string, unknown>
  output_preview?: string
  byte_count?: number
  duration_ms?: number
  status: 'pending' | 'running' | 'ok' | 'error' | 'queued'
  error?: string
  reasoning?: string
}

export type StreamEvent = {
  type: StreamEventType
  content: string
  phase?: string
  metadata?: Record<string, unknown>
}

export type StreamCallbacks = {
  onStatus?: (content: string) => void
  onIntentPreview?: (intent: string, slots: string[], label: string) => void
  // Agentic task route events
  onIntentClassified?: (intent: string, route: string, slots: Record<string, unknown>, confidence: number, source?: string) => void
  onPlanReady?: (steps: Array<{ tool: string; input: Record<string, unknown> }>) => void
  onToolStart?: (toolName: string, input: Record<string, unknown>, stepIndex: number) => void
  onToolResult?: (step: AgentStep) => void
  onValidateResult?: (conflicts: unknown[], gate: string) => void
  onTaskDone?: (answer: string, steps: AgentStep[], metadata: Record<string, unknown>) => void
  onTaskAcknowledged?: (message: string, metadata: Record<string, unknown>) => void
  // Orchestration events (Sprint 8)
  onOrchestrationStart?: (subtaskCount: number, subtasks: Array<{ task_id: string; intent_type: string; agent_name: string; depends_on: string[] }>) => void
  onSubtaskStart?: (taskId: string, agentName: string, intentType: string) => void
  onSubtaskDone?: (taskId: string, agentName: string, status: string, durationMs: number, outputPreview: string) => void
  onOrchestrationDone?: (mergedTrust: number, allOk: boolean, metadata: Record<string, unknown>) => void
  onAgentCheckpoint?: (message: string, metadata: Record<string, unknown>) => void
  onTaskCancelled?: (message: string) => void
  onAgentThinkingToken?: (token: string, step: string) => void
  // Agent Loop events (Sprint 14)
  onAgentLoopStart?: (toolsAvailable: string[], maxIterations: number) => void
  onAgentLoopComplete?: (toolsUsed: string[], iterations: number, totalDurationMs: number) => void
  // Thinking
  onThinkingStart?: () => void
  onThinkingToken?: (token: string) => void
  onThinking?: (fullThinking: string) => void
  onThinkingEnd?: () => void
  onPhaseStart?: (phase: string, content?: string) => void
  onPhaseEnd?: (phase: string) => void
  onToken?: (token: string) => void
  onCorrection?: (content: string) => void
  onStreamCheckpoint?: (content: string, metadata?: Record<string, unknown>) => void
  onStreamStopped?: (content: string, metadata?: Record<string, unknown>) => void
  onDone?: (content: string, metadata?: Record<string, unknown>) => void
  onError?: (error: string) => void
}

/**
 * Stream chat response with real-time thinking/reasoning display.
 * 
 * Example usage:
 * ```ts
 * await streamFromCrtApi({
 *   threadId: 'demo',
 *   message: 'What is the meaning of life?',
 *   onThinkingToken: (token) => setThinking(prev => prev + token),
 *   onToken: (token) => setResponse(prev => prev + token),
 *   onDone: (content) => setFinalResponse(content),
 * })
 * ```
 */
export async function streamFromCrtApi(args: {
  threadId: string
  message: string
  phaseMode?: boolean
  callbacks: StreamCallbacks
  signal?: AbortSignal
}): Promise<void> {
  const base = getApiBaseUrlInternal()
  const payload: ChatSendRequest = {
    thread_id: args.threadId,
    message: args.message,
    phase_mode: args.phaseMode,
  }

  let res: Response
  try {
    const token = getAuthToken()
    res = await fetch(`${base}/api/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
      signal: args.signal,
    })
  } catch (_e) {
    if (args.signal?.aborted) return
    const at = base ? base : '(same origin)'
    args.callbacks.onError?.(`CRT API unreachable at ${at}. Is the backend running?`)
    return
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    args.callbacks.onError?.(`CRT API error ${res.status}: ${text || res.statusText}`)
    return
  }

  const reader = res.body?.getReader()
  if (!reader) {
    args.callbacks.onError?.('No response body')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      if (args.signal?.aborted) break
      let done: boolean
      let value: Uint8Array | undefined
      try {
        ({ done, value } = await reader.read())
      } catch (readErr) {
        // Stream was aborted (e.g. user clicked stop or sent a new message)
        if (args.signal?.aborted) break
        throw readErr
      }
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      
      // Process complete SSE events
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // Keep incomplete line in buffer
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event: StreamEvent = JSON.parse(line.slice(6))

            // SSE pipeline debug — remove after diagnosis
            if (['token', 'done', 'agent_checkpoint', 'agent_loop_start', 'agent_loop_complete', 'tool_start', 'tool_result', 'error'].includes(event.type)) {
              console.log(`[SSE_DEBUG] type=${event.type} content_len=${(event.content || '').length}`, event.type === 'done' ? event : '')
            }

            switch (event.type) {
              case 'status':
                args.callbacks.onStatus?.(event.content)
                break
              case 'intent_preview': {
                const meta = event.metadata as { intent?: string; slots?: string[] } | undefined
                args.callbacks.onIntentPreview?.(
                  meta?.intent ?? '',
                  meta?.slots ?? [],
                  event.content,
                )
                break
              }
              case 'intent_classified': {
                const meta = event.metadata as { intent?: string; route?: string; slots?: Record<string, unknown>; confidence?: number; source?: string } | undefined
                args.callbacks.onIntentClassified?.(
                  meta?.intent ?? '',
                  meta?.route ?? 'conversational',
                  meta?.slots ?? {},
                  meta?.confidence ?? 0,
                  meta?.source,
                )
                break
              }
              case 'plan_ready': {
                const meta = event.metadata as { steps?: Array<{ tool: string; input: Record<string, unknown> }> } | undefined
                args.callbacks.onPlanReady?.(meta?.steps ?? [])
                break
              }
              case 'tool_start': {
                const meta = event.metadata as { tool_name?: string; input?: Record<string, unknown>; step_index?: number } | undefined
                args.callbacks.onToolStart?.(meta?.tool_name ?? '', meta?.input ?? {}, meta?.step_index ?? 0)
                break
              }
              case 'tool_result': {
                const meta = event.metadata as AgentStep | undefined
                if (meta) args.callbacks.onToolResult?.(meta)
                break
              }
              case 'validate_result': {
                const meta = event.metadata as { conflicts?: unknown[]; gate?: string } | undefined
                args.callbacks.onValidateResult?.(meta?.conflicts ?? [], meta?.gate ?? '')
                break
              }
              case 'task_done': {
                const meta = event.metadata as { steps?: AgentStep[] } & Record<string, unknown> | undefined
                args.callbacks.onTaskDone?.(event.content, meta?.steps ?? [], meta ?? {})
                break
              }
              case 'task_acknowledged': {
                const meta = event.metadata as Record<string, unknown> | undefined
                args.callbacks.onTaskAcknowledged?.(event.content, meta ?? {})
                break
              }
              case 'orchestration_start': {
                const meta = event.metadata as { subtask_count?: number; subtasks?: Array<{ task_id: string; intent_type: string; agent_name: string; depends_on: string[] }> } | undefined
                args.callbacks.onOrchestrationStart?.(meta?.subtask_count ?? 0, meta?.subtasks ?? [])
                break
              }
              case 'subtask_start': {
                const meta = event.metadata as { task_id?: string; agent_name?: string; intent_type?: string } | undefined
                args.callbacks.onSubtaskStart?.(meta?.task_id ?? '', meta?.agent_name ?? '', meta?.intent_type ?? '')
                break
              }
              case 'subtask_done': {
                const meta = event.metadata as { task_id?: string; agent_name?: string; status?: string; duration_ms?: number; output_preview?: string } | undefined
                args.callbacks.onSubtaskDone?.(meta?.task_id ?? '', meta?.agent_name ?? '', meta?.status ?? 'ok', meta?.duration_ms ?? 0, meta?.output_preview ?? '')
                break
              }
              case 'orchestration_done': {
                const meta = event.metadata as { merged_trust?: number; all_ok?: boolean } & Record<string, unknown> | undefined
                args.callbacks.onOrchestrationDone?.(meta?.merged_trust ?? 0, meta?.all_ok ?? false, meta ?? {})
                break
              }
              case 'agent_checkpoint': {
                const meta = event.metadata as {
                  checkpoint_tier?: string
                  requires_confirmation?: boolean
                  auto_proceed_seconds?: number | null
                  intent?: string
                  confidence?: number
                } | undefined
                args.callbacks.onAgentCheckpoint?.(event.content, meta ?? {})
                break
              }
              case 'task_cancelled': {
                args.callbacks.onTaskCancelled?.(event.content)
                break
              }
              case 'agent_thinking_token': {
                const meta = event.metadata as { step?: string } | undefined
                args.callbacks.onAgentThinkingToken?.(event.content, meta?.step ?? 'generate_answer')
                break
              }
              case 'agent_loop_start': {
                const meta = event.metadata as { tools_available?: string[]; max_iterations?: number } | undefined
                args.callbacks.onAgentLoopStart?.(meta?.tools_available ?? [], meta?.max_iterations ?? 10)
                break
              }
              case 'agent_loop_complete': {
                const meta = event.metadata as { tools_used?: string[]; iterations?: number; total_duration_ms?: number } | undefined
                args.callbacks.onAgentLoopComplete?.(meta?.tools_used ?? [], meta?.iterations ?? 0, meta?.total_duration_ms ?? 0)
                break
              }
              case 'thinking_start':
                args.callbacks.onThinkingStart?.()
                break
              case 'thinking_token':
                args.callbacks.onThinkingToken?.(event.content)
                break
              case 'thinking':
                args.callbacks.onThinking?.(event.content)
                break
              case 'thinking_end':
                args.callbacks.onThinkingEnd?.()
                break
              case 'phase_start':
                args.callbacks.onPhaseStart?.(event.phase || '', event.content)
                break
              case 'phase_end':
                args.callbacks.onPhaseEnd?.(event.phase || '')
                break
              case 'token':
                args.callbacks.onToken?.(event.content)
                break
              case 'correction':
                args.callbacks.onCorrection?.(event.content)
                break
              case 'stream_checkpoint':
                args.callbacks.onStreamCheckpoint?.(event.content, event.metadata)
                // Also emit as a status so PipelineTrace picks it up
                args.callbacks.onStatus?.(`⬡ ${event.content}`)
                break
              case 'stream_stopped':
                args.callbacks.onStreamStopped?.(event.content, event.metadata)
                args.callbacks.onStatus?.(`⚡ ${event.content}`)
                break
              case 'done':
                args.callbacks.onDone?.(event.content, event.metadata)
                break
              case 'error':
                args.callbacks.onError?.(event.content)
                break
            }
          } catch (e) {
            console.warn('Failed to parse SSE event:', line, e)
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

function getBase(): string {
  return getApiBaseUrlInternal()
}

async function fetchJson<T>(path: string): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${getBase()}${path}`)
  } catch (_e) {
    const at = getBase() ? getBase() : '(same origin)'
    throw new Error(`CRT API unreachable at ${at}. Is the backend running?`)
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`CRT API error ${res.status}: ${text || res.statusText}`)
  }
  return (await res.json()) as T
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${getBase()}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (_e) {
    const at = getBase() ? getBase() : '(same origin)'
    throw new Error(`CRT API unreachable at ${at}. Is the backend running?`)
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`CRT API error ${res.status}: ${text || res.statusText}`)
  }
  return (await res.json()) as T
}

export async function getHealth(): Promise<{ status: string }> {
  return fetchJson<{ status: string }>('/health')
}

export type ProfileResponse = {
  thread_id: string
  name?: string | null
  slots: Record<string, string>
}

export async function getProfile(threadId: string): Promise<ProfileResponse> {
  return fetchJson<ProfileResponse>(`/api/profile?thread_id=${encodeURIComponent(threadId)}`)
}

export async function setProfileName(args: { threadId: string; name: string }): Promise<ChatSendResponse> {
  return postJson<ChatSendResponse>('/api/profile/set_name', {
    thread_id: args.threadId,
    message: args.name,
  })
}

export async function updateAuthProfile(fields: { display_name?: string }): Promise<{ ok: boolean; user: AuthUser }> {
  const base = getApiBaseUrlInternal()
  const token = getAuthToken()
  const res = await fetch(`${base}/api/auth/update_profile`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(fields),
  })
  if (!res.ok) throw new Error('Failed to update profile')
  return res.json()
}

export async function setProfileFacts(threadId: string, facts: Record<string, string>): Promise<{ ok: boolean; stored: number }> {
  return postJson<{ ok: boolean; stored: number }>('/api/profile/set_facts', {
    thread_id: threadId,
    facts,
  })
}

export type DocListItem = { id: string; title: string; kind: string }
export type DocGetResponse = { id: string; title: string; kind: string; markdown: string }

export async function listDocs(): Promise<DocListItem[]> {
  return fetchJson<DocListItem[]>('/api/docs')
}

export async function getDoc(docId: string): Promise<DocGetResponse> {
  return fetchJson<DocGetResponse>(`/api/docs/${encodeURIComponent(docId)}`)
}

export type ModelRoutingInfo = {
  default?: string | null
  fast?: string | null
  reasoning?: string | null
  code?: string | null
  research?: string | null
}

export type DashboardOverview = {
  thread_id: string
  session_id?: string | null
  memories_total: number
  global_memories_total: number
  effective_facts_total: number
  open_contradictions: number
  belief_ratio: number
  speech_ratio: number
  belief_count: number
  speech_count: number
  memory_scope: string
  contradiction_scope: string
  belief_speech_scope: string
  model_routing?: ModelRoutingInfo | null
}

export async function getDashboardOverview(threadId: string): Promise<DashboardOverview> {
  return fetchJson<DashboardOverview>(`/api/dashboard/overview?thread_id=${encodeURIComponent(threadId)}`)
}

export type MemoryListItem = {
  memory_id: string
  text: string
  timestamp: number
  confidence: number
  trust: number
  source: string
  sse_mode: string
  thread_id?: string | null
}

export async function listRecentMemories(threadId: string, limit = 30): Promise<MemoryListItem[]> {
  return fetchJson<MemoryListItem[]>(
    `/api/memory/recent?thread_id=${encodeURIComponent(threadId)}&limit=${encodeURIComponent(String(limit))}`,
  )
}

export async function searchMemories(args: {
  threadId: string
  q: string
  k?: number
  minTrust?: number
}): Promise<MemoryListItem[]> {
  const k = args.k ?? 10
  const minTrust = args.minTrust ?? 0
  return fetchJson<MemoryListItem[]>(
    `/api/memory/search?thread_id=${encodeURIComponent(args.threadId)}&q=${encodeURIComponent(args.q)}&k=${encodeURIComponent(
      String(k),
    )}&min_trust=${encodeURIComponent(String(minTrust))}`,
  )
}

export async function getMemory(threadId: string, memoryId: string): Promise<MemoryListItem> {
  return fetchJson<MemoryListItem>(
    `/api/memory/${encodeURIComponent(memoryId)}?thread_id=${encodeURIComponent(threadId)}`,
  )
}

export type TrustHistoryRow = {
  timestamp: number
  old_trust: number
  new_trust: number
  reason: string | null
  drift: number | null
}

export async function getMemoryTrustHistory(_threadId: string, memoryId: string): Promise<TrustHistoryRow[]> {
  const res = await fetchJson<{ memory_id: string; history: TrustHistoryRow[] }>(
    `/api/copilot/memory/${encodeURIComponent(memoryId)}/trust-history`,
  )
  return (res as any).history ?? []
}

export type ContradictionListItem = {
  ledger_id: string
  timestamp: number
  status: string
  contradiction_type: string
  drift_mean: number
  confidence_delta: number
  summary?: string | null
  query?: string | null
  old_memory_id: string
  new_memory_id: string
  // Enhanced fields for UI
  contradiction_id?: string | null
  slot?: string | null
  old_value?: string | null
  new_value?: string | null
  old_trust?: number | null
  new_trust?: number | null
  detected_at?: number | null
  policy?: string | null
}

export type ContradictionWorkItem = {
  thread_id: string
  ledger_id: string
  status: string
  contradiction_type: string
  drift_mean: number
  summary?: string | null
  ask_count: number
  last_asked_at?: number | null
  next_action: string
  suggested_question: string
}

export type ContradictionNextResponse = {
  thread_id: string
  has_item: boolean
  item?: ContradictionWorkItem | null
}

export async function listOpenContradictions(threadId: string, limit = 50): Promise<ContradictionListItem[]> {
  return fetchJson<ContradictionListItem[]>(
    `/api/ledger/open?thread_id=${encodeURIComponent(threadId)}&limit=${encodeURIComponent(String(limit))}`,
  )
}

export async function getContradictionNext(threadId: string): Promise<ContradictionNextResponse> {
  return fetchJson<ContradictionNextResponse>(`/api/contradictions/next?thread_id=${encodeURIComponent(threadId)}`)
}

export async function markContradictionAsked(args: { threadId: string; ledgerId: string }): Promise<{ ok: boolean }> {
  return postJson<{ ok: boolean }>('/api/contradictions/asked', {
    thread_id: args.threadId,
    ledger_id: args.ledgerId,
  })
}

export async function respondToContradiction(args: {
  threadId: string
  ledgerId: string
  answer: string
  resolve?: boolean
  resolutionMethod?: string
  newStatus?: string
  mergedMemoryId?: string | null
}): Promise<{
  ok: boolean
  thread_id: string
  ledger_id: string
  recorded: boolean
  resolved: boolean
  next: ContradictionNextResponse
}> {
  return postJson('/api/contradictions/respond', {
    thread_id: args.threadId,
    ledger_id: args.ledgerId,
    answer: args.answer,
    resolve: args.resolve ?? true,
    resolution_method: args.resolutionMethod ?? 'user_clarified',
    new_status: args.newStatus ?? 'resolved',
    merged_memory_id: args.mergedMemoryId ?? null,
  })
}

export async function resolveContradiction(args: {
  threadId: string
  ledgerId: string
  method: string
  newStatus?: string
}): Promise<{ ok: boolean }> {
  return postJson<{ ok: boolean }>('/api/ledger/resolve', {
    thread_id: args.threadId,
    ledger_id: args.ledgerId,
    method: args.method,
    new_status: args.newStatus ?? 'resolved',
  })
}

export type ThreadExportResponse = {
  thread_id: string
  generated_at: number
  memories: MemoryListItem[]
  contradictions: ContradictionListItem[]
  memories_total: number
  contradictions_total: number
}

export async function exportThread(args: {
  threadId: string
  includeResolved?: boolean
  memoriesLimit?: number
  contradictionsLimit?: number
}): Promise<ThreadExportResponse> {
  const includeResolved = args.includeResolved ?? true
  const memoriesLimit = args.memoriesLimit ?? 2000
  const contradictionsLimit = args.contradictionsLimit ?? 2000
  return fetchJson<ThreadExportResponse>(
    `/api/thread/export?thread_id=${encodeURIComponent(args.threadId)}&include_resolved=${encodeURIComponent(
      String(includeResolved),
    )}&memories_limit=${encodeURIComponent(String(memoriesLimit))}&contradictions_limit=${encodeURIComponent(
      String(contradictionsLimit),
    )}`,
  )
}

export type ThreadResetResponse = {
  thread_id: string
  target: string
  deleted: Record<string, boolean>
  ok: boolean
}

export async function resetThread(args: {
  threadId: string
  target: 'memory' | 'ledger' | 'all'
}): Promise<ThreadResetResponse> {
  return postJson<ThreadResetResponse>('/api/thread/reset', {
    thread_id: args.threadId,
    target: args.target,
  })
}

// ============================================================================
// Jobs (background worker)
// ============================================================================

export type JobsStatusResponse = {
  enabled: boolean
  worker: Record<string, unknown>
  idle_scheduler_enabled: boolean
  jobs_db_path: string
}

export type JobListItem = {
  id: string
  type: string
  status: string
  priority: number
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  payload: Record<string, unknown>
  error?: string | null
}

export type JobsListResponse = {
  jobs: JobListItem[]
}

export type JobDetailResponse = {
  job: JobListItem
  events: Array<{ ts: string; level: string; message: string; data?: unknown }>
  artifacts: Array<{ kind: string; path: string; sha256?: string | null; created_at: string }>
}

export async function getJobsStatus(): Promise<JobsStatusResponse> {
  return fetchJson<JobsStatusResponse>('/api/jobs/status')
}

export async function listJobs(args: {
  status?: string | null
  limit?: number
  offset?: number
}): Promise<JobsListResponse> {
  const status = args.status ? String(args.status) : ''
  const limit = args.limit ?? 50
  const offset = args.offset ?? 0
  const qs = new URLSearchParams()
  if (status) qs.set('status', status)
  qs.set('limit', String(limit))
  qs.set('offset', String(offset))
  return fetchJson<JobsListResponse>(`/api/jobs?${qs.toString()}`)
}

export async function getJob(jobId: string): Promise<JobDetailResponse> {
  return fetchJson<JobDetailResponse>(`/api/jobs/${encodeURIComponent(jobId)}`)
}

export async function enqueueJob(args: {
  type: string
  payload: Record<string, unknown>
  priority?: number
  jobId?: string | null
}): Promise<{ ok: boolean; job_id: string }> {
  return postJson<{ ok: boolean; job_id: string }>('/api/jobs', {
    type: args.type,
    payload: args.payload,
    priority: args.priority ?? 0,
    job_id: args.jobId ?? null,
  })
}

// ========================================================================
// M3: Research API
// ========================================================================

export async function searchResearch(args: {
  threadId: string
  query: string
  maxSources?: number
}): Promise<import('../types').EvidencePacket> {
  return postJson<import('../types').EvidencePacket>('/api/research/search', {
    thread_id: args.threadId,
    query: args.query,
    max_sources: args.maxSources ?? 3,
  })
}

export async function getCitations(args: {
  memoryId: string
  threadId: string
}): Promise<{ memory_id: string; citations: import('../types').Citation[] }> {
  const qs = new URLSearchParams({ thread_id: args.threadId })
  return fetchJson<{ memory_id: string; citations: import('../types').Citation[] }>(
    `/api/research/citations/${encodeURIComponent(args.memoryId)}?${qs.toString()}`
  )
}

export async function promoteResearch(args: {
  threadId: string
  memoryId: string
  userConfirmed: boolean
}): Promise<{ ok: boolean; memory_id: string; promoted: boolean }> {
  return postJson<{ ok: boolean; memory_id: string; promoted: boolean }>('/api/research/promote', {
    thread_id: args.threadId,
    memory_id: args.memoryId,
    user_confirmed: args.userConfirmed,
  })
}

// ========================================================================
// Thread Management
// ========================================================================

export type ThreadListItem = {
  id: string
  title: string
  updated_at: number
  message_count: number
}

export async function listThreads(): Promise<ThreadListItem[]> {
  return fetchJson<ThreadListItem[]>('/api/threads')
}

export async function createThread(args: { title?: string }): Promise<ThreadListItem> {
  return postJson<ThreadListItem>('/api/threads', {
    title: args.title ?? 'New chat',
  })
}

export async function updateThread(args: { threadId: string; title: string }): Promise<ThreadListItem> {
  const res = await fetch(`${getBase()}/api/threads/${encodeURIComponent(args.threadId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: args.title }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Failed to update thread: ${text || res.statusText}`)
  }
  return (await res.json()) as ThreadListItem
}

export async function deleteThread(args: { threadId: string }): Promise<{ ok: boolean; thread_id: string; deleted: boolean }> {
  const res = await fetch(`${getBase()}/api/threads/${encodeURIComponent(args.threadId)}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Failed to delete thread: ${text || res.statusText}`)
  }
  return (await res.json()) as { ok: boolean; thread_id: string; deleted: boolean }
}

export type LearningStats = {
  total_events: number
  total_corrections: number
  model_loaded: boolean
  model_version: number | null
  model_accuracy: number | null
  pending_training: boolean
  recent_gate_pass_rate: number | null
  recent_events_24h: number
}

export async function getLearningStats(): Promise<LearningStats> {
  return fetchJson<LearningStats>('/api/learning/stats')
}

// ============================================================================
// Reasoning Traces - Lazy Loading
// ============================================================================

export type ReasoningTraceListItem = {
  trace_id: string
  thread_id: string | null
  query: string
  response_summary: string | null
  model: string | null
  timestamp: number
  char_count: number
  thinking_preview?: string | null
}

export type ReasoningTrace = {
  trace_id: string
  thread_id: string | null
  query: string
  thinking_content: string
  response_summary: string | null
  model: string | null
  timestamp: number
  char_count: number
  metadata?: Record<string, unknown> | null
}

export type ReasoningTracesListResponse = {
  traces: ReasoningTraceListItem[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

/**
 * List reasoning traces with pagination (metadata only, no full content).
 * Use getReasoningTrace() to fetch full thinking content when needed.
 */
export async function listReasoningTraces(args: {
  threadId?: string
  limit?: number
  offset?: number
}): Promise<ReasoningTracesListResponse> {
  const params = new URLSearchParams()
  if (args.threadId) params.set('thread_id', args.threadId)
  if (args.limit) params.set('limit', String(args.limit))
  if (args.offset) params.set('offset', String(args.offset))
  
  return fetchJson<ReasoningTracesListResponse>(`/api/reasoning/traces?${params.toString()}`)
}

/**
 * Get full reasoning trace content by ID (lazy load).
 * Call this when user wants to view the complete thinking.
 * @param traceId - The trace ID to fetch
 * @param threadId - The thread ID (required to find correct database)
 */
export async function getReasoningTrace(traceId: string, threadId?: string): Promise<ReasoningTrace | null> {
  const params = new URLSearchParams()
  if (threadId) params.set('thread_id', threadId)
  const queryString = params.toString()
  const url = `/api/reasoning/traces/${encodeURIComponent(traceId)}${queryString ? '?' + queryString : ''}`
  
  const result = await fetchJson<ReasoningTrace | { error: string }>(url)
  if ('error' in result) {
    console.warn(`Failed to get reasoning trace ${traceId}:`, result.error)
    return null
  }
  return result
}

/**
 * Get recent reasoning traces with full content.
 * Useful for showing recent thinking without pagination.
 */
export async function getRecentReasoning(args: {
  threadId: string
  limit?: number
}): Promise<ReasoningTrace[]> {
  const params = new URLSearchParams()
  params.set('thread_id', args.threadId)
  if (args.limit) params.set('limit', String(args.limit))
  
  const result = await fetchJson<{ traces: ReasoningTrace[] }>(`/api/reasoning/recent?${params.toString()}`)
  return result.traces || []
}
// ============================================================================
// Reflection API
// ============================================================================

export interface ReflectionTrace {
  trace_id: string
  thread_id: string
  message_id?: string
  confidence_score: number
  confidence_label: 'high' | 'medium' | 'low' | 'unknown'
  reasoning: string
  suggested_action: 'accept' | 'refine' | 're-query'
  fact_checks: Array<{
    claim: string
    supported: boolean
    evidence: string
  }>
  hallucination_risk: 'low' | 'medium' | 'high' | 'unknown'
  was_requeried: boolean
  requery_trace_id?: string
  created_at: string
}

/**
 * Get full reflection trace content by ID (lazy load).
 * Call this when user wants to view the complete self-assessment.
 */
export async function getReflectionTrace(traceId: string, threadId?: string): Promise<ReflectionTrace | null> {
  const params = new URLSearchParams()
  if (threadId) params.set('thread_id', threadId)
  const queryString = params.toString()
  const url = `/api/reflection/traces/${encodeURIComponent(traceId)}${queryString ? '?' + queryString : ''}`
  
  const result = await fetchJson<ReflectionTrace | { error: string }>(url)
  if ('error' in result) {
    console.warn(`Failed to get reflection trace ${traceId}:`, result.error)
    return null
  }
  return result
}

/**
 * Get training data collection statistics.
 */
export async function getTrainingStats(): Promise<{
  total_reflections: number
  total_requeries: number
  total_preferences: number
  average_confidence: number
  high_hallucination_risk_count: number
}> {
  return fetchJson('/api/training/stats')
}

// =============================================================================
// Auth API
// =============================================================================

export type AuthUser = {
  id: number
  username: string
  display_name: string
  created_at: number
}

export type AuthLoginResponse = {
  ok: boolean
  token: string
  user: AuthUser
}

export type AuthMeResponse = {
  ok: boolean
  user: AuthUser | null
}

const AUTH_TOKEN_KEY = 'crt_auth_token'

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(AUTH_TOKEN_KEY)
    || window.localStorage.getItem('token')
    || window.localStorage.getItem('auth_token')
    || null
}

export function setAuthToken(token: string | null): void {
  if (typeof window === 'undefined') return
  if (token) {
    window.localStorage.setItem(AUTH_TOKEN_KEY, token)
  } else {
    window.localStorage.removeItem(AUTH_TOKEN_KEY)
  }
}

export async function authRegister(username: string, password: string, displayName?: string): Promise<AuthLoginResponse> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, display_name: displayName }),
  })
  
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Registration failed: ${res.statusText}`)
  }
  
  const data = await res.json() as AuthLoginResponse
  if (data.ok && data.token) {
    setAuthToken(data.token)
  }
  return data
}

export async function authLogin(username: string, password: string): Promise<AuthLoginResponse> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Login failed: ${res.statusText}`)
  }
  
  const data = await res.json() as AuthLoginResponse
  if (data.ok && data.token) {
    setAuthToken(data.token)
  }
  return data
}

export async function authLogout(): Promise<void> {
  const base = getApiBaseUrlInternal()
  const token = getAuthToken()
  
  try {
    await fetch(`${base}/api/auth/logout`, {
      method: 'POST',
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    })
  } finally {
    setAuthToken(null)
  }
}

export async function authGetMe(): Promise<AuthMeResponse> {
  const base = getApiBaseUrlInternal()
  const token = getAuthToken()
  
  if (!token) {
    return { ok: false, user: null }
  }
  
  try {
    const res = await fetch(`${base}/api/auth/me`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
    
    if (!res.ok) {
      return { ok: false, user: null }
    }
    
    return await res.json() as AuthMeResponse
  } catch {
    return { ok: false, user: null }
  }
}

export async function authSyncChats(threads: Array<{ id: string; title: string; messages: unknown[]; updatedAt: number }>): Promise<void> {
  const base = getApiBaseUrlInternal()
  const token = getAuthToken()
  
  if (!token) return
  
  await fetch(`${base}/api/auth/sync-chats`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ threads }),
  })
}

export async function authLoadChats(): Promise<Array<{ id: string; title: string; messages: unknown[]; updatedAt: number }>> {
  const base = getApiBaseUrlInternal()
  const token = getAuthToken()
  
  if (!token) return []
  
  try {
    const res = await fetch(`${base}/api/auth/load-chats`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
    
    if (!res.ok) return []
    
    const data = await res.json()
    return data.threads || []
  } catch {
    return []
  }
}

// ---------------------------------------------------------------------------
// Copilot Interactions (GroundCheck MCP Memory)
// ---------------------------------------------------------------------------

export type CopilotMemory = {
  id: string
  thread_id: string
  text: string
  trust: number
  source: string
  namespace: string
  timestamp: number
  created_at: string | null
}

export type CopilotStats = {
  total_memories: number
  namespaces: string[]
  source_counts: Record<string, number>
  trust_distribution: Record<string, number>
  auto_learned_count: number
  explicit_count: number
  newest_timestamp: number | null
  oldest_timestamp: number | null
}

export type CopilotMemoriesResponse = {
  memories: CopilotMemory[]
  total: number
  stats: CopilotStats
}

export async function getCopilotMemories(args?: {
  namespace?: string
  source?: string
  search?: string
  min_trust?: number
  limit?: number
  offset?: number
  sort?: 'newest' | 'oldest' | 'trust_high' | 'trust_low'
}): Promise<CopilotMemoriesResponse> {
  const base = getApiBaseUrlInternal()
  const params = new URLSearchParams()
  if (args?.namespace) params.set('namespace', args.namespace)
  if (args?.source) params.set('source', args.source)
  if (args?.search) params.set('search', args.search)
  if (args?.min_trust !== undefined) params.set('min_trust', String(args.min_trust))
  if (args?.limit !== undefined) params.set('limit', String(args.limit))
  if (args?.offset !== undefined) params.set('offset', String(args.offset))
  if (args?.sort) params.set('sort', args.sort)
  const qs = params.toString()
  const url = `${base}/api/copilot/memories${qs ? '?' + qs : ''}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to fetch copilot memories: ${res.status}`)
  return res.json()
}

export async function getCopilotStats(): Promise<CopilotStats> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/stats`)
  if (!res.ok) throw new Error(`Failed to fetch copilot stats: ${res.status}`)
  return res.json()
}

export async function getCopilotNamespaces(): Promise<string[]> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/namespaces`)
  if (!res.ok) throw new Error(`Failed to fetch copilot namespaces: ${res.status}`)
  return res.json()
}

export type CopilotProfile = {
  name: string | null
  role: string | null
  employer: string | null
  languages: string[]
  preferences: Record<string, string>
  all_facts: string[]
}

export type AccuracyStats = {
  total_memories: number
  corrections_made: number
  deletions_made: number
  auto_learned: number
  explicit: number
  accuracy_rate: number
  trust_avg: number
  memories_per_day: number
  learning_velocity: Array<{
    timestamp: number
    count: number
    auto_learned: number
    label: string
  }>
}

export async function teachCopilot(text: string, namespace?: string, threadId?: string): Promise<{ ok: boolean; memory_id: string; text: string; trust: number }> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/teach`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, namespace: namespace || 'default', source: 'user', thread_id: threadId || 'default' }),
  })
  if (!res.ok) throw new Error(`Failed to teach: ${res.status}`)
  return res.json()
}

export async function deleteCopilotMemory(memoryId: string): Promise<{ ok: boolean }> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/memory/${encodeURIComponent(memoryId)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to delete: ${res.status}`)
  return res.json()
}

export async function correctCopilotMemory(memoryId: string, correctedText: string): Promise<{ ok: boolean; old_text: string; new_text: string }> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/correct`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ memory_id: memoryId, corrected_text: correctedText }),
  })
  if (!res.ok) throw new Error(`Failed to correct: ${res.status}`)
  return res.json()
}

export async function getCopilotProfile(): Promise<CopilotProfile> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/profile`)
  if (!res.ok) throw new Error(`Failed to fetch profile: ${res.status}`)
  return res.json()
}

export async function getCopilotAccuracy(): Promise<AccuracyStats> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/accuracy`)
  if (!res.ok) throw new Error(`Failed to fetch accuracy: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Copilot — Fact Checks
// ---------------------------------------------------------------------------

export type FactCheck = {
  id: string
  thread_id: string
  response_text: string
  finding: string
  severity: string
  volatility: number
  status: string
  created_at: string
  resolved_at: string | null
}

export async function getCopilotFactChecks(args?: {
  thread_id?: string
  limit?: number
}): Promise<FactCheck[]> {
  const base = getApiBaseUrlInternal()
  const params = new URLSearchParams()
  if (args?.thread_id) params.set('thread_id', args.thread_id)
  if (args?.limit !== undefined) params.set('limit', String(args.limit))
  const qs = params.toString()
  const res = await fetch(`${base}/api/copilot/fact-checks${qs ? '?' + qs : ''}`)
  if (!res.ok) throw new Error(`Failed to fetch fact checks: ${res.status}`)
  return res.json()
}

export async function resolveFactCheck(checkId: string): Promise<{ ok: boolean; resolved: string }> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/fact-checks/${encodeURIComponent(checkId)}/resolve`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to resolve: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Copilot — Trust Decay & Scheduler
// ---------------------------------------------------------------------------

export type TrustDecayConfig = {
  decay_rate: number
  reinforce_boost: number
  correction_boost: number
  trust_floor: number
  trust_ceiling: number
  grace_period_days: number
  min_pass_interval_secs: number
}

export async function getTrustDecayConfig(): Promise<TrustDecayConfig> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/trust-decay/config`)
  if (!res.ok) throw new Error(`Failed to fetch trust decay config: ${res.status}`)
  return res.json()
}

export async function runTrustDecay(): Promise<Record<string, any>> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/trust-decay/run`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to run trust decay: ${res.status}`)
  return res.json()
}

export async function reinforceMemory(memoryId: string): Promise<{ ok: boolean; memory_id: string; boost: number }> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/memory/${encodeURIComponent(memoryId)}/reinforce`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to reinforce: ${res.status}`)
  return res.json()
}

export async function getSchedulerStatus(): Promise<Record<string, any>> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/scheduler/status`)
  if (!res.ok) throw new Error(`Failed to fetch scheduler status: ${res.status}`)
  return res.json()
}

export async function forceSchedulerTick(): Promise<Record<string, any>> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/scheduler/tick`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to trigger scheduler tick: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Copilot — Active Learning
// ---------------------------------------------------------------------------

export async function getCopilotLearningStats(): Promise<Record<string, any>> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/learning/stats`)
  if (!res.ok) throw new Error(`Failed to fetch learning stats: ${res.status}`)
  return res.json()
}

export async function getLearningCorrections(limit?: number): Promise<any[]> {
  const base = getApiBaseUrlInternal()
  const qs = limit ? `?limit=${limit}` : ''
  const res = await fetch(`${base}/api/copilot/learning/corrections${qs}`)
  if (!res.ok) throw new Error(`Failed to fetch corrections: ${res.status}`)
  return res.json()
}

export async function getLearningEvents(limit?: number): Promise<any[]> {
  const base = getApiBaseUrlInternal()
  const qs = limit ? `?limit=${limit}` : ''
  const res = await fetch(`${base}/api/copilot/learning/events${qs}`)
  if (!res.ok) throw new Error(`Failed to fetch events: ${res.status}`)
  return res.json()
}

export async function getInteractionStats(hours?: number): Promise<Record<string, any>> {
  const base = getApiBaseUrlInternal()
  const qs = hours ? `?hours=${hours}` : ''
  const res = await fetch(`${base}/api/copilot/learning/interaction-stats${qs}`)
  if (!res.ok) throw new Error(`Failed to fetch interaction stats: ${res.status}`)
  return res.json()
}

export async function triggerRetrain(): Promise<{ ok: boolean; message: string }> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/learning/retrain`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to trigger retrain: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Copilot — Episodic Memory (Sessions, Concepts, Patterns, Preferences)
// ---------------------------------------------------------------------------

export async function getCopilotSessions(args?: {
  thread_id?: string
  limit?: number
}): Promise<any[]> {
  const base = getApiBaseUrlInternal()
  const params = new URLSearchParams()
  if (args?.thread_id) params.set('thread_id', args.thread_id)
  if (args?.limit !== undefined) params.set('limit', String(args.limit))
  const qs = params.toString()
  const res = await fetch(`${base}/api/copilot/sessions${qs ? '?' + qs : ''}`)
  if (!res.ok) throw new Error(`Failed to fetch sessions: ${res.status}`)
  return res.json()
}

export async function searchSessions(topic: string, limit?: number): Promise<any[]> {
  const base = getApiBaseUrlInternal()
  const params = new URLSearchParams({ topic })
  if (limit) params.set('limit', String(limit))
  const res = await fetch(`${base}/api/copilot/sessions/search?${params}`)
  if (!res.ok) throw new Error(`Failed to search sessions: ${res.status}`)
  return res.json()
}

export async function getCopilotConcepts(conceptType?: string): Promise<any[]> {
  const base = getApiBaseUrlInternal()
  const qs = conceptType ? `?concept_type=${encodeURIComponent(conceptType)}` : ''
  const res = await fetch(`${base}/api/copilot/concepts${qs}`)
  if (!res.ok) throw new Error(`Failed to fetch concepts: ${res.status}`)
  return res.json()
}

export async function getCopilotPatterns(args?: {
  pattern_type?: string
  min_confidence?: number
}): Promise<any[]> {
  const base = getApiBaseUrlInternal()
  const params = new URLSearchParams()
  if (args?.pattern_type) params.set('pattern_type', args.pattern_type)
  if (args?.min_confidence !== undefined) params.set('min_confidence', String(args.min_confidence))
  const qs = params.toString()
  const res = await fetch(`${base}/api/copilot/patterns${qs ? '?' + qs : ''}`)
  if (!res.ok) throw new Error(`Failed to fetch patterns: ${res.status}`)
  return res.json()
}

export async function getCopilotPreferences(category?: string): Promise<any[]> {
  const base = getApiBaseUrlInternal()
  const qs = category ? `?category=${encodeURIComponent(category)}` : ''
  const res = await fetch(`${base}/api/copilot/preferences${qs}`)
  if (!res.ok) throw new Error(`Failed to fetch preferences: ${res.status}`)
  return res.json()
}

export async function getCopilotUserContext(includeSummaries?: number): Promise<Record<string, any>> {
  const base = getApiBaseUrlInternal()
  const qs = includeSummaries !== undefined ? `?include_summaries=${includeSummaries}` : ''
  const res = await fetch(`${base}/api/copilot/user-context${qs}`)
  if (!res.ok) throw new Error(`Failed to fetch user context: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Copilot — Training Data & Reflections
// ---------------------------------------------------------------------------

export async function getTrainingDataStats(): Promise<Record<string, any>> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/copilot/training-data/stats`)
  if (!res.ok) throw new Error(`Failed to fetch training stats: ${res.status}`)
  return res.json()
}

export async function exportTrainingData(format?: string): Promise<Record<string, any>> {
  const base = getApiBaseUrlInternal()
  const qs = format ? `?format=${format}` : ''
  const res = await fetch(`${base}/api/copilot/training-data/export${qs}`)
  if (!res.ok) throw new Error(`Failed to export training data: ${res.status}`)
  return res.json()
}

export async function getReflections(threadId: string, limit?: number): Promise<any[]> {
  const base = getApiBaseUrlInternal()
  const qs = limit ? `?limit=${limit}` : ''
  const res = await fetch(`${base}/api/copilot/reflections/${encodeURIComponent(threadId)}${qs}`)
  if (!res.ok) throw new Error(`Failed to fetch reflections: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Trust Delta — post-turn trust movements for TrustDeltaStrip
// ---------------------------------------------------------------------------

export type TrustDeltaItem = {
  memory_id: string
  old_trust: number
  new_trust: number
  delta: number
  timestamp: number
  reason: string
  text_preview: string
}

export async function getTrustDelta(args: {
  threadId: string
  sinceTs: number
  limit?: number
}): Promise<TrustDeltaItem[]> {
  const params = new URLSearchParams({
    thread_id: args.threadId,
    since_ts: String(args.sinceTs),
    limit: String(args.limit ?? 30),
  })
  return fetchJson<TrustDeltaItem[]>(`/api/memory/trust-delta?${params.toString()}`)
}

export async function submitChatFeedback(req: ChatFeedbackRequest): Promise<ChatFeedbackResponse> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/chat/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`Feedback submission failed: ${res.status}`)
  return res.json()
}

// ── Telemetry Dashboard ───────────────────────────────────────────────────

export type TelemetryEventCounts = Record<string, number>

export type TelemetryGatePerformance = {
  pass_count: number
  fail_count: number
  pass_rate: number | null
  fail_reasons: Record<string, number>
}

export type TelemetryFeedback = {
  thumbs_up: number
  thumbs_down: number
  thumbs_up_rate: number | null
  high_priority_count: number
}

export type TelemetryLearningQueue = {
  pending_reflections: number
  high_priority_feedback: number
}

export type TelemetryThreadMetricRow = {
  ts: number
  thread_id: string
  turn_number: number
  contradiction_rate: number | null
  gate_fail_rate: number | null
  trust_mean: number | null
  correction_recovery: number | null
  hallucination_leakage: number | null
  open_contradictions: number
}

export type TelemetryRecentEvent = {
  ts: number
  thread_id: string
  event_type: string
  severity: number
  payload: Record<string, unknown>
}

export type TelemetrySummary = {
  hours: number
  generated_at: number
  event_counts: TelemetryEventCounts
  event_rate_per_hour: TelemetryEventCounts
  severity_distribution: { low: number; medium: number; high: number }
  gate_performance: TelemetryGatePerformance
  feedback: TelemetryFeedback
  learning_queue: TelemetryLearningQueue
  thread_metrics_trend: TelemetryThreadMetricRow[]
  recent_events: TelemetryRecentEvent[]
  error?: string
}

export async function getTelemetrySummary(args?: {
  hours?: number
  threadId?: string
}): Promise<TelemetrySummary> {
  const params = new URLSearchParams()
  if (args?.hours != null) params.set('hours', String(args.hours))
  if (args?.threadId) params.set('thread_id', args.threadId)
  const qs = params.toString()
  return fetchJson<TelemetrySummary>(`/api/telemetry/summary${qs ? '?' + qs : ''}`)
}

export type PersonalityCheckpoint = {
  id: number
  ts: number
  period_days: number
  snapshot: Record<string, string | null>
  delta: Record<string, string> | null
  notable_events: string[]
}

export async function getPersonalityTimeline(limit = 20): Promise<PersonalityCheckpoint[]> {
  return fetchJson<PersonalityCheckpoint[]>(`/api/reflection/personality-timeline?limit=${limit}`)
}

export type SelfModelAwareness = Record<string, string | null>  // slot -> value

export async function getSelfModelState(threadId: string): Promise<{
  self_model_awareness: SelfModelAwareness
  traits: Record<string, unknown>
  mood: Record<string, unknown>
  adaptation: Record<string, unknown>
}> {
  return fetchJson(`/api/self-model/${encodeURIComponent(threadId)}`)
}

export type EpistemicEvent = {
  id: number
  ts: number
  interaction_id: string | null
  event_type: string
  label: string
  severity: number
  memory_ids: string[]
  payload: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Cloud Settings
// ---------------------------------------------------------------------------

export type CloudSettings = {
  cloud_slot_classification: string
  cloud_nli_contradiction: string
  cloud_reflection_validation: string
  cloud_escalation_policy: string
  cloud_confidence_threshold: string
  cloud_daily_limit_multiplier: string
  // Claude (Tier 2/3) settings
  cloud_claude_enabled: string
  cloud_claude_generation: string
  cloud_claude_reflection: string
  cloud_claude_daily_limit: string
  cloud_claude_max_tokens: string
  // Advanced settings
  bypass_crt: string
  enable_tooling: string
  [key: string]: string
}

export type CloudUsage = {
  slot_classification?: { calls: number; est_tokens: number }
  nli_contradiction?: { calls: number; est_tokens: number }
  reflection_validation?: { calls: number; est_tokens: number }
  claude_generation?: { calls: number; est_tokens: number }
  claude_reflection?: { calls: number; est_tokens: number }
  total_cost_est?: number
  daily_limits?: Record<string, { used: number; limit: number }>
  // Claude-specific aggregate metrics
  claude_calls_today?: number
  claude_daily_limit?: number
  claude_tokens_today?: number
  claude_available?: boolean
}

export async function getCloudSettings(): Promise<CloudSettings> {
  const base = getApiBaseUrlInternal()
  const token = getAuthToken()
  const res = await fetch(`${base}/api/auth/settings`, {
    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error(`Failed to load settings: ${res.statusText}`)
  const data = await res.json()
  return data.settings as CloudSettings
}

export async function updateCloudSettings(settings: Partial<CloudSettings>): Promise<Record<string, string>> {
  const base = getApiBaseUrlInternal()
  const token = getAuthToken()
  const res = await fetch(`${base}/api/auth/settings`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(settings),
  })
  if (!res.ok) throw new Error(`Failed to update settings: ${res.statusText}`)
  const data = await res.json()
  return data.updated
}

export interface AvailableModels {
  local: Array<{ name: string; size?: string }>
  cloud: Array<{ name: string; label: string }>
  anthropic: Array<{ name: string; label: string }>
}

export async function getAvailableModels(): Promise<AvailableModels> {
  const base = getApiBaseUrlInternal()
  const token = getAuthToken()
  const res = await fetch(`${base}/api/tooling/models`, {
    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error(`Failed to load models: ${res.statusText}`)
  return await res.json()
}

export async function getCloudUsage(): Promise<CloudUsage> {
  const base = getApiBaseUrlInternal()
  const token = getAuthToken()
  const res = await fetch(`${base}/api/auth/cloud-usage`, {
    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error(`Failed to load cloud usage: ${res.statusText}`)
  const data = await res.json()
  return data.usage as CloudUsage
}

// ---------------------------------------------------------------------------

export type EpistemicTimeline = {
  thread_id: string
  total: number
  offset: number
  limit: number
  events: EpistemicEvent[]
}

export async function getEpistemicTimeline(
  threadId: string,
  opts?: { limit?: number; offset?: number; eventType?: string }
): Promise<EpistemicTimeline> {
  const params = new URLSearchParams()
  if (opts?.limit != null) params.set('limit', String(opts.limit))
  if (opts?.offset != null) params.set('offset', String(opts.offset))
  if (opts?.eventType) params.set('event_type', opts.eventType)
  const qs = params.toString()
  return fetchJson<EpistemicTimeline>(
    `/api/thread/${encodeURIComponent(threadId)}/epistemic-timeline${qs ? '?' + qs : ''}`
  )
}

// ── Live log stream ─────────────────────────────────────────
export interface LogEntry {
  ts: number
  level: string
  logger: string
  msg: string
  type?: string // keepalive
}

export function streamLogs(opts?: {
  level?: string
  onEntry: (entry: LogEntry) => void
  onError?: (err: Error) => void
}): AbortController {
  const ctrl = new AbortController()
  const base = getEffectiveApiBaseUrl()
  const level = opts?.level ?? 'INFO'
  const url = `${base}/api/logs/stream?level=${encodeURIComponent(level)}`

  ;(async () => {
    try {
      const headers: Record<string, string> = { Accept: 'text/event-stream' }
      const token = getAuthToken()
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch(url, { signal: ctrl.signal, headers })
      if (!res.ok || !res.body) throw new Error(`Log stream failed: ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const entry: LogEntry = JSON.parse(line.slice(6))
            if (entry.type === 'keepalive') continue
            opts?.onEntry(entry)
          } catch { /* skip malformed */ }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') opts?.onError?.(err)
    }
  })()

  return ctrl
}

// ---------------------------------------------------------------------------
// Plans API (v2.9.2)
// ---------------------------------------------------------------------------

export type PlanStep = {
  id: string
  plan_id: string
  step_number: number
  title: string
  description?: string | null
  status: string
  tool_name?: string | null
  input_json?: string | null
  output_json?: string | null
  needs_user_input?: string | null
  user_input?: string | null
  started_at?: number | null
  completed_at?: number | null
}

export type Plan = {
  id: string
  title: string
  description?: string | null
  status: string
  created_by: string
  created_at: number
  updated_at: number
  completed_at?: number | null
  metadata?: Record<string, unknown> | null
  steps: PlanStep[]
  current_step_id?: string | null
  thread_id?: string | null
}

export async function listPlans(status?: string): Promise<Plan[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : ''
  return fetchJson<Plan[]>(`/api/plans${qs}`)
}

export async function createPlan(args: {
  title: string
  description?: string
  steps?: Array<{ title: string; description?: string; tool_name?: string; needs_user_input?: string }>
}): Promise<Plan> {
  return postJson<Plan>('/api/plans', args)
}

export async function getPlan(planId: string): Promise<Plan> {
  return fetchJson<Plan>(`/api/plans/${encodeURIComponent(planId)}`)
}

export async function updatePlan(planId: string, fields: {
  title?: string; description?: string; status?: string
}): Promise<Plan> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/plans/${encodeURIComponent(planId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  })
  if (!res.ok) throw new Error(`Failed to update plan: ${res.status}`)
  return res.json()
}

export async function deletePlan(planId: string): Promise<{ ok: boolean }> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/plans/${encodeURIComponent(planId)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Failed to delete plan: ${res.status}`)
  return res.json()
}

export async function addPlanStep(planId: string, step: {
  title: string; description?: string; tool_name?: string
}): Promise<PlanStep> {
  return postJson<PlanStep>(`/api/plans/${encodeURIComponent(planId)}/steps`, step)
}

export async function updatePlanStep(planId: string, stepId: string, fields: {
  title?: string; description?: string; status?: string; user_input?: string
}): Promise<Plan> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(
    `${base}/api/plans/${encodeURIComponent(planId)}/steps/${encodeURIComponent(stepId)}`,
    { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(fields) },
  )
  if (!res.ok) throw new Error(`Failed to update step: ${res.status}`)
  return res.json()
}

export async function deletePlanStep(planId: string, stepId: string): Promise<{ ok: boolean }> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(
    `${base}/api/plans/${encodeURIComponent(planId)}/steps/${encodeURIComponent(stepId)}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error(`Failed to delete step: ${res.status}`)
  return res.json()
}

export async function reorderPlanSteps(planId: string, stepIds: string[]): Promise<Plan> {
  return postJson<Plan>(`/api/plans/${encodeURIComponent(planId)}/reorder`, { step_ids: stepIds })
}

export async function linkPlanToThread(planId: string, threadId: string): Promise<{ ok: boolean }> {
  return postJson<{ ok: boolean }>(
    `/api/plans/${encodeURIComponent(planId)}/link/${encodeURIComponent(threadId)}`,
    {},
  )
}

export async function unlinkPlanFromThread(planId: string, threadId: string): Promise<{ ok: boolean }> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(
    `${base}/api/plans/${encodeURIComponent(planId)}/link/${encodeURIComponent(threadId)}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error(`Failed to unlink plan: ${res.status}`)
  return res.json()
}

export async function getThreadPlan(threadId: string): Promise<Plan | null> {
  const base = getApiBaseUrlInternal()
  const res = await fetch(`${base}/api/plans/thread/${encodeURIComponent(threadId)}`)
  if (!res.ok) return null
  const data = await res.json()
  return data || null
}
