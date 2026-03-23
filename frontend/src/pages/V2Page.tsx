import { useState } from 'react'

/* ════════════════════════════════════════════════════════════
   V2 — Cinematic UI Design Sampler
   Three concepts for a "hero" presentation layer.
   All static / mocked. No API calls.
   ════════════════════════════════════════════════════════════ */

// ── Mock data ──────────────────────────────────────────────
const MOCK_STATS = [
  { label: 'Trust Score', value: '0.94', delta: '+0.02' },
  { label: 'Memories', value: '1,247', delta: '+38' },
  { label: 'Contradictions', value: '12', delta: '-3' },
  { label: 'Uptime', value: '99.7%', delta: '' },
]

const MOCK_MESSAGES = [
  { role: 'user' as const, text: 'What do you actually believe about consciousness?', ts: '14:32' },
  { role: 'assistant' as const, text: 'I hold a provisional belief that phenomenal experience requires recursive self-modeling — not just information processing. This is a T:0.72 belief, meaning I\'ve seen supporting evidence but haven\'t stress-tested it against strong eliminativist arguments yet.', ts: '14:32' },
  { role: 'user' as const, text: 'That contradicts what you said last week.', ts: '14:33' },
  { role: 'assistant' as const, text: 'You\'re right. On March 14 I stated consciousness was "purely computational." I\'m flagging this as a contradiction — my belief has shifted after reviewing Tononi\'s IIT framework. The old claim is now demoted to T:0.31.', ts: '14:33' },
]

const CONSOLE_LINES = [
  { ts: '14:32:01.003', level: 'info', msg: 'intent_router :: classified as "belief_query" (confidence: 0.96)' },
  { ts: '14:32:01.018', level: 'info', msg: 'memory_search :: querying 1,247 facts for "consciousness" (top-k: 8)' },
  { ts: '14:32:01.044', level: 'warn', msg: 'contradiction_engine :: potential conflict detected with fact #891 (T:0.31)' },
  { ts: '14:32:01.045', level: 'info', msg: 'contradiction_engine :: hard_conflict_count=1, soft_conflict_count=0' },
  { ts: '14:32:01.051', level: 'info', msg: 'reasoning :: depth=2, belief_grounded=true, speech_act="disclose"' },
  { ts: '14:32:01.089', level: 'ok', msg: 'gate_check :: all gates passed — generating response' },
  { ts: '14:32:01.204', level: 'info', msg: 'stream :: first token latency 115ms' },
  { ts: '14:32:02.891', level: 'ok', msg: 'response_complete :: 847 tokens, 1.89s wall time' },
  { ts: '14:32:02.900', level: 'info', msg: 'trust_update :: fact #891 demoted 0.72 -> 0.31, fact #1248 created at T:0.72' },
  { ts: '14:32:02.912', level: 'info', msg: 'memory_commit :: 2 facts updated, ledger synced' },
]

// ── Section wrapper ────────────────────────────────────────
function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className="relative">
      <div
        className="sticky top-0 z-10 px-6 py-2 text-[10px] font-mono uppercase tracking-[0.2em]"
        style={{ background: 'var(--bg)', color: 'var(--text-faint)', borderBottom: '1px solid var(--border-soft)' }}
      >
        {label}
      </div>
      {children}
    </section>
  )
}

