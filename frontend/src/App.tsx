import { useEffect, useMemo, useState } from 'react'
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
import { DashboardPage } from './pages/DashboardPage'
import { DocsPage } from './pages/DocsPage'
import { JobsPage } from './pages/JobsPage'
import { ShowcasePage } from './pages/ShowcasePage'
import { newId } from './lib/id'
import { getEffectiveApiBaseUrl, getHealth, getProfile, sendToCrtApi, streamFromCrtApi, setEffectiveApiBaseUrl, searchResearch, setProfileName } from './lib/api'
import { quickActions, seedThreads } from './lib/seed'
import { loadChatStateFromStorage, saveChatStateToStorage } from './lib/chatStorage'

export default function App() {
  const [navActive, setNavActive] = useState<NavId>('chat')
  const [search, setSearch] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [threads, setThreads] = useState<ChatThread[]>(() => {
    const loaded = loadChatStateFromStorage()
    return loaded.threads.length ? loaded.threads : seedThreads()
  })
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
  
  // Streaming state
  const [streamingThinking, setStreamingThinking] = useState<string>('')
  const [streamingResponse, setStreamingResponse] = useState<string>('')
  const [isThinking, setIsThinking] = useState(false)
  const [useStreaming, setUseStreaming] = useState(true) // Toggle for streaming mode

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

  useEffect(() => {
    // Persist threads + selection for the Recent chats sidebar.
    const id = window.setTimeout(() => {
      saveChatStateToStorage({ threads, selectedThreadId: selectedThread?.id ?? selectedThreadId ?? null })
    }, 150)
    return () => window.clearTimeout(id)
  }, [threads, selectedThread?.id, selectedThreadId])

  useEffect(() => {
    let mounted = true
    async function ping() {
      try {
        await getHealth()
        if (mounted) setApiStatus('connected')
      } catch (_e) {
        if (mounted) setApiStatus('disconnected')
      }
    }
    void ping()
    const id = window.setInterval(() => void ping(), 5000)
    return () => {
      mounted = false
      window.clearInterval(id)
    }
  }, [])

  useEffect(() => {
    // Best-effort: load profile slots (including name) for the active thread.
    const tid = selectedThread?.id ?? selectedThreadId
    let mounted = true

    async function load() {
      try {
        const p = await getProfile(tid)
        const raw = (p?.name || p?.slots?.name || '').trim()
        if (!mounted) return
        setProfileHasName(Boolean(raw))
        setUserName(raw || 'User')
      } catch (_e) {
        // Keep existing name on error.
      }
    }

    void load()
    return () => {
      mounted = false
    }
  }, [selectedThread?.id, selectedThreadId])

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

  async function handleSend(text: string) {
    if (!selectedThread) return

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
        ? raw
          .trim()
          .replace(/^FACT:\s*/i, '')
          .replace(/^PREF:\s*/i, '')
          .slice(0, 48) || 'New chat'
      : selectedThread.title

    const withUser: ChatThread = {
      ...selectedThread,
      title: autoTitle,
      updatedAt: now,
      messages: [...selectedThread.messages, userMsg],
    }

    upsertThread(withUser)
    setTyping(true)
    
    // Reset streaming state
    setStreamingThinking('')
    setStreamingResponse('')
    setIsThinking(false)

    try {
      if (useStreaming) {
        // Use streaming API
        let finalContent = ''
        let thinkingContent = ''
        
        await streamFromCrtApi({
          threadId: withUser.id,
          message: outgoingText,
          callbacks: {
            onStatus: (status) => {
              // Could show status in UI if desired
              console.log('[Stream Status]', status)
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
            onToken: (token) => {
              finalContent += token
              setStreamingResponse(finalContent)
            },
            onDone: (content, metadata) => {
              const at = Date.now()
              const asstMsg = {
                id: newId('m'),
                role: 'assistant' as const,
                text: content,
                createdAt: at,
                crt: {
                  response_type: 'speech',
                  gates_passed: true,
                  gate_reason: null,
                  session_id: null,
                  confidence: null,
                  intent_alignment: null,
                  memory_alignment: null,
                  contradiction_detected: null,
                  unresolved_contradictions_total: null,
                  unresolved_hard_conflicts: null,
                  retrieved_memories: [],
                  prompt_memories: [],
                  learned_suggestions: [],
                  heuristic_suggestions: [],
                  agent_activated: null,
                  agent_answer: null,
                  agent_trace: null,
                  xray: null,
                  // Add thinking content to metadata
                  thinking: thinkingContent || undefined,
                },
              }
              upsertThread({ ...withUser, updatedAt: at, messages: [...withUser.messages, asstMsg] })
              // Clear streaming state
              setStreamingThinking('')
              setStreamingResponse('')
              setIsThinking(false)
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
            agent_activated: res.metadata?.agent_activated ?? null,
            agent_answer: res.metadata?.agent_answer ?? null,
            agent_trace: res.metadata?.agent_trace ?? null,
            xray: res.metadata?.xray ?? null,
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

  return (
    <div className="h-screen w-full overflow-hidden">
      <div className="mx-auto h-full max-w-[1480px] px-4 py-6">
        <div className="flex h-full min-h-0 gap-5">
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
          />

          <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
            <Topbar
              onToggleSidebarMobile={() => setSidebarOpen((v) => !v)}
              title="CRT"
              userName={userName}
              userEmail={userEmail}
              apiStatus={apiStatus}
              apiBaseUrl={apiBaseUrl}
              onChangeApiBaseUrl={setApiBaseUrl}
              xrayMode={xrayMode}
              onToggleXray={() => setXrayMode((v) => !v)}
              onOpenDemoMode={() => setDemoModeOpen(true)}
              streamingMode={useStreaming}
              onToggleStreaming={() => setUseStreaming((v) => !v)}
            />

            <div className="relative min-h-0 flex-1">
              <main className="relative flex h-full min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/5 shadow-soft backdrop-blur-xl">
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
                    />
                  ) : (
                    <div className="flex flex-1 items-center justify-center p-10 text-white/60">No chat selected.</div>
                  )
                ) : navActive === 'dashboard' ? (
                  <DashboardPage threadId={selectedThread?.id ?? 'default'} onOpenJobs={() => setNavActive('jobs')} />
                ) : navActive === 'jobs' ? (
                  <JobsPage threadId={selectedThread?.id ?? 'default'} />
                ) : navActive === 'showcase' ? (
                  <ShowcasePage />
                ) : (
                  <DocsPage />
                )}
              </main>
            </div>
          </div>
        </div>
      </div>

      <InspectorLightbox open={navActive === 'chat' && Boolean(selectedMessageId)} message={selectedMessage} onClose={() => setSelectedMessageId(null)} />

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
