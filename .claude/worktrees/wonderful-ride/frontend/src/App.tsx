import { useEffect, useState } from 'react'
import type { QuickAction } from './types'
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
import { MoodBackground, MoodIndicator } from './components/MoodBackground'
import { DashboardPage } from './pages/DashboardPage'
import { DocsPage } from './pages/DocsPage'
import { JobsPage } from './pages/JobsPage'
import { LoopsPage } from './pages/LoopsPage'
import { JournalPage } from './pages/JournalPage'
import { ShowcasePage } from './pages/ShowcasePage'
import { CopilotPage } from './pages/CopilotPage'
import { LiveFeedPage } from './pages/LiveFeedPage'
import { TelemetryPage } from './pages/TelemetryPage'
import { quickActions } from './lib/seed'

// Hooks
import { useNavigation } from './hooks/useNavigation'
import { useApiHealth } from './hooks/useApiHealth'
import { useAuth } from './hooks/useAuth'
import { useProfile } from './hooks/useProfile'
import { useChatThreads } from './hooks/useChatThreads'
import { useChatStream } from './hooks/useChatStream'

export default function App() {
  // ── Navigation ──────────────────────────────────────────────────────────
  const { navActive, setNavActive, sidebarOpen, setSidebarOpen } = useNavigation()

  // ── API health ──────────────────────────────────────────────────────────
  const { apiStatus, apiBaseUrl, setApiBaseUrl } = useApiHealth()

  // ── Chat threads (authUser wired after useAuth, but hook reads it reactively) ──
  const {
    threads, setThreads,
    selectedThread, selectedThreadId, setSelectedThreadId,
    selectedMessage, selectedMessageId, setSelectedMessageId,
    upsertThread,
    newThread, deleteThread,
    openRename, renameThread,
    renameOpen, renameThreadId, setRenameOpen, setRenameThreadId,
    setAuthUserForSync,
  } = useChatThreads({ setNavActive })

  // ── Auth ────────────────────────────────────────────────────────────────
  const {
    authUser, authLoading, showLogin, setShowLogin,
    handleLogin, handleLogout, handleSkipLogin,
  } = useAuth({ setThreads, setSelectedThreadId })

  // Wire authUser into thread sync reactively
  useEffect(() => {
    setAuthUserForSync(authUser)
  }, [authUser, setAuthUserForSync])

  // ── Profile ─────────────────────────────────────────────────────────────
  const {
    userName, userEmail, profileHasName,
    setNameOpen, setSetNameOpen, handleSetName,
  } = useProfile({ threadId: selectedThread?.id ?? selectedThreadId })

  // ── Chat streaming ──────────────────────────────────────────────────────
  const {
    streamingThinking, streamingResponse, isThinking,
    streamPhase, streamStatusLog, intentPreview, agentThinkingState,
    typing, researching, useStreaming, setUseStreaming, currentMood,
    handleSend, handleResearch, pickQuickAction,
  } = useChatStream({ selectedThread, upsertThread })

  // ── Local UI state ──────────────────────────────────────────────────────
  const [search, setSearch] = useState('')
  const [xrayMode, setXrayMode] = useState(false)
  const [demoModeOpen, setDemoModeOpen] = useState(false)
  const [tutorialOpen, setTutorialOpen] = useState(false)
  const [sourceInspectorMemoryId, setSourceInspectorMemoryId] = useState<string | null>(null)
  const [agentPanelMessageId, setAgentPanelMessageId] = useState<string | null>(null)

  // Model selection
  const [selectedModel, setSelectedModel] = useState<string>(() => {
    return localStorage.getItem('crt_selected_model') || 'crt-reasoning'
  })
  useEffect(() => {
    localStorage.setItem('crt_selected_model', selectedModel)
  }, [selectedModel])

  // Tutorial on first visit
  useEffect(() => {
    const tutorialCompleted = localStorage.getItem('crt-tutorial-completed')
    if (!tutorialCompleted && threads.length > 0) {
      const timer = setTimeout(() => setTutorialOpen(true), 1000)
      return () => clearTimeout(timer)
    }
  }, [threads.length])

  // ── Early returns ───────────────────────────────────────────────────────
  if (showLogin && !authUser) {
    return <LoginScreen onLogin={handleLogin} onSkip={handleSkipLogin} />
  }

  if (authLoading) {
    return (
      <div className="aetheris-dark h-screen w-full flex items-center justify-center">
        <div className="text-white/60">Loading...</div>
      </div>
    )
  }

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="aetheris-dark h-screen w-full overflow-hidden relative">
      <MoodBackground mood={currentMood} isThinking={isThinking} />
      {currentMood && <MoodIndicator mood={currentMood} />}

      <div className="mx-auto h-full max-w-[1480px] px-2 py-2 sm:px-4 sm:py-4 lg:py-6 relative z-10">
        <div className="flex h-full min-h-0 gap-2 sm:gap-3 lg:gap-5">
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
            apiStatus={apiStatus}
            apiBaseUrl={apiBaseUrl}
            onChangeApiBaseUrl={setApiBaseUrl}
            authUser={authUser}
            onLogout={handleLogout}
            onShowLogin={() => setShowLogin(true)}
          />

          <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2 sm:gap-3 lg:gap-4">
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
              onToggleStreaming={() => setUseStreaming((v: boolean) => !v)}
              selectedModel={selectedModel}
              onModelChange={setSelectedModel}
              onLogout={handleLogout}
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
                ) : navActive === 'showcase' ? (
                  <ShowcasePage />
                ) : navActive === 'copilot' ? (
                  <CopilotPage threadId={selectedThread?.id ?? 'default'} />
                ) : navActive === 'live' ? (
                  <LiveFeedPage />
                ) : navActive === 'telemetry' ? (
                  <TelemetryPage threadId={selectedThread?.id} />
                ) : (
                  <DocsPage />
                )}
              </main>
            </div>
          </div>
        </div>
      </div>

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
        onSubmit={(name) => handleSetName(name, selectedThread?.id ?? selectedThreadId)}
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
        onPromote={() => {}}
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
