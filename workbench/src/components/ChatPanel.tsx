import { AlertTriangle, ArrowRight, ArrowUp, BrainCircuit, Check, CheckCircle2, CircleDashed, CircleSlash2, Clock3, Database, ExternalLink, History, LoaderCircle, Pin, Plus, ShieldCheck, Sparkles, Trash2 } from 'lucide-react'
import { FormEvent, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api, idempotencyKey, streamChat } from '../api'
import type { ContinuityAlignmentReceipt, Conversation, PublicGovernanceStep, RenderProvider, RunEvent, TaskContinuationSelection, Trace, Turn } from '../types'
import type { UiMode } from '../uiMode'
import { buildAnswerFooterLine, friendlyChatError, humanVerificationLabel } from './WhyThisAnswer'

const STARTER_GROUPS: Array<{
  title: string
  prompts: Array<{ label: string; text: string }>
}> = [
  {
    title: 'About me',
    prompts: [
      { label: 'What do you know about me?', text: 'What do you know about me?' },
      { label: 'My favorite color?', text: 'What is my favorite color?' },
      { label: 'What do they have in common?', text: 'What do my favorites have in common?' },
    ],
  },
  {
    title: 'Code',
    prompts: [
      { label: 'Search for holden', text: 'do a workspace search for holden in ai_round2' },
    ],
  },
]

const VOICE_STORAGE_KEY = 'aether.voiceProfile'
const VOICE_OPTIONS = [
  { value: 'grounded', label: 'Grounded' },
  { value: 'warm', label: 'Warm' },
  { value: 'alive', label: 'Alive' },
]

interface ContinuityActionState {
  busy?: boolean
  loop?: ContinuityLoopRef
  notice?: string
}

interface ContinuityLoopRef {
  loop_id: string
  summary: string
  status: string
  revision_hash: string
}

interface ChatPanelProps {
  model: string
  renderProvider: RenderProvider
  uiMode?: UiMode
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
  /** Keep hosted renderer selected after a successful Grok turn in-thread. */
  onRenderProvider?: (provider: RenderProvider) => void
}

