export const STREAM_EVENT_TYPES = [
  'status',
  'intent_preview',
  'intent_classified',
  'plan_ready',
  'tool_start',
  'tool_result',
  'validate_result',
  'task_done',
  'task_acknowledged',
  'orchestration_start',
  'subtask_start',
  'subtask_done',
  'orchestration_done',
  'agent_checkpoint',
  'task_cancelled',
  'agent_thinking_token',
  'thinking_start',
  'thinking_token',
  'thinking',
  'thinking_end',
  'phase_start',
  'phase_end',
  'token',
  'correction',
  'stream_checkpoint',
  'stream_stopped',
  'plan_proposal',
  'plan_update',
  'plan_complete',
  'agent_loop_start',
  'agent_loop_complete',
  'retrieval',
  'trust_shift',
  'verification',
  'epistemic_event',
  'drift',
  'session_state',
  'followup_suggest',
  'done',
  'error',
] as const

export type StreamEventType = typeof STREAM_EVENT_TYPES[number]

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
  onIntentClassified?: (intent: string, route: string, slots: Record<string, unknown>, confidence: number, source?: string) => void
  onPlanReady?: (steps: Array<{ tool: string; input: Record<string, unknown> }>) => void
  onToolStart?: (toolName: string, input: Record<string, unknown>, stepIndex: number) => void
  onToolResult?: (step: AgentStep) => void
  onValidateResult?: (conflicts: unknown[], gate: string) => void
  onTaskDone?: (answer: string, steps: AgentStep[], metadata: Record<string, unknown>) => void
  onTaskAcknowledged?: (message: string, metadata: Record<string, unknown>) => void
  onOrchestrationStart?: (subtaskCount: number, subtasks: Array<{ task_id: string; intent_type: string; agent_name: string; depends_on: string[] }>) => void
  onSubtaskStart?: (taskId: string, agentName: string, intentType: string) => void
  onSubtaskDone?: (taskId: string, agentName: string, status: string, durationMs: number, outputPreview: string) => void
  onOrchestrationDone?: (mergedTrust: number, allOk: boolean, metadata: Record<string, unknown>) => void
  onAgentCheckpoint?: (message: string, metadata: Record<string, unknown>) => void
  onTaskCancelled?: (message: string) => void
  onAgentThinkingToken?: (token: string, step: string) => void
  onAgentLoopStart?: (toolsAvailable: string[], maxIterations: number) => void
  onAgentLoopComplete?: (toolsUsed: string[], iterations: number, totalDurationMs: number) => void
  onThinkingStart?: () => void
  onThinkingToken?: (token: string) => void
  onThinking?: (fullThinking: string) => void
  onThinkingEnd?: () => void
  onRetrieval?: (memories: Array<{ id: string; text: string; trust: number; kind?: string; pca_x?: number; pca_y?: number; score?: number }>, edges?: Array<{ from: string; to: string; sim: number }>) => void
  onTrustShift?: (shift: { memoryId: string; from: number; to: number; reason: string; text: string }) => void
  onVerification?: (result: { verdict: string; confidence: number }) => void
  onEpistemicEvent?: (eventType: 'drift' | 'contradiction', content: string, data: Record<string, unknown>) => void
  onDrift?: (driftCount: number, totalTrustDelta: number, intentAlignment: number) => void
  onSessionState?: (density: number, contradictions: number, turnCount: number) => void
  onFollowupSuggest?: (followups: string[], complete: boolean) => void
  onPhaseStart?: (phase: string, content?: string) => void
  onPhaseEnd?: (phase: string) => void
  onToken?: (token: string) => void
  onCorrection?: (content: string) => void
  onStreamCheckpoint?: (content: string, metadata?: Record<string, unknown>) => void
  onStreamStopped?: (content: string, metadata?: Record<string, unknown>) => void
  onDone?: (content: string, metadata?: Record<string, unknown>) => void
  onError?: (error: string) => void
}

const STREAM_EVENT_TYPE_SET = new Set<string>(STREAM_EVENT_TYPES)

export function isStreamEventType(value: string): value is StreamEventType {
  return STREAM_EVENT_TYPE_SET.has(value)
}

