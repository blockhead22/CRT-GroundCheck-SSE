import { Brain, Database, Ellipsis, MessagesSquare, ShieldCheck, X } from 'lucide-react'
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
import { WhyThisAnswer } from './components/WhyThisAnswer'
import type { Conversation, Health, ModelInfo, PatchApplyReceipt, RenderProvider, ReviewDraftHandoff, Trace, Turn } from './types'
import { readUiMode, writeUiMode, type UiMode } from './uiMode'
import './styles.css'

type Drawer = 'trace' | 'memory' | 'reflect' | 'support' | 'learn' | 'more' | null
const RENDER_PROVIDER_STORAGE_KEY = 'aether.renderProvider'
const FLOATING_STORAGE_KEY = 'aether.window.floating'
const PINNED_STORAGE_KEY = 'aether.window.pinned'

function readStoredBool(key: string, fallback: boolean): boolean {
  const raw = localStorage.getItem(key)
  if (raw === null) return fallback
  if (raw === 'true' || raw === '1') return true
  if (raw === 'false' || raw === '0') return false
  return fallback
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [model, setModel] = useState('qwen3:14b')
  const [renderProvider, setRenderProvider] = useState<RenderProvider>(() => (
    localStorage.getItem(RENDER_PROVIDER_STORAGE_KEY) === 'grok_build'
      ? 'grok_build'
      : 'local'
  ))
  const [uiMode, setUiMode] = useState<UiMode>(() => readUiMode())
  const [conversationId, setConversationId] = useState<string | null>(() => localStorage.getItem('aether.currentConversation'))
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [turns, setTurns] = useState<Turn[]>([])
  const [trace, setTrace] = useState<Trace | null>(null)
  const [drawer, setDrawer] = useState<Drawer>(null)
  const [settings, setSettings] = useState(false)
  const [traceError, setTraceError] = useState('')
  // Persist window chrome across restarts. First run: floating on (QoL default).
  const [pinned, setPinned] = useState(() => readStoredBool(PINNED_STORAGE_KEY, true))
  const [floating, setFloating] = useState(() => readStoredBool(FLOATING_STORAGE_KEY, true))
  const [autoApproveExactPatchApply, setAutoApproveExactPatchApply] = useState(false)
  const [memoryRefresh, setMemoryRefresh] = useState(0)
  const [memoryPreselectSlot, setMemoryPreselectSlot] = useState<string | null>(null)
  const [memoryDraftHandoff, setMemoryDraftHandoff] = useState<ReviewDraftHandoff | null>(null)
  const [supportDraftHandoff, setSupportDraftHandoff] = useState<ReviewDraftHandoff | null>(null)
  const [reflectionDraftHandoff, setReflectionDraftHandoff] = useState<ReviewDraftHandoff | null>(null)

  const isLab = uiMode === 'lab'

  useEffect(() => {
    localStorage.setItem(RENDER_PROVIDER_STORAGE_KEY, renderProvider)
  }, [renderProvider])

  useEffect(() => {
    writeUiMode(uiMode)
  }, [uiMode])

  useEffect(() => {
    localStorage.setItem(FLOATING_STORAGE_KEY, floating ? 'true' : 'false')
  }, [floating])

  useEffect(() => {
    localStorage.setItem(PINNED_STORAGE_KEY, pinned ? 'true' : 'false')
  }, [pinned])

  // Apply restored window chrome to the desktop shell once on mount.
  useEffect(() => {
    void window.aetherDesktop?.setFloating(floating)
    void window.aetherDesktop?.setAlwaysOnTop(pinned)
    // Intentional mount-only restore of the Electron window state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    Promise.allSettled([
      api.health(),
      api.models(),
      api.conversations(),
      api.toolApprovalPolicy(),
    ]).then(([healthResult, modelsResult, conversationsResult, policyResult]) => {
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
      if (policyResult.status === 'fulfilled') {
        setAutoApproveExactPatchApply(Boolean(policyResult.value.auto_approve_exact_patch_apply))
      }
    })
    const unsubscribe = window.aetherDesktop?.onSidecarStatus(() => {
      api.health().then(setHealth).catch(() => setHealth(null))
    })
    return unsubscribe
  }, [])

  async function setAutoApprovePolicy(next: boolean) {
    setAutoApproveExactPatchApply(next)
    try {
      const policy = await api.setToolApprovalPolicy(next)
      setAutoApproveExactPatchApply(Boolean(policy.auto_approve_exact_patch_apply))
    } catch {
      setAutoApproveExactPatchApply(!next)
    }
  }

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
    localStorage.setItem(PINNED_STORAGE_KEY, next ? 'true' : 'false')
    await window.aetherDesktop?.setAlwaysOnTop(next)
  }

  async function toggleFloating() {
    const next = !floating
    setFloating(next)
    localStorage.setItem(FLOATING_STORAGE_KEY, next ? 'true' : 'false')
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
      'Delete this chat history? What Aether knows (memory), saved documents, and reflections will be preserved.',
    )
    if (!confirmed) return
    await api.deleteConversation(conversationId)
    const remaining = await api.conversations()
    setConversations(remaining)
    startNewConversation()
  }

  function setMode(next: UiMode) {
    setUiMode(next)
    writeUiMode(next)
    // Leaving lab drawers when switching to simple
    if (next === 'simple' && (drawer === 'reflect' || drawer === 'support' || drawer === 'learn' || drawer === 'more')) {
      setDrawer(null)
      void window.aetherDesktop?.setExpanded(false)
    }
  }

  const drawerTitle = (() => {
    if (drawer === 'trace') return isLab ? 'Release trace' : 'Why this answer'
    if (drawer === 'memory') return isLab ? 'Governed memory' : 'What Aether knows'
    if (drawer === 'reflect') return isLab ? 'Reflection review' : 'Things Aether noticed'
    if (drawer === 'support') return isLab ? 'Support review' : 'How it should help'
    if (drawer === 'learn') return isLab ? 'Learner preview' : 'Suggested updates'
    if (drawer === 'more') return 'More tools'
    return ''
  })()

  const drawerExpanded = Boolean(drawer && drawer !== 'more')

  return (
    <div className={`app-shell ${drawerExpanded ? 'expanded' : ''} ui-${uiMode}`}>
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
            uiMode={uiMode}
            pinned={pinned}
            floating={floating}
            autoApproveExactPatchApply={autoApproveExactPatchApply}
            trace={trace}
            onModel={setModel}
            onRenderProvider={setRenderProvider}
            onUiMode={setMode}
            onAutoApproveExactPatchApply={(value) => { void setAutoApprovePolicy(value) }}
            onPinned={(value) => {
              setPinned(value)
              localStorage.setItem(PINNED_STORAGE_KEY, value ? 'true' : 'false')
              void window.aetherDesktop?.setAlwaysOnTop(value)
            }}
            onFloating={(value) => {
              setFloating(value)
              localStorage.setItem(FLOATING_STORAGE_KEY, value ? 'true' : 'false')
              void window.aetherDesktop?.setFloating(value)
            }}
          />
        ) : null}
        <ChatPanel
          model={model}
          renderProvider={renderProvider}
          uiMode={uiMode}
          conversationId={conversationId}
          conversations={conversations}
          turns={turns}
          codexAvailable={Boolean(health?.codex_available)}
          trace={trace}
          onRenderProvider={setRenderProvider}
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
          <button
            className={!drawer ? 'active' : ''}
            onClick={() => {
              setDrawer(null)
              setMemoryPreselectSlot(null)
              setMemoryDraftHandoff(null)
              setSupportDraftHandoff(null)
              setReflectionDraftHandoff(null)
              void window.aetherDesktop?.setExpanded(false)
            }}
          >
            <MessagesSquare size={17} /><span>Chat</span>
          </button>
          <button className={drawer === 'trace' ? 'active' : ''} onClick={() => toggleDrawer('trace')}>
            <ShieldCheck size={17} /><span>{isLab ? 'Trace' : 'Why'}</span>
          </button>
          <button className={drawer === 'memory' ? 'active' : ''} onClick={() => toggleDrawer('memory')}>
            <Database size={17} /><span>{isLab ? 'Memory' : 'Knows'}</span>
          </button>
          {isLab ? (
            <>
              <button className={drawer === 'reflect' ? 'active' : ''} onClick={() => toggleDrawer('reflect')}>
                <Brain size={17} /><span>Reflect</span>
              </button>
              <button className={drawer === 'support' ? 'active' : ''} onClick={() => toggleDrawer('support')}>
                <Sparkles size={17} /><span>Support</span>
              </button>
              <button className={drawer === 'learn' ? 'active' : ''} onClick={() => toggleDrawer('learn')}>
                <GitBranch size={17} /><span>Learn</span>
              </button>
            </>
          ) : (
            <button className={drawer === 'more' ? 'active' : ''} onClick={() => toggleDrawer('more')}>
              <Ellipsis size={17} /><span>More</span>
            </button>
          )}
        </nav>
        {drawer === 'more' && !isLab ? (
          <div className="more-sheet" aria-label="More tools">
            <p className="more-sheet-lead">Advanced tools (Lab). Simple mode keeps chat easy.</p>
            <button type="button" onClick={() => { setMode('lab'); setDrawer('trace'); void window.aetherDesktop?.setExpanded(true) }}>
              <ShieldCheck size={15} /> Switch to Lab mode
            </button>
            <button type="button" onClick={() => { setMode('lab'); setDrawer('reflect'); void window.aetherDesktop?.setExpanded(true) }}>
              <Brain size={15} /> Things Aether noticed
            </button>
            <button type="button" onClick={() => { setMode('lab'); setDrawer('support'); void window.aetherDesktop?.setExpanded(true) }}>
              <Sparkles size={15} /> How it should help
            </button>
            <button type="button" onClick={() => { setMode('lab'); setDrawer('learn'); void window.aetherDesktop?.setExpanded(true) }}>
              <GitBranch size={15} /> Suggested updates
            </button>
            <button type="button" onClick={() => { setSettings(true); setDrawer(null) }}>
              Settings
            </button>
          </div>
        ) : null}
      </section>
      {drawerExpanded ? (
        <aside className="drawer" aria-label={`${drawer} drawer`}>
          <div className="drawer-header">
            <div>
              {drawer === 'trace' ? <ShieldCheck size={18} /> : drawer === 'memory' ? <Database size={18} /> : drawer === 'reflect' ? <Brain size={18} /> : drawer === 'support' ? <Sparkles size={18} /> : <GitBranch size={18} />}
              <span>{drawerTitle}</span>
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
            ? (
              isLab
                ? <TraceDrawer trace={trace} error={traceError} onApplyPatch={applyPatch} />
                : (
                  <WhyThisAnswer
                    trace={trace}
                    error={traceError}
                    onShowLabDetails={() => setMode('lab')}
                    onOpenKnows={(slotId) => openReviewSurface('memory', { slotId })}
                  />
                )
            )
            : drawer === 'memory'
              ? (
                <MemoryDrawer
                  refreshKey={memoryRefresh}
                  uiMode={uiMode}
                  preselectedSlotId={memoryPreselectSlot}
                  draftHandoff={memoryDraftHandoff}
                  onMutated={() => setMemoryRefresh((value) => value + 1)}
                />
              )
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
