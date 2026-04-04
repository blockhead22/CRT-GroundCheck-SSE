import { useState, useRef, useEffect, useCallback } from 'react'
import type { ChatThread, QuickAction } from '../types'
import type { AgentThinkingState } from '../components/chat/AgentThinkingStrip'
import type { MoodData } from '../components/MoodBackground'
import { sendToCrtApi, streamFromCrtApi, searchResearch } from '../lib/api'
import { newId } from '../lib/id'

type UseChatStreamOpts = {
  selectedThread: ChatThread | undefined
  upsertThread: (t: ChatThread) => void
}

export function useChatStream({ selectedThread, upsertThread }: UseChatStreamOpts) {
  // Streaming state
  const [streamingThinking, setStreamingThinking] = useState<string>('')
  const [streamingResponse, setStreamingResponse] = useState<string>('')
  const [isThinking, setIsThinking] = useState(false)
  const [useStreaming, setUseStreaming] = useState(true)
  const phaseMode = true
  const [streamPhase, setStreamPhase] = useState<string | null>(null)
  const [streamStatusLog, setStreamStatusLog] = useState<string[]>([])
  const streamStatusRef = useRef<string[]>([])
  const [intentPreview, setIntentPreview] = useState<{ intent: string; slots: string[]; label: string } | null>(null)
  const [agentThinkingState, setAgentThinkingState] = useState<AgentThinkingState | null>(null)
  const agentThinkingRef = useRef<AgentThinkingState | null>(null)
  const finalBufferRef = useRef('')

  const [typing, setTyping] = useState(false)
  const [researching, setResearching] = useState(false)
  const [currentMood, setCurrentMood] = useState<MoodData | null>(null)

  // Clear agent strip when selectedThread changes (thread identity)
  const threadId = selectedThread?.id
  useEffect(() => {
    setAgentThinkingState(null)
    agentThinkingRef.current = null
  }, [threadId])

  // Set mood to "curious" while AI is thinking
  useEffect(() => {
    if (isThinking) {
      setCurrentMood({
        mood: 'curious',
        intensity: 0.7,
        thinking_depth: 0.8,
        triggers: ['processing', 'thinking']
      })
    }
  }, [isThinking])

  function resetStreamState() {
    setStreamingThinking('')
    setStreamingResponse('')
    setIsThinking(false)
    setStreamPhase(null)
    setStreamStatusLog([])
    streamStatusRef.current = []
    finalBufferRef.current = ''
    setIntentPreview(null)
    setAgentThinkingState(null)
    agentThinkingRef.current = null
  }

  const handleSend = useCallback(async (text: string) => {
    if (!selectedThread) return

    const raw = text
    const trimmed = raw.trim()
    const expandTriggers = [
      'explain more', 'expand', 'expand more', 'tell me more',
      'go deeper', 'continue', 'more detail', 'more details', 'elaborate',
    ]
    const wantsExpand = expandTriggers.some((t) => trimmed.toLowerCase() === t || trimmed.toLowerCase().startsWith(t + ' '))

    const lastAssistant = [...selectedThread.messages].reverse().find((m) => m.role === 'assistant')
    const outgoingText = wantsExpand && lastAssistant?.text
      ? [
          'Expand on your previous answer with more depth and concrete detail.',
          'Requirements:',
          '- Do not repeat the original text verbatim.',
          '- Add examples and a step-by-step breakdown when applicable.',
          '- If you are uncertain about internal mechanisms, say so explicitly.',
          '',
          'Previous answer:',
          lastAssistant.text,
          '',
          `User request: ${raw}`,
        ].join('\n')
      : raw

    const now = Date.now()
    const userMsg = { id: newId('m'), role: 'user' as const, text: raw, createdAt: now }

    const shouldAutoTitle = !selectedThread.title || selectedThread.title === 'New chat'
    const autoTitle = shouldAutoTitle
      ? raw.trim().replace(/^FACT:\s*/i, '').replace(/^PREF:\s*/i, '').slice(0, 48) || 'New chat'
      : selectedThread.title

    const withUser: ChatThread = {
      ...selectedThread,
      title: autoTitle,
      updatedAt: now,
      messages: [...selectedThread.messages, userMsg],
    }

    upsertThread(withUser)
    setTyping(true)
    resetStreamState()

    try {
      if (useStreaming) {
        let thinkingContent = ''

        await streamFromCrtApi({
          threadId: withUser.id,
          message: outgoingText,
          phaseMode,
          callbacks: {
            onIntentPreview: (intent, slots, label) => {
              setIntentPreview({ intent, slots, label })
            },
            onIntentClassified: (intent, route, slots, confidence) => {
              const next = { intent, route, slots, confidence, toolSteps: [] }
              agentThinkingRef.current = next
              setAgentThinkingState(next)
            },
            onPlanReady: (steps) => {
              setAgentThinkingState((prev) => {
                const next = prev ? { ...prev, plan: steps } : { toolSteps: [], plan: steps }
                agentThinkingRef.current = next
                return next
              })
            },
            onToolStart: (toolName, input, stepIndex) => {
              setAgentThinkingState((prev) => {
                if (!prev) return prev
                const existing = prev.toolSteps.find(s => s.step_index === stepIndex)
                const updated = existing
                  ? prev.toolSteps.map(s => s.step_index === stepIndex ? { ...s, status: 'running' as const } : s)
                  : [...prev.toolSteps, { step_index: stepIndex, tool_name: toolName, input, status: 'running' as const }]
                const next = { ...prev, toolSteps: updated, activeStepIndex: stepIndex }
                agentThinkingRef.current = next
                return next
              })
            },
            onToolResult: (step) => {
              setAgentThinkingState((prev) => {
                if (!prev) return prev
                const exists = prev.toolSteps.find(s => s.step_index === step.step_index)
                const updated = exists
                  ? prev.toolSteps.map(s => s.step_index === step.step_index ? { ...s, ...step } : s)
                  : [...prev.toolSteps, step]
                const next = { ...prev, toolSteps: updated, activeStepIndex: undefined }
                agentThinkingRef.current = next
                return next
              })
            },
            onValidateResult: (_conflicts, _gate) => {
              setAgentThinkingState((prev) => {
                const next = prev ? { ...prev, validated: true } : prev
                agentThinkingRef.current = next
                return next
              })
            },
            onTaskDone: (_answer, _steps, _meta) => {
              setAgentThinkingState((prev) => {
                const next = prev ? { ...prev, drafting: true } : prev
                agentThinkingRef.current = next
                return next
              })
            },
            onAgentCheckpoint: (message, _metadata) => {
              setStreamingResponse(message)
            },
            onTaskCancelled: (message) => {
              setStreamingResponse(message)
            },
            onAgentThinkingToken: (token, _step) => {
              setAgentThinkingState((prev) => {
                if (!prev) return prev
                const next = { ...prev, draftingThinking: (prev.draftingThinking ?? '') + token }
                agentThinkingRef.current = next
                return next
              })
            },
            onStatus: (status) => {
              if (!status) return
              setStreamStatusLog((prev) => {
                if (prev.length && prev[prev.length - 1] === status) return prev
                const next = [...prev, status]
                const trimmed = next.slice(-8)
                streamStatusRef.current = trimmed
                return trimmed
              })
            },
            onThinkingStart: () => {
              setIsThinking(true)
            },
            onThinkingToken: (token) => {
              thinkingContent += token
              setStreamingThinking(thinkingContent)
            },
            onThinkingEnd: () => {
              setIsThinking(false)
            },
            onPhaseStart: (phase) => {
              setStreamPhase(phase)
            },
            onPhaseEnd: (phase) => {
              if (phase === 'plan') {
                setStreamPhase(phase)
              }
            },
            onCorrection: (content) => {
              const correctionBlock = `\n\n---\n*${content}*`
              finalBufferRef.current += correctionBlock
              setStreamingResponse(finalBufferRef.current)
            },
            onToken: (token) => {
              finalBufferRef.current += token
              setStreamingResponse(finalBufferRef.current)
            },
            onDone: (content, metadata) => {
              const at = Date.now()
              const finalThinking = (metadata?.thinking as string) || thinkingContent || undefined
              const draft = (finalBufferRef.current || '').trim()
              const draftResponse = draft && draft !== content ? draft : null
              const profileUpdates = Array.isArray((metadata as any)?.profile_updates)
                ? ((metadata as any).profile_updates as any[])
                : []
              const pipelineStatuses = streamStatusRef.current

              if (metadata?.mood) {
                setCurrentMood(metadata.mood as MoodData)
              }

              const _capturedThinking = agentThinkingRef.current
                ? { ...agentThinkingRef.current, done: true, drafting: false }
                : null

              const asstMsg = {
                id: newId('m'),
                role: 'assistant' as const,
                text: content,
                createdAt: at,
                agentThinking: _capturedThinking,
                crt: {
                  response_type: (metadata?.response_type as string) || 'speech',
                  gates_passed: (metadata?.gates_passed as boolean) ?? true,
                  gate_reason: (metadata?.gate_reason as string) || null,
                  session_id: (metadata?.session_id as string) || null,
                  interaction_id: (metadata?.interaction_id as string) || null,
                  confidence: (metadata?.confidence as number) ?? null,
                  intent_alignment: (metadata?.intent_alignment as number) ?? null,
                  memory_alignment: (metadata?.memory_alignment as number) ?? null,
                  contradiction_detected: (metadata?.contradiction_detected as boolean) ?? null,
                  unresolved_contradictions_total: (metadata?.unresolved_contradictions_total as number) ?? null,
                  unresolved_hard_conflicts: (metadata?.unresolved_hard_conflicts as number) ?? null,
                  retrieved_memories: (metadata?.retrieved_memories as any[]) || [],
                  prompt_memories: (metadata?.prompt_memories as any[]) || [],
                  learned_suggestions: [],
                  heuristic_suggestions: [],
                  profile_updates: profileUpdates,
                  pipeline_statuses: pipelineStatuses,
                  draft_response: draftResponse,
                  tasking: (metadata as any)?.tasking ?? null,
                  tool_calls: (metadata as any)?.tool_calls ?? null,
                  agent_activated: null,
                  agent_answer: null,
                  agent_trace: null,
                  xray: null,
                  thinking: finalThinking,
                  thinking_trace_id: (metadata?.thinking_trace_id as string) || null,
                  reflection_trace_id: (metadata?.reflection_trace_id as string) || null,
                  reflection_confidence: (metadata?.reflection_confidence as number) ?? null,
                  reflection_label: (metadata?.reflection_label as string) || null,
                  personality_profile: (metadata as any)?.personality_profile ?? null,
                  reflection_scorecard: (metadata as any)?.reflection_scorecard ?? null,
                  correction_applied: (metadata as any)?.correction_applied ?? false,
                  correction_text: (metadata as any)?.correction_text ?? null,
                },
              }
              upsertThread({ ...withUser, updatedAt: at, messages: [...withUser.messages, asstMsg] })
              resetStreamState()
            },
            onError: (error) => {
              const at = Date.now()
              const asstMsg = {
                id: newId('m'),
                role: 'assistant' as const,
                text: `Stream error: ${error}`,
                createdAt: at,
                crt: {
                  response_type: 'speech',
                  gates_passed: false,
                  gate_reason: 'stream_error',
                },
              }
              upsertThread({ ...withUser, updatedAt: at, messages: [...withUser.messages, asstMsg] })
              resetStreamState()
            },
          },
        })
      } else {
        // Non-streaming API
        const res = await sendToCrtApi({ threadId: withUser.id, message: outgoingText, history: withUser.messages })
        const at = Date.now()
        const asstMsg = {
          id: newId('m'),
          role: 'assistant' as const,
          text: res.answer,
          createdAt: at,
          crt: {
            response_type: res.response_type,
            gates_passed: res.gates_passed,
            gate_reason: res.gate_reason ?? null,
            session_id: res.session_id ?? null,
            interaction_id: (res.metadata as any)?.interaction_id ?? null,
            confidence: res.metadata?.confidence ?? null,
            intent_alignment: res.metadata?.intent_alignment ?? null,
            memory_alignment: res.metadata?.memory_alignment ?? null,
            contradiction_detected: res.metadata?.contradiction_detected ?? null,
            unresolved_contradictions_total: res.metadata?.unresolved_contradictions_total ?? null,
            unresolved_hard_conflicts: res.metadata?.unresolved_hard_conflicts ?? null,
            retrieved_memories: res.metadata?.retrieved_memories ?? [],
            prompt_memories: res.metadata?.prompt_memories ?? [],
            learned_suggestions: res.metadata?.learned_suggestions ?? [],
            heuristic_suggestions: res.metadata?.heuristic_suggestions ?? [],
            profile_updates: Array.isArray(res.metadata?.profile_updates) ? res.metadata?.profile_updates ?? [] : [],
            pipeline_statuses: [],
            draft_response: null,
            tasking: res.metadata?.tasking ?? null,
            agent_activated: res.metadata?.agent_activated ?? null,
            agent_answer: res.metadata?.agent_answer ?? null,
            agent_trace: res.metadata?.agent_trace ?? null,
            xray: res.metadata?.xray ?? null,
            personality_profile: (res.metadata as any)?.personality_profile ?? null,
            reflection_scorecard: (res.metadata as any)?.reflection_scorecard ?? null,
          },
        }
        upsertThread({ ...withUser, updatedAt: at, messages: [...withUser.messages, asstMsg] })
      }
    } catch (e) {
      const at = Date.now()
      const errText = e instanceof Error ? e.message : String(e)
      const asstMsg = {
        id: newId('m'),
        role: 'assistant' as const,
        text: `CRT API error: ${errText}`,
        createdAt: at,
        crt: {
          response_type: 'speech',
          gates_passed: false,
          gate_reason: 'api_error',
        },
      }
      upsertThread({ ...withUser, updatedAt: at, messages: [...withUser.messages, asstMsg] })
    } finally {
      setTyping(false)
    }
  }, [selectedThread, upsertThread, useStreaming])

  const pickQuickAction = useCallback((a: QuickAction) => {
    void handleSend(a.seedPrompt)
  }, [handleSend])

  const handleResearch = useCallback(async (query: string) => {
    if (!selectedThread || !query.trim()) return

    setResearching(true)
    const now = Date.now()
    const userMsg = { id: newId('m'), role: 'user' as const, text: `Research: ${query}`, createdAt: now }

    const withUser: ChatThread = {
      ...selectedThread,
      updatedAt: now,
      messages: [...selectedThread.messages, userMsg],
    }

    upsertThread(withUser)

    try {
      const packet = await searchResearch({
        threadId: withUser.id,
        query,
        maxSources: 3,
      })

      const at = Date.now()
      const asstMsg = {
        id: newId('m'),
        role: 'assistant' as const,
        text: packet.summary,
        createdAt: at,
        crt: {
          response_type: 'research',
          gates_passed: true,
          research_packet: packet,
        },
      }
      upsertThread({ ...withUser, updatedAt: at, messages: [...withUser.messages, asstMsg] })
    } catch (e) {
      const at = Date.now()
      const errText = e instanceof Error ? e.message : String(e)
      const asstMsg = {
        id: newId('m'),
        role: 'assistant' as const,
        text: `Research failed: ${errText}`,
        createdAt: at,
        crt: {
          response_type: 'speech',
          gates_passed: false,
          gate_reason: 'research_error',
        },
      }
      upsertThread({ ...withUser, updatedAt: at, messages: [...withUser.messages, asstMsg] })
    } finally {
      setResearching(false)
    }
  }, [selectedThread, upsertThread])

  return {
    // Streaming display state
    streamingThinking,
    streamingResponse,
    isThinking,
    streamPhase,
    streamStatusLog,
    intentPreview,
    agentThinkingState,
    // Controls
    typing,
    researching,
    useStreaming,
    setUseStreaming,
    currentMood,
    // Actions
    handleSend,
    handleResearch,
    pickQuickAction,
  }
}
