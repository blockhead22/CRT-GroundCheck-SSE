import { AlertTriangle, CheckCircle2, CircleSlash2, ShieldQuestion } from 'lucide-react'
import { useState } from 'react'
import type { PatchApplyReceipt, ReleaseDecision, Trace } from '../types'

const releaseMeta: Record<ReleaseDecision, { label: string; icon: typeof CheckCircle2 }> = {
  answerable: { label: 'Released', icon: CheckCircle2 },
  withhold: { label: 'Withheld', icon: ShieldQuestion },
  conflict: { label: 'Conflict', icon: AlertTriangle },
  no_evidence: { label: 'No evidence', icon: CircleSlash2 },
}

function toolMetadata(output: Record<string, unknown>) {
  const rows: Array<{ label: string; value: string }> = []
  const competency = typeof output.competency_checks === 'object' && output.competency_checks
    ? output.competency_checks as Record<string, unknown>
    : {}
  const firstResult = Array.isArray(output.results)
    ? output.results.find((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    : null
  const path = typeof output.path === 'string'
    ? output.path
    : typeof firstResult?.path === 'string'
      ? firstResult.path
      : ''
  const writePerformed = typeof output.write_performed === 'boolean'
    ? output.write_performed
    : typeof competency.write_performed === 'boolean'
      ? competency.write_performed
      : null
  const staleHash = typeof output.sha256 === 'string' || competency.stale_hash_captured === true

  if (path) rows.push({ label: firstResult ? 'Top path' : 'Path', value: path })
  if (typeof output.test_file === 'string') rows.push({ label: 'Test file', value: output.test_file })
  if (typeof output.command === 'string' && output.command) rows.push({ label: 'Command', value: output.command })
  if (typeof output.start_line === 'number' && typeof output.end_line === 'number') {
    rows.push({ label: 'Lines', value: `${output.start_line}-${output.end_line}` })
  }
  if (typeof output.ready === 'boolean') rows.push({ label: 'Ready', value: output.ready ? 'yes' : 'no' })
  if (typeof output.applied === 'boolean') rows.push({ label: 'Applied', value: output.applied ? 'yes' : 'no' })
  if (typeof output.executed === 'boolean') rows.push({ label: 'Executed', value: output.executed ? 'yes' : 'no' })
  if (typeof output.exit_code === 'number') rows.push({ label: 'Exit code', value: String(output.exit_code) })
  if (typeof output.passed === 'boolean') rows.push({ label: 'Passed', value: output.passed ? 'yes' : 'no' })
  if (typeof output.timed_out === 'boolean') rows.push({ label: 'Timed out', value: output.timed_out ? 'yes' : 'no' })
  if (typeof output.duration_ms === 'number') rows.push({ label: 'Duration', value: `${output.duration_ms} ms` })
  if (writePerformed !== null) rows.push({ label: 'Write', value: writePerformed ? 'performed' : 'not performed' })
  if (staleHash) rows.push({ label: 'Stale hash', value: 'captured' })
  if (typeof output.error === 'string') rows.push({ label: 'Error', value: output.error })
  return rows.slice(0, 10)
}

function toolOutputBlocks(output: Record<string, unknown>) {
  return [
    typeof output.stdout === 'string' && output.stdout.trim()
      ? { label: 'stdout', value: clipToolOutput(output.stdout) }
      : null,
    typeof output.stderr === 'string' && output.stderr.trim()
      ? { label: 'stderr', value: clipToolOutput(output.stderr) }
      : null,
  ].filter((item): item is { label: string; value: string } => Boolean(item))
}

function clipToolOutput(value: string) {
  const trimmed = value.trim()
  if (trimmed.length <= 1600) return trimmed
  return `...${trimmed.slice(-1600)}`
}

function toolSnippetBlocks(output: Record<string, unknown>) {
  const blocks: Array<{ label: string; value: string }> = []
  if (typeof output.content === 'string' && output.content.trim()) {
    blocks.push({ label: 'read content', value: clipToolOutput(output.content) })
  }
  if (Array.isArray(output.results)) {
    for (const result of output.results) {
      if (!isRecord(result) || blocks.length >= 4) continue
      const path = typeof result.path === 'string' ? result.path : 'result'
      const excerpts = Array.isArray(result.excerpts)
        ? result.excerpts
          .filter(isRecord)
          .map((excerpt) => {
            const line = typeof excerpt.line === 'number' ? `${excerpt.line}: ` : ''
            const text = typeof excerpt.text === 'string' ? excerpt.text : ''
            return `${line}${text}`.trim()
          })
          .filter(Boolean)
        : []
      if (excerpts.length) {
        blocks.push({
          label: path,
          value: clipToolOutput(excerpts.join('\n')),
        })
      }
    }
  }
  return blocks
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function toolNotice(status: string, output: Record<string, unknown>) {
  if (status !== 'completed') {
    if (typeof output.error === 'string' && output.error) return output.error
    return 'Tool did not complete.'
  }
  if (typeof output.error === 'string' && output.error) return output.error
  if (output.ready === false && typeof output.path === 'string') {
    if (typeof output.occurrences === 'number') {
      return `Patch is not ready: expected one exact match, found ${output.occurrences}.`
    }
    return 'Patch is not ready; exact replacement text is required.'
  }
  if (output.applied === false && output.ready === true && typeof output.sha256 === 'string') {
    return 'Patch is preview-only. Approval is required, and apply will be blocked if the file hash changes.'
  }
  if (output.timed_out === true) return 'Test timed out before completion.'
  return ''
}

export function TraceDrawer({
  trace,
  error = '',
  onApplyPatch,
}: {
  trace: Trace | null
  error?: string
  onApplyPatch?: (toolRunId: string) => Promise<PatchApplyReceipt>
}) {
  const [applying, setApplying] = useState<string | null>(null)
  const [patchError, setPatchError] = useState('')
  if (error) {
    return (
      <div className="drawer-empty">
        <AlertTriangle size={28} />
        <h3>Trace unavailable</h3>
        <p>{error}</p>
      </div>
    )
  }
  if (!trace) {
    return (
      <div className="drawer-empty">
        <ShieldQuestion size={28} />
        <h3>No release trace yet</h3>
        <p>Ask Aether something. Each clause will show what memory was released, held back, or missing.</p>
      </div>
    )
  }

  return (
    <div className="trace-view">
      <div className="trace-summary">
        <div>
          <span>Coverage</span>
          <strong>{Math.round(trace.plan.coverage * 100)}%</strong>
        </div>
        <div>
          <span>Planner</span>
          <strong>{trace.plan.status}</strong>
        </div>
        <div>
          <span>Result</span>
          <strong>{trace.status}</strong>
        </div>
      </div>
      <article className="trace-route" aria-label="Response route">
        <div className="tool-run-heading">Response route</div>
        <div className="route-grid">
          {responseRoute(trace).map((item) => (
            <div className="route-cell" key={item.label}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </article>
      {responseDepth(trace).length ? (
        <article className="trace-route" aria-label="Response depth">
          <div className="tool-run-heading">Response depth</div>
          <div className="route-grid">
            {responseDepth(trace).map((item) => (
              <div className="route-cell" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
        </article>
      ) : null}
      {trace.document_write ? (
        <article className="trace-packet answerable tool-packet">
          <div className="packet-head">
            <CheckCircle2 size={17} />
            <span>Context saved</span>
            <code>{trace.document_write.chunk_count} chunks</code>
          </div>
          <p className="clause-text">{trace.document_write.title}</p>
        </article>
      ) : null}
      {trace.tool_runs?.length ? (
        <section className="tool-run-list" aria-label="Tool activity">
          <div className="tool-run-heading">Tools used</div>
          {trace.tool_runs.map((run) => (
            <article className={`trace-packet tool-packet ${run.status === 'completed' ? 'answerable' : 'conflict'}`} key={run.tool_run_id}>
              <div className="packet-head">
                {run.status === 'completed' ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}
                <span>{run.tool.replaceAll('_', ' ')}</span>
                <code>{run.status}</code>
              </div>
              <p className="tool-output">{summarizeToolOutput(run.output)}</p>
              {toolNotice(run.status, run.output) ? (
                <div className="tool-notice" role="status">{toolNotice(run.status, run.output)}</div>
              ) : null}
              {toolMetadata(run.output).length ? (
                <div className="tool-meta-grid" aria-label={`${run.tool.replaceAll('_', ' ')} metadata`}>
                  {toolMetadata(run.output).map((item) => (
                    <div className="tool-meta-cell" key={item.label}>
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                    </div>
                  ))}
                </div>
              ) : null}
              {toolOutputBlocks(run.output).length ? (
                <div className="tool-output-blocks" aria-label={`${run.tool.replaceAll('_', ' ')} captured output`}>
                  {toolOutputBlocks(run.output).map((item) => (
                    <section className="tool-output-block" key={item.label}>
                      <div>{item.label}</div>
                      <pre>{item.value}</pre>
                    </section>
                  ))}
                </div>
              ) : null}
              {toolSnippetBlocks(run.output).length ? (
                <div className="tool-snippet-blocks" aria-label={`${run.tool.replaceAll('_', ' ')} retrieved snippets`}>
                  {toolSnippetBlocks(run.output).map((item) => (
                    <section className="tool-snippet-block" key={item.label}>
                      <div>{item.label}</div>
                      <pre>{item.value}</pre>
                    </section>
                  ))}
                </div>
              ) : null}
              {run.tool === 'workspace_patch_propose' && typeof run.output.patch === 'string' ? (
                <>
                  {typeof run.output.rationale === 'string' ? (
                    <p className="patch-rationale"><strong>Why:</strong> {run.output.rationale}</p>
                  ) : null}
                  {typeof run.output.verification === 'string' ? (
                    <p className="patch-rationale"><strong>Verify:</strong> {run.output.verification}</p>
                  ) : null}
                  <pre className="patch-preview">{run.output.patch}</pre>
                  {run.output.ready === true && run.output.applied !== true ? (
                    <button
                      className="approve-patch"
                      disabled={!onApplyPatch || applying === run.tool_run_id}
                      onClick={async () => {
                        if (!onApplyPatch) return
                        setApplying(run.tool_run_id)
                        setPatchError('')
                        try {
                          await onApplyPatch(run.tool_run_id)
                        } catch (reason) {
                          setPatchError(reason instanceof Error ? reason.message : 'Patch application failed.')
                        } finally {
                          setApplying(null)
                        }
                      }}
                    >
                      {applying === run.tool_run_id ? 'Applying…' : 'Approve exact patch'}
                    </button>
                  ) : null}
                  {run.output.applied === true ? (
                    <div className="patch-applied">Applied · receipt {String(run.output.receipt_id || '')}</div>
                  ) : null}
                </>
              ) : null}
            </article>
          ))}
          {patchError ? <div className="inline-notice">{patchError}</div> : null}
        </section>
      ) : null}
      <div className="packet-list">
        {trace.plan.clauses.map((clause) => {
          const packets = trace.packets.filter((packet) => packet.clause_id === clause.clause_id)
          if (!packets.length) {
            return (
              <article className="trace-packet no_evidence" key={clause.clause_id}>
                <div className="packet-head">
                  <CircleSlash2 size={17} />
                  <span>No resolved slot</span>
                </div>
                <p className="clause-text">{clause.text}</p>
                <small>{clause.reason_code}</small>
              </article>
            )
          }
          return packets.map((packet) => {
            const meta = releaseMeta[packet.release]
            const Icon = meta.icon
            return (
              <article className={`trace-packet ${packet.release}`} key={packet.request_id}>
                <div className="packet-head">
                  <Icon size={17} />
                  <span>{meta.label}</span>
                  <code>{packet.slot_id}</code>
                </div>
                <p className="clause-text">{packet.clause_text}</p>
                <div className="decision-row">
                  <span>{packet.mode}</span>
                  <span>{packet.reason.replaceAll('_', ' ')}</span>
                </div>
                {packet.contradiction_disposition ? (
                  <div className="disposition-row" aria-label="Contradiction disposition">
                    <strong>{packet.contradiction_disposition.label.replaceAll('_', ' ')}</strong>
                    <span>
                      {packet.contradiction_disposition.reason.replaceAll('_', ' ')}
                      {' '}
                      ({Math.round(packet.contradiction_disposition.confidence * 100)}%)
                    </span>
                  </div>
                ) : null}
                {packet.evidence.map((item) => (
                  <div className="evidence-row" key={item.state_id}>
                    <div>
                      <strong>{item.value}</strong>
                      <span>{item.authority} · {Math.round(item.trust * 100)}% trust</span>
                    </div>
                    <small>{item.source}</small>
                  </div>
                ))}
              </article>
            )
          })
        })}
      </div>
    </div>
  )
}

function responseDepth(trace: Trace) {
  const depth = trace.completion?.depth
  const policy = depth || trace.depth_policy
  if (!policy) return []
  const assessment = depth?.assessment
  return [
    { label: 'Mode', value: policy.mode },
    { label: 'Requested', value: policy.requested ? 'yes' : 'no' },
    depth ? { label: 'Continued', value: String(depth.continuation_count) } : null,
    depth ? { label: 'Satisfied', value: depth.depth_satisfied ? 'yes' : 'no' } : null,
    assessment?.word_count != null ? { label: 'Words', value: String(assessment.word_count) } : null,
    depth?.continued_reason ? { label: 'Reason', value: depth.continued_reason.replaceAll('_', ' ') } : null,
  ].filter((item): item is { label: string; value: string } => Boolean(item))
}

function responseRoute(trace: Trace) {
  const generationModel = trace.completion?.generation_model || trace.generation_model || trace.model
  const guidanceKind = trace.completion?.guidance_kind || trace.character_answer?.kind || ''
  const source = trace.completion?.source || trace.meta_answer?.source || trace.direct_answer?.source
    || trace.self_description_answer?.source || trace.character_answer?.source || 'local_generation'
  const repair = trace.completion?.guidance_repaired == null
    ? ''
    : trace.completion.guidance_repair_failed
      ? 'repair failed'
      : trace.completion.guidance_repaired
        ? 'repaired'
        : 'clean'
  return [
    { label: 'Source', value: source.replaceAll('_', ' ') },
    { label: 'Selected', value: trace.model },
    { label: 'Generated', value: generationModel },
    guidanceKind ? { label: 'Guidance', value: guidanceKind.replaceAll('_', ' ') } : null,
    repair ? { label: 'Repair', value: repair } : null,
    trace.completion ? {
      label: 'Boundary',
      value: trace.completion.needs_stronger_model ? 'needs stronger model' : 'local ok',
    } : null,
  ].filter((item): item is { label: string; value: string } => Boolean(item))
}

function summarizeToolOutput(output: Record<string, unknown>) {
  if (typeof output.command === 'string' && output.command) {
    return `Suggested command: ${output.command}`
  }
  if (output.applied === false && typeof output.path === 'string') {
    if (output.ready === true) return `Patch preview ready · not applied · ${output.path}`
    if (typeof output.error === 'string') return `Patch not ready · ${output.error}`
    return `Patch needs exact replacement text · ${output.path}`
  }
  if (Array.isArray(output.results)) return `${output.results.length} result(s) returned`
  if (Array.isArray(output.entries) && typeof output.path === 'string') {
    return `${output.path} · ${output.entries.length} entries`
  }
  if (typeof output.path === 'string') {
    if (typeof output.start_line === 'number' && typeof output.end_line === 'number') {
      return `${output.path} · lines ${output.start_line}-${output.end_line}`
    }
    return output.path
  }
  if (typeof output.purpose === 'string') return output.purpose
  if (typeof output.model === 'string') return `Model: ${output.model}`
  return Object.keys(output).slice(0, 4).join(' · ') || 'No result'
}