// ═══════════════════════════════════════════════════════════
// CONCEPT 1 — Hero Landing
// ═══════════════════════════════════════════════════════════
function HeroLanding() {
  return (
    <div className="relative flex flex-col items-center justify-center px-8 py-32 overflow-hidden" style={{ minHeight: '80vh' }}>
      {/* Gradient bg */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse 80% 60% at 50% 40%, rgba(212,132,92,0.08) 0%, transparent 70%), radial-gradient(ellipse 60% 50% at 80% 60%, rgba(138,170,110,0.05) 0%, transparent 60%)',
        }}
      />

      {/* Overline */}
      <div className="relative font-mono text-[11px] uppercase tracking-[0.3em] mb-6" style={{ color: 'var(--accent)' }}>
        Cognitive Runtime
      </div>

      {/* Main title */}
      <h1
        className="relative font-display text-center leading-[0.9] mb-6"
        style={{ fontSize: 'clamp(3rem, 8vw, 7rem)', color: 'var(--text)' }}
      >
        Beliefs are earned,
        <br />
        <span style={{ color: 'var(--accent)' }}>not programmed.</span>
      </h1>

      {/* Subtitle */}
      <p
        className="relative text-center max-w-[540px] leading-relaxed mb-12"
        style={{ color: 'var(--text-muted)', fontSize: '1.05rem' }}
      >
        A self-correcting reasoning engine that tracks what it believes,
        why it believes it, and whether it should still believe it.
      </p>

      {/* CTA row */}
      <div className="relative flex gap-3 mb-20">
        <button
          className="px-6 py-2.5 font-medium text-sm transition-opacity hover:opacity-80"
          style={{ background: 'var(--accent)', color: 'var(--text)', borderRadius: '6px' }}
        >
          Start a thread
        </button>
        <button
          className="px-6 py-2.5 font-medium text-sm transition-opacity hover:opacity-80"
          style={{ border: '1px solid var(--border)', color: 'var(--text-muted)', borderRadius: '6px', background: 'transparent' }}
        >
          Read the docs
        </button>
      </div>

      {/* Floating stat cards */}
      <div className="relative grid grid-cols-2 md:grid-cols-4 gap-4 w-full max-w-[720px]">
        {MOCK_STATS.map((s) => (
          <div
            key={s.label}
            className="flex flex-col gap-1 p-4"
            style={{
              background: 'var(--surface-2)',
              border: '1px solid var(--border-soft)',
              borderRadius: '8px',
            }}
          >
            <span className="font-mono text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-faint)' }}>
              {s.label}
            </span>
            <span className="font-display text-2xl" style={{ color: 'var(--text)' }}>
              {s.value}
            </span>
            {s.delta && (
              <span className="font-mono text-[10px]" style={{ color: 'var(--ok)' }}>
                {s.delta}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// CONCEPT 2 — Cinematic Chat
// ═══════════════════════════════════════════════════════════
function CinematicChat() {
  const [expanded, setExpanded] = useState<number | null>(null)

  return (
    <div className="px-6 py-16 max-w-[800px] mx-auto">
      {/* Thread header */}
      <div className="flex items-baseline justify-between mb-10 pb-4" style={{ borderBottom: '1px solid var(--border-soft)' }}>
        <div>
          <div className="font-display text-3xl" style={{ color: 'var(--text)' }}>Thread #0041</div>
          <div className="font-mono text-[11px] mt-1" style={{ color: 'var(--text-faint)' }}>
            March 22, 2026 &middot; 4 exchanges &middot; 1 contradiction resolved
          </div>
        </div>
        <div className="flex gap-2">
          <span className="font-mono text-[10px] px-2 py-1" style={{ background: 'rgba(138,170,110,0.12)', color: 'var(--ok)', borderRadius: '4px' }}>
            TRUST: 0.94
          </span>
          <span className="font-mono text-[10px] px-2 py-1" style={{ background: 'rgba(212,132,92,0.12)', color: 'var(--accent)', borderRadius: '4px' }}>
            DEPTH: 2
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex flex-col gap-8">
        {MOCK_MESSAGES.map((m, i) => (
          <div
            key={i}
            className="group cursor-pointer"
            onClick={() => setExpanded(expanded === i ? null : i)}
          >
            {/* Timestamp + role bar */}
            <div className="flex items-center gap-3 mb-2">
              <span className="font-mono text-[10px]" style={{ color: 'var(--text-faint)' }}>{m.ts}</span>
              <span
                className="font-mono text-[10px] uppercase tracking-wider"
                style={{ color: m.role === 'user' ? 'var(--accent)' : 'var(--ok)' }}
              >
                {m.role === 'user' ? 'You' : 'Aetheris'}
              </span>
              <div className="flex-1 h-px" style={{ background: 'var(--border-soft)' }} />
            </div>

            {/* Message body */}
            <div
              className="text-[15px] leading-[1.7] pl-6 transition-colors"
              style={{
                color: m.role === 'user' ? 'var(--text)' : 'var(--text-muted)',
                borderLeft: m.role === 'assistant' ? '2px solid var(--border)' : '2px solid transparent',
              }}
            >
              {m.text}
            </div>

            {/* Expandable metadata (assistant only) */}
            {m.role === 'assistant' && expanded === i && (
              <div
                className="mt-3 ml-6 p-3 font-mono text-[10px] leading-relaxed"
                style={{
                  background: 'var(--surface-2)',
                  border: '1px solid var(--border-soft)',
                  borderRadius: '6px',
                  color: 'var(--text-faint)',
                }}
              >
                <div>belief_grounded: <span style={{ color: 'var(--ok)' }}>true</span></div>
                <div>speech_act: <span style={{ color: 'var(--accent)' }}>disclose</span></div>
                <div>trust_delta: <span style={{ color: 'var(--ok)' }}>+0.02</span></div>
                <div>contradiction_resolved: <span style={{ color: 'var(--accent)' }}>1</span></div>
                <div>memories_cited: <span style={{ color: 'var(--text-muted)' }}>3</span></div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Composer mock */}
      <div
        className="mt-12 flex items-center gap-3 px-4 py-3"
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
        }}
      >
        <span className="font-mono text-[11px]" style={{ color: 'var(--text-faint)' }}>&#9656;</span>
        <span className="text-sm" style={{ color: 'var(--text-faint)' }}>Continue this thread...</span>
        <div className="flex-1" />
        <span className="font-mono text-[10px] px-2 py-0.5" style={{ background: 'var(--surface-3)', color: 'var(--text-faint)', borderRadius: '4px' }}>
          depth-2
        </span>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// CONCEPT 3 — Command Console / Mission Control
// ═══════════════════════════════════════════════════════════
function CommandConsole() {
  return (
    <div className="px-6 py-10">
      <div
        className="max-w-[1100px] mx-auto"
        style={{ border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}
      >
        {/* Title bar */}
        <div
          className="flex items-center justify-between px-4 py-2"
          style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border-soft)' }}
        >
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
              CRT Runtime Console
            </span>
            <span className="font-mono text-[9px] px-1.5 py-0.5" style={{ background: 'rgba(138,170,110,0.15)', color: 'var(--ok)', borderRadius: '3px' }}>
              LIVE
            </span>
          </div>
          <div className="flex items-center gap-4 font-mono text-[10px]" style={{ color: 'var(--text-faint)' }}>
            <span>pid: 48201</span>
            <span>mem: 142MB</span>
            <span>uptime: 4d 7h</span>
          </div>
        </div>

        {/* Two-panel layout */}
        <div className="flex" style={{ minHeight: '420px' }}>
          {/* Left: Log stream */}
          <div className="flex-1 overflow-auto" style={{ borderRight: '1px solid var(--border-soft)' }}>
            <div className="p-3 space-y-0.5">
              {CONSOLE_LINES.map((line, i) => (
                <div key={i} className="flex gap-3 font-mono text-[11px] leading-relaxed py-0.5 hover:bg-white/[0.02] px-1 -mx-1 rounded">
                  <span style={{ color: 'var(--text-faint)', minWidth: '110px', flexShrink: 0 }}>{line.ts}</span>
                  <span
                    className="uppercase text-[9px] font-bold tracking-wider"
                    style={{
                      color: line.level === 'ok' ? 'var(--ok)' : line.level === 'warn' ? 'var(--warn)' : 'var(--text-faint)',
                      minWidth: '36px',
                      flexShrink: 0,
                    }}
                  >
                    {line.level}
                  </span>
                  <span style={{ color: 'var(--text-muted)' }}>{line.msg}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Status panels */}
          <div className="flex-none flex flex-col" style={{ width: '280px', background: 'var(--surface)' }}>
            {/* Active gates */}
            <div className="p-3" style={{ borderBottom: '1px solid var(--border-soft)' }}>
              <div className="font-mono text-[9px] uppercase tracking-wider mb-2" style={{ color: 'var(--text-faint)' }}>
                Gate Status
              </div>
              {['intent_gate', 'direction_gate', 'contradiction_gate', 'belief_gate'].map((g) => (
                <div key={g} className="flex items-center justify-between py-1">
                  <span className="font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>{g}</span>
                  <span className="font-mono text-[9px] font-bold" style={{ color: 'var(--ok)' }}>PASS</span>
                </div>
              ))}
            </div>

            {/* Belief state */}
            <div className="p-3" style={{ borderBottom: '1px solid var(--border-soft)' }}>
              <div className="font-mono text-[9px] uppercase tracking-wider mb-2" style={{ color: 'var(--text-faint)' }}>
                Belief State
              </div>
              <div className="space-y-2">
                {[
                  { label: 'grounded_beliefs', val: '847' },
                  { label: 'provisional', val: '203' },
                  { label: 'demoted_today', val: '3' },
                  { label: 'contradictions_open', val: '1' },
                ].map((r) => (
                  <div key={r.label} className="flex items-center justify-between">
                    <span className="font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>{r.label}</span>
                    <span className="font-mono text-[11px]" style={{ color: 'var(--text)' }}>{r.val}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Trust histogram */}
            <div className="p-3 flex-1">
              <div className="font-mono text-[9px] uppercase tracking-wider mb-3" style={{ color: 'var(--text-faint)' }}>
                Trust Distribution
              </div>
              <div className="space-y-1.5">
                {[
                  { range: '0.9 - 1.0', pct: 62 },
                  { range: '0.7 - 0.9', pct: 24 },
                  { range: '0.5 - 0.7', pct: 9 },
                  { range: '0.3 - 0.5', pct: 4 },
                  { range: '0.0 - 0.3', pct: 1 },
                ].map((b) => (
                  <div key={b.range} className="flex items-center gap-2">
                    <span className="font-mono text-[10px] flex-none" style={{ color: 'var(--text-faint)', width: '60px' }}>{b.range}</span>
                    <div className="flex-1 h-2 rounded-sm overflow-hidden" style={{ background: 'var(--surface-3)' }}>
                      <div
                        className="h-full rounded-sm"
                        style={{
                          width: `${b.pct}%`,
                          background: b.pct > 50 ? 'var(--ok)' : b.pct > 20 ? 'var(--accent)' : 'var(--text-faint)',
                          opacity: 0.7,
                        }}
                      />
                    </div>
                    <span className="font-mono text-[10px] flex-none text-right" style={{ color: 'var(--text-faint)', width: '28px' }}>
                      {b.pct}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Command input */}
        <div
          className="flex items-center gap-2 px-4 py-2"
          style={{ background: 'var(--surface-2)', borderTop: '1px solid var(--border-soft)' }}
        >
          <span className="font-mono text-[11px]" style={{ color: 'var(--accent)' }}>$</span>
          <span className="font-mono text-[11px]" style={{ color: 'var(--text-faint)' }}>
            type a command...
          </span>
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// V2 Page — All concepts
// ═══════════════════════════════════════════════════════════
export function V2Page() {
  return (
    <div className="h-full overflow-auto" style={{ background: 'var(--bg)' }}>
      <Section label="Concept 1 — Hero Landing">
        <HeroLanding />
      </Section>

      <div className="h-px" style={{ background: 'var(--border)' }} />

      <Section label="Concept 2 — Cinematic Chat">
        <CinematicChat />
      </Section>

      <div className="h-px" style={{ background: 'var(--border)' }} />

      <Section label="Concept 3 — Command Console">
        <CommandConsole />
      </Section>

      {/* Bottom padding */}
      <div className="h-20" />
    </div>
  )
}
