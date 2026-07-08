import { AlertTriangle, ArrowUp, BrainCircuit, CheckCircle2, CircleDashed, CircleSlash2, Database, ExternalLink, LoaderCircle, Plus, ShieldCheck, Sparkles, Trash2 } from 'lucide-react'
import { FormEvent, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api, streamChat } from '../api'
import type { Conversation, PublicGovernanceStep, Trace, Turn } from '../types'
import { ModelPolicySummary } from './ModelPolicySummary'

const VOICE_STORAGE_KEY = 'aether.voiceProfile'
const VOICE_OPTIONS = [
  { value: 'grounded', label: 'Grounded' },
  { value: 'warm', label: 'Warm' },
  { value: 'alive', label: 'Alive' },
]

interface ChatPanelProps {
  model: string
  conversationId: string | null
  conversations: Conversation[]
  turns: Turn[]
  codexAvailable: boolean
  trace: Trace | null
  onConversation: (conversationId: string) => void
  onNewConversation: () => void
  onDeleteConversation: () => void
  onTrace: (trace: Trace) => void
  onOpenTrace: (turnId: string) => void
  onTurns: (turns: Turn[]) => void
}

export function ChatPanel({
  model,
  conversationId,
  conversations,
  turns,
  codexAvailable,
  trace,
  onConversation,
  onNewConversation,
  onDeleteConversation,
  onTrace,
  onOpenTrace,
  onTurns,
}: ChatPanelProps) {
  const [message, setMessage] = useState('')
  const [streaming, setStreaming] = useState('')
  const [governanceSteps, setGovernanceSteps] = useState<PublicGovernanceStep[]>([])
  const [thinkingTraceCache, setThinkingTraceCache] = useState<Record<string, Trace>>({})
  const [openThinkingTurn, setOpenThinkingTurn] = useState<string | null>(null)
  const [thinkingLoadingTurn, setThinkingLoadingTurn] = useState<string | null>(null)
  const [pendingTurn, setPendingTurn] = useState<string | null>(null)
  const [pendingUser, setPendingUser] = useState('')
  const [needsStronger, setNeedsStronger] = useState(false)
  const [escalating, setEscalating] = useState(false)
  const [frontierAnswer, setFrontierAnswer] = useState('')
  const [error, setError] = useState('')
  const [voiceProfile, setVoiceProfile] = useState(() => {
    const stored = window.localStorage.getItem(VOICE_STORAGE_KEY)
    return VOICE_OPTIONS.some((option) => option.value === stored) ? stored || 'warm' : 'warm'
  })
  const scrollRef = useRef<HTMLDivElement>(null)
  const activeConversationRef = useRef(conversationId)
  const activeTraceRef = useRef<Trace | null>(null)
  const dispatchedMapActionsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    activeConversationRef.current = conversationId
  }, [conversationId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns, streaming, frontierAnswer, governanceSteps])

  useEffect(() => {
    window.localStorage.setItem(VOICE_STORAGE_KEY, voiceProfile)
  }, [voiceProfile])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const text = message.trim()
    if (!text || pendingTurn) return
    setMessage('')
    setPendingUser(text)
    setStreaming('')
    setGovernanceSteps([])
    setFrontierAnswer('')
    setNeedsStronger(false)
    setError('')

    try {
      await streamChat(
        { message: text, conversation_id: conversationId || undefined, model, voice_profile: voiceProfile },
        {
          onTurn: ({ turn_id, conversation_id }) => {
            setPendingTurn(turn_id)
            activeConversationRef.current = conversation_id
            onConversation(conversation_id)
          },
          onTrace: (trace) => {
            activeTraceRef.current = trace
            onTrace(trace)
            dispatchWisconsinMapActions(trace, dispatchedMapActionsRef.current)
          },
          onGovernanceStep: (step) => {
            setGovernanceSteps((current) => {
              if (current.some((item) => item.step_id === step.step_id)) return current
              return [...current, step]
            })
          },
          onToken: (token) => setStreaming((current) => current + token),
          onDone: async (done) => {
            const { needs_stronger_model } = done
            setNeedsStronger(needs_stronger_model)
            if (activeTraceRef.current) {
              const completedTrace: Trace = {
                ...activeTraceRef.current,
                completion: {
                  source: done.source || done.guidance_source || inferTraceSource(activeTraceRef.current),
                  needs_stronger_model,
                  generation_model: done.generation_model || activeTraceRef.current.generation_model,
                  guidance_kind: done.guidance_kind || activeTraceRef.current.character_answer?.kind,
                  guidance_repaired: done.guidance_repaired,
                  guidance_repair_failed: done.guidance_repair_failed,
                },
              }
              activeTraceRef.current = completedTrace
              onTrace(completedTrace)
              dispatchWisconsinMapActions(completedTrace, dispatchedMapActionsRef.current)
            }
            try {
              const activeConversation = activeConversationRef.current
              if (activeConversation) onTurns(await api.turns(activeConversation))
            } catch (reason) {
              setError(reason instanceof Error
                ? `Response saved, but refresh failed: ${reason.message}`
                : 'Response saved, but the conversation refresh failed.')
            } finally {
              setPendingTurn(null)
              setPendingUser('')
              setStreaming('')
              setGovernanceSteps([])
            }
          },
          onError: async (reason) => {
            setError(reason)
            try {
              const activeConversation = activeConversationRef.current
              if (activeConversation) onTurns(await api.turns(activeConversation))
            } finally {
              setPendingTurn(null)
              setPendingUser('')
              setStreaming('')
              setGovernanceSteps([])
            }
          },
        },
      )
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Local response failed.')
      setPendingTurn(null)
      setPendingUser('')
      setStreaming('')
      setGovernanceSteps([])
    }
  }

  const lastTurn = turns.at(-1)
  const escalationTurn = pendingTurn || lastTurn?.turn_id
  const showStronger = needsStronger || lastTurn?.needs_stronger_model

  async function escalate() {
    if (!escalationTurn) return
    setEscalating(true)
    setError('')
    try {
      const result = await api.escalate(
        escalationTurn,
        'The local answer needs stronger reasoning or unresolved clauses remain.',
      )
      setFrontierAnswer(result.answer)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Codex escalation failed.')
    } finally {
      setEscalating(false)
    }
  }

  async function toggleThinkingTrace(turnId: string) {
    if (openThinkingTurn === turnId) {
      setOpenThinkingTurn(null)
      return
    }
    setOpenThinkingTurn(turnId)
    const activeTrace = trace?.turn_id === turnId ? trace : thinkingTraceCache[turnId]
    if (activeTrace) return
    setThinkingLoadingTurn(turnId)
    try {
      const result = await api.trace(turnId)
      setThinkingTraceCache((current) => ({ ...current, [turnId]: result.trace }))
      onTrace(result.trace)
    } catch (reason) {
      setError(reason instanceof Error ? `Thinking trace failed: ${reason.message}` : 'Thinking trace failed.')
    } finally {
      setThinkingLoadingTurn(null)
    }
  }

  return (
    <main className="chat-panel">
      <div className="model-strip">
        <div>
          <BrainCircuit size={16} />
          <span>{model}</span>
        </div>
        <div className={`strength-indicator ${showStronger ? 'needs' : ''}`}>
          {showStronger ? 'Needs stronger model' : 'Locally answerable'}
        </div>
      </div>
      <ModelPolicySummary trace={trace} />
      <div className="conversation-toolbar">
        <select
          aria-label="Conversation"
          value={conversationId || ''}
          onChange={(event) => {
            if (event.target.value) onConversation(event.target.value)
          }}
        >
          <option value="">New chat</option>
          {conversations.map((conversation) => (
            <option value={conversation.conversation_id} key={conversation.conversation_id}>
              {conversation.title}
            </option>
          ))}
        </select>
        <select
          aria-label="Aether voice"
          value={voiceProfile}
          onChange={(event) => setVoiceProfile(event.target.value)}
          title="Aether voice"
        >
          {VOICE_OPTIONS.map((option) => (
            <option value={option.value} key={option.value}>{option.label}</option>
          ))}
        </select>
        <button aria-label="New chat" onClick={onNewConversation}>
          <Plus size={15} />
        </button>
        <button
          aria-label="Delete current chat"
          disabled={!conversationId}
          onClick={onDeleteConversation}
        >
          <Trash2 size={14} />
        </button>
      </div>
      <div className="conversation" ref={scrollRef}>
        {!turns.length && !pendingUser ? (
          <div className="welcome">
            <div className="welcome-mark"><Sparkles size={23} /></div>
            <h1>Talk to your governed memory.</h1>
            <p>Aether releases only evidence it can defend. Open the trace when you want to see the line it held.</p>
            <div className="welcome-signals">
              <span><Database size={14} /> Local substrate</span>
              <span><ShieldCheck size={14} /> Clause-level release</span>
            </div>
          </div>
        ) : null}
        {turns.map((turn) => (
          <div className="turn" key={turn.turn_id}>
            <div className="user-message">{turn.user_message}</div>
            <div className="assistant-message">
              <div className="assistant-head">
                <div className="assistant-label"><span className="tiny-mark">Æ</span> Local answer</div>
                <div className="assistant-actions">
                  <button
                    className="turn-thinking-button"
                    aria-label={`Toggle thinking trace for turn ${turn.turn_id}`}
                    title="Thinking trace"
                    onClick={() => void toggleThinkingTrace(turn.turn_id)}
                  >
                    <BrainCircuit size={13} />
                    <span>Thinking</span>
                  </button>
                  <button
                    className="turn-trace-button"
                    aria-label={`Open trace for turn ${turn.turn_id}`}
                    title="Open trace"
                    onClick={() => onOpenTrace(turn.turn_id)}
                  >
                    <ShieldCheck size={13} />
                  </button>
                </div>
              </div>
              <AnswerMarkdown>{turn.local_answer}</AnswerMarkdown>
              {openThinkingTurn === turn.turn_id ? (
                <AnswerThinkingTrace
                  loading={thinkingLoadingTurn === turn.turn_id}
                  trace={trace?.turn_id === turn.turn_id ? trace : thinkingTraceCache[turn.turn_id]}
                />
              ) : null}
              <div className="answer-meta">
                <span>Local</span><span>Governed</span><span>Checked</span>
              </div>
            </div>
          </div>
        ))}
        {pendingUser ? (
          <div className="turn">
            <div className="user-message">{pendingUser}</div>
            <div className="assistant-message streaming">
              <div className="assistant-label"><LoaderCircle className="spin" size={14} /> Governing response</div>
              {governanceSteps.length ? (
                <div className="governance-live-trace" aria-label="Live governance trace">
                  {governanceSteps.map((step) => (
                    <GovernanceLiveStep step={step} key={step.step_id} />
                  ))}
                </div>
              ) : (
                <div className="governance-live-trace" aria-label="Live governance trace">
                  <div className="governance-live-step started">
                    <LoaderCircle className="spin" size={12} />
                    <span className="governance-live-step-copy">
                      <span>Waiting for governance trace</span>
                      <small>Route, memory, tools, and verifier checks have not reported yet.</small>
                    </span>
                    <em>pending</em>
                  </div>
                </div>
              )}
              {streaming ? <AnswerMarkdown>{streaming}</AnswerMarkdown> : <span className="thinking-line" />}
            </div>
          </div>
        ) : null}
        {frontierAnswer ? (
          <div className="frontier-message">
            <div className="assistant-label"><ExternalLink size={14} /> Codex escalation</div>
            <AnswerMarkdown>{frontierAnswer}</AnswerMarkdown>
          </div>
        ) : null}
        {error ? <div className="chat-error">{error}</div> : null}
      </div>
      {showStronger && escalationTurn ? (
        <button className="escalation-bar" disabled={!codexAvailable || escalating} onClick={escalate}>
          <span>
            <strong>Local model reached its boundary</strong>
            <small>{codexAvailable ? 'Send a bounded packet to Codex' : 'Codex is unavailable'}</small>
          </span>
          <span>{escalating ? 'Asking…' : 'Ask Codex'} <ExternalLink size={14} /></span>
        </button>
      ) : null}
      <form className="composer" onSubmit={submit}>
        <textarea
          aria-label="Message Aether"
          placeholder="Ask Aether…"
          rows={2}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              event.currentTarget.form?.requestSubmit()
            }
          }}
        />
        <button aria-label="Send message" disabled={!message.trim() || Boolean(pendingTurn)}>
          <ArrowUp size={17} />
        </button>
        <div className="composer-foot">
          <span><span className="status-dot" /> Aether governs context before inference</span>
          <span>Enter to send</span>
        </div>
      </form>
    </main>
  )
}

