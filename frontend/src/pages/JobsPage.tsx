import { useEffect, useMemo, useState } from 'react'
import {
  enqueueJob,
  getJob,
  getJobsStatus,
  listJobs,
  listPlans,
  createPlan,
  deletePlan,
  updatePlan,
  addPlanStep,
  deletePlanStep,
  updatePlanStep,
  type JobDetailResponse,
  type JobListItem,
  type JobsStatusResponse,
  type Plan,
  type PlanStep,
} from '../lib/api'

type JobStatusFilter = 'all' | 'queued' | 'running' | 'succeeded' | 'failed'

type JobTemplate = {
  type: string
  title: string
  subtitle: string
  payload: (threadId: string) => Record<string, unknown>
}

const templates: JobTemplate[] = [
  {
    type: 'auto_resolve_contradictions',
    title: 'Auto-resolve contradictions',
    subtitle: 'Conservative, only explicit user revisions; queued + logged',
    payload: (threadId) => ({ thread_id: threadId, max_to_resolve: 10 }),
  },
  {
    type: 'propose_promotions',
    title: 'Propose slot promotions',
    subtitle: 'Extracts latest FACT/PREF per slot (approval required)',
    payload: (threadId) => ({ thread_id: threadId }),
  },
  {
    type: 'research_fetch',
    title: 'Fetch URL (research)',
    subtitle: 'Downloads HTML/text; optionally stores as EXTERNAL memory with provenance',
    payload: (threadId) => ({
      thread_id: threadId,
      url: 'https://example.com',
      store_as_external_memory: false,
    }),
  },
  {
    type: 'research_summarize',
    title: 'Summarize text (research)',
    subtitle: 'Deterministic short summary; optionally stores as EXTERNAL memory',
    payload: (threadId) => ({
      thread_id: threadId,
      url: '',
      text: 'Paste some text to summarize…',
      store_as_external_memory: false,
    }),
  },
  {
    type: 'summarize_session',
    title: 'Summarize session',
    subtitle: 'Toy summarizer (no LLM) – useful for smoke testing jobs plumbing',
    payload: (_threadId) => ({ text: 'Summarize this text…' }),
  },
]

function Pill(props: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      onClick={props.onClick}
      className={
        'rounded px-3 py-1.5 text-xs font-semibold ' +
        (props.active ? 'bg-violet-600 text-white' : 'bg-white/5 text-white/80 hover:bg-white/10')
      }
    >
      {props.label}
    </button>
  )
}

function statusBadge(status: string) {
  const s = (status || '').toLowerCase()
  const base = 'rounded-full px-2 py-0.5 text-[11px] font-semibold '
  if (s === 'succeeded') return base + 'bg-emerald-500/15 text-emerald-200 border border-emerald-500/20'
  if (s === 'failed') return base + 'bg-rose-500/15 text-rose-200 border border-rose-500/20'
  if (s === 'running') return base + 'bg-amber-500/15 text-amber-200 border border-amber-500/20'
  if (s === 'queued') return base + 'bg-sky-500/15 text-sky-200 border border-sky-500/20'
  return base + 'bg-white/5 text-white/70 border border-white/10'
}

function fmtIso(iso: string | null | undefined): string {
  const v = (iso || '').trim()
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return v
  }
}

