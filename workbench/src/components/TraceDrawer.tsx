import { AlertTriangle, CheckCircle2, CircleSlash2, ShieldQuestion } from 'lucide-react'
import { useState } from 'react'
import type { PatchApplyReceipt, ReleaseDecision, Trace } from '../types'

const releaseMeta: Record<ReleaseDecision, { label: string; icon: typeof CheckCircle2 }> = {
  answerable: { label: 'Released', icon: CheckCircle2 },
  withhold: { label: 'Withheld', icon: ShieldQuestion },
  conflict: { label: 'Conflict', icon: AlertTriangle },
  no_evidence: { label: 'No evidence', icon: CircleSlash2 },
}

export function TraceDrawer({
  trace,
  onApplyPatch,
}: {
  trace: Trace | null
  onApplyPatch?: (toolRunId: string) => Promise<PatchApplyReceipt>
}) {
  const [applying, setApplying] = useState<string | null>(null)
  const [patchError, setPatchError] = useState('')
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

function summarizeToolOutput(output: Record<string, unknown>) {
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
