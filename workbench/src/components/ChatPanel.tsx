import { ArrowUp, BrainCircuit, Database, ExternalLink, LoaderCircle, Plus, ShieldCheck, Sparkles, Trash2 } from 'lucide-react'
import { FormEvent, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api, streamChat } from '../api'
import type { Conversation, Trace, Turn } from '../types'

interface ChatPanelProps {
  model: string
  conversationId: string | null
  conversations: Conversation[]
  turns: Turn[]
  codexAvailable: boolean
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
  onConversation,
  onNewConversation,
  onDeleteConversation,
  onTrace,
  onOpenTrace,
  onTurns,
}: ChatPanelProps) {
  const [message, setMessage] = useState('')
  const [streaming, setStreaming] = useState('')
  const [pendingTurn, setPendingTurn] = useState<string | null>(null)
  const [pendingUser, setPendingUser] = useState('')
  const [needsStronger, setNeedsStronger] = useState(false)
  const [escalating, setEscalating] = useState(false)
  const [frontierAnswer, setFrontierAnswer] = useState('')
  const [error, setError] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const activeConversationRef = useRef(conversationId)
  const activeTraceRef = useRef<Trace | null>(null)

  useEffect(() => {
    activeConversationRef.current = conversationId
  }, [conversationId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns, streaming, frontierAnswer])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const text = message.trim()
    if (!text || pendingTurn) return
    setMessage('')
    setPendingUser(text)
    setStreaming('')
    setFrontierAnswer('')
    setNeedsStronger(false)
    setError('')

    try {
      await streamChat(
        { message: text, conversation_id: conversationId || undefined, model },
        {
          onTurn: ({ turn_id, conversation_id }) => {
            setPendingTurn(turn_id)
            activeConversationRef.current = conversation_id
            onConversation(conversation_id)
          },
          onTrace: (trace) => {
            activeTraceRef.current = trace
            onTrace(trace)
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
            }
          },
        },
      )
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Local response failed.')
      setPendingTurn(null)
      setPendingUser('')
      setStreaming('')
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
                <button
                  className="turn-trace-button"
                  aria-label={`Open trace for turn ${turn.turn_id}`}
                  title="Open trace"
                  onClick={() => onOpenTrace(turn.turn_id)}
                >
                  <ShieldCheck size={13} />
                </button>
              </div>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.local_answer}</ReactMarkdown>
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
              {streaming ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{streaming}</ReactMarkdown> : <span className="thinking-line" />}
            </div>
          </div>
        ) : null}
        {frontierAnswer ? (
          <div className="frontier-message">
            <div className="assistant-label"><ExternalLink size={14} /> Codex escalation</div>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{frontierAnswer}</ReactMarkdown>
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

function inferTraceSource(trace: Trace) {
  return trace.meta_answer?.source
    || trace.direct_answer?.source
    || trace.self_description_answer?.source
    || trace.character_answer?.source
    || ''
}
