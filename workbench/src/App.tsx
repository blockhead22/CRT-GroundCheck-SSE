import { Database, MessagesSquare, ShieldCheck, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { ChatPanel } from './components/ChatPanel'
import { Header } from './components/Header'
import { MemoryDrawer } from './components/MemoryDrawer'
import { SettingsPopover } from './components/SettingsPopover'
import { TraceDrawer } from './components/TraceDrawer'
import type { Health, ModelInfo, Trace, Turn } from './types'
import './styles.css'

type Drawer = 'trace' | 'memory' | null

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [model, setModel] = useState('qwen2.5:7b-instruct')
  const [conversationId, setConversationId] = useState<string | null>(() => localStorage.getItem('aether.currentConversation'))
  const [turns, setTurns] = useState<Turn[]>([])
  const [trace, setTrace] = useState<Trace | null>(null)
  const [drawer, setDrawer] = useState<Drawer>(null)
  const [settings, setSettings] = useState(false)
  const [pinned, setPinned] = useState(true)
  const [floating, setFloating] = useState(false)
  const [memoryRefresh, setMemoryRefresh] = useState(0)

  useEffect(() => {
    Promise.allSettled([api.health(), api.models()]).then(([healthResult, modelsResult]) => {
      if (healthResult.status === 'fulfilled') {
        setHealth(healthResult.value)
        setModel(healthResult.value.model)
      }
      if (modelsResult.status === 'fulfilled') setModels(modelsResult.value)
    })
    const unsubscribe = window.aetherDesktop?.onSidecarStatus(() => {
      api.health().then(setHealth).catch(() => setHealth(null))
    })
    return unsubscribe
  }, [])

  useEffect(() => {
    if (!conversationId) return
    localStorage.setItem('aether.currentConversation', conversationId)
    api.turns(conversationId).then(setTurns).catch(() => setTurns([]))
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
          turns={turns}
          codexAvailable={Boolean(health?.codex_available)}
          onConversation={setConversationId}
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
        </nav>
      </section>
      {drawer ? (
        <aside className="drawer" aria-label={`${drawer} drawer`}>
          <div className="drawer-header">
            <div>
              {drawer === 'trace' ? <ShieldCheck size={18} /> : <Database size={18} />}
              <span>{drawer === 'trace' ? 'Release trace' : 'Governed memory'}</span>
            </div>
            <button aria-label="Close drawer" onClick={() => {
              setDrawer(null)
              void window.aetherDesktop?.setExpanded(false)
            }}><X size={17} /></button>
          </div>
          {drawer === 'trace'
            ? <TraceDrawer trace={trace} />
            : <MemoryDrawer refreshKey={memoryRefresh} onMutated={() => setMemoryRefresh((value) => value + 1)} />}
        </aside>
      ) : null}
    </div>
  )
}
