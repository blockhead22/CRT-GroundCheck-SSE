import { Brain, Database, MessagesSquare, ShieldCheck, X } from 'lucide-react'
import { Sparkles } from 'lucide-react'
import { GitBranch } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { ChatPanel } from './components/ChatPanel'
import { ConsolidationDrawer } from './components/ConsolidationDrawer'
import { Header } from './components/Header'
import { MemoryDrawer } from './components/MemoryDrawer'
import { ReflectionDrawer } from './components/ReflectionDrawer'
import { SettingsPopover } from './components/SettingsPopover'
import { SupportPatternDrawer } from './components/SupportPatternDrawer'
import { TraceDrawer } from './components/TraceDrawer'
import type { Conversation, Health, ModelInfo, PatchApplyReceipt, RenderProvider, ReviewDraftHandoff, Trace, Turn } from './types'
import './styles.css'

type Drawer = 'trace' | 'memory' | 'reflect' | 'support' | 'learn' | null
const RENDER_PROVIDER_STORAGE_KEY = 'aether.renderProvider'

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [model, setModel] = useState('qwen3:14b')
  const [renderProvider, setRenderProvider] = useState<RenderProvider>(() => (
    localStorage.getItem(RENDER_PROVIDER_STORAGE_KEY) === 'grok_build'
      ? 'grok_build'
      : 'local'
  ))
  const [conversationId, setConversationId] = useState<string | null>(() => localStorage.getItem('aether.currentConversation'))
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [turns, setTurns] = useState<Turn[]>([])
  const [trace, setTrace] = useState<Trace | null>(null)
  const [drawer, setDrawer] = useState<Drawer>(null)
  const [settings, setSettings] = useState(false)
  const [traceError, setTraceError] = useState('')
  const [pinned, setPinned] = useState(true)
  const [floating, setFloating] = useState(false)
  const [memoryRefresh, setMemoryRefresh] = useState(0)
  const [memoryPreselectSlot, setMemoryPreselectSlot] = useState<string | null>(null)
  const [memoryDraftHandoff, setMemoryDraftHandoff] = useState<ReviewDraftHandoff | null>(null)
  const [supportDraftHandoff, setSupportDraftHandoff] = useState<ReviewDraftHandoff | null>(null)
  const [reflectionDraftHandoff, setReflectionDraftHandoff] = useState<ReviewDraftHandoff | null>(null)

  useEffect(() => {
    localStorage.setItem(RENDER_PROVIDER_STORAGE_KEY, renderProvider)
  }, [renderProvider])

  useEffect(() => {
    Promise.allSettled([api.health(), api.models(), api.conversations()]).then(([healthResult, modelsResult, conversationsResult]) => {
      if (healthResult.status === 'fulfilled') {
        setHealth(healthResult.value)
        setModel(healthResult.value.model)
      }
      if (modelsResult.status === 'fulfilled') setModels(modelsResult.value)
      if (conversationsResult.status === 'fulfilled') {
        setConversations(conversationsResult.value)
        const saved = localStorage.getItem('aether.currentConversation')
        if (saved && !conversationsResult.value.some((item) => item.conversation_id === saved)) {
          localStorage.removeItem('aether.currentConversation')
          setConversationId(null)
        }
      }
    })
    const unsubscribe = window.aetherDesktop?.onSidecarStatus(() => {
      api.health().then(setHealth).catch(() => setHealth(null))
    })
    return unsubscribe
  }, [])

  useEffect(() => {
    if (!conversationId) {
      localStorage.removeItem('aether.currentConversation')
      setTurns([])
      return
    }
    localStorage.setItem('aether.currentConversation', conversationId)
    api.turns(conversationId).then(setTurns).catch(() => setTurns([]))
    api.conversations().then(setConversations).catch(() => {})
  }, [conversationId])

  const toggleDrawer = useCallback((next: Exclude<Drawer, null>) => {
    setMemoryPreselectSlot(null)
    setMemoryDraftHandoff(null)
    setSupportDraftHandoff(null)
    setReflectionDraftHandoff(null)
    setDrawer((current) => {
      const value = current === next ? null : next
      void window.aetherDesktop?.setExpanded(Boolean(value))
      return value
    })
    setSettings(false)
  }, [])

  const openReviewSurface = useCallback((next: 'memory' | 'support' | 'reflect', options?: { slotId?: string; draftHandoff?: ReviewDraftHandoff }) => {
    setMemoryPreselectSlot(next === 'memory' ? options?.slotId || null : null)
    setMemoryDraftHandoff(next === 'memory' ? options?.draftHandoff || null : null)
    setSupportDraftHandoff(next === 'support' ? options?.draftHandoff || null : null)
    setReflectionDraftHandoff(next === 'reflect' ? options?.draftHandoff || null : null)
    setDrawer(next)
    setSettings(false)
    void window.aetherDesktop?.setExpanded(true)
  }, [])

  async function togglePinned() {
    const next = !pinned
    setPinned(next)
    await window.aetherDesktop?.setAlwaysOnTop(next)
  }

  async function toggleFloating() {
    const next = !floating
    setFloating(next)
    await window.aetherDesktop?.setFloating(next)
  }

  async function applyPatch(toolRunId: string): Promise<PatchApplyReceipt> {
    const receipt = await api.applyPatch(toolRunId, `apply-patch-${crypto.randomUUID()}`)
    if (trace?.turn_id) {
      const refreshed = await api.trace(trace.turn_id)
      setTrace(refreshed.trace)
    }
    return receipt
  }

  async function openTurnTrace(turnId: string) {
    setTraceError('')
    setSettings(false)
    setDrawer('trace')
    void window.aetherDesktop?.setExpanded(true)
    try {
      const result = await api.trace(turnId)
      setTrace(result.trace)
    } catch (reason) {
      setTrace(null)
      setTraceError(reason instanceof Error ? reason.message : 'Trace is unavailable for this turn.')
    }
  }

  function startNewConversation() {
    setConversationId(null)
    setTurns([])
    setTrace(null)
  }

  async function deleteCurrentConversation() {
    if (!conversationId) return
    const confirmed = window.confirm(
      'Delete this chat history? Governed memory, saved documents, and reflections will be preserved.',
    )
    if (!confirmed) return
    await api.deleteConversation(conversationId)
    const remaining = await api.conversations()
    setConversations(remaining)
    startNewConversation()
  }

  return (
    <div className={`app-shell ${drawer ? 'expanded' : ''}`}>
      <section className="dock">
        <Header
          connected={Boolean(health?.ok)}
          pinned={pinned}
          floating={floating}
          onTogglePinned={togglePinned}
          onToggleFloating={toggleFloating}
          onToggleSettings={() => setSettings((value) => !value)}
        />
        {settings ? (
          <SettingsPopover
            health={health}
            models={models}
            model={model}
            renderProvider={renderProvider}
            pinned={pinned}
            floating={floating}
            trace={trace}
            onModel={setModel}
            onRenderProvider={setRenderProvider}
            onPinned={(value) => {
              setPinned(value)
              void window.aetherDesktop?.setAlwaysOnTop(value)
            }}
            onFloating={(value) => {
              setFloating(value)
              void window.aetherDesktop?.setFloating(value)
            }}
          />
        ) : null}
        <ChatPanel
          model={model}
          renderProvider={renderProvider}
          conversationId={conversationId}
          conversations={conversations}
          turns={turns}
          codexAvailable={Boolean(health?.codex_available)}
          trace={trace}
          onConversation={(nextConversationId) => {
            setConversationId(nextConversationId)
            api.conversations().then(setConversations).catch(() => {})
          }}
          onNewConversation={startNewConversation}
          onDeleteConversation={() => void deleteCurrentConversation()}
          onTrace={setTrace}
          onOpenTrace={(turnId) => void openTurnTrace(turnId)}
          onTurns={setTurns}
        />
        <nav className="bottom-nav" aria-label="Workbench panels">
          <button className={!drawer ? 'active' : ''} onClick={() => {
            setDrawer(null)
            setMemoryPreselectSlot(null)
            setMemoryDraftHandoff(null)
            setSupportDraftHandoff(null)
            setReflectionDraftHandoff(null)
            void window.aetherDesktop?.setExpanded(false)
          }}>
            <MessagesSquare size={17} /><span>Chat</span>
          </button>
          <button className={drawer === 'trace' ? 'active' : ''} onClick={() => toggleDrawer('trace')}>
            <ShieldCheck size={17} /><span>Trace</span>
          </button>
          <button className={drawer === 'memory' ? 'active' : ''} onClick={() => toggleDrawer('memory')}>
            <Database size={17} /><span>Memory</span>
          </button>
          <button className={drawer === 'reflect' ? 'active' : ''} onClick={() => toggleDrawer('reflect')}>
            <Brain size={17} /><span>Reflect</span>
          </button>
          <button className={drawer === 'support' ? 'active' : ''} onClick={() => toggleDrawer('support')}>
            <Sparkles size={17} /><span>Support</span>
          </button>
          <button className={drawer === 'learn' ? 'active' : ''} onClick={() => toggleDrawer('learn')}>
            <GitBranch size={17} /><span>Learn</span>
          </button>
        </nav>
      </section>
      {drawer ? (
        <aside className="drawer" aria-label={`${drawer} drawer`}>
          <div className="drawer-header">
            <div>
              {drawer === 'trace' ? <ShieldCheck size={18} /> : drawer === 'memory' ? <Database size={18} /> : drawer === 'reflect' ? <Brain size={18} /> : drawer === 'support' ? <Sparkles size={18} /> : <GitBranch size={18} />}
              <span>{drawer === 'trace' ? 'Release trace' : drawer === 'memory' ? 'Governed memory' : drawer === 'reflect' ? 'Reflection review' : drawer === 'support' ? 'Support review' : 'Learner preview'}</span>
            </div>
            <button aria-label="Close drawer" onClick={() => {
              setDrawer(null)
              setMemoryPreselectSlot(null)
              setMemoryDraftHandoff(null)
              setSupportDraftHandoff(null)
              setReflectionDraftHandoff(null)
              void window.aetherDesktop?.setExpanded(false)
            }}><X size={17} /></button>
          </div>
          {drawer === 'trace'
            ? <TraceDrawer trace={trace} error={traceError} onApplyPatch={applyPatch} />
            : drawer === 'memory'
              ? <MemoryDrawer refreshKey={memoryRefresh} preselectedSlotId={memoryPreselectSlot} draftHandoff={memoryDraftHandoff} onMutated={() => setMemoryRefresh((value) => value + 1)} />
              : drawer === 'reflect'
                ? <ReflectionDrawer draftHandoff={reflectionDraftHandoff} />
                : drawer === 'support'
                  ? <SupportPatternDrawer draftHandoff={supportDraftHandoff} />
                  : <ConsolidationDrawer onOpenReviewSurface={openReviewSurface} />}
        </aside>
      ) : null}
    </div>
  )
}
