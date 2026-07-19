import { AlertTriangle, CheckCircle2, CircleSlash2, ShieldQuestion } from 'lucide-react'
import { useState } from 'react'
import type {
  CompletionVerification,
  GovernanceAnswerSpine,
  GovernanceSpineCompliance,
  LocalRouterRagEvidenceReview,
  PatchApplyReceipt,
  PublicGovernanceStep,
  ReleaseDecision,
  Trace,
} from '../types'

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
  const evidenceReview = localRouterEvidenceReview(trace)
  const governanceReview = governanceSpineReview(trace)
  const completionVerification = trace.completion?.verification_summary
  const completionCoverage = trace.coverage
  // Continuity is a read-only, source-bound route and intentionally has no
  // durable-memory clause plan or evidence packets.  The drawer still needs
  // to show its receipt and public trace rather than treating that omission
  // as a rendering error.
  const plan = trace.plan || {
    status: 'not_applicable',
    coverage: 0,
    coverage_applicable: false,
    unresolved_clauses: [],
    clauses: [],
  }
  const packets = trace.packets || []
  const coverageLabel = completionCoverage?.status === 'complete'
    ? `${completionCoverage.passed ?? 0}/${completionCoverage.applicable ?? 0}`
    : plan.coverage_applicable === false
      ? 'not applicable'
      : `${Math.round(plan.coverage * 100)}%`
  const plannerLabel = trace.planner
    ? trace.planner.applicable ? trace.planner.status : 'not applicable'
    : plan.status
  const resultLabel = trace.result?.status || trace.status

  return (
    <div className="trace-view">
      <div className="trace-summary">
        <div>
          <span>Coverage</span>
          <strong>{coverageLabel}</strong>
        </div>
        <div>
          <span>Planner</span>
          <strong>{plannerLabel}</strong>
        </div>
        <div>
          <span>Result</span>
          <strong>{resultLabel}</strong>
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
      {routeDecision(trace).length ? (
        <article className="trace-route" aria-label="Route decision">
          <div className="tool-run-heading">Route decision</div>
          <div className="route-grid">
            {routeDecision(trace).map((item) => (
              <div className="route-cell" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
        </article>
      ) : null}
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
      {governanceReview ? (
        <article className="trace-route" aria-label="Governance spine">
          <div className="tool-run-heading">Governance spine</div>
          <div className="route-grid">
            {governanceSpineRows(governanceReview.spine, governanceReview.compliance).map((item) => (
              <div className="route-cell" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
          {governanceReview.compliance?.flags?.length ? (
            <div className="tool-notice" role="status">
              Flags: {governanceReview.compliance.flags.map(formatRouteValue).join(', ')}
            </div>
          ) : null}
          {governanceReview.spine.render_contract?.length ? (
            <p className="tool-output">
              {governanceReview.spine.render_contract.slice(0, 2).join(' · ')}
            </p>
          ) : null}
          {governanceReview.spine.tension_packet ? (
            <div className="tool-meta-grid" aria-label="Tension packet">
              {tensionPacketRows(governanceReview.spine).map((item) => (
                <div className="tool-meta-cell" key={item.label}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>
          ) : null}
        </article>
      ) : null}
      {completionVerification ? (
        <article className="trace-route" aria-label="Completion verification">
          <div className="tool-run-heading">Completion verification</div>
          <div className="route-grid">
            {completionVerificationRows(completionVerification).map((item) => (
              <div className="route-cell" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
        </article>
      ) : null}
      {trace.continuity_alignment_receipt ? (
        <article className="trace-route" aria-label="Cross-conversation alignment receipt">
          <div className="tool-run-heading">Cross-conversation alignment</div>
          <div className="route-grid">
            <div className="route-cell"><span>Status</span><strong>{trace.continuity_alignment_receipt.status}</strong></div>
            <div className="route-cell"><span>Retrieval</span><strong>{trace.continuity_alignment_receipt.retrieval_method.replaceAll('_', ' ')}</strong></div>
            <div className="route-cell"><span>Source</span><strong>{trace.continuity_alignment_receipt.source_conversation_ids.join(', ') || 'none'}</strong></div>
            <div className="route-cell"><span>Profile writes</span><strong>{trace.continuity_alignment_receipt.profile_memory_write_count}</strong></div>
          </div>
          {trace.cross_conversation_context?.candidates?.length ? (
            <div className="tool-meta-grid" aria-label="Conversation retrieval candidates">
              {trace.cross_conversation_context.candidates.map((candidate) => (
                <div className="tool-meta-cell" key={candidate.conversation_id}>
                  <span>{candidate.match_kind.replaceAll('_', ' ')} · {candidate.score.toFixed(3)}</span>
                  <strong>{candidate.title} ({candidate.conversation_id})</strong>
                </div>
              ))}
            </div>
          ) : null}
          {trace.cross_conversation_context?.turns?.length ? (
            <div className="tool-snippet-blocks" aria-label="Cited archived conversation turns">
              {trace.cross_conversation_context.turns.map((turn) => (
                <section className="tool-snippet-block" key={turn.turn_id}>
                  <div>{turn.turn_id} · user · {turn.user.authority.replaceAll('_', ' ')}</div>
                  <pre>{turn.user.text}</pre>
                  {turn.assistant.included ? (
                    <>
                      <div>assistant · accepted derived answer</div>
                      <pre>{turn.assistant.text}</pre>
                    </>
                  ) : (
                    <div className="tool-notice" role="status">
                      Assistant excluded: {turn.assistant.exclusion_reason.replaceAll('_', ' ')}
                    </div>
                  )}
                </section>
              ))}
            </div>
          ) : null}
        </article>
      ) : null}
      {trace.task_continuation_receipt ? (
        <article className="trace-route" aria-label="Task continuation receipt">
          <div className="tool-run-heading">Task continuation</div>
          <div className="route-grid">
            <div className="route-cell"><span>Status</span><strong>{trace.task_continuation_receipt.status.replaceAll('_', ' ')}</strong></div>
            <div className="route-cell"><span>Open loop</span><strong>{trace.task_continuation_receipt.selected_loop_id || 'none'}</strong></div>
            <div className="route-cell"><span>Next action authorized</span><strong>{trace.task_continuation_receipt.next_action_authorized ? 'yes' : 'no'}</strong></div>
            <div className="route-cell"><span>Automatic execution</span><strong>{trace.task_continuation_receipt.automatic_execution_allowed ? 'allowed' : 'blocked'}</strong></div>
            <div className="route-cell"><span>Workspace tools</span><strong>{trace.task_continuation_receipt.workspace_tool_use_allowed ? 'allowed' : 'blocked'}</strong></div>
            <div className="route-cell"><span>Durable writes</span><strong>{trace.task_continuation_receipt.durable_write_count}</strong></div>
            <div className="route-cell"><span>Profile writes</span><strong>{trace.task_continuation_receipt.profile_memory_write_count}</strong></div>
          </div>
          {trace.task_continuation_packet?.next_action ? (
            <p className="tool-output">{trace.task_continuation_packet.next_action}</p>
          ) : null}
        </article>
      ) : null}
      {trace.public_governance_steps?.length ? (
        <article className="trace-route" aria-label="Public governance steps">
          <div className="tool-run-heading">Public governance steps</div>
          <div className="governance-step-list">
            {trace.public_governance_steps.map((step) => (
              <div className="governance-step-row" key={step.step_id}>
                <span>{formatStepStatus(step)}</span>
                <strong>{step.summary}</strong>
                <p>{step.detail}</p>
              </div>
            ))}
          </div>
        </article>
      ) : null}
      {evidenceReview ? (
        <article className="trace-route" aria-label="Local router evidence review">
          <div className="tool-run-heading">Local router evidence review</div>
          <div className="route-grid">
            {localRouterEvidenceRows(evidenceReview).map((item) => (
              <div className="route-cell" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
          <p className="tool-output">{evidenceReview.next_review}</p>
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
        {plan.clauses.map((clause) => {
          const clausePackets = packets.filter((packet) => packet.clause_id === clause.clause_id)
          if (!clausePackets.length) {
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
          return clausePackets.map((packet) => {
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

function localRouterEvidenceReview(trace: Trace): LocalRouterRagEvidenceReview | null {
  const source = trace.local_router_trace?.evidence_review || trace.local_router_trace
  if (!isRecord(source) || source.kind !== 'local_router_rag_evidence_review') return null
  return source as unknown as LocalRouterRagEvidenceReview
}

function governanceSpineReview(trace: Trace): {
  spine: GovernanceAnswerSpine
  compliance?: GovernanceSpineCompliance
} | null {
  if (!trace.governance_answer_spine) return null
  return {
    spine: trace.governance_answer_spine,
    compliance: trace.completion?.governance_spine_compliance,
  }
}

function governanceSpineRows(
  spine: GovernanceAnswerSpine,
  compliance?: GovernanceSpineCompliance,
) {
  const scope = spine.context_scope || {}
  const route = spine.route || {}
  const safety = spine.safety_contract || {}
  return [
    { label: 'Render', value: formatRouteValue(spine.render_mode || 'unknown') },
    spine.deterministic_source ? {
      label: 'Deterministic',
      value: formatRouteValue(spine.deterministic_source),
    } : null,
    route.selected_route ? {
      label: 'Route',
      value: formatRouteValue(route.selected_route),
    } : null,
    route.selected_model_policy ? {
      label: 'Model policy',
      value: formatRouteValue(route.selected_model_policy),
    } : null,
    {
      label: 'Answerable',
      value: String(scope.answerable_packet_count ?? spine.answerable?.length ?? 0),
    },
    {
      label: 'Restricted',
      value: String(scope.restricted_packet_count ?? spine.restricted?.length ?? 0),
    },
    { label: 'Guidance', value: scope.has_answer_guidance ? 'yes' : 'no' },
    { label: 'Context bridge', value: scope.has_context_bridge ? 'yes' : 'no' },
    compliance ? {
      label: 'Compliance',
      value: compliance.passed ? 'passed' : 'flagged',
    } : { label: 'Compliance', value: 'pending' },
    compliance ? {
      label: 'Flags',
      value: String(compliance.flags?.length ?? 0),
    } : null,
    compliance ? {
      label: 'Restricted leak',
      value: compliance.restricted_value_leak ? 'yes' : 'no',
    } : null,
    compliance ? {
      label: 'Memory claim',
      value: compliance.unauthorized_memory_write_claim ? 'yes' : 'no',
    } : null,
    {
      label: 'Memory writes',
      value: safety.memory_writes_allowed ? 'allowed' : 'blocked',
    },
    {
      label: 'Raw CoT',
      value: safety.raw_chain_of_thought_stored ? 'stored' : 'not stored',
    },
  ].filter((item): item is { label: string; value: string } => Boolean(item))
}

function completionVerificationRows(verification: CompletionVerification) {
  const summary = [
    {
      label: 'Overall',
      value: verification.failed_dimension_count
        ? 'flagged'
        : verification.fully_verified ? 'fully verified' : 'partially checked',
    },
    {
      label: 'Checked',
      value: `${verification.checked_dimension_count}/${verification.applicable_dimension_count}`,
    },
  ]
  const dimensions = Object.entries(verification.dimensions).map(([name, value]) => ({
    label: formatRouteValue(name),
    value: formatRouteValue(value.status),
  }))
  return [...summary, ...dimensions]
}

function tensionPacketRows(spine: GovernanceAnswerSpine) {
  const packet = spine.tension_packet
  if (!packet) return []
  const [sideA, sideB] = packet.sides || []
  return [
    { label: 'Packet', value: formatRouteValue(packet.tension_type || packet.packet_id) },
    sideA ? { label: 'Side A', value: `${sideA.label}: ${sideA.claim}` } : null,
    sideB ? { label: 'Side B', value: `${sideB.label}: ${sideB.claim}` } : null,
    { label: 'Allowed synthesis', value: packet.allowed_synthesis },
    { label: 'Forbidden collapse', value: packet.forbidden_collapse },
    { label: 'Trace preview', value: packet.trace_summary },
  ].filter((item): item is { label: string; value: string } => Boolean(item?.value))
}

function formatStepStatus(step: PublicGovernanceStep) {
  return formatRouteValue(step.status || 'done')
}

function localRouterEvidenceRows(review: LocalRouterRagEvidenceReview | null) {
  if (!review) return []
  const governed = review.baselines.governed
  const scaffolded = review.baselines.scaffolded_rag
  const safety = review.safety_contract
  const delta = review.governed_delta_vs_scaffolded_rag
  return [
    { label: 'Pack', value: review.pack || 'unknown' },
    { label: 'Cases', value: String(review.case_count) },
    { label: 'Baseline', value: formatRouteValue(review.baseline_to_beat) },
    governed ? { label: 'Governed', value: formatPassRate(governed.answer_pass_count, review.case_count, governed.answer_avg_score) } : null,
    scaffolded ? { label: 'Scaffolded RAG', value: formatPassRate(scaffolded.answer_pass_count, review.case_count, scaffolded.answer_avg_score) } : null,
    { label: 'Delta', value: formatDelta(delta.answer_pass_delta, delta.answer_avg_score_delta) },
    { label: 'Trace', value: delta.trace_complete ? 'complete' : 'needs review' },
    { label: 'Promotion', value: formatRouteValue(safety.promotion_status) },
    { label: 'Memory writes', value: safety.memory_writes_allowed ? 'allowed' : 'blocked' },
    { label: 'Silent mutation', value: safety.silent_policy_mutation_allowed ? 'allowed' : 'blocked' },
    review.review_flags.includes('perfect_governed_score_requires_holdout')
      ? { label: 'Caution', value: 'holdout required' }
      : null,
  ].filter((item): item is { label: string; value: string } => Boolean(item))
}

function formatPassRate(passCount: number, total: number, score: number | null) {
  const scoreText = score == null ? 'no score' : `avg ${score.toFixed(3)}`
  return `${passCount}/${total} ${scoreText}`
}

function formatDelta(passDelta: number, scoreDelta: number | null) {
  const sign = passDelta > 0 ? '+' : ''
  const score = scoreDelta == null ? 'no score delta' : `${scoreDelta >= 0 ? '+' : ''}${scoreDelta.toFixed(3)} avg`
  return `${sign}${passDelta} pass, ${score}`
}

function routeDecision(trace: Trace) {
  const decision = trace.completion?.route_decision || trace.route_decision
  if (!decision) return []
  const recommendation = decision.model_recommendation
  return [
    { label: 'Selected route', value: formatRouteValue(decision.selected_route) },
    { label: 'Model policy', value: formatRouteValue(decision.selected_model_policy) },
    recommendation?.current_selected_model ? {
      label: 'Current model',
      value: recommendation.current_selected_model,
    } : null,
    recommendation?.recommended_model_policy ? {
      label: 'Recommended',
      value: formatRouteValue(recommendation.recommended_model_policy),
    } : null,
    recommendation?.fallback_model ? {
      label: 'Fallback',
      value: recommendation.fallback_model,
    } : null,
    recommendation?.confidence ? {
      label: 'Confidence',
      value: formatRouteValue(recommendation.confidence),
    } : null,
    { label: 'Tool policy', value: formatRouteValue(decision.tool_policy) },
    { label: 'Repair', value: formatRouteValue(decision.repair_policy) },
    { label: 'Risk', value: formatRouteValue(decision.risk_level) },
    { label: 'Escalation', value: decision.escalation_allowed ? 'allowed' : 'no' },
    recommendation?.latency_caveat ? {
      label: 'Latency',
      value: recommendation.latency_caveat,
    } : null,
    recommendation?.evidence_path ? {
      label: 'Evidence',
      value: recommendation.evidence_path,
    } : null,
  ].filter((item): item is { label: string; value: string } => Boolean(item))
}

function formatRouteValue(value: string) {
  return value.replaceAll('_', ' ')
}

function responseRoute(trace: Trace) {
  const generationModel = trace.completion?.generation_model || trace.generation_model || trace.model
  const renderProvider = trace.completion?.render_provider
  const hostedRenderer = renderProvider?.effective === 'grok_build'
  const verification = trace.completion?.verification_summary
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
    { label: 'Source', value: hostedRenderer ? 'Aether governed' : source.replaceAll('_', ' ') },
    { label: 'Selected', value: trace.model },
    { label: 'Generated', value: generationModel },
    hostedRenderer ? { label: 'Provider', value: 'Grok governed renderer' } : null,
    renderProvider?.fallback_applied ? { label: 'Provider', value: 'Local fallback' } : null,
    guidanceKind ? { label: 'Guidance', value: guidanceKind.replaceAll('_', ' ') } : null,
    repair ? { label: 'Repair', value: repair } : null,
    trace.completion ? {
      label: 'Boundary',
      value: trace.completion.needs_stronger_model
        ? 'needs stronger model'
        : hostedRenderer
          ? verification?.accepted === false
            ? 'release rejected'
            : verification?.fully_verified
              ? 'Aether verified'
              : 'Aether accepted · partial checks'
          : 'local ok',
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
