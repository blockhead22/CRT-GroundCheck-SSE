import type { ChatMessage, ChatThread } from '../types'

const STORAGE_KEY = 'crt_recent_chats_v1'

type PersistedStateV1 = {
  version: 1
  savedAt: number
  selectedThreadId: string | null
  threads: ChatThread[]
}

function safeJsonParse<T>(raw: string | null): T | null {
  if (!raw) return null
  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

function isValidThread(t: unknown): t is ChatThread {
  if (!t || typeof t !== 'object') return false
  const anyT = t as Record<string, unknown>
  return (
    typeof anyT.id === 'string' &&
    typeof anyT.title === 'string' &&
    typeof anyT.updatedAt === 'number' &&
    Array.isArray(anyT.messages)
  )
}

function compactMessage(m: ChatMessage): ChatMessage {
  if (!m.crt) return m
  const crt = {
    response_type: m.crt.response_type,
    gates_passed: m.crt.gates_passed,
    gate_reason: m.crt.gate_reason ?? null,
    session_id: m.crt.session_id ?? null,
    confidence: m.crt.confidence ?? null,
    intent_alignment: m.crt.intent_alignment ?? null,
    memory_alignment: m.crt.memory_alignment ?? null,
    contradiction_detected: m.crt.contradiction_detected ?? null,
    unresolved_contradictions_total: m.crt.unresolved_contradictions_total ?? null,
    unresolved_hard_conflicts: m.crt.unresolved_hard_conflicts ?? null,
    retrieved_memories: (m.crt.retrieved_memories ?? []).slice(0, 12),
    prompt_memories: (m.crt.prompt_memories ?? []).slice(0, 12),
    profile_updates: (m.crt.profile_updates ?? []).slice(0, 12),
    tasking: m.crt.tasking
      ? {
          mode: m.crt.tasking.mode,
          passes: m.crt.tasking.passes,
          skipped: m.crt.tasking.skipped,
          interval_seconds: m.crt.tasking.interval_seconds,
          plan: m.crt.tasking.plan
            ? {
                notes: m.crt.tasking.plan.notes ?? null,
                tasks: (m.crt.tasking.plan.tasks ?? []).slice(0, 8).map((t) => ({
                  task_id: t.task_id,
                  goal: t.goal,
                  acceptance_criteria: t.acceptance_criteria,
                  status: t.status,
                  summary: t.summary ?? null,
                })),
              }
            : null,
          coverage: m.crt.tasking.coverage
            ? {
                score: m.crt.tasking.coverage.score,
                missing_items: (m.crt.tasking.coverage.missing_items ?? []).slice(0, 8),
                notes: m.crt.tasking.coverage.notes ?? null,
              }
            : null,
        }
      : null,
    // Persist trace_id for lazy-loading thinking after refresh (drop full content to save space)
    thinking_trace_id: m.crt.thinking_trace_id ?? null,
    // Persist reflection trace ID and confidence for lazy-loading
    reflection_trace_id: m.crt.reflection_trace_id ?? null,
    reflection_confidence: m.crt.reflection_confidence ?? null,
    reflection_label: m.crt.reflection_label ?? null,
  }
  return { ...m, crt }
}

function compactThread(t: ChatThread): ChatThread {
  const maxMessages = 250
  const messages = t.messages.slice(-maxMessages).map(compactMessage)
  return { ...t, messages }
}

export function loadChatStateFromStorage(): {
  threads: ChatThread[]
  selectedThreadId: string | null
} {
  if (typeof window === 'undefined') return { threads: [], selectedThreadId: null }
  const parsed = safeJsonParse<PersistedStateV1>(window.localStorage.getItem(STORAGE_KEY))
  if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.threads)) return { threads: [], selectedThreadId: null }

  const threads = parsed.threads.filter(isValidThread)
  threads.sort((a, b) => b.updatedAt - a.updatedAt)
  return { threads, selectedThreadId: typeof parsed.selectedThreadId === 'string' ? parsed.selectedThreadId : null }
}

export function saveChatStateToStorage(args: { threads: ChatThread[]; selectedThreadId: string | null }) {
  if (typeof window === 'undefined') return
  const maxThreads = 40
  const threads = [...args.threads]
  threads.sort((a, b) => b.updatedAt - a.updatedAt)

  const compacted = threads.slice(0, maxThreads).map(compactThread)

  const payload: PersistedStateV1 = {
    version: 1,
    savedAt: Date.now(),
    selectedThreadId: args.selectedThreadId,
    threads: compacted,
  }

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // Ignore quota errors.
  }
}

export function clearChatStateStorage() {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(STORAGE_KEY)
}
