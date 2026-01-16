import type { ChatMessage } from '../types'

export type ChatSendRequest = {
  thread_id: string
  message: string
  user_marked_important?: boolean
  mode?: string | null
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
  }
}

function getApiBaseUrlInternal(): string {
  const fromEnv = import.meta.env.VITE_API_BASE_URL
  const fromStorage = typeof window !== 'undefined' ? window.localStorage.getItem('crt_api_base_url') : null
  // Default behavior:
  // - Dev: same-origin (works with Vite proxy for /api and /health)
  // - Prod: explicit loopback (for the common “API on :8123” setup)
  const fallback = import.meta.env.DEV ? '' : 'http://127.0.0.1:8123'
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
    res = await fetch(`${base}/api/chat/send`, {
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

  return (await res.json()) as ChatSendResponse
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

export type DocListItem = { id: string; title: string; kind: string }
export type DocGetResponse = { id: string; title: string; kind: string; markdown: string }

export async function listDocs(): Promise<DocListItem[]> {
  return fetchJson<DocListItem[]>('/api/docs')
}

export async function getDoc(docId: string): Promise<DocGetResponse> {
  return fetchJson<DocGetResponse>(`/api/docs/${encodeURIComponent(docId)}`)
}

export type DashboardOverview = {
  thread_id: string
  session_id?: string | null
  memories_total: number
  open_contradictions: number
  belief_ratio: number
  speech_ratio: number
  belief_count: number
  speech_count: number
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

export type TrustHistoryRow = Record<string, unknown>

export async function getMemoryTrustHistory(threadId: string, memoryId: string): Promise<TrustHistoryRow[]> {
  return fetchJson<TrustHistoryRow[]>(
    `/api/memory/${encodeURIComponent(memoryId)}/trust?thread_id=${encodeURIComponent(threadId)}`,
  )
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

