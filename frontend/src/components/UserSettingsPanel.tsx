import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export type ModelOption = {
  id: string
  name: string
  provider: string
  description: string
  isLocal: boolean
  isReasoning?: boolean
}

const AVAILABLE_MODELS: ModelOption[] = [
  {
    id: 'ollama-llama3.2',
    name: 'Llama 3.2',
    provider: 'Ollama (Local)',
    description: 'Fast local inference',
    isLocal: true,
  },
  {
    id: 'ollama-mistral',
    name: 'Mistral',
    provider: 'Ollama (Local)',
    description: 'Efficient and capable',
    isLocal: true,
  },
  {
    id: 'ollama-phi',
    name: 'Phi-3',
    provider: 'Ollama (Local)',
    description: 'Lightweight and quick',
    isLocal: true,
  },
  {
    id: 'crt-reasoning',
    name: 'CRT Reasoning',
    provider: 'Built-in',
    description: 'LLM-guided fact-based reasoning',
    isLocal: true,
    isReasoning: true,
  },
  {
    id: 'openai-gpt4',
    name: 'GPT-4',
    provider: 'OpenAI',
    description: 'Requires API key',
    isLocal: false,
  },
  {
    id: 'openai-o1',
    name: 'o1-preview',
    provider: 'OpenAI',
    description: 'Reasoning model (requires API key)',
    isLocal: false,
    isReasoning: true,
  },
]

export function UserSettingsPanel(props: {
  isOpen: boolean
  onClose: () => void
  userName: string
  userEmail: string
  selectedModel?: string
  onModelChange: (modelId: string) => void
  onLogout?: () => void
}) {
  const panelRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        props.onClose()
      }
    }
    if (props.isOpen) {
      document.addEventListener('mousedown', handleClick)
      return () => document.removeEventListener('mousedown', handleClick)
    }
  }, [props.isOpen, props.onClose])

  const currentModel = AVAILABLE_MODELS.find((m) => m.id === props.selectedModel) || AVAILABLE_MODELS[3]

  return (
    <AnimatePresence>
      {props.isOpen && (
        <motion.div
          ref={panelRef}
          initial={{ opacity: 0, y: -10, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -10, scale: 0.95 }}
          transition={{ duration: 0.15 }}
          className="absolute right-0 top-[calc(100%+8px)] z-50 w-[380px] overflow-hidden rounded-2xl glass-panel border border-white/10 shadow-2xl"
        >
          {/* Header */}
          <div className="border-b border-white/10 bg-white/5 p-4">
            <div className="flex items-center gap-3">
              <div className="grid h-12 w-12 place-items-center rounded-full accent-button text-lg font-semibold text-white">
                {(props.userName?.trim()?.[0] || 'U').toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-white">{props.userName || 'User'}</div>
                {props.userEmail && <div className="truncate text-xs text-white/60">{props.userEmail}</div>}
              </div>
            </div>
          </div>

          {/* Current Model Display */}
          <div className="border-b border-white/10 bg-white/5 p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-white/50">Current Model</div>
            <div className="mt-2 flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 p-3">
              <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 text-sm">
                {currentModel.isReasoning ? '🧠' : '🤖'}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-white">{currentModel.name}</div>
                <div className="text-xs text-white/50">{currentModel.provider}</div>
              </div>
              {currentModel.isLocal && (
                <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-medium text-emerald-300">
                  Local
                </span>
              )}
            </div>
          </div>

          {/* Model Selection */}
          <div className="max-h-[400px] overflow-y-auto p-4">
            <div className="mb-3 text-xs font-medium uppercase tracking-wide text-white/50">Available Models</div>
            <div className="space-y-2">
              {AVAILABLE_MODELS.map((model) => {
                const isSelected = model.id === props.selectedModel || (model.id === 'crt-reasoning' && !props.selectedModel)
                return (
                  <button
                    key={model.id}
                    onClick={() => props.onModelChange(model.id)}
                    className={`
                      group w-full rounded-xl border p-3 text-left transition-all
                      ${
                        isSelected
                          ? 'border-violet-500/50 bg-violet-500/10'
                          : 'border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/10'
                      }
                    `}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className={`
                        grid h-10 w-10 flex-shrink-0 place-items-center rounded-lg text-base transition-all
                        ${
                          isSelected
                            ? 'bg-gradient-to-br from-violet-500 to-purple-600'
                            : 'bg-white/10 group-hover:bg-white/15'
                        }
                      `}
                      >
                        {model.isReasoning ? '🧠' : '🤖'}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-white">{model.name}</span>
                          {model.isLocal && (
                            <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-medium text-emerald-300">
                              Local
                            </span>
                          )}
                          {model.isReasoning && (
                            <span className="rounded-full bg-purple-500/20 px-2 py-0.5 text-xs font-medium text-purple-300">
                              Reasoning
                            </span>
                          )}
                        </div>
                        <div className="mt-0.5 text-xs text-white/50">{model.provider}</div>
                        <div className="mt-1 text-xs text-white/60">{model.description}</div>
                      </div>
                      {isSelected && (
                        <div className="flex-shrink-0 text-violet-400">
                          <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                            <path
                              fillRule="evenodd"
                              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </div>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Footer Actions */}
          {props.onLogout && (
            <div className="border-t border-white/10 bg-white/5 p-4">
              <button
                onClick={props.onLogout}
                className="w-full rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-2.5 text-sm font-medium text-rose-300 transition-all hover:border-rose-500/50 hover:bg-rose-500/20"
              >
                Sign Out
              </button>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