function safeJsonParse(text: string): { ok: true; value: unknown } | { ok: false; error: string } {
  try {
    return { ok: true, value: JSON.parse(text) }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

function safeCopy(text: string) {
  try {
    void navigator.clipboard.writeText(text)
  } catch {
    // ignore
  }
}

// ── Plan status badge ──────────────────────────────────────────────────
function planStatusBadge(status: string) {
  const s = (status || '').toLowerCase()
  const base = 'rounded-full px-2 py-0.5 text-[11px] font-semibold '
  if (s === 'completed') return base + 'bg-emerald-500/15 text-emerald-200 border border-emerald-500/20'
  if (s === 'paused') return base + 'bg-amber-500/15 text-amber-200 border border-amber-500/20'
  if (s === 'archived') return base + 'bg-white/5 text-white/40 border border-white/10'
  return base + 'bg-violet-500/15 text-violet-200 border border-violet-500/20' // active
}

const STEP_ICONS: Record<string, string> = {
  completed: '✓', in_progress: '►', waiting_input: '?',
  failed: '✗', skipped: '—', pending: '○',
}

// ── Plans Section Component ───────────────────────────────────────────
function PlansSection(props: { threadId: string }) {
  const [plans, setPlans] = useState<Plan[]>([])
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newSteps, setNewSteps] = useState<Array<{ title: string; description: string }>>([
    { title: '', description: '' },
  ])
  const [plansBusy, setPlansBusy] = useState(false)

  async function refreshPlans() {
    try {
      const list = await listPlans()
      setPlans(list)
    } catch { /* ignore */ }
  }

  useEffect(() => {
    void refreshPlans()
    const id = window.setInterval(() => void refreshPlans(), 8000)
    return () => window.clearInterval(id)
  }, [])

  async function handleCreatePlan() {
    if (!newTitle.trim()) return
    setPlansBusy(true)
    try {
      const validSteps = newSteps.filter((s) => s.title.trim())
      await createPlan({
        title: newTitle.trim(),
        description: newDesc.trim() || undefined,
        steps: validSteps.map((s) => ({ title: s.title.trim(), description: s.description.trim() || undefined })),
      })
      setNewTitle('')
      setNewDesc('')
      setNewSteps([{ title: '', description: '' }])
      setShowNew(false)
      await refreshPlans()
    } catch { /* ignore */ } finally {
      setPlansBusy(false)
    }
  }

  async function handleDeletePlan(planId: string) {
    setPlansBusy(true)
    try {
      await deletePlan(planId)
      await refreshPlans()
    } catch { /* ignore */ } finally {
      setPlansBusy(false)
    }
  }

  async function handlePlanStatus(planId: string, status: string) {
    try {
      await updatePlan(planId, { status })
      await refreshPlans()
    } catch { /* ignore */ }
  }

  async function handleStepStatus(planId: string, stepId: string, status: string) {
    try {
      await updatePlanStep(planId, stepId, { status })
      await refreshPlans()
    } catch { /* ignore */ }
  }

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-sm font-semibold text-white/90">Plans</div>
          <div className="text-xs text-white/40">Multi-step task plans</div>
        </div>
        <button
          onClick={() => setShowNew(!showNew)}
          className="rounded px-3 py-1.5 text-xs font-semibold bg-violet-600 text-white hover:bg-violet-500 transition-colors"
        >
          {showNew ? 'Cancel' : '+ New Plan'}
        </button>
      </div>

      {/* New plan form */}
      {showNew && (
        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 mb-3 space-y-3">
          <input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="Plan title"
            className="w-full rounded glass-field px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-violet-500/50"
          />
          <input
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            placeholder="Description (optional)"
            className="w-full rounded glass-field px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
          />
          <div className="space-y-2">
            <div className="text-xs text-white/50 font-semibold">Steps</div>
            {newSteps.map((step, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-xs text-white/30 pt-2 w-5 shrink-0">{i + 1}.</span>
                <input
                  value={step.title}
                  onChange={(e) => {
                    const copy = [...newSteps]
                    copy[i] = { ...copy[i], title: e.target.value }
                    setNewSteps(copy)
                  }}
                  placeholder={`Step ${i + 1}`}
                  className="flex-1 rounded glass-field px-3 py-1.5 text-xs text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
                />
                {newSteps.length > 1 && (
                  <button
                    onClick={() => setNewSteps(newSteps.filter((_, j) => j !== i))}
                    className="text-xs text-rose-400/60 hover:text-rose-400 px-1"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
            <button
              onClick={() => setNewSteps([...newSteps, { title: '', description: '' }])}
              className="text-xs text-white/40 hover:text-white/60"
            >
              + Add step
            </button>
          </div>
          <div className="flex justify-end">
            <button
              onClick={handleCreatePlan}
              disabled={plansBusy || !newTitle.trim()}
              className="rounded px-4 py-2 text-xs font-semibold bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-40 transition-colors"
            >
              Create Plan
            </button>
          </div>
        </div>
      )}

      {/* Plan list */}
      {plans.length === 0 && !showNew && (
        <div className="text-xs text-white/30 py-4 text-center">No plans yet</div>
      )}
      <div className="space-y-2">
        {plans.map((plan) => {
          const steps = plan.steps || []
          const completed = steps.filter((s) => s.status === 'completed').length
          const total = steps.length
          const pct = total > 0 ? Math.round((completed / total) * 100) : 0
          const isExpanded = expandedId === plan.id

          return (
            <div
              key={plan.id}
              className={`rounded-lg border transition-colors ${
                plan.status === 'active'
                  ? 'border-violet-500/20 bg-violet-500/[0.03]'
                  : 'border-white/10 bg-white/[0.02]'
              }`}
            >
              {/* Plan header */}
              <button
                onClick={() => setExpandedId(isExpanded ? null : plan.id)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-white/5 transition-colors rounded-lg"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-white/90 truncate">{plan.title}</span>
                    <span className={planStatusBadge(plan.status)}>{plan.status}</span>
                  </div>
                  {plan.description && (
                    <div className="text-xs text-white/40 mt-0.5 truncate">{plan.description}</div>
                  )}
                </div>
                {total > 0 && (
                  <div className="flex items-center gap-2 shrink-0">
                    <div className="w-20 h-1.5 rounded-full bg-white/10 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: pct === 100 ? '#34d399' : 'var(--accent, #c084fc)',
                        }}
                      />
                    </div>
                    <span className="text-[10px] text-white/40 w-12 text-right">
                      {completed}/{total}
                    </span>
                  </div>
                )}
                <span className="text-white/20 text-xs">{isExpanded ? '▲' : '▼'}</span>
              </button>

              {/* Expanded steps */}
              {isExpanded && (
                <div className="border-t border-white/5 px-4 py-3">
                  {steps.length === 0 && (
                    <div className="text-xs text-white/30 py-2">No steps defined</div>
                  )}
                  <div className="space-y-1">
                    {steps.map((step) => (
                      <div
                        key={step.id}
                        className={`flex items-center gap-2 rounded px-2 py-1.5 text-xs group ${
                          step.status === 'in_progress' ? 'bg-white/[0.04]' : ''
                        }`}
                      >
                        <button
                          onClick={() => {
                            const next = step.status === 'completed' ? 'pending' : 'completed'
                            void handleStepStatus(plan.id, step.id, next)
                          }}
                          className={`font-mono shrink-0 w-4 text-center ${
                            step.status === 'completed' ? 'text-emerald-400' :
                            step.status === 'in_progress' ? 'text-amber-300' :
                            step.status === 'failed' ? 'text-rose-400' :
                            'text-white/30 hover:text-white/60'
                          }`}
                        >
                          {STEP_ICONS[step.status] ?? '○'}
                        </button>
                        <span className={`flex-1 min-w-0 truncate ${
                          step.status === 'completed' ? 'text-white/40 line-through' : 'text-white/80'
                        }`}>
                          {step.title}
                        </span>
                        {step.tool_name && (
                          <span className="shrink-0 rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-white/30 font-mono">
                            {step.tool_name}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Plan actions */}
                  <div className="flex items-center gap-2 mt-3 pt-2 border-t border-white/5">
                    <span className="text-[10px] text-white/25 flex-1">
                      {plan.created_by === 'aether' ? 'Created by Aether' : 'Manual'} ·{' '}
                      {new Date(plan.created_at * 1000).toLocaleDateString()}
                    </span>
                    {plan.status === 'active' && (
                      <button
                        onClick={() => void handlePlanStatus(plan.id, 'paused')}
                        className="text-[10px] text-amber-400/60 hover:text-amber-400"
                      >
                        Pause
                      </button>
                    )}
                    {plan.status === 'paused' && (
                      <button
                        onClick={() => void handlePlanStatus(plan.id, 'active')}
                        className="text-[10px] text-emerald-400/60 hover:text-emerald-400"
                      >
                        Resume
                      </button>
                    )}
                    {plan.status === 'completed' && (
                      <button
                        onClick={() => void handlePlanStatus(plan.id, 'archived')}
                        className="text-[10px] text-white/40 hover:text-white/60"
                      >
                        Archive
                      </button>
                    )}
                    <button
                      onClick={() => void handleDeletePlan(plan.id)}
                      className="text-[10px] text-rose-400/40 hover:text-rose-400"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function JobsPage(props: { threadId: string }) {
  const [status, setStatus] = useState<JobsStatusResponse | null>(null)
  const [statusFilter, setStatusFilter] = useState<JobStatusFilter>('all')
  const [jobs, setJobs] = useState<JobListItem[]>([])
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [selected, setSelected] = useState<JobDetailResponse | null>(null)

  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [templateType, setTemplateType] = useState<string>(templates[0]?.type ?? 'summarize_session')
  const [priority, setPriority] = useState(0)
  const [payloadText, setPayloadText] = useState<string>(() => {
    const t = templates[0]
    return JSON.stringify(t ? t.payload(props.threadId) : {}, null, 2)
  })

  const template = useMemo(() => templates.find((t) => t.type === templateType) ?? null, [templateType])

  useEffect(() => {
    // When changing template, reset payload editor to a sane default.
    const t = templates.find((x) => x.type === templateType)
    if (!t) return
    setPayloadText(JSON.stringify(t.payload(props.threadId), null, 2))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [templateType, props.threadId])

  async function refresh() {
    const st = await getJobsStatus().catch(() => null)
    const list = await listJobs({ status: statusFilter === 'all' ? null : statusFilter, limit: 50, offset: 0 })
    setStatus(st)
    setJobs(list.jobs || [])

    // Keep selection in sync if the job disappears.
    if (selectedJobId && !(list.jobs || []).some((j) => j.id === selectedJobId)) {
      setSelectedJobId(null)
      setSelected(null)
    }
  }

  useEffect(() => {
    setError(null)
    void refresh().catch((e) => setError(e instanceof Error ? e.message : String(e)))
    // POLLING FIX: jobs refresh raised from 2.5s to 5s
    const id = window.setInterval(() => void refresh().catch(() => {}), 5000)
    return () => window.clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter])

  useEffect(() => {
    if (!selectedJobId) {
      setSelected(null)
      return
    }
    let mounted = true
    setError(null)
    getJob(selectedJobId)
      .then((d) => {
        if (!mounted) return
        setSelected(d)
      })
      .catch((e) => {
        if (!mounted) return
        setError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      mounted = false
    }
  }, [selectedJobId])

  async function doEnqueue() {
    setError(null)
    const parsed = safeJsonParse(payloadText)
    if (!parsed.ok) {
      setError(`Payload JSON invalid: ${parsed.error}`)
      return
    }
    if (parsed.value === null || typeof parsed.value !== 'object' || Array.isArray(parsed.value)) {
      setError('Payload must be a JSON object')
      return
    }

    setBusy(true)
    try {
      const res = await enqueueJob({
        type: templateType,
        payload: parsed.value as Record<string, unknown>,
        priority,
      })
      setSelectedJobId(res.job_id)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const jobCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const j of jobs) counts[j.status] = (counts[j.status] || 0) + 1
    return counts
  }, [jobs])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-white/10 px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-lg font-semibold text-white">Plans & Jobs</div>
            <div className="mt-1 text-sm text-white/60">Task plans, queue visibility, and manual enqueuing</div>
          </div>
          <div className="flex items-center gap-2">
            <div className="rounded border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/70">
              Thread: <span className="font-semibold text-white">{props.threadId}</span>
            </div>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Pill active={statusFilter === 'all'} label={`All (${jobs.length})`} onClick={() => setStatusFilter('all')} />
          <Pill
            active={statusFilter === 'queued'}
            label={`Queued (${jobCounts.queued || 0})`}
            onClick={() => setStatusFilter('queued')}
          />
          <Pill
            active={statusFilter === 'running'}
            label={`Running (${jobCounts.running || 0})`}
            onClick={() => setStatusFilter('running')}
          />
          <Pill
            active={statusFilter === 'succeeded'}
            label={`Succeeded (${jobCounts.succeeded || 0})`}
            onClick={() => setStatusFilter('succeeded')}
          />
          <Pill
            active={statusFilter === 'failed'}
            label={`Failed (${jobCounts.failed || 0})`}
            onClick={() => setStatusFilter('failed')}
          />
        </div>
      </div>

      {/* ═══════════ PLANS SECTION ═══════════ */}
      <div className="border-b border-white/10 px-5 py-4">
        <PlansSection threadId={props.threadId} />
      </div>

      {/* ═══════════ JOBS SECTION ═══════════ */}
      <div className="min-h-0 flex-1 overflow-hidden">
        <div className="flex h-full min-h-0">
          <div className="w-[380px] flex-none border-r border-white/10 p-5">
            <div className="text-xs font-semibold tracking-wide text-white/60">Worker</div>
            <div className="mt-3 rounded border border-white/10 bg-white/5 p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-white">Status</div>
                <button
                  onClick={() => void refresh().catch(() => {})}
                  className="rounded border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/70 hover:bg-white/10"
                >
                  Refresh
                </button>
              </div>
              <div className="mt-3 space-y-2 text-xs text-white/70">
                <div>
                  Enabled: <span className="font-semibold text-white">{status?.enabled ? 'yes' : 'no'}</span>
                </div>
                <div>
                  Idle scheduler: <span className="font-semibold text-white">{status?.idle_scheduler_enabled ? 'yes' : 'no'}</span>
                </div>
                <div>
                  Jobs DB: <span className="font-semibold text-white">{status?.jobs_db_path || '—'}</span>
                </div>
                <div className="text-white/50">
                  Worker: <span className="font-mono text-[11px]">{JSON.stringify(status?.worker ?? {})}</span>
                </div>
              </div>
            </div>

            <div className="mt-6 text-xs font-semibold tracking-wide text-white/60">Enqueue</div>
            <div className="mt-3 rounded border border-white/10 bg-white/5 p-4">
              <div className="text-sm font-semibold text-white">New job</div>
              {template ? (
                <div className="mt-1 text-xs text-white/60">{template.title} — {template.subtitle}</div>
              ) : null}

              <div className="mt-4 space-y-3">
                <label className="block">
                  <div className="text-xs font-semibold text-white/70">Type</div>
                  <select
                    value={templateType}
                    onChange={(e) => setTemplateType(e.target.value)}
                    className="mt-1 w-full rounded border border-white/10 bg-black/20 px-3 py-2 text-sm text-white focus:outline-none"
                  >
                    {templates.map((t) => (
                      <option key={t.type} value={t.type}>
                        {t.type}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block">
                  <div className="text-xs font-semibold text-white/70">Priority</div>
                  <input
                    type="number"
                    value={priority}
                    onChange={(e) => setPriority(Number(e.target.value))}
                    className="mt-1 w-full rounded border border-white/10 bg-black/20 px-3 py-2 text-sm text-white focus:outline-none"
                  />
                </label>

                <label className="block">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-semibold text-white/70">Payload (JSON)</div>
                    <button
                      onClick={() => template && setPayloadText(JSON.stringify(template.payload(props.threadId), null, 2))}
                      className="rounded border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/70 hover:bg-white/10"
                    >
                      Reset
                    </button>
                  </div>
                  <textarea
                    value={payloadText}
                    onChange={(e) => setPayloadText(e.target.value)}
                    rows={10}
                    className="mt-1 w-full resize-none rounded border border-white/10 bg-black/20 px-3 py-2 font-mono text-[12px] text-white/90 focus:outline-none"
                  />
                </label>

                <button
                  disabled={busy}
                  onClick={() => void doEnqueue()}
                  className={
                    'w-full rounded px-4 py-2 text-sm font-semibold ' +
                    (busy
                      ? 'cursor-not-allowed bg-white/10 text-white/50'
                      : 'bg-violet-600 text-white hover:bg-violet-500')
                  }
                >
                  {busy ? 'Enqueuing…' : 'Enqueue job'}
                </button>
              </div>
            </div>

            {error ? (
              <div className="mt-4 rounded border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
                {error}
              </div>
            ) : null}
          </div>

          <div className="min-w-0 flex-1 overflow-hidden">
            <div className="flex h-full min-h-0">
              <div className="w-[440px] flex-none border-r border-white/10 p-5">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold tracking-wide text-white/60">Queue</div>
                  <div className="text-xs text-white/50">Showing {jobs.length}</div>
                </div>

                <div className="mt-3 space-y-2 overflow-auto pr-1" style={{ maxHeight: 'calc(100vh - 220px)' }}>
                  {jobs.map((j) => {
                    const active = j.id === selectedJobId
                    const tid = String((j.payload as Record<string, unknown>)?.thread_id || '')
                    const matchesThread = tid && tid === props.threadId
                    return (
                      <button
                        key={j.id}
                        onClick={() => setSelectedJobId(j.id)}
                        className={
                          'w-full rounded border px-3 py-3 text-left transition ' +
                          (active ? 'border-violet-400/40 bg-white/10' : 'border-white/10 bg-white/5 hover:bg-white/10')
                        }
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-semibold text-white">{j.type}</div>
                            <div className="mt-1 truncate text-xs text-white/60">{j.id}</div>
                          </div>
                          <div className="flex flex-col items-end gap-1">
                            <span className={statusBadge(j.status)}>{j.status}</span>
                            {matchesThread ? (
                              <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[10px] font-semibold text-violet-200">
                                this thread
                              </span>
                            ) : null}
                          </div>
                        </div>
                        <div className="mt-2 text-xs text-white/50">Created {fmtIso(j.created_at)}</div>
                      </button>
                    )
                  })}

                  {!jobs.length ? (
                    <div className="rounded border border-white/10 bg-white/5 p-4 text-sm text-white/60">
                      No jobs found.
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="min-w-0 flex-1 overflow-auto p-5">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold tracking-wide text-white/60">Details</div>
                  {selected?.job?.id ? (
                    <button
                      onClick={() => safeCopy(selected.job.id)}
                      className="rounded border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/70 hover:bg-white/10"
                    >
                      Copy job id
                    </button>
                  ) : null}
                </div>

                {!selected ? (
                  <div className="mt-4 rounded border border-white/10 bg-white/5 p-6 text-sm text-white/60">
                    Select a job to inspect events and artifacts.
                  </div>
                ) : (
                  <div className="mt-4 space-y-4">
                    <div className="rounded border border-white/10 bg-white/5 p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="truncate text-lg font-semibold text-white">{selected.job.type}</div>
                          <div className="mt-1 truncate text-xs text-white/60">{selected.job.id}</div>
                        </div>
                        <span className={statusBadge(selected.job.status)}>{selected.job.status}</span>
                      </div>

                      <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-white/70">
                        <div>
                          <div className="text-white/50">Created</div>
                          <div className="font-semibold text-white">{fmtIso(selected.job.created_at)}</div>
                        </div>
                        <div>
                          <div className="text-white/50">Started</div>
                          <div className="font-semibold text-white">{fmtIso(selected.job.started_at)}</div>
                        </div>
                        <div>
                          <div className="text-white/50">Finished</div>
                          <div className="font-semibold text-white">{fmtIso(selected.job.finished_at)}</div>
                        </div>
                        <div>
                          <div className="text-white/50">Priority</div>
                          <div className="font-semibold text-white">{selected.job.priority}</div>
                        </div>
                      </div>

                      {selected.job.error ? (
                        <div className="mt-3 rounded border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-200">
                          {selected.job.error}
                        </div>
                      ) : null}

                      <div className="mt-3">
                        <div className="text-xs font-semibold text-white/70">Payload</div>
                        <pre className="mt-2 overflow-auto rounded border border-white/10 bg-black/20 p-3 text-[12px] text-white/80">
                          {JSON.stringify(selected.job.payload ?? {}, null, 2)}
                        </pre>
                      </div>
                    </div>

                    <div className="rounded border border-white/10 bg-white/5 p-4">
                      <div className="text-sm font-semibold text-white">Events</div>
                      <div className="mt-3 space-y-2">
                        {(selected.events || []).map((e, idx) => (
                          <div key={idx} className="rounded border border-white/10 bg-white/5 p-3">
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-xs font-semibold text-white">{e.message}</div>
                              <div className="text-[11px] text-white/50">{fmtIso(e.ts)}</div>
                            </div>
                            <div className="mt-1 text-[11px] text-white/60">level: {e.level}</div>
                            {e.data ? (
                              <pre className="mt-2 overflow-auto rounded border border-white/10 bg-black/20 p-2 text-[11px] text-white/70">
                                {JSON.stringify(e.data, null, 2)}
                              </pre>
                            ) : null}
                          </div>
                        ))}
                        {!(selected.events || []).length ? (
                          <div className="text-sm text-white/60">No events.</div>
                        ) : null}
                      </div>
                    </div>

                    <div className="rounded border border-white/10 bg-white/5 p-4">
                      <div className="text-sm font-semibold text-white">Artifacts</div>
                      <div className="mt-3 space-y-2">
                        {(selected.artifacts || []).map((a, idx) => (
                          <div key={idx} className="rounded border border-white/10 bg-white/5 p-3">
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-xs font-semibold text-white">{a.kind}</div>
                              <div className="text-[11px] text-white/50">{fmtIso(a.created_at)}</div>
                            </div>
                            <div className="mt-1 break-all text-[11px] text-white/70">{a.path}</div>
                            {a.sha256 ? <div className="mt-1 break-all text-[11px] text-white/50">sha256: {a.sha256}</div> : null}
                            <div className="mt-2">
                              <button
                                onClick={() => safeCopy(a.path)}
                                className="rounded border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/70 hover:bg-white/10"
                              >
                                Copy path
                              </button>
                            </div>
                          </div>
                        ))}
                        {!(selected.artifacts || []).length ? (
                          <div className="text-sm text-white/60">No artifacts.</div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
