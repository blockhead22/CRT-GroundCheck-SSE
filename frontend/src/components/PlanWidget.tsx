import { useEffect, useState } from 'react'
import {
  getThreadPlan,
  updatePlanStep,
  type Plan,
  type PlanStep,
} from '../lib/api'

type Props = {
  threadId: string
  /** Incremented by parent after each message to trigger refresh */
  refreshKey?: number
}

const STATUS_ICONS: Record<string, string> = {
  completed: '✓',
  in_progress: '►',
  waiting_input: '?',
  failed: '✗',
  skipped: '—',
  pending: '○',
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'text-emerald-400',
  in_progress: 'text-amber-300',
  waiting_input: 'text-sky-300',
  failed: 'text-rose-400',
  skipped: 'text-white/30',
  pending: 'text-white/40',
}

function stepStatusBadge(status: string) {
  const icon = STATUS_ICONS[status] ?? '○'
  const color = STATUS_COLORS[status] ?? 'text-white/40'
  return <span className={`font-mono text-xs ${color}`}>{icon}</span>
}

export function PlanWidget({ threadId, refreshKey }: Props) {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getThreadPlan(threadId)
      .then((p) => { if (!cancelled) setPlan(p) })
      .catch(() => { if (!cancelled) setPlan(null) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [threadId, refreshKey])

  if (loading || !plan) return null

  const steps = plan.steps || []
  const completed = steps.filter((s) => s.status === 'completed').length
  const total = steps.length
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0
  const current = steps.find((s) => s.status === 'in_progress' || s.status === 'waiting_input')

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-2">
      <div className="rounded-lg border border-white/10 bg-white/[0.03]">
        {/* Collapsed bar */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-white/5 transition-colors rounded-lg"
        >
          {/* Progress ring */}
          <div className="relative flex h-7 w-7 shrink-0 items-center justify-center">
            <svg className="h-7 w-7 -rotate-90" viewBox="0 0 28 28">
              <circle cx="14" cy="14" r="11" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="2.5" />
              <circle
                cx="14" cy="14" r="11" fill="none"
                stroke={pct === 100 ? '#34d399' : 'var(--accent, #c084fc)'}
                strokeWidth="2.5"
                strokeDasharray={`${(pct / 100) * 69.1} 69.1`}
                strokeLinecap="round"
              />
            </svg>
            <span className="absolute text-[9px] font-bold text-white/80">{pct}%</span>
          </div>

          {/* Title + current step */}
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs font-semibold text-white/90">{plan.title}</div>
            {current && (
              <div className="truncate text-[11px] text-white/50">
                Step {completed + 1}/{total}: {current.title}
              </div>
            )}
            {!current && pct === 100 && (
              <div className="text-[11px] text-emerald-400">All {total} steps complete</div>
            )}
          </div>

          {/* Expand chevron */}
          <span className="text-white/30 text-xs">{expanded ? '▲' : '▼'}</span>
        </button>

        {/* Expanded step list */}
        {expanded && (
          <div className="border-t border-white/5 px-3 py-2 space-y-1">
            {steps.map((step) => (
              <div
                key={step.id}
                className={`flex items-start gap-2 rounded px-2 py-1.5 text-xs ${
                  step.status === 'in_progress' ? 'bg-white/[0.04]' : ''
                }`}
              >
                {stepStatusBadge(step.status)}
                <div className="min-w-0 flex-1">
                  <div className={`${step.status === 'completed' ? 'text-white/50 line-through' : 'text-white/80'}`}>
                    {step.title}
                  </div>
                  {step.description && (
                    <div className="text-[11px] text-white/30 mt-0.5">{step.description}</div>
                  )}
                  {step.status === 'waiting_input' && step.needs_user_input && (
                    <div className="mt-1 text-[11px] text-sky-300/80 italic">
                      Needs input: {step.needs_user_input}
                    </div>
                  )}
                </div>
                {step.tool_name && (
                  <span className="shrink-0 rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-white/40 font-mono">
                    {step.tool_name}
                  </span>
                )}
              </div>
            ))}

            {/* Plan status bar */}
            <div className="flex items-center justify-between pt-2 border-t border-white/5 mt-2">
              <span className="text-[10px] text-white/30">
                {plan.created_by === 'aether' ? 'Created by Aether' : 'Manual plan'}
              </span>
              <span className={`text-[10px] font-semibold ${
                plan.status === 'completed' ? 'text-emerald-400' :
                plan.status === 'paused' ? 'text-amber-400' :
                'text-white/50'
              }`}>
                {plan.status.toUpperCase()}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