export function dispatchStreamEvent(event: StreamEvent, callbacks: StreamCallbacks): void {
  switch (event.type) {
    case 'status':
      callbacks.onStatus?.(event.content)
      break
    case 'intent_preview': {
      const meta = event.metadata as { intent?: string; slots?: string[] } | undefined
      callbacks.onIntentPreview?.(meta?.intent ?? '', meta?.slots ?? [], event.content)
      break
    }
    case 'intent_classified': {
      const meta = event.metadata as { intent?: string; route?: string; slots?: Record<string, unknown>; confidence?: number; source?: string } | undefined
      callbacks.onIntentClassified?.(meta?.intent ?? '', meta?.route ?? 'conversational', meta?.slots ?? {}, meta?.confidence ?? 0, meta?.source)
      break
    }
    case 'plan_ready': {
      const meta = event.metadata as { steps?: Array<{ tool: string; input: Record<string, unknown> }> } | undefined
      callbacks.onPlanReady?.(meta?.steps ?? [])
      break
    }
    case 'tool_start': {
      const meta = event.metadata as { tool_name?: string; input?: Record<string, unknown>; step_index?: number } | undefined
      callbacks.onToolStart?.(meta?.tool_name ?? '', meta?.input ?? {}, meta?.step_index ?? 0)
      break
    }
    case 'tool_result': {
      const meta = event.metadata as AgentStep | undefined
      if (meta) callbacks.onToolResult?.(meta)
      break
    }
    case 'validate_result': {
      const meta = event.metadata as { conflicts?: unknown[]; gate?: string } | undefined
      callbacks.onValidateResult?.(meta?.conflicts ?? [], meta?.gate ?? '')
      break
    }
    case 'task_done': {
      const meta = event.metadata as { steps?: AgentStep[] } & Record<string, unknown> | undefined
      callbacks.onTaskDone?.(event.content, meta?.steps ?? [], meta ?? {})
      break
    }
    case 'task_acknowledged': {
      const meta = event.metadata as Record<string, unknown> | undefined
      callbacks.onTaskAcknowledged?.(event.content, meta ?? {})
      break
    }
    case 'orchestration_start': {
      const meta = event.metadata as { subtask_count?: number; subtasks?: Array<{ task_id: string; intent_type: string; agent_name: string; depends_on: string[] }> } | undefined
      callbacks.onOrchestrationStart?.(meta?.subtask_count ?? 0, meta?.subtasks ?? [])
      break
    }
    case 'subtask_start': {
      const meta = event.metadata as { task_id?: string; agent_name?: string; intent_type?: string } | undefined
      callbacks.onSubtaskStart?.(meta?.task_id ?? '', meta?.agent_name ?? '', meta?.intent_type ?? '')
      break
    }
    case 'subtask_done': {
      const meta = event.metadata as { task_id?: string; agent_name?: string; status?: string; duration_ms?: number; output_preview?: string } | undefined
      callbacks.onSubtaskDone?.(meta?.task_id ?? '', meta?.agent_name ?? '', meta?.status ?? 'ok', meta?.duration_ms ?? 0, meta?.output_preview ?? '')
      break
    }
    case 'orchestration_done': {
      const meta = event.metadata as { merged_trust?: number; all_ok?: boolean } & Record<string, unknown> | undefined
      callbacks.onOrchestrationDone?.(meta?.merged_trust ?? 0, meta?.all_ok ?? false, meta ?? {})
      break
    }
    case 'agent_checkpoint':
      callbacks.onAgentCheckpoint?.(event.content, (event.metadata as Record<string, unknown> | undefined) ?? {})
      break
    case 'task_cancelled':
      callbacks.onTaskCancelled?.(event.content)
      break
    case 'agent_thinking_token': {
      const meta = event.metadata as { step?: string; alignment?: number } | undefined
      callbacks.onAgentThinkingToken?.(event.content, meta?.step ?? 'generate_answer')
      if (meta?.alignment != null && meta.alignment < 0.3) {
        callbacks.onEpistemicEvent?.('drift', event.content.slice(0, 80), { alignment: meta.alignment })
      }
      break
    }
    case 'agent_loop_start': {
      const meta = event.metadata as { tools_available?: string[]; max_iterations?: number } | undefined
      callbacks.onAgentLoopStart?.(meta?.tools_available ?? [], meta?.max_iterations ?? 10)
      break
    }
    case 'agent_loop_complete': {
      const meta = event.metadata as { tools_used?: string[]; iterations?: number; total_duration_ms?: number } | undefined
      callbacks.onAgentLoopComplete?.(meta?.tools_used ?? [], meta?.iterations ?? 0, meta?.total_duration_ms ?? 0)
      break
    }
    case 'thinking_start':
      callbacks.onThinkingStart?.()
      break
    case 'thinking_token':
      callbacks.onThinkingToken?.(event.content)
      break
    case 'thinking':
      callbacks.onThinking?.(event.content)
      break
    case 'thinking_end':
      callbacks.onThinkingEnd?.()
      break
    case 'retrieval': {
      const meta = event.metadata as {
        memories?: Array<{ id: string; text: string; trust: number; kind?: string; pca_x?: number; pca_y?: number; score?: number }>
        edges?: Array<{ from: string; to: string; sim: number }>
      } | undefined
      callbacks.onRetrieval?.(meta?.memories ?? [], meta?.edges)
      break
    }
    case 'trust_shift': {
      const meta = event.metadata as { memoryId?: string; from?: number; to?: number; reason?: string; text?: string } | undefined
      if (meta?.memoryId) {
        callbacks.onTrustShift?.({
          memoryId: meta.memoryId,
          from: meta.from ?? 0,
          to: meta.to ?? 0,
          reason: meta.reason ?? '',
          text: meta.text ?? '',
        })
      }
      break
    }
    case 'verification': {
      const meta = event.metadata as { verdict?: string; confidence?: number } | undefined
      callbacks.onVerification?.({ verdict: meta?.verdict ?? 'none', confidence: meta?.confidence ?? 0 })
      break
    }
    case 'epistemic_event': {
      const meta = event.metadata as { event?: string } & Record<string, unknown> | undefined
      const eventType = (meta?.event ?? 'drift') as 'drift' | 'contradiction'
      callbacks.onEpistemicEvent?.(eventType, event.content, meta ?? {})
      break
    }
    case 'drift': {
      const meta = event.metadata as { drift_count?: number; total_trust_delta?: number; intent_alignment?: number } | undefined
      callbacks.onDrift?.(meta?.drift_count ?? 0, meta?.total_trust_delta ?? 0, meta?.intent_alignment ?? 1)
      break
    }
    case 'session_state': {
      const meta = event.metadata as { cumulative_density?: number; open_contradiction_count?: number; turn_count?: number } | undefined
      callbacks.onSessionState?.(meta?.cumulative_density ?? 0, meta?.open_contradiction_count ?? 0, meta?.turn_count ?? 0)
      break
    }
    case 'followup_suggest': {
      const meta = event.metadata as { followups?: string[]; complete?: boolean } | undefined
      callbacks.onFollowupSuggest?.(meta?.followups ?? [], meta?.complete ?? true)
      break
    }
    case 'phase_start':
      callbacks.onPhaseStart?.(event.phase ?? '', event.content)
      break
    case 'phase_end':
      callbacks.onPhaseEnd?.(event.phase ?? '')
      break
    case 'token':
      callbacks.onToken?.(event.content)
      break
    case 'correction':
      callbacks.onCorrection?.(event.content)
      break
    case 'stream_checkpoint':
      callbacks.onStreamCheckpoint?.(event.content, event.metadata)
      callbacks.onStatus?.(`□ ${event.content}`)
      break
    case 'stream_stopped':
      callbacks.onStreamStopped?.(event.content, event.metadata)
      callbacks.onStatus?.(`⚡ ${event.content}`)
      break
    case 'done':
      callbacks.onDone?.(event.content, event.metadata)
      break
    case 'error':
      callbacks.onError?.(event.content)
      break
    case 'plan_proposal':
    case 'plan_update':
    case 'plan_complete':
      break
  }
}
