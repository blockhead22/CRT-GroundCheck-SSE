import { Brain, Database, MessagesSquare, ShieldCheck, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { ChatPanel } from './components/ChatPanel'
import { Header } from './components/Header'
import { MemoryDrawer } from './components/MemoryDrawer'
import { ReflectionDrawer } from './components/ReflectionDrawer'
import { SettingsPopover } from './components/SettingsPopover'
import { TraceDrawer } from './components/TraceDrawer'
import type { Conversation, Health, ModelInfo, PatchApplyReceipt, Trace, Turn } from './types'
import './styles.css'

type Drawer = 'trace' | 'memory' | 'reflect' | null

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [model, setModel] = useState('qwen2.5:7b-instruct')
  const [conversationId, setConversationId] = useState<string | null>(() => localStorage.getItem('aether.currentConversation'))
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [turns, setTurns] = useState<Turn[]>([])
  const [trace, setTrace] = useState<Trace | null>(null)
  const [drawer, setDrawer] = useState<Drawer>(null)
  const [settings, setSettings] = useState(false)
  const [pinned, setPinned] = useState(true)
  const [floating, setFloating] = useState(false)
  const [memoryRefresh, setMemoryRefresh] = useState(0)

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
    setDrawer((current) => {
      const value = current === next ? null : next
      void window.aetherDesktop?.setExpanded(Boolean(value))
      return value
    })
    setSettings(false)
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
            pinned={pinned}
            floating={floating}
            onModel={setModel}
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
          conversationId={conversationId}
          conversations={conversations}
          turns={turns}
          codexAvailable={Boolean(health?.codex_available)}
          onConversation={(nextConversationId) => {
            setConversationId(nextConversationId)
            api.conversations().then(setConversations).catch(() => {})
          }}
          onNewConversation={startNewConversation}
          onDeleteConversation={() => void deleteCurrentConversation()}
          onTrace={setTrace}
          onTurns={setTurns}
        />
        <nav className="bottom-nav" aria-label="Workbench panels">
          <button className={!drawer ? 'active' : ''} onClick={() => {
            setDrawer(null)
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
        </nav>
      </section>
      {drawer ? (
        <aside className="drawer" aria-label={`${drawer} drawer`}>
          <div className="drawer-header">
            <div>
              {drawer === 'trace' ? <ShieldCheck size={18} /> : drawer === 'memory' ? <Database size={18} /> : <Brain size={18} />}
              <span>{drawer === 'trace' ? 'Release trace' : drawer === 'memory' ? 'Governed memory' : 'Reflection review'}</span>
            </div>
            <button aria-label="Close drawer" onClick={() => {
              setDrawer(null)
              void window.aetherDesktop?.setExpanded(false)
            }}><X size={17} /></button>
          </div>
          {drawer === 'trace'
            ? <TraceDrawer trace={trace} onApplyPatch={applyPatch} />
            : drawer === 'memory'
              ? <MemoryDrawer refreshKey={memoryRefresh} onMutated={() => setMemoryRefresh((value) => value + 1)} />
              : <ReflectionDrawer />}
        </aside>
      ) : null}
    </div>
  )
}
