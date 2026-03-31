import { motion, AnimatePresence } from 'framer-motion'
import { useCallback, useEffect, useRef, useState } from 'react'
import { getCloudSettings, updateCloudSettings, getAvailableModels, uploadImage, type AvailableModels } from '../../lib/api'
import { ClaudeLogo } from '../icons/ClaudeLogo'
import { OpenAILogo } from '../icons/OpenAILogo'

type GenerationMode = 'local' | 'local_network' | 'cloud_openai' | 'cloud_claude'

const SERVER_ICON = (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
    <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
    <line x1="6" y1="6" x2="6.01" y2="6" />
    <line x1="6" y1="18" x2="6.01" y2="18" />
  </svg>
)

const NETWORK_ICON = (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>
)

const MODEL_OPTIONS: { value: GenerationMode; label: string; shortLabel: string; icon: React.ReactNode }[] = [
  { value: 'local', label: 'Local (Ollama)', shortLabel: 'Local', icon: SERVER_ICON },
  { value: 'local_network', label: 'Network (Ollama/LAN)', shortLabel: 'Network', icon: NETWORK_ICON },
  { value: 'cloud_openai', label: 'Cloud (OpenAI)', shortLabel: 'OpenAI', icon: <OpenAILogo size={12} color="currentColor" /> },
  { value: 'cloud_claude', label: 'Cloud (Claude)', shortLabel: 'Claude', icon: <ClaudeLogo size={12} color="currentColor" /> },
]

