import { type LucideIcon, FileText, PenLine, Terminal, Search, Globe, Brain, FolderOpen, Save, Zap, CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import type { ToolResult } from './ToolResultCard'

// ─────────────────────────────────────────────────────────────
// Icon mapping
// ─────────────────────────────────────────────────────────────

function toolIcon(name: string): LucideIcon {
  const n = name.toLowerCase()
  if (/read|file_read|file_text|open/.test(n)) return FileText
  if (/edit|write|patch|pen|modify|update/.test(n)) return PenLine
  if (/bash|command|terminal|exec|run|shell/.test(n)) return Terminal
  if (/search|grep|find|query/.test(n)) return Search
  if (/web|fetch|http|url|browse/.test(n)) return Globe
  if (/memory|recall|remember|retrieve/.test(n)) return Brain
  if (/folder|dir|list|ls/.test(n)) return FolderOpen
  if (/save|output|dump/.test(n)) return Save
  return Zap
}

function formatToolName(name: string): string {
  return name.replace(/_/g, ' ')
}

function formatArg(args?: Record<string, unknown>): string {
  if (!args) return ''
  const vals = Object.values(args).filter(v => typeof v === 'string') as string[]
  if (!vals.length) return ''
  const joined = vals.join(', ')
  return joined.length > 38 ? joined.slice(0, 38) + '…' : joined
}

function formatResult(result?: string, durationMs?: number): string {
  const parts: string[] = []
  if (durationMs != null) parts.push(`${durationMs < 1000 ? durationMs + 'ms' : (durationMs / 1000).toFixed(1) + 's'}`)
  return parts.join(' · ')
}

// ─────────────────────────────────────────────────────────────
// ToolRow — single tool call line inside the pipeline panel
// ─────────────────────────────────────────────────────────────

export function ToolRow({ result }: { result: ToolResult }) {
  const Icon = toolIcon(result.tool)
  const isRunning = result.status === 'running' || result.status === undefined
  const isError = result.status === 'error'
  const isDone = !isRunning && !isError

  const argStr = formatArg(result.args)
  const latency = result.durationMs != null ? formatResult(result.result, result.durationMs) : ''

  return (
    <div className="flex items-center gap-2 py-[3px] text-[11px] font-mono">

      {/* Tool icon */}
      <Icon
        size={12}
        style={{ color: 'rgba(224,160,128,0.55)', flexShrink: 0 }}
      />

      {/* Tool name */}
      <span style={{ color: 'rgba(240,235,225,0.55)' }}>
        {formatToolName(result.tool)}
      </span>

      {/* Arg preview */}
      {argStr && (
        <span
          className="truncate"
          style={{ color: 'rgba(240,235,225,0.25)', maxWidth: '220px' }}
          title={argStr}
        >
          {argStr}
        </span>
      )}

      {/* Spacer */}
      <span className="flex-1" />

      {/* Status */}
      {isRunning && (
        <Loader2
          size={10}
          className="animate-spin flex-shrink-0"
          style={{ color: 'rgba(224,160,128,0.4)' }}
        />
      )}
      {isDone && latency && (
        <span style={{ color: 'rgba(240,235,225,0.2)' }}>
          ✓ {latency}
        </span>
      )}
      {isDone && !latency && (
        <CheckCircle2 size={10} style={{ color: 'rgba(52,211,153,0.5)', flexShrink: 0 }} />
      )}
      {isError && (
        <XCircle size={10} style={{ color: '#D47058', flexShrink: 0 }} />
      )}
    </div>
  )
}