function GovernanceLiveStep({ step }: { step: PublicGovernanceStep }) {
  const status = step.status || 'started'
  const statusLabel = governanceStepStatusLabel(status)
  const Icon = governanceStepIcon(status)
  return (
    <div className={`governance-live-step ${status}`} title={step.detail}>
      <Icon className={status === 'started' ? 'spin' : undefined} size={12} />
      <span className="governance-live-step-copy">
        <span>{step.summary}</span>
        <small>{step.detail}</small>
      </span>
      <em>{statusLabel}</em>
    </div>
  )
}

function governanceStepIcon(status: string) {
  if (status === 'done') return CheckCircle2
  if (status === 'skipped') return CircleSlash2
  if (status === 'failed' || status === 'flagged') return AlertTriangle
  if (status === 'started') return LoaderCircle
  return CircleDashed
}

function governanceStepStatusLabel(status: string) {
  if (status === 'done') return 'earned'
  if (status === 'skipped') return 'skipped'
  if (status === 'failed') return 'failed'
  if (status === 'flagged') return 'flagged'
  if (status === 'started') return 'pending'
  return status.replace(/_/g, ' ')
}

function AnswerMarkdown({ children }: { children: string }) {
  return (
    <div className="answer-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ ...props }) => <h2 className="answer-heading answer-heading-lg" {...props} />,
          h2: ({ ...props }) => <h3 className="answer-heading answer-heading-md" {...props} />,
          h3: ({ ...props }) => <h4 className="answer-heading answer-heading-sm" {...props} />,
          blockquote: ({ ...props }) => <blockquote className="answer-callout" {...props} />,
          table: ({ ...props }) => (
            <div className="answer-table-scroll">
              <table {...props} />
            </div>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}

function inferTraceSource(trace: Trace) {
  return trace.meta_answer?.source
    || trace.direct_answer?.source
    || trace.self_description_answer?.source
    || trace.character_answer?.source
    || ''
}

function AnswerThinkingTrace({
  trace,
  loading,
}: {
  trace?: Trace
  loading: boolean
}) {
  if (loading && !trace) {
    return (
      <div className="answer-thinking-panel" aria-label="Answer thinking trace">
        <div className="answer-thinking-loading">
          <LoaderCircle className="spin" size={13} /> Loading thinking trace
        </div>
      </div>
    )
  }
  if (!trace) {
    return (
      <div className="answer-thinking-panel" aria-label="Answer thinking trace">
        <div className="answer-thinking-loading">No thinking trace is available for this turn yet.</div>
      </div>
    )
  }

  const sections = answerThinkingSections(trace)
  return (
    <div className="answer-thinking-panel" aria-label="Answer thinking trace">
      <div className="answer-thinking-heading">How this answer formed</div>
      <div className="answer-thinking-sections">
        {sections.map((section) => (
          <section className="answer-thinking-section" key={section.label}>
            <h4>{section.label}</h4>
            {section.items.length ? (
              <ul>
                {section.items.slice(0, 12).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p>{section.empty}</p>
            )}
          </section>
        ))}
      </div>
    </div>
  )
}

function answerThinkingSections(trace: Trace) {
  const route = trace.completion?.route_decision || trace.route_decision
  const compliance = trace.completion?.governance_spine_compliance
  const process = cleanItems([
    ...(trace.public_governance_steps || []).map((step) => `${step.summary}: ${step.detail}`),
    ...mirusLogicGraphLines(trace),
    ...(trace.memory_candidates || []).map((candidate) => (
      `Mirus candidate: ${formatTraceLabel(candidate.semantic_signal || candidate.candidate_kind || 'review required')}`
    )),
    route?.selected_route ? `Selected route: ${formatTraceLabel(route.selected_route)}` : '',
    route?.selected_model_policy ? `Model policy: ${formatTraceLabel(route.selected_model_policy)}` : '',
    trace.voice_profile ? `Voice profile: ${formatTraceLabel(trace.voice_profile)}` : '',
    route?.repair_policy ? `Repair policy: ${formatTraceLabel(route.repair_policy)}` : '',
    route?.model_recommendation?.recommended_model ? (
      `Recommended model: ${route.model_recommendation.recommended_model} (${route.model_recommendation.confidence})`
    ) : '',
    route?.model_recommendation?.fallback_model && route.model_recommendation.fallback_model !== 'none' ? (
      `Fallback model: ${route.model_recommendation.fallback_model}`
    ) : '',
    trace.governance_answer_spine?.render_mode ? `Render mode: ${formatTraceLabel(trace.governance_answer_spine.render_mode)}` : '',
  ])

  const memory = (trace.packets || []).map((packet) => {
    const evidenceCount = packet.evidence?.length ?? 0
    return `${formatTraceLabel(packet.release)} ${packet.slot_id || packet.planner_slot}: ${evidenceCount} receipt(s)`
  })
  memory.push(...(trace.memory_writes || []).map((write) => (
    `${write.created ? 'Stored' : 'Updated'} ${write.slot_id}: ${write.authority}`
  )))
  memory.push(...(trace.memory_candidates || []).map((candidate) => (
    `Review-only memory candidate ${candidate.slot_id}: ${candidate.summary || candidate.claim_summary || candidate.candidate_kind || 'needs review'}`
  )))

  const tools = (trace.tool_runs || []).map((tool) => (
    `${formatTraceLabel(tool.tool)}: ${formatTraceLabel(tool.status)}`
  ))
  tools.push(...(trace.tool_considerations || []).map((item) => (
    `${formatTraceLabel(item.tool)} ${formatTraceLabel(item.status)}: ${item.reason}`
  )))

  const verifier = cleanItems([
    compliance ? `Governance compliance: ${compliance.passed ? 'passed' : 'flagged'}` : '',
    compliance?.flags?.length ? `Flags: ${compliance.flags.map(formatTraceLabel).join(', ')}` : '',
    safetyBoundaryLine(
      'Memory writes',
      trace.governance_answer_spine?.safety_contract?.memory_writes_allowed ?? route?.memory_write_allowed,
    ),
    safetyBoundaryLine(
      'Silent escalation',
      route?.silent_escalation_allowed,
    ),
    trace.governance_answer_spine?.safety_contract?.raw_chain_of_thought_stored === false
      ? 'Raw hidden chain-of-thought not stored'
      : '',
    trace.governance_answer_spine?.safety_contract?.review_required_before_promotion
      ? 'Promotion requires review before behavior changes'
      : '',
    trace.completion?.guidance_repaired ? 'Repair applied before final answer' : '',
    trace.completion?.guidance_repair_failed ? 'Repair failed; boundary should be reviewed' : '',
  ])

  const learning = cleanItems([
    compliance && !compliance.passed ? 'Potential learning event: answer violated the governance spine.' : '',
    ...(trace.memory_candidates || []).map((candidate) => (
      `Review candidate: ${candidate.slot_id} (${candidate.authority || 'unconfirmed'}, ${candidate.review_required === false ? 'review optional' : 'review required'}, ${candidate.memory_write_allowed === false ? 'write blocked' : 'write policy unknown'})`
    )),
    route?.model_recommendation?.observational_only ? 'Model recommendation stayed observational; no automatic switch.' : '',
    trace.governance_answer_spine?.safety_contract?.review_required_before_promotion ? 'Promotion requires review before behavior changes.' : '',
  ])
  const heldTension = tensionPacketLines(trace)

  return [
    { label: 'Thinking / Process', items: process, empty: 'No public process steps were stored for this turn.' },
    ...(heldTension.length
      ? [{ label: 'Held Tension', items: heldTension, empty: 'No tension packet was stored for this turn.' }]
      : []),
    { label: 'Memory', items: memory, empty: 'No governed memory packets were released for this turn.' },
    { label: 'Tools', items: tools, empty: 'No semantic tool considerations were stored.' },
    { label: 'Verifier', items: verifier, empty: 'No post-render verifier flags were stored.' },
    { label: 'Learning', items: learning, empty: 'No review candidate was raised from this trace.' },
  ]
}

function tensionPacketLines(trace: Trace) {
  const packet = trace.governance_answer_spine?.tension_packet
  if (!packet) return []
  const [sideA, sideB] = packet.sides || []
  return cleanItems([
    packet.tension_type ? `Packet type: ${formatTraceLabel(packet.tension_type)}` : '',
    sideA ? `Side A: ${sideA.label} - ${sideA.claim}` : '',
    sideB ? `Side B: ${sideB.label} - ${sideB.claim}` : '',
    packet.allowed_synthesis ? `Allowed synthesis: ${packet.allowed_synthesis}` : '',
    packet.forbidden_collapse ? `Forbidden collapse: ${packet.forbidden_collapse}` : '',
    packet.trace_summary ? `Trace preview: ${packet.trace_summary}` : '',
  ])
}

function mirusLogicGraphLines(trace: Trace) {
  const discovery = trace.mirus_governed_discovery
  if (!discovery?.enabled) return []
  const front = discovery.front_packet
  const nodes = discovery.logic_graph?.nodes || []
  const edges = discovery.logic_graph?.edges || []
  const graphPath = nodes.length
    ? nodes.map((node) => node.id).join(' -> ')
    : edges.map((edge) => `${edge.from} -> ${edge.to}`).join(', ')
  return cleanItems([
    front?.preferred_intent ? `Mirus front packet: ${formatTraceLabel(front.preferred_intent)}` : '',
    front?.candidate_hints?.length ? `Candidate hints: ${front.candidate_hints.join(', ')}` : '',
    graphPath ? `Logic graph: ${graphPath}` : '',
    discovery.repairs?.length ? `CRT repair: ${discovery.repairs.map(formatTraceLabel).join(', ')}` : '',
  ])
}

function dispatchWisconsinMapActions(trace: Trace, dispatched: Set<string>) {
  if (window.parent === window) return
  const runs = trace.tool_runs || []
  for (const run of runs) {
    if (run.tool !== 'wisconsin_map_control' || run.status !== 'completed') continue
    const key = `${trace.turn_id}:${run.tool_run_id || JSON.stringify(run.input)}`
    if (dispatched.has(key)) continue
    const output = run.output as {
      schema?: string
      actions?: Array<Record<string, unknown>>
      summary?: string
      target?: string
    }
    if (output.schema !== 'wisconsin_map_control.v1' || !Array.isArray(output.actions)) continue
    dispatched.add(key)
    window.parent.postMessage({
      source: 'aether-workbench',
      type: 'wisconsin-map-control',
      version: 1,
      turnId: trace.turn_id,
      target: output.target || 'wisconsin_state_parks_map',
      summary: output.summary || '',
      actions: output.actions,
    }, '*')
  }
}

function cleanItems(items: string[]) {
  return items.filter((item) => item.trim())
}

function formatTraceLabel(value: string) {
  return value.replace(/_/g, ' ').trim()
}

function safetyBoundaryLine(label: string, allowed?: boolean) {
  if (allowed == null) return ''
  return `${label}: ${allowed ? 'allowed' : 'blocked'}`
}
