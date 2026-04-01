import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export type ToolResult = {
  tool: string
  args?: Record<string, unknown>
  result?: string
  hits?: number
  durationMs?: number
  status?: string
  /** Structured result items (e.g., search hits with scores) */
  items?: Array<{ label: string; score?: number; detail?: string }>
}

const TOOL_ICONS: Record<string, string> = {
  gpt_log_search: '\u25C8',
  gpt_log_context: '\u25C8',
  memory_search: '\u25C8',
  web_search: '\u25C8',
  code_read: '\u25B7',
  code_write: '\u25B7',
  file_read: '\u25B7',
  default: '\u25C8',
}

function formatToolName(name: string): string {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export function ToolResultCard({ result, streaming }: { result: ToolResult; streaming?: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const icon = TOOL_ICONS[result.tool] || TOOL_ICONS.default

  const queryStr = result.args
    ? Object.values(result.args).filter(v => typeof v === 'string').join(', ')
    : ''

  const summaryParts: string[] = []
  if (result.hits != null) summaryParts.push(`${result.hits} hit${result.hits !== 1 ? 's' : ''}`)
  if (result.durationMs != null) summaryParts.push(`${result.durationMs}ms`)
  if (result.status && result.status !== 'ok') summaryParts.push(result.status)

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className="my-2"
    >
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full text-left"
      >
        <div className="flex items-center gap-2 text-[12px] font-mono">
          <span style={{ color: '#E0A080' }}>{icon}</span>
          <span className="uppercase tracking-wider font-medium" style={{ color: 'rgba(240,235,225,0.6)' }}>
            {formatToolName(result.tool)}
          </span>
          {summaryParts.length > 0 && (
            <span style={{ color: 'rgba(240,235,225,0.3)' }}>
              {summaryParts.join(' \u00B7 ')}
            </span>
          )}
          {streaming && (
            <span
              className="inline-block w-1.5 h-1.5 rounded-full animate-pulse"
              style={{ background: '#E0A080' }}
            />
          )}
          <span className="ml-auto text-[10px]" style={{ color: 'rgba(240,235,225,0.2)' }}>
            {expanded ? '\u25BE' : '\u25B8'}
          </span>
        </div>
        {queryStr && (
          <div className="mt-0.5 text-[11px] pl-5" style={{ color: 'rgba(240,235,225,0.35)' }}>
            {queryStr.length > 80 ? queryStr.slice(0, 80) + '\u2026' : queryStr}
          </div>
        )}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div
              className="mt-1.5 ml-5 pl-3 text-[11px] font-mono space-y-1"
              style={{ borderLeft: '1px solid rgba(224,160,128,0.15)' }}
            >
              {/* Structured items */}
              {result.items?.map((item, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span style={{ color: 'rgba(240,235,225,0.5)' }}>{'\u25B8'}</span>
                  <span style={{ color: 'rgba(240,235,225,0.6)' }}>{item.label}</span>
                  {item.score != null && (
                    <span style={{ color: 'rgba(240,235,225,0.25)' }}>{item.score.toFixed(3)}</span>
                  )}
                  {item.detail && (
                    <span className="truncate" style={{ color: 'rgba(240,235,225,0.3)' }}>{item.detail}</span>
                  )}
                </div>
              ))}

              {/* Raw result text fallback */}
              {!result.items?.length && result.result && (
                <div
                  className="whitespace-pre-wrap"
                  style={{ color: 'rgba(240,235,225,0.4)' }}
                >
                  {result.result.length > 500 ? result.result.slice(0, 500) + '\u2026' : result.result}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
