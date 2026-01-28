import type { ChatMessage } from '../../types'

function pct01(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const clamped = Math.max(0, Math.min(1, v))
  return `${Math.round(clamped * 100)}%`
}

export function CrtInspector(props: { message: ChatMessage | null; onClear: () => void }) {
  if (!props.message || props.message.role !== 'assistant') {
    return (
      <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
        <div className="text-sm font-semibold text-white">Inspector</div>
        <div className="mt-2 text-sm text-white/60">Select an assistant message to inspect CRT details.</div>
      </div>
    )
  }

  const meta = props.message.crt

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-white">Inspector</div>
        <button
          onClick={props.onClear}
          className="rounded-xl border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/80 hover:bg-white/10"
          title="Clear selection"
        >
          Clear
        </button>
      </div>

      <div className="mt-3 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/80">
        <div className="font-medium text-white">Message</div>
        <div className="mt-1 line-clamp-6 whitespace-pre-wrap text-white/80">{props.message.text}</div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
          <div className="text-white/60">Response</div>
          <div className="mt-0.5 font-medium text-white">{(meta?.response_type ?? '—').toUpperCase()}</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
          <div className="text-white/60">Gates</div>
          <div className="mt-0.5 font-medium text-white">
            {typeof meta?.gates_passed === 'boolean' ? (meta.gates_passed ? 'PASS' : 'FAIL') : '—'}
          </div>
          <div className="mt-0.5 text-white/60">{meta?.gate_reason ?? '—'}</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
          <div className="text-white/60">Confidence</div>
          <div className="mt-0.5 font-medium text-white">{pct01(meta?.confidence)}</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
          <div className="text-white/60">Session</div>
          <div className="mt-0.5 font-medium text-white">{meta?.session_id ?? '—'}</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
          <div className="text-white/60">Intent align</div>
          <div className="mt-0.5 font-medium text-white">{pct01(meta?.intent_alignment)}</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
          <div className="text-white/60">Memory align</div>
          <div className="mt-0.5 font-medium text-white">{pct01(meta?.memory_alignment)}</div>
        </div>
      </div>

      <div className="mt-4">
        <div className="text-xs font-semibold tracking-wide text-white/60">Retrieved memories</div>
        <div className="mt-2 space-y-2">
          {(meta?.retrieved_memories ?? []).slice(0, 8).map((m, idx) => (
            <div key={idx} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
              {m.memory_id ? <div className="font-mono text-[11px] text-white/50">{m.memory_id}</div> : null}
              <div className="line-clamp-3 whitespace-pre-wrap text-xs text-white/80">{m.text || '—'}</div>
              <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-white/60">
                <span>src: {m.source ?? '—'}</span>
                <span>trust: {m.trust ?? '—'}</span>
                <span>conf: {m.confidence ?? '—'}</span>
                {typeof (m as any).score === 'number' ? <span>score: {(m as any).score.toFixed(3)}</span> : null}
              </div>
            </div>
          ))}
          {!(meta?.retrieved_memories && meta.retrieved_memories.length) ? (
            <div className="text-sm text-white/60">No retrieved memories in this response.</div>
          ) : null}
        </div>
      </div>

      <div className="mt-4">
        <div className="text-xs font-semibold tracking-wide text-white/60">Prompt memories</div>
        <div className="mt-2 space-y-2">
          {(meta?.prompt_memories ?? []).slice(0, 8).map((m, idx) => (
            <div key={idx} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
              {m.memory_id ? <div className="font-mono text-[11px] text-white/50">{m.memory_id}</div> : null}
              <div className="line-clamp-3 whitespace-pre-wrap text-xs text-white/80">{m.text || '—'}</div>
              <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-white/60">
                <span>src: {m.source ?? '—'}</span>
                <span>trust: {m.trust ?? '—'}</span>
                <span>conf: {m.confidence ?? '—'}</span>
              </div>
            </div>
          ))}
          {!(meta?.prompt_memories && meta.prompt_memories.length) ? (
            <div className="text-sm text-white/60">No prompt memories in this response.</div>
          ) : null}
        </div>
      </div>

      {(meta as any)?.gaslighting_detected && (meta as any)?.gaslighting_citation ? (
        <div className="mt-4">
          <div className="text-xs font-semibold tracking-wide text-orange-400">⚠️ Gaslighting Detection</div>
          <div className="mt-2 rounded-xl border border-orange-500/30 bg-orange-500/10 px-3 py-2">
            <div className="whitespace-pre-wrap text-xs text-orange-200">{(meta as any).gaslighting_citation}</div>
          </div>
        </div>
      ) : null}

      {(meta as any)?.llm_claims && (meta as any).llm_claims.length > 0 ? (
        <div className="mt-4">
          <div className="text-xs font-semibold tracking-wide text-cyan-400">📝 LLM Claims Extracted</div>
          <div className="mt-2 space-y-2">
            {(meta as any).llm_claims.map((claim: any, idx: number) => (
              <div key={idx} className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2">
                <div className="text-[11px] font-medium text-cyan-200">{claim.slot}</div>
                <div className="mt-1 text-xs text-white/90">Value: {claim.value}</div>
                <div className="mt-1 text-[11px] text-white/60">Trust: {claim.trust.toFixed(2)} | Source: {claim.source}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {(meta as any)?.llm_disclosures && (meta as any).llm_disclosures.length > 0 ? (
        <div className="mt-4">
          <div className="text-xs font-semibold tracking-wide text-amber-400">⚠️ LLM Contradictions</div>
          <div className="mt-2 space-y-2">
            {(meta as any).llm_disclosures.map((disclosure: string, idx: number) => (
              <div key={idx} className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                <div className="whitespace-pre-wrap text-xs text-amber-200">{disclosure}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
