import { CheckCircle2, CircleSlash2, Database, FileText, Search, ShieldQuestion, User, Wrench } from 'lucide-react'
import type { Trace } from '../types'
import { humanSlotLabel } from '../uiMode'

/**
 * Plain-language summary of what Aether used / withheld / ran for a turn.
 * Default Simple-mode surface; Lab mode still has full TraceDrawer.
 */
export function WhyThisAnswer({
  trace,
  error = '',
  onShowLabDetails,
  onOpenKnows,
}: {
  trace: Trace | null
  error?: string
  onShowLabDetails?: () => void
  /** Open Knows drawer on a personal fact slot (Simple honesty path). */
  onOpenKnows?: (slotId: string) => void
}) {
  if (error) {
    return (
      <div className="drawer-empty">
        <ShieldQuestion size={28} />
        <h3>Details unavailable</h3>
        <p>{friendlyChatError(error)}</p>
      </div>
    )
  }
  if (!trace) {
    return (
      <div className="drawer-empty">
        <ShieldQuestion size={28} />
        <h3>No answer details yet</h3>
        <p>
          Ask Aether something. This panel will show which stored facts and tools
          it used — and what it refused to invent.
        </p>
      </div>
    )
  }

  const summary = summarizeTrace(trace)
  const cancelled = trace.run_state?.status === 'cancelled'
    || Boolean((trace as { cancelled?: boolean }).cancelled)

  return (
    <div className="why-answer" aria-label="Why this answer">
      <p className="why-lead">
        In plain English: what Aether used for this reply, and what it held back.
      </p>

      {cancelled ? (
        <div className="why-callout cancelled" role="status">
          <CircleSlash2 size={15} />
          <div>
            <strong>This run was stopped</strong>
            <span>Nothing further was released after cancel. Partial wording may still appear above.</span>
          </div>
        </div>
      ) : null}

      {!summary.usedFacts.length && summary.contextSources.length ? (
        <div className="why-callout honesty" role="note">
          <ShieldQuestion size={15} />
          <div>
            <strong>Not from your personal profile</strong>
            <span>
              This reply used project or system context below. Aether did not release
              stored facts about you for this answer.
            </span>
          </div>
        </div>
      ) : null}

      <section className="why-section">
        <div className="why-section-head">
          <Database size={15} />
          <span>Personal facts released</span>
          <strong>{summary.usedFacts.length}</strong>
        </div>
        {summary.usedFacts.length ? (
          <ul className="why-list">
            {summary.usedFacts.map((item) => (
              <li key={item.key}>
                <CheckCircle2 size={14} />
                <span>
                  <strong>{item.label}</strong>
                  {item.value ? <em>{item.value}</em> : null}
                  {item.slotId && onOpenKnows ? (
                    <button
                      type="button"
                      className="why-knows-link"
                      onClick={() => onOpenKnows(item.slotId!)}
                    >
                      Review in Knows
                    </button>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="why-empty">
            <strong>No personal memory facts</strong> were released for this answer.
            {summary.contextSources.length
              ? ' The reply used other governed context below — not invented identity.'
              : ' The reply is general reasoning under Aether’s rules, not your profile.'}
          </p>
        )}
      </section>

      {summary.contextSources.length ? (
        <section className="why-section">
          <div className="why-section-head">
            <FileText size={15} />
            <span>Other context used</span>
            <strong>{summary.contextSources.length}</strong>
          </div>
          <ul className="why-list">
            {summary.contextSources.map((item) => (
              <li key={item.key}>
                {item.kind === 'self' ? <User size={14} /> : <FileText size={14} />}
                <span>
                  <strong>{item.label}</strong>
                  {item.detail ? <em>{item.detail}</em> : null}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="why-section">
        <div className="why-section-head">
          <Wrench size={15} />
          <span>Tools run</span>
          <strong>{summary.tools.length}</strong>
        </div>
        {summary.tools.length ? (
          <ul className="why-list">
            {summary.tools.map((item) => (
              <li key={item.key}>
                <Search size={14} />
                <span>
                  <strong>{item.label}</strong>
                  {item.paths?.length ? (
                    <ul className="why-path-list">
                      {item.paths.map((path) => (
                        <li key={path}><code>{path}</code></li>
                      ))}
                    </ul>
                  ) : item.detail ? (
                    <em>{item.detail}</em>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="why-empty">No workspace tools ran on this turn.</p>
        )}
      </section>

      <section className="why-section">
        <div className="why-section-head">
          <CircleSlash2 size={15} />
          <span>Held back</span>
          <strong>{summary.heldBack.length}</strong>
        </div>
        {summary.heldBack.length ? (
          <ul className="why-list muted">
            {summary.heldBack.map((item) => (
              <li key={item.key}>
                <ShieldQuestion size={14} />
                <span>
                  <strong>{item.label}</strong>
                  {item.detail ? <em>{item.detail}</em> : null}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="why-empty">Nothing was explicitly withheld as a conflict or quarantine.</p>
        )}
      </section>

      <section className="why-section compact">
        <div className="why-chips">
          <span>{summary.whereAnswered}</span>
          <span>{summary.verified}</span>
          {summary.route ? <span>{summary.route}</span> : null}
        </div>
      </section>

      {onShowLabDetails ? (
        <button type="button" className="why-lab-link" onClick={onShowLabDetails}>
          Curious how it works under the hood? Open full Lab trace
        </button>
      ) : null}
    </div>
  )
}

export function buildAnswerFooterLine(trace: Trace | null | undefined): string {
  if (!trace) return 'Tap for Why this answer'
  if (trace.run_state?.status === 'cancelled') return 'Stopped · open Why'
  const summary = summarizeTrace(trace)
  const parts: string[] = []

  if (summary.usedFacts.length) {
    parts.push(
      summary.usedFacts.length === 1
        ? '1 personal fact'
        : `${summary.usedFacts.length} personal facts`,
    )
  } else if (summary.contextSources.length) {
    const labels = summary.contextSources.map((c) => c.short).slice(0, 2)
    parts.push(`${labels.join(' + ')} · no personal facts`)
  } else {
    parts.push('no personal facts released')
  }

  if (summary.tools.length) {
    parts.push(
      summary.tools.length === 1
        ? '1 tool'
        : `${summary.tools.length} tools`,
    )
  }
  if (summary.heldBack.length) {
    parts.push('held something back')
  }
  return parts.join(' · ')
}

/** Map raw API / stream errors into Simple-friendly copy. */
export function friendlyChatError(raw: string): string {
  const text = String(raw || '').trim()
  if (!text) return 'Something went wrong.'
  const lower = text.toLowerCase()
  if (lower.includes('failed to fetch') || lower.includes('networkerror') || lower.includes('load failed')) {
    return 'Can’t reach Aether. Is the sidecar running on this PC?'
  }
  if (lower.includes('no longer active') || lower.includes('run is not active')) {
    return 'That answer already finished — nothing left to stop.'
  }
  if (lower.includes('not active in this sidecar')) {
    return 'This run isn’t active in the current Workbench process. Try again after a restart if Stop keeps failing.'
  }
  if (lower.includes('404') && lower.includes('turn')) {
    return 'That turn wasn’t found. It may be from an older session.'
  }
  if (lower.includes('trace is unavailable') || lower.includes('trace not found')) {
    return 'Why details aren’t available for this turn yet.'
  }
  // FastAPI sometimes embeds status as "Request failed (409)"
  if (/\(409\)/.test(text) || lower.includes('conflict')) {
    return 'That action conflicted with the current run state. If you were stopping, the answer may already be done.'
  }
  return text
}

export function humanVerificationLabel(
  trace?: Trace | null,
  persistedVerification?: {
    accepted?: boolean
    fully_verified?: boolean
    checked_dimension_count?: number
    applicable_dimension_count?: number
    failed_dimension_count?: number
    passed_dimension_count?: number
  } | null,
): string {
  if (trace?.run_state?.status === 'cancelled') return 'Cancelled'
  const verification = trace?.completion?.verification_summary || persistedVerification
  if (!verification) return 'Checks not shown'
  if (verification.accepted === false) return 'Not released — failed a hard check'
  const checked = Number(verification.checked_dimension_count || 0)
  const applicable = Number(verification.applicable_dimension_count || 0)
  const failed = Number(verification.failed_dimension_count || 0)
  const passed = Number(verification.passed_dimension_count || 0)
  if (failed > 0) {
    return applicable
      ? `Mostly checked (${checked} of ${applicable}; ${failed} advisory)`
      : 'Mostly checked (some advisory flags)'
  }
  if (verification.fully_verified) {
    return applicable ? `Checks passed (${passed} of ${applicable})` : 'Checks passed'
  }
  if (applicable > 0 && checked < applicable) {
    return `Partial checks (${checked} of ${applicable}) — still released`
  }
  if (applicable > 0) {
    return `Checks OK (${checked} of ${applicable})`
  }
  return 'Governed release'
}

type ContextSource = {
  key: string
  kind: 'project' | 'self' | 'meta' | 'other'
  label: string
  short: string
  detail: string
}

function summarizeTrace(trace: Trace) {
  const usedFacts: Array<{ key: string; label: string; value: string; slotId?: string }> = []
  const heldBack: Array<{ key: string; label: string; detail: string }> = []
  const seenFacts = new Set<string>()

  for (const packet of trace.packets || []) {
    const slot = String(packet.slot_id || packet.planner_slot || '')
    const label = humanSlotLabel(slot || 'fact')
    const value = String(packet.evidence?.[packet.evidence.length - 1]?.value || '').trim()
    const key = `${packet.clause_id || slot}:${packet.release}`
    if (packet.release === 'answerable' && (slot || value)) {
      const factKey = `${slot}:${value}`.toLowerCase()
      if (!seenFacts.has(factKey)) {
        seenFacts.add(factKey)
        usedFacts.push({
          key,
          label,
          value: clip(value, 80),
          slotId: slot.startsWith('user:') || slot.includes(':') ? slot : undefined,
        })
      }
    } else if (packet.release === 'withhold' || packet.release === 'conflict') {
      heldBack.push({
        key,
        label: packet.release === 'conflict' ? `Conflict: ${label}` : `Withheld: ${label}`,
        detail: humanReason(packet.reason) || clip(packet.clause_text || '', 100),
      })
    } else if (packet.release === 'no_evidence') {
      heldBack.push({
        key,
        label: `No stored fact for ${label}`,
        detail: 'Aether did not invent a value.',
      })
    }
  }

  // Profile bridge rows count as personal facts when packets did not already list them.
  const bridge = trace.context_bridge as Record<string, unknown> | null | undefined
  const bridgeRows = bridge?.profile_summary
  if (Array.isArray(bridgeRows)) {
    for (const row of bridgeRows.slice(0, 8)) {
      if (!row || typeof row !== 'object') continue
      const rec = row as Record<string, unknown>
      const slot = String(rec.slot_id || rec.label || '')
      const value = String(rec.value || '').trim()
      if (!slot && !value) continue
      const factKey = `${slot}:${value}`.toLowerCase()
      if (seenFacts.has(factKey)) continue
      seenFacts.add(factKey)
      usedFacts.push({
        key: factKey,
        label: humanSlotLabel(slot),
        value: clip(value, 80),
        slotId: slot.includes(':') ? slot : undefined,
      })
    }
  }

  const tools: Array<{ key: string; label: string; detail: string; paths?: string[] }> = []
  for (const run of trace.tool_runs || []) {
    const tool = String(run.tool || '').replaceAll('_', ' ')
    const output = (run.output || {}) as Record<string, unknown>
    const paths = toolPathsFromOutput(output)
    let detail = String(run.status || '')
    if (paths.length) {
      detail = paths.length === 1
        ? paths[0]
        : `${paths.length} paths`
    } else if (typeof output.path === 'string') {
      detail = String(output.path)
    }
    tools.push({
      key: run.tool_run_id || `${tool}-${tools.length}`,
      label: tool || 'tool',
      detail: clip(detail, 100),
      paths: paths.slice(0, 4),
    })
  }

  const contextSources = detectContextSources(trace)

  const provider = trace.completion?.render_provider?.effective
    || (trace as { render_provider?: { effective?: string } }).render_provider?.effective
  const whereAnswered = provider === 'grok_build'
    ? 'Wording: Hosted Grok (Aether still governs facts/tools)'
    : 'Wording: Local model on this PC'

  const verified = humanVerificationLabel(trace)

  const routeRaw = String(
    trace.completion?.route_decision?.selected_route
    || trace.route_decision?.selected_route
    || '',
  )
  const route = humanRoute(routeRaw)

  return {
    usedFacts: usedFacts.slice(0, 10),
    tools: tools.slice(0, 8),
    heldBack: heldBack.slice(0, 8),
    contextSources,
    whereAnswered,
    verified,
    route,
  }
}

function detectContextSources(trace: Trace): ContextSource[] {
  const out: ContextSource[] = []
  const route = String(
    trace.completion?.route_decision?.selected_route
    || trace.route_decision?.selected_route
    || '',
  ).toLowerCase()
  const characterKind = String(trace.character_answer?.kind || '')
  const meta = Boolean(trace.meta_answer)
  const selfDesc = Boolean(trace.self_description_answer)
  const bridge = trace.context_bridge as Record<string, unknown> | null | undefined
  const hasBridge = Boolean(bridge && Object.keys(bridge).length)

  if (
    route.includes('context_bridge')
    || route.includes('project')
    || hasBridge
  ) {
    const hasProject = Boolean(
      bridge?.project
      || bridge?.project_summary
      || bridge?.self_model
      || route.includes('project')
      || route.includes('context_bridge'),
    )
    if (hasProject || route.includes('context_bridge')) {
      out.push({
        key: 'project-context',
        kind: 'project',
        label: 'Project / product context',
        short: 'project context',
        detail: 'Governed docs and bridge about Aether/Workbench — not your personal profile slots.',
      })
    }
  }

  if (
    characterKind
    || selfDesc
    || route.includes('character')
    || route.includes('self')
  ) {
    out.push({
      key: 'self-voice',
      kind: 'self',
      label: 'Aether self / character framing',
      short: 'self/voice',
      detail: characterKind
        ? `Voice path: ${characterKind.replaceAll('_', ' ')}`
        : 'How Aether is allowed to talk about itself — not invented user biography.',
    })
  }

  if (meta) {
    out.push({
      key: 'meta',
      kind: 'meta',
      label: 'System meta answer',
      short: 'system meta',
      detail: 'Answer about how Aether works, not a personal memory lookup.',
    })
  }

  // Dedupe by key
  const seen = new Set<string>()
  return out.filter((item) => {
    if (seen.has(item.key)) return false
    seen.add(item.key)
    return true
  })
}

function humanRoute(route: string) {
  if (!route) return ''
  const r = route.replaceAll('_', ' ')
  if (r.includes('context bridge')) return 'Route: project/self context'
  if (r.includes('memory')) return 'Route: memory lookup'
  if (r.includes('code tool') || r.includes('tool')) return 'Route: tools first'
  if (r.includes('character')) return 'Route: character/self'
  if (r.includes('general')) return 'Route: general local'
  return `Route: ${r}`
}

function clip(value: string, max: number) {
  const text = value.trim()
  if (text.length <= max) return text
  return `${text.slice(0, max - 1)}…`
}

function humanReason(reason: string | undefined) {
  if (!reason) return ''
  return reason.replaceAll('_', ' ')
}

function toolPathsFromOutput(output: Record<string, unknown>): string[] {
  const paths: string[] = []
  const push = (raw: unknown) => {
    if (typeof raw !== 'string') return
    const clean = raw.trim()
    if (!clean || paths.includes(clean)) return
    paths.push(shortPath(clean))
  }
  push(output.path)
  push(output.relative_path)
  if (Array.isArray(output.results)) {
    for (const row of output.results) {
      if (!row || typeof row !== 'object') continue
      const rec = row as Record<string, unknown>
      push(rec.relative_path || rec.path)
    }
  }
  if (Array.isArray(output.paths)) {
    for (const p of output.paths) push(p)
  }
  if (Array.isArray(output.preferred_read_paths)) {
    for (const p of output.preferred_read_paths) push(p)
  }
  return paths
}

function shortPath(path: string) {
  const normalized = path.replaceAll('\\', '/')
  const parts = normalized.split('/').filter(Boolean)
  if (parts.length <= 3) return path
  return parts.slice(-3).join('/')
}
