import { useEffect, useMemo, useState, useRef, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import type { ChatThread, NavId, QuickAction } from './types'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { ChatThreadView } from './components/chat/ChatThreadView'
import { InspectorLightbox } from './components/InspectorLightbox'
import { ProfileNameLightbox } from './components/ProfileNameLightbox'
import { ThreadRenameLightbox } from './components/ThreadRenameLightbox'
import { SourceInspector } from './components/SourceInspector'
import { AgentPanel } from './components/AgentPanel'
import { DemoModeLightbox } from './components/DemoModeLightbox'
import { WelcomeTutorial } from './components/onboarding/WelcomeTutorial'
import { LoginScreen } from './components/LoginScreen'
import { MoodBackground, MoodIndicator, type MoodData } from './components/MoodBackground'
import { DashboardPage } from './pages/DashboardPage'
import { DocsPage } from './pages/DocsPage'
import { JobsPage } from './pages/JobsPage'
import { LoopsPage } from './pages/LoopsPage'
import { JournalPage } from './pages/JournalPage'
import { CopilotPage } from './pages/CopilotPage'
import { LiveFeedPage } from './pages/LiveFeedPage'
import { TelemetryPage } from './pages/TelemetryPage'
import { newId } from './lib/id'
import { getEffectiveApiBaseUrl, getHealth, getProfile, sendToCrtApi, streamFromCrtApi, setEffectiveApiBaseUrl, searchResearch, setProfileName, authGetMe, authLogout, authSyncChats, authLoadChats, getAuthToken, updateAuthProfile, type AuthUser } from './lib/api'
import { SettingsPage } from './pages/SettingsPage'
import { V2Page } from './pages/V2Page'
import { DiagnosticsDrawer } from './components/chat/DiagnosticsDrawer'
import { quickActions, seedThreads } from './lib/seed'
import { loadChatStateFromStorage, saveChatStateToStorage } from './lib/chatStorage'

export default function App() {
  // Auth state
  const [authUser, setAuthUser] = useState<AuthUser | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [showLogin, setShowLogin] = useState(false)
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false)
  
  // URL-synced navigation
  const navigate = useNavigate()
  const location = useLocation()
  const validNavIds: NavId[] = ['chat', 'dashboard', 'loops', 'journal', 'jobs', 'docs', 'copilot', 'live', 'telemetry', 'settings', 'v2']
  const navFromUrl = (): NavId => {
    const path = location.pathname.replace(/^\//, '').split('/')[0] || 'chat'
    return validNavIds.includes(path as NavId) ? (path as NavId) : 'chat'
  }
  const [navActive, setNavActiveRaw] = useState<NavId>(navFromUrl)
  const setNavActive = useCallback((id: NavId) => {
    setNavActiveRaw(id)
    navigate(id === 'chat' ? '/' : `/${id}`)
  }, [navigate])
  // Sync on browser back/forward
  useEffect(() => {
    setNavActiveRaw(navFromUrl())
  }, [location.pathname])

  const [search, setSearch] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [threads, setThreads] = useState<ChatThread[]>(() => {
    const loaded = loadChatStateFromStorage()
    return loaded.threads.length ? loaded.threads : seedThreads()
  })

  // Pinned thread IDs — persisted to localStorage
  const [pinnedThreadIds, setPinnedThreadIds] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem('crt_pinned_threads')
      return raw ? JSON.parse(raw) : []
    } catch { return [] }
  })
  useEffect(() => {
    try { localStorage.setItem('crt_pinned_threads', JSON.stringify(pinnedThreadIds)) } catch {}
  }, [pinnedThreadIds])

  const togglePinThread = useCallback((id: string) => {
    setPinnedThreadIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])
  }, [])
  const [selectedThreadId, setSelectedThreadId] = useState<string>(() => {
    const loaded = loadChatStateFromStorage()
    if (loaded.selectedThreadId) return loaded.selectedThreadId
    return loaded.threads[0]?.id ?? seedThreads()[0]?.id ?? 't1'
  })
  const [typing, setTyping] = useState(false)
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)
  const [apiStatus, setApiStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking')
  const [apiBaseUrl, setApiBaseUrl] = useState<string>(getEffectiveApiBaseUrl())
  const [userName, setUserName] = useState<string>('User')
  const [userEmail, setUserEmail] = useState<string>('')
  const [profileHasName, setProfileHasName] = useState<boolean>(false)
  const [setNameOpen, setSetNameOpen] = useState<boolean>(false)
  const [renameOpen, setRenameOpen] = useState(false)
  const [renameThreadId, setRenameThreadId] = useState<string | null>(null)
  const [sourceInspectorMemoryId, setSourceInspectorMemoryId] = useState<string | null>(null)
  const [researching, setResearching] = useState(false)
  const [agentPanelMessageId, setAgentPanelMessageId] = useState<string | null>(null)
  const [xrayMode, setXrayMode] = useState(false)
  const [demoModeOpen, setDemoModeOpen] = useState(false)
  const [tutorialOpen, setTutorialOpen] = useState(false)
  
  // Model selection
  const [selectedModel, setSelectedModel] = useState<string>(() => {
    return localStorage.getItem('crt_selected_model') || 'crt-reasoning'
  })
  
  // Save model selection to localStorage
  useEffect(() => {
    localStorage.setItem('crt_selected_model', selectedModel)
  }, [selectedModel])

  // Clear agent strip when switching threads — strip belongs to a specific turn, not the thread
  useEffect(() => {
    setAgentThinkingState(null)
    agentThinkingRef.current = null
  }, [selectedThreadId])
  
  // Streaming state
  const [streamingThinking, setStreamingThinking] = useState<string>('')
  const [streamingResponse, setStreamingResponse] = useState<string>('')
  const [isThinking, setIsThinking] = useState(false)
  const [useStreaming, setUseStreaming] = useState(true) // Toggle for streaming mode
  const phaseMode = true
  const [streamPhase, setStreamPhase] = useState<string | null>(null)
  const [streamStatusLog, setStreamStatusLog] = useState<string[]>([])
  const streamStatusRef = useRef<string[]>([])
  const [intentPreview, setIntentPreview] = useState<{ intent: string; slots: string[]; label: string } | null>(null)
  const [agentThinkingState, setAgentThinkingState] = useState<import('./components/chat/AgentThinkingStrip').AgentThinkingState | null>(null)
  // Ref mirrors state so onDone closure can read the latest value without stale capture
  const agentThinkingRef = useRef<import('./components/chat/AgentThinkingStrip').AgentThinkingState | null>(null)
  const finalBufferRef = useRef('')
  const streamAbortRef = useRef<AbortController | null>(null)
  const [taskWorking, setTaskWorking] = useState(false)
  const inflightThreadRef = useRef<ChatThread | null>(null)
  
  // Mood background state
  const [currentMood, setCurrentMood] = useState<MoodData | null>(null)

  // Agent checkpoint state — when the task agent asks for confirmation
  const [pendingCheckpoint, setPendingCheckpoint] = useState<{
    message: string
    metadata: Record<string, unknown>
  } | null>(null)

  // Sprint 4 — proactive suggestion from done metadata
  const [proactiveSuggestion, setProactiveSuggestion] = useState<{
    trigger: string
    suggestion: string
    action: string
  } | null>(null)

  const selectedThread = useMemo(
    () => threads.find((t) => t.id === selectedThreadId) ?? threads[0],
    [threads, selectedThreadId],
  )

  const selectedMessage = useMemo(() => {
    if (!selectedThread || !selectedMessageId) return null
    return selectedThread.messages.find((m) => m.id === selectedMessageId) ?? null
  }, [selectedThread, selectedMessageId])

  function upsertThread(updated: ChatThread) {
    setThreads((prev) => {
      const exists = prev.some((t) => t.id === updated.id)
      const next = exists ? prev.map((t) => (t.id === updated.id ? updated : t)) : [updated, ...prev]
      next.sort((a, b) => b.updatedAt - a.updatedAt)
      return next
    })
  }

  function openRename(id: string) {
    setRenameThreadId(id)
    setRenameOpen(true)
  }

  function renameThread(id: string, title: string) {
    const clean = title.trim()
    if (!clean) return
    const now = Date.now()
    setThreads((prev) => {
      const next = prev.map((t) => (t.id === id ? { ...t, title: clean, updatedAt: now } : t))
      next.sort((a, b) => b.updatedAt - a.updatedAt)
      return next
    })
  }

  function newThread() {
    const now = Date.now()
    const t: ChatThread = { id: newId('t'), title: 'New chat', updatedAt: now, messages: [] }
    setThreads((prev) => [t, ...prev].sort((a, b) => b.updatedAt - a.updatedAt))
    setSelectedThreadId(t.id)
    setSelectedMessageId(null)
    setNavActive('chat')
  }

  function deleteThread(id: string) {
    setThreads((prev) => {
      const remaining = prev.filter((t) => t.id !== id)
      if (selectedThreadId === id) {
        const next = remaining[0]
        if (next) {
          setSelectedThreadId(next.id)
        } else {
          const now = Date.now()
          const t: ChatThread = { id: newId('t'), title: 'New chat', updatedAt: now, messages: [] }
          remaining.unshift(t)
          setSelectedThreadId(t.id)
        }
        setSelectedMessageId(null)
        setNavActive('chat')
      }
      return remaining
    })
  }

  // Check for existing auth session on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = getAuthToken()
      if (!token) {
        setAuthLoading(false)
        // Show login for first-time users
        const hasSeenLogin = localStorage.getItem('crt-seen-login')
        if (!hasSeenLogin) {
          setShowLogin(true)
        }
        return
      }

      try {
        const result = await authGetMe()
        if (result.ok && result.user) {
          setAuthUser(result.user)
          // Load user's chat history from server
          const serverThreads = await authLoadChats()
          if (serverThreads.length > 0) {
            setThreads(serverThreads.map(t => ({
              id: t.id,
              title: t.title,
              messages: t.messages as any[],
              updatedAt: t.updatedAt
            })))
            if (serverThreads[0]) {
              setSelectedThreadId(serverThreads[0].id)
            }
          }
        }
      } catch {
        // Session invalid
      } finally {
        setAuthLoading(false)
      }
    }

    checkAuth()
  }, [])

  // Sprint 4 — notification SSE stream for commitment reminders
  useEffect(() => {
    const base = getEffectiveApiBaseUrl()
    let es: EventSource | null = null
    let retryTimeout: ReturnType<typeof setTimeout> | null = null

    function connect() {
      try {
        es = new EventSource(`${base}/api/notifications/stream`)
        es.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (data.type === 'commitment_notification') {
              // Show browser notification
              if (Notification.permission === 'granted') {
                new Notification('Aether Reminder', {
                  body: data.content,
                  icon: '/favicon.ico',
                })
              }
              // Inject as system message in active thread
              const notifMsg = {
                id: newId('m'),
                role: 'assistant' as const,
                text: `🔔 **Reminder:** ${data.content}`,
                createdAt: Date.now(),
                crt: {
                  response_type: 'notification',
                  notification_type: 'commitment',
                  commitment_id: data.metadata?.commitment_id,
                  priority: data.metadata?.priority,
                  consequence: data.metadata?.consequence,
                },
              }
              setThreads(prev => prev.map(t =>
                t.id === selectedThreadId
                  ? { ...t, messages: [...t.messages, notifMsg], updatedAt: Date.now() }
                  : t
              ))
            }
          } catch { /* ignore parse errors */ }
        }
        es.onerror = () => {
          es?.close()
          // Retry in 10s
          retryTimeout = setTimeout(connect, 10000)
        }
      } catch { /* EventSource not available */ }
    }

    // Request notification permission on first load
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }

    connect()
    return () => {
      es?.close()
      if (retryTimeout) clearTimeout(retryTimeout)
    }
  }, [selectedThreadId])

  // Sync threads to server when logged in
  useEffect(() => {
    if (!authUser) return
    
    const syncTimer = window.setTimeout(() => {
      authSyncChats(threads.map(t => ({
        id: t.id,
        title: t.title,
        messages: t.messages,
        updatedAt: t.updatedAt
      }))).catch(() => {})
    }, 2000) // Debounce sync
    
    return () => window.clearTimeout(syncTimer)
  }, [authUser, threads])

  useEffect(() => {
    // Persist threads + selection for the Recent chats sidebar.
    const id = window.setTimeout(() => {
      saveChatStateToStorage({ threads, selectedThreadId: selectedThread?.id ?? selectedThreadId ?? null })
    }, 150)
    return () => window.clearTimeout(id)
  }, [threads, selectedThread?.id, selectedThreadId])

  useEffect(() => {
    let mounted = true
    let id: number | undefined

    async function ping() {
      try {
        await getHealth()
        if (mounted) setApiStatus('connected')
      } catch (_e) {
        if (mounted) setApiStatus('disconnected')
      }
    }

    function startPolling() {
      stopPolling()
      id = window.setInterval(() => void ping(), 30_000)
    }

    function stopPolling() {
      if (id !== undefined) {
        window.clearInterval(id)
        id = undefined
      }
    }

    function handleVisibility() {
      if (document.visibilityState === 'visible') {
        void ping() // immediate check on tab focus
        startPolling()
      } else {
        stopPolling()
      }
    }

    void ping()
    startPolling()
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      mounted = false
      stopPolling()
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [])

  useEffect(() => {
    // Best-effort: load profile slots (including name) for the active thread.
    // BUT: never overwrite if the user has an explicit display_name in auth.
    const tid = selectedThread?.id ?? selectedThreadId
    let mounted = true

    async function load() {
      try {
        const p = await getProfile(tid)
        const raw = (p?.name || p?.slots?.name || '').trim()
        if (!mounted) return
        setProfileHasName(Boolean(raw))
        // Auth display_name takes priority — don't let CRT profile overwrite it
        if (!authUser?.display_name) {
          setUserName(raw || 'User')
        }
      } catch (_e) {
        // Keep existing name on error.
      }
    }

    void load()
    return () => {
      mounted = false
    }
  }, [selectedThread?.id, selectedThreadId, authUser?.display_name])

  useEffect(() => {
    // Show tutorial on first visit
    const tutorialCompleted = localStorage.getItem('crt-tutorial-completed')
    if (!tutorialCompleted && threads.length > 0) {
      // Delay slightly to let the UI settle
      const timer = setTimeout(() => setTutorialOpen(true), 1000)
      return () => clearTimeout(timer)
    }
  }, [threads.length])

  useEffect(() => {
    setEffectiveApiBaseUrl(apiBaseUrl)
  }, [apiBaseUrl])

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

  async function handleSend(text: string, opts?: { silent?: boolean }) {
    if (!selectedThread) return
    const silent = opts?.silent ?? false

    const raw = text
    const trimmed = raw.trim()
    const expandTriggers = [
      'explain more',
      'expand',
      'expand more',
      'tell me more',
      'go deeper',
      'continue',
      'more detail',
      'more details',
      'elaborate',
    ]
    const wantsExpand = !silent && expandTriggers.some((t) => trimmed.toLowerCase() === t || trimmed.toLowerCase().startsWith(t + ' '))

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

    // Silent mode: don't show user bubble (used for checkpoint confirmations)
    const withUser: ChatThread = silent
      ? { ...selectedThread, updatedAt: now }
      : (() => {
          const userMsg = { id: newId('m'), role: 'user' as const, text: raw, createdAt: now }
          const shouldAutoTitle = !selectedThread.title || selectedThread.title === 'New chat'
          const autoTitle = shouldAutoTitle
              ? raw.trim().replace(/^FACT:\s*/i, '').replace(/^PREF:\s*/i, '').slice(0, 48) || 'New chat'
            : selectedThread.title
          return {
            ...selectedThread,
            title: autoTitle,
            updatedAt: now,
            messages: [...selectedThread.messages, userMsg],
          }
        })()

    upsertThread(withUser)
    setTyping(true)
    
    // Reset streaming state (including agent strip — must clear ref before new stream)
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
    setPendingCheckpoint(null)

    try {
      if (useStreaming) {
        // Use streaming API
        let thinkingContent = ''
        const abortController = new AbortController()
        streamAbortRef.current = abortController
        inflightThreadRef.current = withUser

        await streamFromCrtApi({
          threadId: withUser.id,
          message: outgoingText,
          phaseMode,
          signal: abortController.signal,
          callbacks: {
            onIntentPreview: (intent, slots, label) => {
              setIntentPreview({ intent, slots, label })
            },
            onIntentClassified: (intent, route, slots, confidence, source) => {
              const next = { intent, route, slots, confidence, source, toolSteps: [] }
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
                // Freeze any pending reasoning into the new tool step
                const pendingReasoning = prev.pendingReasoning || ''
                const existing = prev.toolSteps.find(s => s.step_index === stepIndex)
                const newStep = { step_index: stepIndex, tool_name: toolName, input, status: 'running' as const, reasoning: pendingReasoning }
                const updated = existing
                  ? prev.toolSteps.map(s => s.step_index === stepIndex ? { ...s, status: 'running' as const, reasoning: pendingReasoning || s.reasoning } : s)
                  : [...prev.toolSteps, newStep]
                const next = { ...prev, toolSteps: updated, activeStepIndex: stepIndex, pendingReasoning: '' }
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
            onTaskAcknowledged: (message, _meta) => {
              // Render acknowledgment as a real streamed assistant message
              setStreamingResponse(message)
              // Start pulse animation on input area
              setTaskWorking(true)
            },
            // Sprint 8: Orchestration callbacks
            onOrchestrationStart: (_count, subtasks) => {
              setAgentThinkingState((prev) => {
                const orch = {
                  subtasks: subtasks.map((st) => ({
                    taskId: st.task_id,
                    agentName: st.agent_name,
                    intentType: st.intent_type,
                    dependsOn: st.depends_on,
                    status: 'pending' as const,
                  })),
                }
                const next = prev ? { ...prev, orchestration: orch } : { toolSteps: [], orchestration: orch }
                agentThinkingRef.current = next
                return next
              })
            },
            onSubtaskStart: (taskId, agentName, _intentType) => {
              setAgentThinkingState((prev) => {
                if (!prev?.orchestration) return prev
                const updated = prev.orchestration.subtasks.map((st) =>
                  st.taskId === taskId ? { ...st, status: 'running' as const, agentName: agentName || st.agentName } : st
                )
                const next = { ...prev, orchestration: { ...prev.orchestration, subtasks: updated } }
                agentThinkingRef.current = next
                return next
              })
            },
            onSubtaskDone: (taskId, agentName, status, durationMs, outputPreview) => {
              setAgentThinkingState((prev) => {
                if (!prev?.orchestration) return prev
                const updated = prev.orchestration.subtasks.map((st) =>
                  st.taskId === taskId
                    ? { ...st, status: (status === 'ok' ? 'ok' : 'error') as 'ok' | 'error', durationMs, outputPreview, agentName: agentName || st.agentName }
                    : st
                )
                const next = { ...prev, orchestration: { ...prev.orchestration, subtasks: updated } }
                agentThinkingRef.current = next
                return next
              })
            },
            onOrchestrationDone: (mergedTrust, allOk, _meta) => {
              setAgentThinkingState((prev) => {
                if (!prev?.orchestration) return prev
                const next = {
                  ...prev,
                  orchestration: { ...prev.orchestration, mergedTrust, allOk, done: true },
                  drafting: true,
                  pendingReasoning: '',
                }
                agentThinkingRef.current = next
                return next
              })
            },
            onTaskDone: (_answer, _steps, _meta) => {
              // Stop pulse animation
              setTaskWorking(false)
              setAgentThinkingState((prev) => {
                const next = prev ? { ...prev, drafting: true, pendingReasoning: '' } : prev
                agentThinkingRef.current = next
                return next
              })
              // If the task includes suggested follow-up actions, show the action card
              const suggested = (_meta as Record<string, unknown>)?.suggested_actions
              if (Array.isArray(suggested) && suggested.length > 0) {
                const msg = ((_meta as Record<string, unknown>)?.followup_prompt as string) || 'What would you like to do?'
                setPendingCheckpoint({
                  message: msg,
                  metadata: { suggested_actions: suggested, is_followup: true },
                })
              }
            },
            onAgentCheckpoint: (message, metadata) => {
              console.log(`[APP_DEBUG] onAgentCheckpoint message="${message}" meta=`, metadata)
              // Show the checkpoint message as streamed response AND activate the action card
              setStreamingResponse(message)
              setPendingCheckpoint({ message, metadata })
            },
            onTaskCancelled: (message) => {
              setStreamingResponse(message)
            },
            onAgentThinkingToken: (token, step) => {
              setAgentThinkingState((prev) => {
                if (!prev) return prev
                if (step === 'tool_loop') {
                  // Accumulate reasoning — will be attached to the next tool_start
                  const next = { ...prev, pendingReasoning: (prev.pendingReasoning ?? '') + token }
                  agentThinkingRef.current = next
                  return next
                }
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
                // keep phase visible until answer starts
                setStreamPhase(phase)
              }
            },
            onCorrection: (content) => {
              // Self-correction: append to the streamed response with visual separator
              const correctionBlock = `\n\n---\n*${content}*`
              finalBufferRef.current += correctionBlock
              setStreamingResponse(finalBufferRef.current)
            },
            onToken: (token) => {
              console.log(`[APP_DEBUG] onToken len=${token.length} preview=${token.slice(0, 100)}`)
              finalBufferRef.current += token
              setStreamingResponse(finalBufferRef.current)
            },
            onDone: (content, metadata) => {
              console.log(`[APP_DEBUG] onDone content_len=${content.length} checkpoint_pending=${(metadata as any)?.checkpoint_pending} agent_loop=${(metadata as any)?.agent_loop}`, content.slice(0, 200))
              const at = Date.now()
              // Prefer thinking from metadata (server-side) if available, fallback to streamed content
              const finalThinking = (metadata?.thinking as string) || thinkingContent || undefined
              const draft = (finalBufferRef.current || '').trim()
              const draftResponse = draft && draft !== content ? draft : null
              const profileUpdates = Array.isArray((metadata as any)?.profile_updates)
                ? ((metadata as any).profile_updates as any[])
                : []
              const pipelineStatuses = streamStatusRef.current
              
              // Extract mood data for dynamic background
              if (metadata?.mood) {
                setCurrentMood(metadata.mood as MoodData)
              }
              
              // Capture agent thinking state from ref (avoids stale closure — ref is always current)
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
                  // Add thinking content from metadata or streamed content
                  thinking: finalThinking,
                  // Store trace_id for lazy-loading after refresh
                  thinking_trace_id: (metadata?.thinking_trace_id as string) || null,
                  // Store reflection trace for self-assessment dropdown
                  reflection_trace_id: (metadata?.reflection_trace_id as string) || null,
                  reflection_confidence: (metadata?.reflection_confidence as number) ?? null,
                  reflection_label: (metadata?.reflection_label as string) || null,
                  personality_profile: (metadata as any)?.personality_profile ?? null,
                  reflection_scorecard: (metadata as any)?.reflection_scorecard ?? null,
                  correction_applied: (metadata as any)?.correction_applied ?? false,
                  correction_text: (metadata as any)?.correction_text ?? null,
                  generation_source: (metadata?.generation_source as string) || null,
                  escalation: (metadata as any)?.escalation ?? null,
                  cloud_governance_used: (metadata as any)?.cloud_governance_used ?? false,
                },
              }
              upsertThread({ ...withUser, updatedAt: at, messages: [...withUser.messages, asstMsg] })
              // Clear streaming state
              setStreamingThinking('')
              setStreamingResponse('')
              setIsThinking(false)
              setStreamPhase(null)
              setStreamStatusLog([])
              streamStatusRef.current = []
              finalBufferRef.current = ''
              setIntentPreview(null)
              setAgentThinkingState(null)
              setTaskWorking(false)

              // Sprint 4 — capture proactive suggestion from done metadata
              const ps = (metadata as any)?.proactive_suggestion
              if (ps && ps.suggestion) {
                setProactiveSuggestion({ trigger: ps.trigger, suggestion: ps.suggestion, action: ps.action })
              } else {
                setProactiveSuggestion(null)
              }
              agentThinkingRef.current = null
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
              setStreamingThinking('')
              setStreamingResponse('')
              setIsThinking(false)
              setStreamPhase(null)
              setStreamStatusLog([])
              streamStatusRef.current = []
              finalBufferRef.current = ''
              setIntentPreview(null)
              setTaskWorking(false)
            },
          },
        })
      } else {
        // Use non-streaming API (original behavior)
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
            generation_source: (res.metadata as any)?.generation_source ?? null,
            escalation: (res.metadata as any)?.escalation ?? null,
            cloud_governance_used: (res.metadata as any)?.cloud_governance_used ?? false,
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
      streamAbortRef.current = null
      inflightThreadRef.current = null
    }
  }

  /** Stop the current SSE stream — finalize partial content as the assistant message */
  function handleStopGeneration() {
    const controller = streamAbortRef.current
    const thread = inflightThreadRef.current
    if (!controller || !thread) return

    controller.abort()

    // Finalize whatever has been streamed so far
    const partial = (finalBufferRef.current || '').trim()
    if (partial) {
      const at = Date.now()
      const capturedThinking = agentThinkingRef.current
        ? { ...agentThinkingRef.current, done: true, drafting: false }
        : null
      const asstMsg = {
        id: newId('m'),
        role: 'assistant' as const,
        text: partial,
        createdAt: at,
        agentThinking: capturedThinking,
        crt: {
          response_type: 'speech',
          gates_passed: true,
          gate_reason: 'stopped_by_user',
        },
      }
      upsertThread({ ...thread, updatedAt: at, messages: [...thread.messages, asstMsg] })
    }

    // Clear all streaming state
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
    setPendingCheckpoint(null)
    setTyping(false)
    streamAbortRef.current = null
    inflightThreadRef.current = null
  }

  /** Respond to an agent checkpoint without showing a user message bubble */
  async function handleCheckpointRespond(text: string) {
    if (!selectedThread) return
    const isFollowup = pendingCheckpoint?.metadata?.is_followup === true
    setPendingCheckpoint(null)
    // Follow-up actions (from task_done suggested_actions) should show as a
    // normal user message so context is clear. Checkpoint confirmations stay silent.
    await handleSend(text, { silent: !isFollowup })
  }

  function pickQuickAction(a: QuickAction) {
    void handleSend(a.seedPrompt)
  }

  async function handleResearch(query: string) {
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
  }

  async function handleSetName(name: string) {
    if (!selectedThread) return
    try {
      await setProfileName({ threadId: selectedThread.id, name })
      setUserName(name)
      setProfileHasName(true)
      setSetNameOpen(false)
      // Refresh profile to confirm
      const p = await getProfile(selectedThread.id)
      const raw = (p?.name || p?.slots?.name || '').trim()
      if (raw) setUserName(raw)
    } catch (e) {
      console.error('Failed to set name:', e)
      alert(`Failed to set name: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const handleLogin = async (user: AuthUser) => {
    setAuthUser(user)
    setShowLogin(false)
    localStorage.setItem('crt-seen-login', 'true')
    
    // Load user's chat history
    try {
      const serverThreads = await authLoadChats()
      if (serverThreads.length > 0) {
        setThreads(serverThreads.map(t => ({
          id: t.id,
          title: t.title,
          messages: t.messages as any[],
          updatedAt: t.updatedAt
        })))
        if (serverThreads[0]) {
          setSelectedThreadId(serverThreads[0].id)
        }
      }
    } catch {
      // Keep local threads
    }
  }

  const handleLogout = async () => {
    await authLogout()
    setAuthUser(null)
  }

  const handleSkipLogin = () => {
    setShowLogin(false)
    localStorage.setItem('crt-seen-login', 'true')
  }

  // Show login screen
  if (showLogin && !authUser) {
    return (
      <LoginScreen
        onLogin={handleLogin}
        onSkip={handleSkipLogin}
      />
    )
  }

  // Show loading while checking auth
  if (authLoading) {
    return (
      <div className="aetheris-dark h-screen w-full flex items-center justify-center">
        <div className="text-white/60">Loading...</div>
      </div>
    )
  }

  // ── Standalone Docs route — completely outside the dashboard shell ──
  if (location.pathname.startsWith('/docs')) {
    return (
      <div className="aetheris-dark h-screen w-full overflow-hidden relative">
        <DocsPage onBackToApp={() => { navigate('/'); setNavActiveRaw('chat') }} />
      </div>
    )
  }

  return (
    <div className="aetheris-dark h-screen w-full overflow-hidden relative">
      {/* Dynamic mood-reactive background */}
      <MoodBackground mood={currentMood} isThinking={isThinking} />
      
      {/* Mood indicator badge (for debugging - shows current mood) */}
      {currentMood && <MoodIndicator mood={currentMood} />}
      
      <div className="h-full relative z-10">
        <div className="flex h-full min-h-0">
          <Sidebar
            open={sidebarOpen}
            onClose={() => setSidebarOpen(false)}
            navActive={navActive}
            onNav={(id) => setNavActive(id)}
            search={search}
            onSearch={setSearch}
            threads={threads}
            selectedThreadId={selectedThread?.id ?? null}
            onSelectThread={(id) => {
              setSelectedThreadId(id)
              setSelectedMessageId(null)
              setNavActive('chat')
            }}
            onNewThread={newThread}
            onDeleteThread={deleteThread}
            onRequestRenameThread={openRename}
            pinnedThreadIds={pinnedThreadIds}
            onTogglePinThread={togglePinThread}
            apiStatus={apiStatus}
            apiBaseUrl={apiBaseUrl}
            onChangeApiBaseUrl={setApiBaseUrl}
            authUser={authUser}
            onLogout={handleLogout}
            onShowLogin={() => setShowLogin(true)}
          />

          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            <Topbar
              onToggleSidebarMobile={() => setSidebarOpen((v) => !v)}
              title="CRT"
              userName={authUser?.display_name || userName}
              userEmail={userEmail}
              apiStatus={apiStatus}
              apiBaseUrl={apiBaseUrl}
              onChangeApiBaseUrl={setApiBaseUrl}
              xrayMode={xrayMode}
              onToggleXray={() => setXrayMode((v) => !v)}
              onOpenDemoMode={() => setDemoModeOpen(true)}
              streamingMode={useStreaming}
              onToggleStreaming={() => setUseStreaming((v) => !v)}
              selectedModel={selectedModel}
              onModelChange={setSelectedModel}
              onLogout={handleLogout}
              onOpenSettings={() => setNavActive('settings')}
            />

            <div className="relative min-h-0 flex-1">
              <main className="relative flex h-full min-w-0 flex-1 flex-col overflow-hidden">
                {navActive === 'chat' ? (
                  selectedThread ? (
                    <ChatThreadView
                      thread={selectedThread}
                      typing={typing}
                      onSend={handleSend}
                      quickActions={quickActions}
                      onPickQuickAction={pickQuickAction}
                      userName={userName}
                      showSetNameCta={!profileHasName}
                      onRequestSetName={() => setSetNameOpen(true)}
                      selectedMessageId={selectedMessageId}
                      onSelectAssistantMessage={(id) => setSelectedMessageId(id)}
                      onResearch={handleResearch}
                      researching={researching}
                      onOpenSourceInspector={setSourceInspectorMemoryId}
                      onOpenAgentPanel={setAgentPanelMessageId}
                      xrayMode={xrayMode}
                      streamingThinking={streamingThinking}
                      streamingResponse={streamingResponse}
                      isThinking={isThinking}
                      streamStatusLog={streamStatusLog}
                      streamPhase={streamPhase}
                      intentPreview={intentPreview}
                      agentThinkingState={agentThinkingState}
                      taskWorking={taskWorking}
                      diagnosticsOpen={diagnosticsOpen}
                      onToggleDiagnostics={() => setDiagnosticsOpen((v) => !v)}
                      pendingCheckpoint={pendingCheckpoint}
                      onCheckpointRespond={handleCheckpointRespond}
                      onCheckpointDismiss={() => setPendingCheckpoint(null)}
                      onStopGeneration={handleStopGeneration}
                      proactiveSuggestion={proactiveSuggestion}
                      onProactiveSuggestionClick={(action) => {
                        // Send the suggestion action as a chat message
                        if (action === 'create_commitment') {
                          handleSend('Yes, set a reminder for that')
                        } else if (action === 'project_scan') {
                          handleSend('Yes, check the project status')
                        } else if (action === 'trip_research') {
                          handleSend('Yes, look that up for me')
                        } else {
                          handleSend(`Yes, ${proactiveSuggestion?.suggestion || 'go ahead'}`)
                        }
                        setProactiveSuggestion(null)
                      }}
                      onDismissProactiveSuggestion={() => setProactiveSuggestion(null)}
                    />
                  ) : (
                    <div className="flex flex-1 items-center justify-center p-10 text-white/60">No chat selected.</div>
                  )
                ) : navActive === 'dashboard' ? (
                  <DashboardPage threadId={selectedThread?.id ?? 'default'} onOpenJobs={() => setNavActive('jobs')} />
                ) : navActive === 'jobs' ? (
                  <JobsPage threadId={selectedThread?.id ?? 'default'} />
                ) : navActive === 'loops' ? (
                  <LoopsPage threadId={selectedThread?.id ?? 'default'} />
                ) : navActive === 'journal' ? (
                  <JournalPage threadId={selectedThread?.id ?? 'default'} />
                ) : navActive === 'copilot' ? (
                  <CopilotPage threadId={selectedThread?.id ?? 'default'} />
                ) : navActive === 'live' ? (
                  <LiveFeedPage />
                ) : navActive === 'telemetry' ? (
                  <TelemetryPage threadId={selectedThread?.id} />
                ) : navActive === 'v2' ? (
                  <V2Page />
                ) : navActive === 'settings' ? (
                  <SettingsPage
                    authUser={authUser}
                    threadId={selectedThread?.id ?? 'default'}
                    onDisplayNameChanged={(name) => {
                      setUserName(name)
                      setAuthUser((prev) => prev ? { ...prev, display_name: name } : prev)
                    }}
                    onProfileUpdated={() => {
                      const tid = selectedThread?.id ?? selectedThreadId
                      getProfile(tid).then((p) => {
                        const raw = (p?.name || p?.slots?.name || '').trim()
                        setProfileHasName(Boolean(raw))
                        // Only use CRT profile name if auth display_name isn't set
                        if (raw && !authUser?.display_name) setUserName(raw)
                      }).catch(() => {})
                    }}
                  />
                ) : (
                  <div className="flex flex-1 items-center justify-center p-10 text-white/40 text-sm">Page not found</div>
                )}
              </main>
            </div>
          </div>
        </div>
      </div>

      <DiagnosticsDrawer open={diagnosticsOpen} onClose={() => setDiagnosticsOpen(false)} />

      <InspectorLightbox
        open={navActive === 'chat' && Boolean(selectedMessageId)}
        message={selectedMessage}
        threadId={selectedThread?.id ?? null}
        streamStatusLog={streamStatusLog}
        streamPhase={streamPhase}
        onClose={() => setSelectedMessageId(null)}
      />

      <ProfileNameLightbox
        open={navActive === 'chat' && setNameOpen}
        initialName={profileHasName ? userName : ''}
        onClose={() => setSetNameOpen(false)}
        onSubmit={handleSetName}
      />


      <ThreadRenameLightbox
        open={renameOpen}
        initialTitle={threads.find((t) => t.id === renameThreadId)?.title ?? 'New chat'}
        onClose={() => {
          setRenameOpen(false)
          setRenameThreadId(null)
        }}
        onSubmit={(title) => {
          if (renameThreadId) renameThread(renameThreadId, title)
          setRenameOpen(false)
          setRenameThreadId(null)
        }}
      />

      <SourceInspector
        memoryId={sourceInspectorMemoryId}
        threadId={selectedThread?.id ?? 'default'}
        onClose={() => setSourceInspectorMemoryId(null)}
        onPromote={() => {
          // Optionally refresh chat or show success message
        }}
      />

      <AgentPanel
        trace={(() => {
          if (!agentPanelMessageId) return null
          const msg = selectedThread?.messages.find(m => m.id === agentPanelMessageId)
          return msg?.crt?.agent_trace ?? null
        })()}
        agentAnswer={(() => {
          if (!agentPanelMessageId) return null
          const msg = selectedThread?.messages.find(m => m.id === agentPanelMessageId)
          return msg?.crt?.agent_answer ?? null
        })()}
        onClose={() => setAgentPanelMessageId(null)}
      />

      <DemoModeLightbox
        open={demoModeOpen}
        onClose={() => setDemoModeOpen(false)}
        onSendMessage={handleSend}
      />

      <WelcomeTutorial
        open={tutorialOpen}
        onClose={() => setTutorialOpen(false)}
        onSendMessage={handleSend}
        onNavigateToDashboard={() => setNavActive('dashboard')}
      />
    </div>
  )
}
