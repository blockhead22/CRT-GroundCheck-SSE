import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { AgentTrace, AgentStep } from '../types'

type AgentPanelProps = {
  trace: AgentTrace | null
  agentAnswer?: string | null
  onClose: () => void
}

export function AgentPanel({ trace, agentAnswer, onClose }: AgentPanelProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set([0]))

  if (!trace) {
    return null
  }

  const toggleStep = (stepNum: number) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev)
      if (next.has(stepNum)) {
        next.delete(stepNum)
      } else {
        next.add(stepNum)
      }
      return next
    })
  }

  const expandAll = () => {
    setExpandedSteps(new Set(trace.steps.map((s) => s.step_num)))
  }

  const collapseAll = () => {
    setExpandedSteps(new Set())
  }

  const getActionIcon = (tool: string) => {
    const icons: Record<string, string> = {
      search_memory: '🧠',
      search_research: '🔍',
      store_memory: '💾',
      check_contradiction: '⚖️',
      calculate: '🧮',
      read_file: '📄',
      list_files: '📁',
      synthesize: '🔗',
      reflect: '🤔',
      plan: '📋',
      finish: '✅',
    }
    return icons[tool] || '⚡'
  }

  const formatTimestamp = (iso: string) => {
    const date = new Date(iso)
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit',
      fractionalSecondDigits: 1 
    })
  }

  const formatDuration = (start: string, end: string) => {
    const startMs = new Date(start).getTime()
    const endMs = new Date(end).getTime()
    const durationMs = endMs - startMs
    if (durationMs < 1000) return `${durationMs}ms`
    return `${(durationMs / 1000).toFixed(2)}s`
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95 }}
        animate={{ scale: 1 }}
        exit={{ scale: 0.95 }}
        className="relative w-full max-w-4xl max-h-[90vh] overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 border-b border-gray-200 bg-white px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="text-2xl">🤖</div>
              <div>
                <h2 className="text-xl font-semibold text-gray-900">Agent Execution Trace</h2>
                <p className="text-sm text-gray-500">
                  {trace.steps.length} step{trace.steps.length !== 1 ? 's' : ''} • 
                  {trace.success ? (
                    <span className="ml-1 text-green-600">✅ Success</span>
                  ) : trace.error ? (
                    <span className="ml-1 text-red-600">❌ Failed</span>
                  ) : (
                    <span className="ml-1 text-yellow-600">⏱️ In Progress</span>
                  )}
                  {trace.started_at && trace.completed_at && (
                    <span className="ml-2 text-gray-400">
                      {formatDuration(trace.started_at, trace.completed_at)}
                    </span>
                  )}
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={expandAll}
                className="rounded-lg px-3 py-1 text-sm text-gray-600 hover:bg-gray-100 transition-colors"
              >
                Expand All
              </button>
              <button
                onClick={collapseAll}
                className="rounded-lg px-3 py-1 text-sm text-gray-600 hover:bg-gray-100 transition-colors"
              >
                Collapse All
              </button>
              <button
                onClick={onClose}
                className="rounded-lg px-3 py-1.5 text-gray-600 hover:bg-gray-100 transition-colors"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Query */}
        <div className="border-b border-gray-200 bg-blue-50 px-6 py-4">
          <div className="text-xs font-medium text-blue-600 uppercase tracking-wide mb-1">Task</div>
          <div className="text-gray-900 font-medium">{trace.query}</div>
        </div>

        {/* Steps */}
        <div className="overflow-y-auto max-h-[calc(90vh-300px)] px-6 py-4">
          <div className="space-y-3">
            {trace.steps.map((step) => (
              <StepCard
                key={step.step_num}
                step={step}
                isExpanded={expandedSteps.has(step.step_num)}
                onToggle={() => toggleStep(step.step_num)}
                getActionIcon={getActionIcon}
                formatTimestamp={formatTimestamp}
              />
            ))}
          </div>
        </div>

        {/* Final Answer */}
        {(agentAnswer || trace.final_answer) && (
          <div className="sticky bottom-0 border-t border-gray-200 bg-green-50 px-6 py-4">
            <div className="text-xs font-medium text-green-700 uppercase tracking-wide mb-2">
              Final Answer
            </div>
            <div className="text-gray-900 whitespace-pre-wrap">
              {agentAnswer || trace.final_answer}
            </div>
          </div>
        )}

        {/* Error */}
        {trace.error && (
          <div className="sticky bottom-0 border-t border-red-200 bg-red-50 px-6 py-4">
            <div className="text-xs font-medium text-red-700 uppercase tracking-wide mb-2">
              Error
            </div>
            <div className="text-red-900 font-mono text-sm">{trace.error}</div>
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}

type StepCardProps = {
  step: AgentStep
  isExpanded: boolean
  onToggle: () => void
  getActionIcon: (tool: string) => string
  formatTimestamp: (iso: string) => string
}

function StepCard({ step, isExpanded, onToggle, getActionIcon, formatTimestamp }: StepCardProps) {
  const hasAction = step.action !== null && step.action !== undefined
  const hasObservation = step.observation !== null && step.observation !== undefined

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden hover:border-gray-300 transition-colors">
      {/* Step Header */}
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-blue-700">
            {step.step_num}
          </div>
          <div className="text-left">
            <div className="text-sm font-medium text-gray-900 line-clamp-1">
              💭 {step.thought || 'Thinking...'}
            </div>
            {hasAction && (
              <div className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                <span>{getActionIcon(step.action!.tool)}</span>
                <span>{step.action!.tool}</span>
                {hasObservation && (
                  <span className={step.observation!.success ? 'text-green-600' : 'text-red-600'}>
                    • {step.observation!.success ? '✓' : '✗'}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
        <svg
          className={`h-5 w-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Expanded Content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-t border-gray-200 bg-gray-50 px-4 py-3 space-y-3">
              {/* Thought */}
              <div>
                <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                  💭 Thought
                </div>
                <div className="text-sm text-gray-900 bg-white rounded px-3 py-2 border border-gray-200">
                  {step.thought || 'No thought recorded'}
                </div>
              </div>

              {/* Action */}
              {hasAction && (
                <div>
                  <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                    ⚡ Action
                  </div>
                  <div className="text-sm bg-white rounded px-3 py-2 border border-gray-200">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">{getActionIcon(step.action!.tool)}</span>
                      <span className="font-mono font-semibold text-blue-700">
                        {step.action!.tool}
                      </span>
                    </div>
                    {step.action!.args && Object.keys(step.action!.args).length > 0 && (
                      <div className="mt-2">
                        <div className="text-xs text-gray-500 mb-1">Arguments:</div>
                        <pre className="text-xs bg-gray-50 rounded p-2 overflow-x-auto border border-gray-200">
                          {JSON.stringify(step.action!.args, null, 2)}
                        </pre>
                      </div>
                    )}
                    {step.action!.reasoning && (
                      <div className="mt-2 text-xs text-gray-600 italic">
                        "{step.action!.reasoning}"
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Observation */}
              {hasObservation && (
                <div>
                  <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                    👁️ Observation
                  </div>
                  <div
                    className={`text-sm rounded px-3 py-2 border ${
                      step.observation!.success
                        ? 'bg-green-50 border-green-200'
                        : 'bg-red-50 border-red-200'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">
                        {step.observation!.success ? '✅' : '❌'}
                      </span>
                      <span className="font-semibold">
                        {step.observation!.success ? 'Success' : 'Failed'}
                      </span>
                    </div>
                    {step.observation!.result && (
                      <div className="mt-2">
                        <div className="text-xs text-gray-600 mb-1">Result:</div>
                        <div className="bg-white rounded p-2 border border-gray-200 max-h-40 overflow-y-auto">
                          <pre className="text-xs whitespace-pre-wrap break-words">
                            {typeof step.observation!.result === 'string'
                              ? step.observation!.result
                              : JSON.stringify(step.observation!.result, null, 2)}
                          </pre>
                        </div>
                      </div>
                    )}
                    {step.observation!.error && (
                      <div className="mt-2 text-xs text-red-700 font-mono">
                        Error: {step.observation!.error}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Timestamp */}
              {step.timestamp && (
                <div className="text-xs text-gray-400 text-right">
                  {formatTimestamp(step.timestamp)}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