export function ChatPanel({
  model,
  renderProvider,
  uiMode = 'simple',
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
  onRenderProvider,
}: ChatPanelProps) {
  const isSimple = uiMode === 'simple'
  const [message, setMessage] = useState('')
  const [streaming, setStreaming] = useState('')
  const [governanceSteps, setGovernanceSteps] = useState<PublicGovernanceStep[]>([])
  const [runEvents, setRunEvents] = useState<RunEvent[]>([])
  const [thinkingTraceCache, setThinkingTraceCache] = useState<Record<string, Trace>>({})
  const [openThinkingTurn, setOpenThinkingTurn] = useState<string | null>(null)
  const [thinkingLoadingTurn, setThinkingLoadingTurn] = useState<string | null>(null)
  const [pendingTurn, setPendingTurn] = useState<string | null>(null)
  const [pendingUser, setPendingUser] = useState('')
  const [cancellingRun, setCancellingRun] = useState(false)
  const [cancelRequested, setCancelRequested] = useState(false)
  const [needsStronger, setNeedsStronger] = useState(false)
  const [escalating, setEscalating] = useState(false)
  const [frontierAnswer, setFrontierAnswer] = useState('')
  const [error, setError] = useState('')
  const [continuityActions, setContinuityActions] = useState<Record<string, ContinuityActionState>>({})
  const [voiceProfile, setVoiceProfile] = useState(() => {
    const stored = window.localStorage.getItem(VOICE_STORAGE_KEY)
    return VOICE_OPTIONS.some((option) => option.value === stored) ? stored || 'warm' : 'warm'
  })
  const scrollRef = useRef<HTMLDivElement>(null)
  const activeConversationRef = useRef(conversationId)
  const activeTurnRef = useRef<string | null>(null)
  /** One free Why open after the first finished answer this session (Simple only). */
  const autoOpenedWhyRef = useRef(false)
  const activeTraceRef = useRef<Trace | null>(null)
  const dispatchedMapActionsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    activeConversationRef.current = conversationId
  }, [conversationId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns, streaming, frontierAnswer, governanceSteps, runEvents])

  useEffect(() => {
    window.localStorage.setItem(VOICE_STORAGE_KEY, voiceProfile)
  }, [voiceProfile])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const text = message.trim()
    if (!text) return
    setMessage('')
    await runMessage(text)
  }

  async function runMessage(
    text: string,
    targetConversationId: string | null = conversationId,
    taskSelection?: TaskContinuationSelection,
  ) {
    if (!text || pendingTurn) return
    setPendingUser(text)
    setCancellingRun(false)
    setCancelRequested(false)
    setStreaming('')
    setGovernanceSteps([])
    setRunEvents([])
    setFrontierAnswer('')
    setNeedsStronger(false)
    setError('')

    try {
      await streamChat(
        {
          message: text,
          conversation_id: targetConversationId || undefined,
          model,
          voice_profile: voiceProfile,
          render_provider: renderProvider,
          task_continuation_selection: taskSelection,
        },
        {
          onTurn: ({ turn_id, conversation_id }) => {
            setPendingTurn(turn_id)
            activeTurnRef.current = turn_id
            activeConversationRef.current = conversation_id
            onConversation(conversation_id)
          },
          onTrace: (trace) => {
            activeTraceRef.current = trace
            setRunEvents(trace.run_events || [])
            onTrace(trace)
            dispatchWisconsinMapActions(trace, dispatchedMapActionsRef.current)
          },
          onGovernanceStep: (step) => {
            setGovernanceSteps((current) => {
              if (current.some((item) => item.step_id === step.step_id)) return current
              return [...current, step]
            })
          },
          onRunEvent: (event) => {
            setRunEvents((current) => upsertRunEvent(current, event))
            if (event.phase === 'cancel' && event.status === 'done') setCancelRequested(true)
          },
          onToken: (token) => setStreaming((current) => current + token),
          onDone: async (done) => {
            const { needs_stronger_model } = done
            setNeedsStronger(needs_stronger_model)
            // Conversation sticky: keep hosted Grok selected after a successful
            // hosted turn so follow-ups don't silently drop to local in the UI.
            const effectiveProvider = done.render_provider?.effective
            const fallbackApplied = Boolean(done.render_provider?.fallback_applied)
            if (
              onRenderProvider
              && effectiveProvider === 'grok_build'
              && !fallbackApplied
              && renderProvider !== 'grok_build'
            ) {
              onRenderProvider('grok_build')
            }
            if (activeTraceRef.current) {
              let completedTrace: Trace = {
                ...activeTraceRef.current,
                completion: {
                  source: done.source || done.guidance_source || inferTraceSource(activeTraceRef.current),
                  needs_stronger_model,
                  generation_model: done.generation_model || activeTraceRef.current.generation_model,
                  guidance_kind: done.guidance_kind || activeTraceRef.current.character_answer?.kind,
                  guidance_repaired: done.guidance_repaired,
                  guidance_repair_failed: done.guidance_repair_failed,
                  character_critic_repair: done.character_critic_repair,
                },
              }
              if (activeTurnRef.current) {
                try {
                  const result = await api.trace(activeTurnRef.current)
                  completedTrace = result.trace
                  setThinkingTraceCache((current) => ({
                    ...current,
                    [activeTurnRef.current as string]: result.trace,
                  }))
                } catch {
                  // The streamed trace remains usable if final trace readback fails.
                }
              }
              activeTraceRef.current = completedTrace
              onTrace(completedTrace)
              dispatchWisconsinMapActions(completedTrace, dispatchedMapActionsRef.current)
            }
            const finishedTurnId = activeTurnRef.current
            try {
              const activeConversation = activeConversationRef.current
              if (activeConversation) onTurns(await api.turns(activeConversation))
            } catch (reason) {
              setError(friendlyChatError(
                reason instanceof Error
                  ? `Response saved, but refresh failed: ${reason.message}`
                  : 'Response saved, but the conversation refresh failed.',
              ))
            } finally {
              activeTurnRef.current = null
              setPendingTurn(null)
              setPendingUser('')
              setStreaming('')
              setGovernanceSteps([])
              setRunEvents([])
              setCancellingRun(false)
              setCancelRequested(false)
            }
            // Teach Simple once: open Why so Nick sees facts/tools without hunting Process.
            if (isSimple && finishedTurnId && !autoOpenedWhyRef.current) {
              autoOpenedWhyRef.current = true
              onOpenTrace(finishedTurnId)
            }
          },
          onError: async (reason) => {
            setError(friendlyChatError(String(reason || 'Response failed.')))
            try {
              const activeConversation = activeConversationRef.current
              if (activeConversation) onTurns(await api.turns(activeConversation))
            } finally {
              activeTurnRef.current = null
              setPendingTurn(null)
              setPendingUser('')
              setStreaming('')
              setGovernanceSteps([])
              setRunEvents([])
              setCancellingRun(false)
              setCancelRequested(false)
            }
          },
        },
      )
    } catch (reason) {
      setError(friendlyChatError(
        reason instanceof Error ? reason.message : 'Local response failed.',
      ))
      activeTurnRef.current = null
      setPendingTurn(null)
      setPendingUser('')
      setStreaming('')
      setGovernanceSteps([])
      setRunEvents([])
      setCancellingRun(false)
      setCancelRequested(false)
    }
  }

  async function cancelActiveRun() {
    if (!pendingTurn || cancellingRun || cancelRequested) return
    setCancellingRun(true)
    setError('')
    try {
      const receipt = await api.cancelRun(pendingTurn)
      setCancelRequested(receipt.accepted)
      setRunEvents((current) => upsertRunEvent(current, receipt.run_event))
    } catch (reason) {
      setError(friendlyChatError(
        reason instanceof Error ? reason.message : 'Could not stop the active answer.',
      ))
    } finally {
      setCancellingRun(false)
    }
  }

  function continueFromConversation(sourceConversationId: string) {
    if (!sourceConversationId || pendingTurn) return
    onNewConversation()
    void runMessage(
      `Continue from conversation ${sourceConversationId} and explicitly align this new conversation with it.`,
      null,
    )
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
      setError(reason instanceof Error ? `Process receipt failed: ${reason.message}` : 'Process receipt failed.')
    } finally {
      setThinkingLoadingTurn(null)
    }
  }

  async function pinContinuityLoop(turnId: string, summary: string) {
    setContinuityActions((current) => ({
      ...current,
      [turnId]: { ...current[turnId], busy: true },
    }))
    setError('')
    try {
      const loop = await api.createContinuityOpenLoop(
        summary,
        idempotencyKey(`continuity-pin-${turnId}`),
      )
      setContinuityActions((current) => ({
        ...current,
        [turnId]: {
          busy: false,
          loop,
          notice: 'Pinned as open next step',
        },
      }))
    } catch (reason) {
      setContinuityActions((current) => ({
        ...current,
        [turnId]: { ...current[turnId], busy: false },
      }))
      setError(reason instanceof Error ? reason.message : 'Could not pin the next step.')
    }
  }

  async function reviewContinuityLoop(
    turnId: string,
    loop: ContinuityLoopRef,
    action: 'done' | 'defer',
  ) {
    setContinuityActions((current) => ({
      ...current,
      [turnId]: { ...current[turnId], busy: true, loop },
    }))
    setError('')
    try {
      const reviewed = await api.reviewContinuityOpenLoop(loop.loop_id, {
        action,
        note: action === 'done'
          ? 'Marked done from the Workbench Continuity answer.'
          : 'Deferred from the Workbench Continuity answer.',
        revision_hash: loop.revision_hash,
        idempotency_key: idempotencyKey(`continuity-${action}-${loop.loop_id}`),
      })
      setContinuityActions((current) => ({
        ...current,
        [turnId]: {
          busy: false,
          loop: reviewed,
          notice: action === 'done' ? 'Marked done' : 'Deferred',
        },
      }))
    } catch (reason) {
      setContinuityActions((current) => ({
        ...current,
        [turnId]: { ...current[turnId], busy: false, loop },
      }))
      setError(reason instanceof Error ? reason.message : 'Could not update the open next step.')
    }
  }

  return (
    <main className="chat-panel">
      <div className="model-strip">
        <div>
          <BrainCircuit size={16} />
          <span>
            {isSimple
              ? (renderProvider === 'grok_build' ? 'Hosted wording · Aether in charge' : 'Local on this PC')
              : (renderProvider === 'grok_build' ? 'Grok · governed renderer' : model)}
          </span>
        </div>
        <div className={`strength-indicator ${showStronger ? 'needs' : ''}`}>
          {showStronger
            ? (isSimple ? 'May need a stronger model' : 'Needs stronger model')
            : renderProvider === 'grok_build'
              ? (isSimple ? 'Aether still governs facts' : 'Aether governed')
              : (isSimple ? 'Ready' : 'Locally answerable')}
        </div>
      </div>
      <div
        className="model-policy-summary-placeholder"
        data-testid="model-policy-summary-placeholder"
        aria-hidden="true"
      />
      <div className={`conversation-toolbar ${isSimple ? 'simple' : ''}`}>
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
        {!isSimple ? (
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
        ) : null}
        {!isSimple ? (
          <>
            <button
              className="continuity-resume-button"
              aria-label="Resume work from governed evidence"
              title="Resume work from governed evidence"
              disabled={Boolean(pendingTurn)}
              onClick={() => void runMessage('/resume')}
            >
              <History size={14} />
            </button>
            <button
              className="cross-conversation-button"
              aria-label="Continue current chat in a new aligned chat"
              title="Continue current chat in a new aligned chat"
              disabled={!conversationId || Boolean(pendingTurn)}
              onClick={() => conversationId && continueFromConversation(conversationId)}
            >
              <ExternalLink size={14} />
            </button>
          </>
        ) : null}
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
            <h1>{isSimple ? 'Your local AI that won’t invent who you are.' : 'Talk to your governed memory.'}</h1>
            <p>
              {isSimple
                ? 'Ask about yourself or your project. After the first answer, Why opens so you can see what it used — no Process dump.'
                : 'Aether releases only evidence it can defend. Open the trace when you want to see the line it held.'}
            </p>
            <div className="welcome-signals">
              <span><Database size={14} /> {isSimple ? 'Stored on this PC' : 'Local substrate'}</span>
              <span><ShieldCheck size={14} /> {isSimple ? 'Won’t invent your life' : 'Clause-level release'}</span>
            </div>
            {/* Starters always on empty chat (Simple + Lab) so they are hard to miss. */}
            <div className="welcome-starters" aria-label="Suggested prompts">
              {STARTER_GROUPS.map((group) => (
                <div className="welcome-starter-group" key={group.title}>
                  <span className="welcome-starter-group-title">{group.title}</span>
                  {group.prompts.map((starter) => (
                    <button
                      type="button"
                      key={starter.text}
                      className="welcome-starter"
                      disabled={Boolean(pendingTurn)}
                      onClick={() => void runMessage(starter.text)}
                    >
                      {starter.label}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {turns.map((turn) => (
          <div className="turn" key={turn.turn_id}>
            <div className="user-message">{turn.user_message}</div>
            <div className="assistant-message">
              <div className="assistant-head">
                <div className="assistant-label"><span className="tiny-mark">Æ</span> {answerProviderLabel(turn, isSimple)}</div>
                <div className="assistant-actions">
                  {!isSimple ? (
                    <button
                      className="turn-thinking-button"
                      aria-label={`Toggle process for turn ${turn.turn_id}`}
                      title="How this answer formed"
                      onClick={() => void toggleThinkingTrace(turn.turn_id)}
                    >
                      <BrainCircuit size={13} />
                      <span>Process</span>
                    </button>
                  ) : null}
                  <button
                    className="turn-trace-button"
                    aria-label={isSimple ? `Why this answer for turn ${turn.turn_id}` : `Open trace for turn ${turn.turn_id}`}
                    title={isSimple ? 'Why this answer' : 'Open trace'}
                    onClick={() => onOpenTrace(turn.turn_id)}
                  >
                    <ShieldCheck size={13} />
                    {isSimple ? <span>Why</span> : null}
                  </button>
                </div>
              </div>
              <AnswerMarkdown>{turn.local_answer}</AnswerMarkdown>
              {!isSimple ? (
                <>
                  <ConversationAlignmentChip
                    receipt={
                      turn.continuity_alignment_receipt
                      || (trace?.turn_id === turn.turn_id
                        ? trace.continuity_alignment_receipt
                        : thinkingTraceCache[turn.turn_id]?.continuity_alignment_receipt)
                    }
                    onOpen={onConversation}
                    onContinue={continueFromConversation}
                  />
                  <ContinuityLoopActions
                    turnId={turn.turn_id}
                    trace={trace?.turn_id === turn.turn_id ? trace : thinkingTraceCache[turn.turn_id]}
                    state={continuityActions[turn.turn_id]}
                    onPin={pinContinuityLoop}
                    onReview={reviewContinuityLoop}
                  />
                  <TaskContinuationChoices
                    trace={trace?.turn_id === turn.turn_id ? trace : thinkingTraceCache[turn.turn_id]}
                    disabled={Boolean(pendingTurn)}
                    onSelect={(selection) => runMessage('/resume', conversationId, selection)}
                  />
                </>
              ) : null}
              {/* Lab only: full process dump. Simple uses Why drawer instead. */}
              {!isSimple && openThinkingTurn === turn.turn_id ? (
                <AnswerProcessTrace
                  loading={thinkingLoadingTurn === turn.turn_id}
                  trace={trace?.turn_id === turn.turn_id ? trace : thinkingTraceCache[turn.turn_id]}
                />
              ) : null}
              <div className={`answer-meta ${isSimple ? 'simple-footer' : ''}`}>
                {isSimple ? (
                  <>
                    <span className="answer-meta-chip">
                      {turn.render_provider?.effective === 'grok_build' ? 'Hosted wording' : 'Local'}
                    </span>
                    <button
                      type="button"
                      className="answer-footer-why"
                      aria-label={`Open Why summary for turn ${turn.turn_id}`}
                      title="Open Why this answer"
                      onClick={() => onOpenTrace(turn.turn_id)}
                    >
                      <ShieldCheck size={12} />
                      <span>
                        {buildAnswerFooterLine(
                          trace?.turn_id === turn.turn_id ? trace : thinkingTraceCache[turn.turn_id],
                        )}
                      </span>
                    </button>
                    <span className="answer-meta-chip">
                      {humanVerificationLabel(
                        trace?.turn_id === turn.turn_id ? trace : thinkingTraceCache[turn.turn_id],
                        turn.completion_verification,
                      )}
                    </span>
                  </>
                ) : (
                  <>
                    <span>{turn.render_provider?.effective === 'grok_build' ? 'Grok' : 'Local'}</span>
                    <span>Governed</span>
                    <span>{completionCheckLabel(
                      trace?.turn_id === turn.turn_id ? trace : thinkingTraceCache[turn.turn_id],
                      turn.completion_verification,
                    )}</span>
                  </>
                )}
              </div>
            </div>
          </div>
        ))}
        {pendingUser ? (
          <div className="turn">
            <div className="user-message">{pendingUser}</div>
            <div className="assistant-message streaming">
              <div className="assistant-label">
                <LoaderCircle className="spin" size={14} />
                {isSimple
                  ? (renderProvider === 'grok_build' ? 'Working (hosted wording)…' : 'Working…')
                  : `Governing ${renderProvider === 'grok_build' ? 'hosted ' : ''}response`}
              </div>
              {isSimple ? (
                <div
                  className={`simple-live-status ${cancelRequested ? 'stopping' : ''}`}
                  aria-label="Working status"
                >
                  {cancelRequested
                    ? <CircleSlash2 size={12} />
                    : <LoaderCircle className="spin" size={12} />}
                  <span>
                    <strong>
                      {simpleLiveHeadline(runEvents, governanceSteps, cancelRequested || cancellingRun)}
                    </strong>
                    <small>
                      {cancelRequested
                        ? 'Stop requested — Aether will halt at the next safe checkpoint and release nothing more.'
                        : 'Aether checks memory and tools, then words the answer. Open Why after for a plain summary.'}
                    </small>
                  </span>
                </div>
              ) : runEvents.length ? (
                <RunEventTimeline events={runEvents} live />
              ) : governanceSteps.length ? (
                <div className="governance-live-trace" aria-label="Live governance receipts">
                  {governanceSteps.map((step) => <GovernanceLiveStep step={step} key={step.step_id} />)}
                </div>
              ) : (
                <div className="governance-live-trace" aria-label="Live process timeline">
                  <div className="governance-live-step started">
                    <LoaderCircle className="spin" size={12} />
                    <span className="governance-live-step-copy">
                      <span>Starting governed run</span>
                      <small>The sidecar has not reported its first public phase yet.</small>
                    </span>
                    <em>pending</em>
                  </div>
                </div>
              )}
              <button
                className={`run-cancel-button ${isSimple ? 'simple' : ''}`}
                type="button"
                aria-label={isSimple
                  ? (cancelRequested || cancellingRun ? 'Stopping' : 'Stop answering')
                  : (cancelRequested
                    ? 'Cancellation requested'
                    : cancellingRun
                      ? 'Requesting cancellation…'
                      : 'Cancel run')}
                disabled={!pendingTurn || cancellingRun || cancelRequested}
                onClick={() => void cancelActiveRun()}
              >
                <CircleSlash2 size={isSimple ? 14 : 12} />
                {isSimple
                  ? (cancelRequested || cancellingRun ? 'Stopping…' : 'Stop answering')
                  : (cancelRequested
                    ? 'Cancellation requested'
                    : cancellingRun
                      ? 'Requesting cancellation…'
                      : 'Cancel run')}
              </button>
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
      {showStronger && escalationTurn && !isSimple ? (
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
          placeholder={isSimple ? 'Ask about you, your project, or what Aether knows…' : 'Ask Aether…'}
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
          <span>
            <span className="status-dot" />
            {isSimple
              ? 'Won’t invent personal facts · tools leave receipts'
              : `Aether governs context before ${renderProvider === 'grok_build' ? 'hosted ' : ''}inference`}
          </span>
          <span>Enter to send</span>
        </div>
      </form>
    </main>
  )
}

function answerProviderLabel(turn: Turn, simple = false) {
  if (turn.render_provider?.effective === 'grok_build') {
    return simple ? 'Aether · hosted wording' : 'Hosted Grok answer'
  }
  if (turn.render_provider?.fallback_applied) {
    return simple ? 'Aether · local fallback' : 'Local fallback answer'
  }
  return simple ? 'Aether' : 'Local answer'
}

function simpleLiveHeadline(
  events: RunEvent[],
  steps: PublicGovernanceStep[],
  stopping = false,
) {
  if (stopping) return 'Stopping…'
  const lastEvent = events[events.length - 1]
  if (lastEvent?.phase === 'cancel') return 'Stopping…'
  if (lastEvent?.phase === 'render' || /render|wording|grok/i.test(lastEvent?.summary || '')) {
    return 'Writing the answer…'
  }
  if (lastEvent?.phase === 'tools' || /tool|search|read|workspace/i.test(lastEvent?.summary || '')) {
    return 'Using tools…'
  }
  if (lastEvent?.phase === 'verify' || /coverage|check|verif/i.test(lastEvent?.summary || '')) {
    return 'Checking the answer…'
  }
  if (lastEvent?.phase === 'memory' || /memory|slot|profile/i.test(lastEvent?.summary || '')) {
    return 'Checking what it knows…'
  }
  if (lastEvent || steps.length) return 'Still working…'
  return 'Starting…'
}

function ConversationAlignmentChip({
  receipt,
  onOpen,
  onContinue,
}: {
  receipt?: ContinuityAlignmentReceipt
  onOpen: (conversationId: string) => void
  onContinue: (conversationId: string) => void
}) {
  if (!receipt) return null
  const sources = receipt.source_conversations?.length
    ? receipt.source_conversations
    : receipt.source_conversation_ids.map((conversationId) => ({
        conversation_id: conversationId,
        title: conversationId,
      }))
  const candidates = receipt.status === 'ambiguous'
    ? receipt.candidate_conversations || []
    : []
  const successful = receipt.status === 'exact' || receipt.status === 'partial'
  const Icon = successful ? CheckCircle2 : AlertTriangle

  return (
    <section className={`conversation-alignment ${receipt.status}`} aria-label="Conversation alignment">
      <div className="conversation-alignment-head">
        <Icon size={13} />
        <strong>{receipt.status} cross-chat alignment</strong>
        <span>{receipt.retrieval_method.replaceAll('_', ' ')}</span>
      </div>
      {sources.map((source) => (
        <div className="conversation-source" key={source.conversation_id}>
          <span title={source.conversation_id}>{source.title || source.conversation_id}</span>
          <button
            onClick={() => onOpen(source.conversation_id)}
            aria-label={`Open source conversation ${source.conversation_id}`}
          >
            Open source
          </button>
        </div>
      ))}
      {candidates.map((candidate) => (
        <div className="conversation-source candidate" key={candidate.conversation_id}>
          <span title={candidate.conversation_id}>{candidate.title || candidate.conversation_id}</span>
          <button
            onClick={() => onContinue(candidate.conversation_id)}
            aria-label={`Continue from candidate conversation ${candidate.conversation_id}`}
          >
            Continue here
          </button>
        </div>
      ))}
      <small>
        {receipt.profile_memory_write_count === 0
          ? 'Conversation context only · no profile memory written'
          : `${receipt.profile_memory_write_count} profile write(s) recorded`}
      </small>
    </section>
  )
}

function ContinuityLoopActions({
  turnId,
  trace,
  state,
  onPin,
  onReview,
}: {
  turnId: string
  trace?: Trace
  state?: ContinuityActionState
  onPin: (turnId: string, summary: string) => Promise<void>
  onReview: (
    turnId: string,
    loop: ContinuityLoopRef,
    action: 'done' | 'defer',
  ) => Promise<void>
}) {
  if (taskContinuationNeedsSelection(trace?.task_continuation_packet?.status)) {
    return null
  }
  const target = continuityLoopTarget(trace, state?.loop)
  if (!target) return null
  const closed = target.mode === 'manage' && target.loop.status !== 'open'
  return (
    <div className="continuity-loop-actions" aria-label="Continuity next-step actions">
      <small>{state?.notice || (
        target.mode === 'pin' ? 'Review-only candidate' : 'Explicit open loop'
      )}</small>
      {!closed && target.mode === 'pin' ? (
        <button
          aria-label="Pin as open next step"
          title="Pin as open next step"
          disabled={Boolean(state?.busy)}
          onClick={() => void onPin(turnId, target.summary)}
        >
          <Pin size={13} />
        </button>
      ) : null}
      {!closed && target.mode === 'manage' ? (
        <>
          <button
            aria-label="Mark open next step done"
            title="Mark done"
            disabled={Boolean(state?.busy)}
            onClick={() => void onReview(turnId, target.loop, 'done')}
          >
            <Check size={13} />
          </button>
          <button
            aria-label="Defer open next step"
            title="Defer"
            disabled={Boolean(state?.busy)}
            onClick={() => void onReview(turnId, target.loop, 'defer')}
          >
            <Clock3 size={13} />
          </button>
        </>
      ) : null}
    </div>
  )
}

function TaskContinuationChoices({
  trace,
  disabled,
  onSelect,
}: {
  trace?: Trace
  disabled: boolean
  onSelect: (selection: TaskContinuationSelection) => Promise<void>
}) {
  const packet = trace?.task_continuation_packet
  if (!packet || !taskContinuationNeedsSelection(packet.status) || !packet.pending_steps.length) return null

  return (
    <section className="task-continuation-choices" aria-label="Choose work to resume">
      <div className="task-continuation-choice-head">
        <AlertTriangle size={13} />
        <strong>Choose work to resume</strong>
        <span>revision bound</span>
      </div>
      {packet.pending_steps.map((item) => (
        <div className="task-continuation-choice" key={`${item.loop_id}:${item.revision_hash}`}>
          <span>{item.summary}</span>
          <button
            aria-label={`Resume ${item.summary}`}
            title="Resume this open step"
            disabled={disabled}
            onClick={() => void onSelect({
              loop_id: item.loop_id,
              revision_hash: item.revision_hash,
            })}
          >
            <ArrowRight size={13} />
            <span>Resume</span>
          </button>
        </div>
      ))}
      <small>Response alignment only · tools and durable writes remain blocked</small>
    </section>
  )
}

function taskContinuationNeedsSelection(status?: string) {
  return status === 'ambiguous'
    || status === 'stale_selection'
    || status === 'selection_unavailable'
    || status === 'invalid_selection'
}

function continuityLoopTarget(
  trace?: Trace,
  confirmedLoop?: ContinuityLoopRef,
): { mode: 'pin'; summary: string } | { mode: 'manage'; loop: ContinuityLoopRef } | null {
  if (confirmedLoop) return { mode: 'manage', loop: confirmedLoop }
  const atom = trace?.continuity_claim_atoms?.atoms.find(
    (item) => item.section === 'next_candidate',
  )
  if (!atom) return null
  if (atom.state === 'inferred_candidate') {
    return { mode: 'pin', summary: atom.proposition }
  }
  if (atom.state !== 'explicit_open_loop') return null
  const evidence = new Set(atom.evidence_ids)
  const item = trace?.continuity_packet?.open_loops?.find((row) => (
    row.evidence_ids.some((referenceId) => evidence.has(referenceId))
  ))
  if (!item?.loop_id || !item.revision_hash) return null
  return {
    mode: 'manage',
    loop: {
      loop_id: item.loop_id,
      summary: item.summary,
      status: 'open',
      revision_hash: item.revision_hash,
    },
  }
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

function upsertRunEvent(current: RunEvent[], event: RunEvent) {
  const next = current.filter((item) => item.event_id !== event.event_id)
  return [...next, event].sort((left, right) => left.index - right.index)
}

function RunEventTimeline({ events, live = false }: { events: RunEvent[]; live?: boolean }) {
  return (
    <div className="governance-live-trace" aria-label={live ? 'Live process timeline' : 'Process timeline'}>
      {events.map((event) => (
        <RunEventStep event={event} key={event.event_id} />
      ))}
    </div>
  )
}

function RunEventStep({ event }: { event: RunEvent }) {
  const Icon = governanceStepIcon(event.status)
  const spinning = event.status === 'in_progress'
  return (
    <div className={`governance-live-step ${event.status}`} title={event.detail}>
      <Icon className={spinning ? 'spin' : undefined} size={12} />
      <span className="governance-live-step-copy">
        <span>{event.summary}</span>
        <small>{event.detail}</small>
      </span>
      <em>{governanceStepStatusLabel(event.status)}</em>
    </div>
  )
}

function governanceStepIcon(status: string) {
  if (status === 'done') return CheckCircle2
  if (status === 'skipped') return CircleSlash2
  if (status === 'failed' || status === 'flagged' || status === 'attention') return AlertTriangle
  if (status === 'started' || status === 'in_progress') return LoaderCircle
  return CircleDashed
}

function governanceStepStatusLabel(status: string) {
  if (status === 'done') return 'earned'
  if (status === 'skipped') return 'skipped'
  if (status === 'failed') return 'failed'
  if (status === 'flagged') return 'flagged'
  if (status === 'started' || status === 'in_progress') return 'working'
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

function AnswerProcessTrace({
  trace,
  loading,
}: {
  trace?: Trace
  loading: boolean
}) {
  if (loading && !trace) {
    return (
      <div className="answer-thinking-panel" aria-label="Answer process">
        <div className="answer-thinking-loading">
          <LoaderCircle className="spin" size={13} /> Loading process
        </div>
      </div>
    )
  }
  if (!trace) {
    return (
      <div className="answer-thinking-panel" aria-label="Answer process">
        <div className="answer-thinking-loading">No public process receipt is available for this turn yet.</div>
      </div>
    )
  }

  const sections = answerThinkingSections(trace)
  return (
    <div className="answer-thinking-panel" aria-label="Answer process">
      <div className="answer-thinking-heading">How this answer formed</div>
      {trace.run_events?.length ? <RunEventTimeline events={trace.run_events} /> : null}
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

function completionCheckLabel(trace?: Trace, persistedVerification?: Turn['completion_verification']) {
  if (trace?.run_state?.status === 'cancelled') return 'Cancelled'
  const verification = trace?.completion?.verification_summary || persistedVerification
  if (!verification) return 'Checks unavailable'
  if (!verification.accepted) return 'Rejected by checks'
  if (verification.failed_dimension_count > 0) {
    return `Checked ${verification.checked_dimension_count}/${verification.applicable_dimension_count} · ${verification.failed_dimension_count} advisory`
  }
  if (!verification.fully_verified) {
    return `Checked ${verification.checked_dimension_count}/${verification.applicable_dimension_count}`
  }
  return `Verified ${verification.passed_dimension_count}/${verification.applicable_dimension_count}`
}

function answerThinkingSections(trace: Trace) {
  const route = trace.completion?.route_decision || trace.route_decision
  const compliance = trace.completion?.governance_spine_compliance
  const criticRepair = trace.completion?.character_critic_repair
  const process = cleanItems([
    ...(trace.public_governance_steps || []).map((step) => `${step.summary}: ${step.detail}`),
    ...mirusLogicGraphLines(trace),
    ...(trace.memory_candidates || []).map((candidate) => (
      `Mirus candidate: ${formatTraceLabel(candidate.semantic_signal || candidate.candidate_kind || 'review required')}`
    )),
    ...(trace.task_authority_candidates || []).map((candidate) => (
      `Task candidate (${formatTraceLabel(candidate.record_kind)}): ${candidate.summary}`
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
    trace.character_answer?.critic_repair_contract
      ? `Critic contract: ${formatTraceLabel(trace.character_answer.critic_repair_contract.kind || 'public bounded critic')}`
      : '',
    criticRepair?.repair_triggered_by?.length
      ? `Critic repair trigger: ${criticRepair.repair_triggered_by.map(formatTraceLabel).join(', ')}`
      : '',
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
    ...criticFindingLines('Pre-repair critic', criticRepair?.pre_repair_findings),
    ...criticFindingLines('Post-repair critic', criticRepair?.post_repair_findings),
  ])

  const learning = cleanItems([
    compliance && !compliance.passed ? 'Potential learning event: answer violated the governance spine.' : '',
    ...(trace.memory_candidates || []).map((candidate) => (
      `Review candidate: ${candidate.slot_id} (${candidate.authority || 'unconfirmed'}, ${candidate.review_required === false ? 'review optional' : 'review required'}, ${candidate.memory_write_allowed === false ? 'write blocked' : 'write policy unknown'})`
    )),
    ...(trace.task_authority_candidates || []).map((candidate) => (
      `Task review candidate: ${candidate.summary} (${candidate.review_required ? 'review required' : 'review optional'}, ${candidate.task_authority_write_allowed ? 'task write allowed' : 'task write blocked'})`
    )),
    route?.model_recommendation?.observational_only ? 'Model recommendation stayed observational; no automatic switch.' : '',
    trace.governance_answer_spine?.safety_contract?.review_required_before_promotion ? 'Promotion requires review before behavior changes.' : '',
  ])
  const heldTension = tensionPacketLines(trace)

  return [
    { label: 'Governance receipts', items: process, empty: 'No public governance receipts were stored for this turn.' },
    ...(heldTension.length
      ? [{ label: 'Held Tension', items: heldTension, empty: 'No tension packet was stored for this turn.' }]
      : []),
    { label: 'Memory', items: memory, empty: 'No governed memory packets were released for this turn.' },
    { label: 'Tools', items: tools, empty: 'No semantic tool considerations were stored.' },
    { label: 'Verifier', items: verifier, empty: 'No post-render verifier flags were stored.' },
    { label: 'Learning', items: learning, empty: 'No review candidate was raised from this trace.' },
  ]
}

function criticFindingLines(label: string, findings?: Array<{ dimension?: string; status?: string; note?: string }>) {
  if (!findings?.length) return []
  return findings
    .filter((finding) => finding.status && finding.status !== 'passed')
    .slice(0, 4)
    .map((finding) => (
      `${label}: ${formatTraceLabel(finding.dimension || 'finding')} ${formatTraceLabel(finding.status || '')}${finding.note ? ` - ${finding.note}` : ''}`
    ))
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
