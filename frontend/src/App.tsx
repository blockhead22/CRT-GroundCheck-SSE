import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import type { ChatThread, NavId, QuickAction } from './types'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { ChatThreadView } from './components/chat/ChatThreadView'
import { InspectorLightbox } from './components/InspectorLightbox'
import { DashboardPage } from './pages/DashboardPage'
import { DocsPage } from './pages/DocsPage'
import { newId } from './lib/id'
import { getEffectiveApiBaseUrl, getHealth, getProfile, sendToCrtApi, setEffectiveApiBaseUrl } from './lib/api'
import { quickActions, seedThreads } from './lib/seed'

export default function App() {
  const [navActive, setNavActive] = useState<NavId>('chat')
  const [search, setSearch] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [threads, setThreads] = useState<ChatThread[]>(() => seedThreads())
  const [selectedThreadId, setSelectedThreadId] = useState<string>(() => seedThreads()[0]?.id ?? 't1')
  const [typing, setTyping] = useState(false)
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)
  const [apiStatus, setApiStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking')
  const [apiBaseUrl, setApiBaseUrl] = useState<string>(getEffectiveApiBaseUrl())
  const [userName, setUserName] = useState<string>('User')
  const [userEmail, setUserEmail] = useState<string>('')

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
      const next = prev.map((t) => (t.id === updated.id ? updated : t))
      next.sort((a, b) => b.updatedAt - a.updatedAt)
      return next
    })
  }

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
        const name = (p?.name || p?.slots?.name || '').trim()
        if (mounted) setUserName(name || 'User')
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
    setEffectiveApiBaseUrl(apiBaseUrl)
  }, [apiBaseUrl])

  async function handleSend(text: string) {
    if (!selectedThread) return

    const now = Date.now()
    const userMsg = { id: newId('m'), role: 'user' as const, text, createdAt: now }
    const withUser: ChatThread = {
      ...selectedThread,
      updatedAt: now,
      messages: [...selectedThread.messages, userMsg],
    }

    upsertThread(withUser)
    setTyping(true)

    try {
      const res = await sendToCrtApi({ threadId: withUser.id, message: text, history: withUser.messages })
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
        },
      }
      upsertThread({ ...withUser, updatedAt: at, messages: [...withUser.messages, asstMsg] })
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

  return (
    <div className="min-h-screen w-full">
      <div className="mx-auto max-w-[1480px] px-4 py-6">
        <div className="flex gap-5">
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
          />

          <div className="flex min-w-0 flex-1 flex-col gap-4">
            <Topbar
              onToggleSidebarMobile={() => setSidebarOpen((v) => !v)}
              title="CRT"
              userName={userName}
              userEmail={userEmail}
              apiStatus={apiStatus}
              apiBaseUrl={apiBaseUrl}
              onChangeApiBaseUrl={setApiBaseUrl}
            />

            <div className="relative">
              <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/5 shadow-soft backdrop-blur-xl">
                {navActive === 'chat' ? (
                  selectedThread ? (
                    <ChatThreadView
                      thread={selectedThread}
                      typing={typing}
                      onSend={handleSend}
                      quickActions={quickActions}
                      onPickQuickAction={pickQuickAction}
                      userName={userName}
                      selectedMessageId={selectedMessageId}
                      onSelectAssistantMessage={(id) => setSelectedMessageId(id)}
                    />
                  ) : (
                    <div className="flex flex-1 items-center justify-center p-10 text-white/60">No chat selected.</div>
                  )
                ) : navActive === 'dashboard' ? (
                  <DashboardPage threadId={selectedThread?.id ?? 'default'} />
                ) : (
                  <DocsPage />
                )}
              </main>
            </div>
          </div>
        </div>
      </div>

      <InspectorLightbox open={navActive === 'chat' && Boolean(selectedMessageId)} message={selectedMessage} onClose={() => setSelectedMessageId(null)} />
    </div>
  )
}