export function Composer(props: {
  disabled?: boolean
  placeholder?: string
  onSend: (text: string) => void
  onResearch?: (query: string) => void
  researching?: boolean
  typing?: boolean
  taskWorking?: boolean
  onStop?: () => void
  diagnosticsOpen?: boolean
  onToggleDiagnostics?: () => void
}) {
  const [text, setText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [focused, setFocused] = useState(false)
  const [generationMode, setGenerationMode] = useState<GenerationMode>('local')
  const [modelSelectorOpen, setModelSelectorOpen] = useState(false)
  const [settingsLoaded, setSettingsLoaded] = useState(false)
  const [bypassCrt, setBypassCrt] = useState(false)
  const [enableTooling, setEnableTooling] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [modelsOpen, setModelsOpen] = useState(false)
  const [availableModels, setAvailableModels] = useState<AvailableModels | null>(null)
  const [selectedModelName, setSelectedModelName] = useState<string>('')
  const [attachMenuOpen, setAttachMenuOpen] = useState(false)
  const [attachedPaths, setAttachedPaths] = useState<{ path: string; type: 'file' | 'dir' | 'image' }[]>([])
  const [imageUploading, setImageUploading] = useState(false)
  const selectorRef = useRef<HTMLDivElement>(null)
  const attachRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)

  const canSend = text.trim().length > 0

  // Load current generation mode + available models on mount
  useEffect(() => {
    getCloudSettings()
      .then((settings) => {
        const mode = settings.generation_mode as GenerationMode
        if (mode && ['local', 'local_network', 'cloud_openai', 'cloud_claude'].includes(mode)) {
          setGenerationMode(mode)
        }
        setBypassCrt(settings.bypass_crt === 'true' || settings.bypass_crt === 'on')
        setEnableTooling(settings.enable_tooling === 'true' || settings.enable_tooling === 'on')
        // Track the specific model name for display
        if (mode === 'cloud_openai') setSelectedModelName(settings.cloud_model_openai || 'gpt-4o-mini')
        else if (mode === 'cloud_claude') setSelectedModelName(settings.cloud_model_claude || 'claude-sonnet-4-20250514')
        else if (mode === 'local_network') setSelectedModelName(settings.network_ollama_model || '')
        else setSelectedModelName('')
        setSettingsLoaded(true)
      })
      .catch(() => {
        setSettingsLoaded(true)
      })
    getAvailableModels().then(setAvailableModels).catch(() => {})
  }, [])

  // Close selector on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (selectorRef.current && !selectorRef.current.contains(e.target as Node)) {
        setModelSelectorOpen(false)
        setAdvancedOpen(false)
        setModelsOpen(false)
      }
      if (attachRef.current && !attachRef.current.contains(e.target as Node)) {
        setAttachMenuOpen(false)
      }
    }
    if (modelSelectorOpen || attachMenuOpen) {
      document.addEventListener('mousedown', handleClick)
      return () => document.removeEventListener('mousedown', handleClick)
    }
  }, [modelSelectorOpen, attachMenuOpen])

  /** Add a file/folder path as an attached reference pill */
  function insertPathReference(type: 'file' | 'folder' | 'working') {
    setAttachMenuOpen(false)
    if (type === 'working') {
      const ref = 'D:/AI_round2'
      setAttachedPaths((prev) => prev.some((p) => p.path === ref) ? prev : [...prev, { path: ref, type: 'dir' }])
      textareaRef.current?.focus()
      return
    }
    if (type === 'file') {
      // Trigger the native file picker — Electron exposes the full filesystem
      // path on File objects, so handleFileSelected will capture it.
      fileInputRef.current?.click()
      return
    } else {
      // Browser APIs can't return full filesystem paths (security sandbox),
      // so we use a direct path input for folder targeting.
      const path = window.prompt('Enter folder path (e.g. D:/lumi or C:/projects/my-app):')
      if (path) {
        const normalized = path.replace(/\\/g, '/')
        setAttachedPaths((prev) =>
          prev.some((p) => p.path === normalized) ? prev : [...prev, { path: normalized, type: 'dir' }]
        )
      }
      textareaRef.current?.focus()
    }
  }

  function removeAttachedPath(path: string) {
    setAttachedPaths((prev) => prev.filter((p) => p.path !== path))
  }

  /** Handle file selection from the native picker */
  function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files || files.length === 0) return
    const newPaths: { path: string; type: 'file' | 'dir' }[] = []
    for (let i = 0; i < files.length; i++) {
      const f = files[i]
      // Electron exposes the full filesystem path on File objects.
      // Fall back to name only if path is unavailable (standard browser).
      const raw = (f as unknown as { path?: string }).path || f.name
      const path = raw.replace(/\\/g, '/')
      if (!newPaths.some((p) => p.path === path)) {
        newPaths.push({ path, type: 'file' })
      }
    }
    setAttachedPaths((prev) => {
      const existing = new Set(prev.map((p) => p.path))
      return [...prev, ...newPaths.filter((p) => !existing.has(p.path))]
    })
    e.target.value = ''
    textareaRef.current?.focus()
  }

  /** Upload an image file to the backend and attach the returned path */
  async function handleImageUpload(file: File) {
    if (!file.type.startsWith('image/')) return
    setImageUploading(true)
    try {
      const result = await uploadImage(file)
      if (result.success) {
        setAttachedPaths((prev) =>
          prev.some((p) => p.path === result.path) ? prev : [...prev, { path: result.path, type: 'image' as const }]
        )
      }
    } catch (err) {
      console.warn('[Composer] Image upload failed:', err)
    } finally {
      setImageUploading(false)
    }
  }

  /** Handle image file selection from picker */
  function handleImageSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files) return
    for (let i = 0; i < files.length; i++) {
      handleImageUpload(files[i])
    }
    e.target.value = ''
  }

  /** Handle paste — intercept images from clipboard */
  function handlePaste(e: React.ClipboardEvent) {
    const items = e.clipboardData?.items
    if (!items) return
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        e.preventDefault()
        const file = items[i].getAsFile()
        if (file) handleImageUpload(file)
        return
      }
    }
  }

  /** Handle drop — intercept image files */
  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    const files = e.dataTransfer?.files
    if (!files) return
    for (let i = 0; i < files.length; i++) {
      if (files[i].type.startsWith('image/')) {
        handleImageUpload(files[i])
      }
    }
  }

  // Auto-grow textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [text])

  const send = useCallback(() => {
    const t = text.trim()
    if (!t || props.disabled) return
    // Prepend attached path references so the LLM sees them
    let fullMessage = t
    if (attachedPaths.length > 0) {
      const refs = attachedPaths.map((p) => `[${p.type}: ${p.path}]`).join(' ')
      fullMessage = refs + ' ' + t
    }
    props.onSend(fullMessage)
    setText('')
    setAttachedPaths([])
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [text, props, attachedPaths])

  const research = useCallback(() => {
    const t = text.trim()
    if (!t || !props.onResearch || props.disabled) return
    props.onResearch(t)
    setText('')
  }, [text, props])

  // Escape key to stop generation (global)
  useEffect(() => {
    if (!props.typing || !props.onStop) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault()
        props.onStop?.()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [props.typing, props.onStop])

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  async function handleModelSelect(mode: GenerationMode) {
    setGenerationMode(mode)
    setModelSelectorOpen(false)
    setModelsOpen(false)
    try {
      await updateCloudSettings({ generation_mode: mode })
    } catch (err) {
      console.warn('[Composer] Failed to persist generation mode:', err)
    }
  }

  async function handleSpecificModelSelect(mode: GenerationMode, modelName: string) {
    setGenerationMode(mode)
    setSelectedModelName(modelName)
    setModelSelectorOpen(false)
    setModelsOpen(false)
    try {
      const updates: Record<string, string> = { generation_mode: mode }
      if (mode === 'local') { /* routing_llm_model removed — Layer 4 handles routing */ }
      else if (mode === 'local_network') updates.network_ollama_model = modelName
      else if (mode === 'cloud_openai') updates.cloud_model_openai = modelName
      else if (mode === 'cloud_claude') updates.cloud_model_claude = modelName
      await updateCloudSettings(updates)
    } catch (err) {
      console.warn('[Composer] Failed to persist model selection:', err)
    }
  }

  async function handleAdvancedToggle(key: 'bypass_crt' | 'enable_tooling', value: boolean) {
    const newVal = value ? 'true' : 'false'
    if (key === 'bypass_crt') setBypassCrt(value)
    if (key === 'enable_tooling') setEnableTooling(value)
    try {
      await updateCloudSettings({ [key]: newVal })
    } catch (err) {
      console.warn(`[Composer] Failed to persist ${key}:`, err)
      if (key === 'bypass_crt') setBypassCrt(!value)
      if (key === 'enable_tooling') setEnableTooling(!value)
    }
  }

  const isDisabled = props.disabled || props.researching
  const activeModel = MODEL_OPTIONS.find((m) => m.value === generationMode) ?? MODEL_OPTIONS[0]
  const isLocalMode = generationMode === 'local' || generationMode === 'local_network'
  // Show specific model name if user picked one from All Models
  const displayLabel = selectedModelName && selectedModelName !== ''
    ? (isLocalMode ? selectedModelName.split(':')[0] : selectedModelName.replace(/^gpt-/, '').replace(/^claude-/, 'claude ').split('-20')[0])
    : activeModel.shortLabel

  return (
    <div className="w-full px-4 pb-6 pt-2">
      <div
        className="mx-auto w-full"
        style={{ maxWidth: '760px' }}
      >
        {/* Model selector pill + attached paths - above the input */}
        <div className="mb-2 flex items-center justify-start gap-1.5 flex-wrap" ref={selectorRef}>
          <div className="relative">
            <button
              onClick={() => setModelSelectorOpen(!modelSelectorOpen)}
              className="flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-medium transition-all hover:bg-white/[0.06]"
              style={{
                borderColor: 'rgba(240,235,225,0.08)',
                background: 'rgba(22,20,16,0.6)',
                color: 'rgba(240,235,225,0.5)',
              }}
            >
              <span className="flex items-center gap-1.5">
                {!isLocalMode && (
                  <span style={{ color: 'rgba(212,132,92,0.7)' }}>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
                    </svg>
                  </span>
                )}
                {activeModel.icon}
                <span>{displayLabel}{bypassCrt ? ' (Raw)' : ''}</span>
              </span>
              <svg
                width="8" height="8" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"
                className="ml-0.5 opacity-40"
                style={{ transform: modelSelectorOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }}
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>

            <AnimatePresence>
              {modelSelectorOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 4, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 4, scale: 0.95 }}
                  transition={{ duration: 0.12 }}
                  className="absolute left-0 bottom-full z-50 mb-1 min-w-[200px] rounded border"
                  style={{
                    borderColor: 'rgba(240,235,225,0.08)',
                    background: 'rgba(18,16,12,0.95)',
                    boxShadow: '0 -8px 32px rgba(0,0,0,0.5), 0 -2px 8px rgba(0,0,0,0.3)',
                    maxHeight: '400px',
                    overflowY: 'auto',
                  }}
                >
                  {MODEL_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => handleModelSelect(opt.value)}
                      className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-[12px] transition-colors hover:bg-white/[0.06]"
                      style={{
                        color: generationMode === opt.value ? 'rgba(212,132,92,0.9)' : 'rgba(240,235,225,0.6)',
                      }}
                    >
                      <span className="flex-shrink-0">{opt.icon}</span>
                      <span className="flex-1 font-medium">{opt.label}</span>
                      {generationMode === opt.value && (
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      )}
                    </button>
                  ))}

                  {/* All Models — inline accordion */}
                  <div
                    className="border-t mt-1"
                    style={{ borderColor: 'rgba(240,235,225,0.06)' }}
                  >
                    <button
                      onClick={(e) => { e.stopPropagation(); setModelsOpen(!modelsOpen); setAdvancedOpen(false) }}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-[11px] font-medium uppercase tracking-wide transition-colors hover:bg-white/[0.06]"
                      style={{ color: modelsOpen ? 'rgba(212,132,92,0.7)' : 'rgba(240,235,225,0.3)' }}
                    >
                      <span className="flex-1">All Models</span>
                      <svg
                        width="8" height="8" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"
                        style={{ transform: modelsOpen ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}
                      >
                        <polyline points="6 9 12 15 18 9" />
                      </svg>
                    </button>

                    {/* Inline model list (accordion) */}
                    {modelsOpen && availableModels && (
                      <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
                        {/* Network (Ollama/LAN) models */}
                        {availableModels.local.length > 0 && (
                          <>
                            <div className="px-3 pt-1.5 pb-0.5">
                              <div className="text-[9px] font-medium uppercase tracking-wide" style={{ color: 'rgba(240,235,225,0.25)' }}>
                                Network (Ollama/LAN)
                              </div>
                            </div>
                            {availableModels.local.map((m) => (
                              <button
                                key={`local-${m.name}`}
                                onClick={(e) => { e.stopPropagation(); handleSpecificModelSelect('local_network', m.name) }}
                                className="flex w-full items-center gap-2 px-4 py-1.5 text-left text-[11px] transition-colors hover:bg-white/[0.06]"
                                style={{
                                  color: (generationMode === 'local_network' || generationMode === 'local') && selectedModelName === m.name
                                    ? 'rgba(212,132,92,0.9)' : 'rgba(240,235,225,0.5)',
                                }}
                              >
                                <span className="flex-shrink-0 opacity-40">{NETWORK_ICON}</span>
                                <span className="flex-1 font-medium truncate">{m.name}</span>
                                {m.size && <span className="text-[9px] opacity-25 flex-shrink-0">{m.size}</span>}
                                {(generationMode === 'local_network' || generationMode === 'local') && selectedModelName === m.name && (
                                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0"><polyline points="20 6 9 17 4 12" /></svg>
                                )}
                              </button>
                            ))}
                          </>
                        )}

                        {/* OpenAI models */}
                        {availableModels.cloud.length > 0 && (
                          <>
                            <div className="px-3 pt-2 pb-0.5 border-t" style={{ borderColor: 'rgba(240,235,225,0.05)' }}>
                              <div className="text-[9px] font-medium uppercase tracking-wide" style={{ color: 'rgba(240,235,225,0.25)' }}>
                                OpenAI
                              </div>
                            </div>
                            {availableModels.cloud.map((m) => (
                              <button
                                key={`cloud-${m.name}`}
                                onClick={(e) => { e.stopPropagation(); handleSpecificModelSelect('cloud_openai', m.name) }}
                                className="flex w-full items-center gap-2 px-4 py-1.5 text-left text-[11px] transition-colors hover:bg-white/[0.06]"
                                style={{
                                  color: generationMode === 'cloud_openai' && selectedModelName === m.name
                                    ? 'rgba(212,132,92,0.9)' : 'rgba(240,235,225,0.5)',
                                }}
                              >
                                <span className="flex-shrink-0"><OpenAILogo size={11} color="currentColor" /></span>
                                <span className="flex-1 font-medium truncate">{m.label || m.name}</span>
                                {generationMode === 'cloud_openai' && selectedModelName === m.name && (
                                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0"><polyline points="20 6 9 17 4 12" /></svg>
                                )}
                              </button>
                            ))}
                          </>
                        )}

                        {/* Anthropic models */}
                        {availableModels.anthropic.length > 0 && (
                          <>
                            <div className="px-3 pt-2 pb-0.5 border-t" style={{ borderColor: 'rgba(240,235,225,0.05)' }}>
                              <div className="text-[9px] font-medium uppercase tracking-wide" style={{ color: 'rgba(240,235,225,0.25)' }}>
                                Anthropic
                              </div>
                            </div>
                            {availableModels.anthropic.map((m) => (
                              <button
                                key={`anthropic-${m.name}`}
                                onClick={(e) => { e.stopPropagation(); handleSpecificModelSelect('cloud_claude', m.name) }}
                                className="flex w-full items-center gap-2 px-4 py-1.5 text-left text-[11px] transition-colors hover:bg-white/[0.06]"
                                style={{
                                  color: generationMode === 'cloud_claude' && selectedModelName === m.name
                                    ? 'rgba(212,132,92,0.9)' : 'rgba(240,235,225,0.5)',
                                }}
                              >
                                <span className="flex-shrink-0"><ClaudeLogo size={11} color="currentColor" /></span>
                                <span className="flex-1 font-medium truncate">{m.label || m.name}</span>
                                {generationMode === 'cloud_claude' && selectedModelName === m.name && (
                                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0"><polyline points="20 6 9 17 4 12" /></svg>
                                )}
                              </button>
                            ))}
                          </>
                        )}
                      </div>
                    )}

                    {/* Advanced toggle */}
                    <button
                      onClick={(e) => { e.stopPropagation(); setAdvancedOpen(!advancedOpen); setModelsOpen(false) }}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-[11px] font-medium uppercase tracking-wide transition-colors hover:bg-white/[0.06]"
                      style={{ color: advancedOpen ? 'rgba(212,132,92,0.7)' : 'rgba(240,235,225,0.3)' }}
                    >
                      <span className="flex-1">Advanced</span>
                      <svg
                        width="8" height="8" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"
                        style={{ transform: advancedOpen ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}
                      >
                        <polyline points="6 9 12 15 18 9" />
                      </svg>
                    </button>

                    {/* Inline advanced toggles (accordion) */}
                    {advancedOpen && (
                      <div className="px-3 pb-2.5 space-y-1">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleAdvancedToggle('bypass_crt', !bypassCrt) }}
                          className="flex w-full items-center gap-2.5 py-1.5 text-left text-[12px] transition-colors hover:bg-white/[0.06] rounded px-1"
                          style={{ color: 'rgba(240,235,225,0.6)' }}
                        >
                          <span
                            className="flex-shrink-0 h-3.5 w-7 rounded-full relative transition-colors"
                            style={{ background: bypassCrt ? 'rgba(212,132,92,0.6)' : 'rgba(240,235,225,0.1)' }}
                          >
                            <span
                              className="absolute top-[2px] h-2.5 w-2.5 rounded-full bg-white shadow transition-transform"
                              style={{ left: bypassCrt ? '13px' : '2px' }}
                            />
                          </span>
                          <span className="flex-1 font-medium">Bypass CRT</span>
                        </button>

                        <button
                          onClick={(e) => { e.stopPropagation(); handleAdvancedToggle('enable_tooling', !enableTooling) }}
                          className="flex w-full items-center gap-2.5 py-1.5 text-left text-[12px] transition-colors hover:bg-white/[0.06] rounded px-1"
                          style={{ color: 'rgba(240,235,225,0.6)' }}
                        >
                          <span
                            className="flex-shrink-0 h-3.5 w-7 rounded-full relative transition-colors"
                            style={{ background: enableTooling ? 'rgba(212,132,92,0.6)' : 'rgba(240,235,225,0.1)' }}
                          >
                            <span
                              className="absolute top-[2px] h-2.5 w-2.5 rounded-full bg-white shadow transition-transform"
                              style={{ left: enableTooling ? '13px' : '2px' }}
                            />
                          </span>
                          <span className="flex-1 font-medium">Tooling</span>
                        </button>
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Advanced side card removed — now inline accordion above */}
          </div>

          {/* Diagnostics toggle */}
          {props.onToggleDiagnostics && (
            <button
              onClick={props.onToggleDiagnostics}
              className="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-mono transition-all hover:bg-white/[0.06]"
              style={{
                borderColor: props.diagnosticsOpen ? 'rgba(212,132,92,0.3)' : 'rgba(240,235,225,0.08)',
                background: props.diagnosticsOpen ? 'rgba(212,132,92,0.1)' : 'rgba(22,20,16,0.6)',
                color: props.diagnosticsOpen ? 'var(--accent)' : 'rgba(240,235,225,0.35)',
              }}
              title="Toggle diagnostics console"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="4 17 10 11 4 5" />
                <line x1="12" y1="19" x2="20" y2="19" />
              </svg>
              <span className="tracking-wider uppercase text-[9px]">Log</span>
            </button>
          )}

          {/* Attached path pills */}
          {attachedPaths.map((ap) => {
            const name = ap.path.replace(/\\/g, '/').split('/').pop() || ap.path
            return (
              <div
                key={ap.path}
                className="flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-mono"
                style={{
                  borderColor: 'rgba(212,132,92,0.25)',
                  background: 'rgba(212,132,92,0.08)',
                  color: 'rgba(240,235,225,0.7)',
                }}
                title={ap.path}
              >
                <svg
                  width="10" height="10" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                  style={{ opacity: 0.5, flexShrink: 0 }}
                >
                  {ap.type === 'dir' ? (
                    <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
                  ) : ap.type === 'image' ? (
                    <>
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                      <circle cx="8.5" cy="8.5" r="1.5" />
                      <polyline points="21 15 16 10 5 21" />
                    </>
                  ) : (
                    <>
                      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </>
                  )}
                </svg>
                <span style={{ maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {name}
                </span>
                <button
                  onClick={() => removeAttachedPath(ap.path)}
                  className="flex items-center justify-center rounded-full hover:bg-white/10 transition-colors"
                  style={{ width: '14px', height: '14px', flexShrink: 0 }}
                  title="Remove"
                >
                  <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            )
          })}
        </div>

        {/* Hidden file inputs for native OS file picker */}
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={(e) => handleFileSelected(e)}
        />
        <input
          ref={imageInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => handleImageSelected(e)}
        />

        {/* Main input container */}
        <motion.div
          animate={{
            boxShadow: props.taskWorking
              ? [
                  '0 0 0 0 rgba(212,132,92,0.3)',
                  '0 0 12px 4px rgba(212,132,92,0.15)',
                  '0 0 0 0 rgba(212,132,92,0.3)',
                ]
              : focused
                ? '0 0 0 1px rgba(212,132,92,0.3), 0 8px 32px rgba(0,0,0,0.4), 0 0 48px rgba(212,132,92,0.06)'
                : '0 2px 12px rgba(0,0,0,0.2), 0 1px 4px rgba(0,0,0,0.15)',
            borderColor: props.taskWorking
              ? 'rgba(212,132,92,0.35)'
              : focused
                ? 'rgba(212,132,92,0.25)'
                : 'rgba(240,235,225,0.06)',
          }}
          transition={props.taskWorking
            ? { duration: 2, ease: 'easeInOut', repeat: Infinity }
            : { duration: 0.2 }
          }
          className="relative border"
          style={{
            background: 'var(--surface)',
            borderRadius: '8px',
          }}
        >
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            disabled={isDisabled}
            placeholder={props.placeholder ?? 'Message Aether...'}
            rows={1}
            className="w-full resize-none bg-transparent px-5 pb-3 pt-4 text-[15px] leading-relaxed text-white/90 placeholder:text-white/20 focus:outline-none disabled:opacity-50"
            style={{ scrollbarWidth: 'none' }}
            autoComplete="off"
            spellCheck="true"
          />

          {/* Bottom bar with attach + hint + buttons */}
          <div className="flex items-center justify-between px-5 pb-3">
            <div className="flex items-center gap-2">
              {/* + attach button */}
              <div className="relative" ref={attachRef}>
                <motion.button
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  onClick={() => setAttachMenuOpen(!attachMenuOpen)}
                  className="flex h-6 w-6 items-center justify-center rounded-full border transition-all hover:bg-white/[0.08]"
                  style={{
                    borderColor: attachMenuOpen ? 'rgba(212,132,92,0.3)' : 'rgba(240,235,225,0.08)',
                    background: attachMenuOpen ? 'rgba(212,132,92,0.1)' : 'transparent',
                    color: attachMenuOpen ? 'rgba(212,132,92,0.9)' : 'rgba(240,235,225,0.3)',
                  }}
                  title="Attach file or folder reference"
                >
                  <svg
                    width="12" height="12" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                    style={{ transform: attachMenuOpen ? 'rotate(45deg)' : 'none', transition: 'transform 0.15s' }}
                  >
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                </motion.button>

                <AnimatePresence>
                  {attachMenuOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 8, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 8, scale: 0.95 }}
                      transition={{ duration: 0.12 }}
                      className="absolute bottom-full left-0 z-50 mb-2 min-w-[170px] overflow-hidden rounded-lg border"
                      style={{
                        borderColor: 'rgba(240,235,225,0.08)',
                        background: 'rgba(18,16,12,0.95)',
                        boxShadow: '0 -8px 32px rgba(0,0,0,0.5), 0 -2px 8px rgba(0,0,0,0.3)',
                      }}
                    >
                      <div className="px-3 pt-2 pb-1">
                        <div className="text-[9px] font-medium uppercase tracking-wider" style={{ color: 'rgba(240,235,225,0.25)' }}>
                          Reference
                        </div>
                      </div>

                      <button
                        onClick={() => insertPathReference('file')}
                        className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-[12px] transition-colors hover:bg-white/[0.06]"
                        style={{ color: 'rgba(240,235,225,0.7)' }}
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.5 }}>
                          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                          <polyline points="14 2 14 8 20 8" />
                        </svg>
                        <span>Add file path</span>
                      </button>

                      <button
                        onClick={() => insertPathReference('folder')}
                        className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-[12px] transition-colors hover:bg-white/[0.06]"
                        style={{ color: 'rgba(240,235,225,0.7)' }}
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.5 }}>
                          <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
                        </svg>
                        <span>Add folder path</span>
                      </button>

                      <button
                        onClick={() => { setAttachMenuOpen(false); imageInputRef.current?.click() }}
                        className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-[12px] transition-colors hover:bg-white/[0.06]"
                        style={{ color: 'rgba(240,235,225,0.7)' }}
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.5 }}>
                          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                          <circle cx="8.5" cy="8.5" r="1.5" />
                          <polyline points="21 15 16 10 5 21" />
                        </svg>
                        <span>{imageUploading ? 'Uploading...' : 'Upload image'}</span>
                      </button>

                      <div style={{ borderTop: '1px solid rgba(240,235,225,0.06)' }}>
                        <button
                          onClick={() => insertPathReference('working')}
                          className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-[12px] transition-colors hover:bg-white/[0.06]"
                          style={{ color: 'rgba(240,235,225,0.5)' }}
                        >
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.4 }}>
                            <circle cx="12" cy="12" r="10" />
                            <line x1="2" y1="12" x2="22" y2="12" />
                            <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
                          </svg>
                          <span>Working directory</span>
                        </button>

                        <button
                          onClick={() => {
                            setAttachMenuOpen(false)
                            const path = window.prompt('Enter full path (file or folder):')
                            if (path) {
                              const normalized = path.replace(/\\/g, '/')
                              const isDir = !normalized.includes('.') || normalized.endsWith('/')
                              setAttachedPaths((prev) =>
                                prev.some((p) => p.path === normalized)
                                  ? prev
                                  : [...prev, { path: normalized, type: isDir ? 'dir' : 'file' }]
                              )
                            }
                            textareaRef.current?.focus()
                          }}
                          className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-[12px] transition-colors hover:bg-white/[0.06]"
                          style={{ color: 'rgba(240,235,225,0.5)' }}
                        >
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.4 }}>
                            <polyline points="4 17 10 11 4 5" />
                            <line x1="12" y1="19" x2="20" y2="19" />
                          </svg>
                          <span>Type path...</span>
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              <div className="text-[10px] text-white/15 font-mono">
                {props.typing ? 'Esc to stop' : canSend ? 'Enter to send' : ''}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {props.onResearch ? (
                <motion.button
                  whileHover={canSend && !isDisabled ? { scale: 1.05 } : undefined}
                  whileTap={canSend && !isDisabled ? { scale: 0.95 } : undefined}
                  onClick={research}
                  disabled={isDisabled || !canSend}
                  title="Deep research"
                  className="flex h-8 w-8 items-center justify-center rounded bg-white/[0.04] text-white/30 transition-all hover:bg-white/[0.08] hover:text-white/60 disabled:cursor-not-allowed disabled:opacity-20"
                >
                  {props.researching ? (
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/20 border-t-white/70" />
                  ) : (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="11" cy="11" r="8" />
                      <line x1="21" y1="21" x2="16.65" y2="16.65" />
                    </svg>
                  )}
                </motion.button>
              ) : null}

              <AnimatePresence mode="wait">
                {props.typing && props.onStop ? (
                  <motion.button
                    key="stop"
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0.8, opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={props.onStop}
                    aria-label="Stop generation"
                    title="Stop generation (Esc)"
                    className="flex h-8 w-8 items-center justify-center rounded bg-[var(--accent)] text-white hover:opacity-90 shadow-[0_0_16px_rgba(212,132,92,0.35)]"
                  >
                    <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                      <rect x="2" y="2" width="12" height="12" rx="1.5" />
                    </svg>
                  </motion.button>
                ) : (
                  <motion.button
                    key="send"
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0.8, opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    whileHover={canSend && !isDisabled ? { scale: 1.05 } : undefined}
                    whileTap={canSend && !isDisabled ? { scale: 0.95 } : undefined}
                    onClick={send}
                    disabled={isDisabled || !canSend}
                    aria-label="Send"
                    className={`flex h-8 w-8 items-center justify-center rounded transition-all ${
                      canSend && !isDisabled
                        ? 'bg-[var(--accent)] text-white hover:opacity-90 shadow-[0_0_16px_rgba(212,132,92,0.35)]'
                        : 'bg-white/[0.04] text-white/15 cursor-not-allowed'
                    }`}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 12h14" />
                      <path d="M12 5l7 7-7 7" />
                    </svg>
                  </motion.button>
                )}
              </AnimatePresence>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
