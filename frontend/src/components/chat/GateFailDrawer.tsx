import { motion, AnimatePresence } from 'framer-motion'

// ── Threshold constants (match backend gate logic) ──────────
const THRESHOLDS: Record<string, { intent: number; memory: number; grounding: number }> = {
  factual_intent_fail:   { intent: 0.35, memory: 0.30, grounding: 0.25 },
  explanatory_fail:      { intent: 0.35, memory: 0.30, grounding: 0.25 },
  conversational_fail:   { intent: 0.30, memory: 0.25, grounding: 0.20 },
  contradiction_fail:    { intent: 0.35, memory: 0.30, grounding: 0.25 },
  grounding_fail:        { intent: 0.35, memory: 0.30, grounding: 0.25 },
}

const DEFAULT_THRESHOLD = { intent: 0.35, memory: 0.30, grounding: 0.25 }

// ── Reason labels ───────────────────────────────────────────
const REASON_LABEL: Record<string, string> = {
  factual_intent_fail:   'Factual Intent',
  explanatory_fail:      'Explanatory',
  conversational_fail:   'Conversational',
  contradiction_fail:    'Contradiction',
  grounding_fail:        'Grounding',
  stream_error:          'Stream Error',
  api_error:             'API Error',
  research_error:        'Research Error',
  stopped_by_user:       'Stopped',
}

const REASON_COLOR: Record<string, string> = {
  factual_intent_fail:   '#D47058',
  explanatory_fail:      '#fb923c',
  conversational_fail:   '#818cf8',
  contradiction_fail:    '#fb7185',
  grounding_fail:        '#D47058',
  stream_error:          '#a78bfa',
  api_error:             '#a78bfa',
  research_error:        '#fb923c',
  stopped_by_user:       'rgba(240,235,225,0.4)',
}

// ── Types ───────────────────────────────────────────────────
export type GateFailDrawerProps = {
  open: boolean
  onClose: () => void
  gateReason: string
  gateDebug?: {
    slot?: string | null
    intent_align?: number | null
    memory_align?: number | null
    grounding_score?: number | null
    grounding?: number | null
    hard_conflicts?: number | null
    open_total?: number | null
    trigger?: string | null
    explanation?: string | null
    stored?: string | null
    incoming?: string | null
  } | null
  retrievedMemories?: Array<{
    memory_id?: string | null
    text?: string | null
    trust?: number | null
    score?: number | null
  }>
  contradictionCount?: number
  onRetrySend?: () => void
  onOpenContradictions?: () => void
}

// ── Metric row ──────────────────────────────────────────────
function MetricRow({ label, value, threshold, suffix }: {
  label: string
  value: number | null | undefined
  threshold: number
  suffix?: string
}) {
  const actual = value ?? 0
  const failed = actual < threshold
  return (
    <div className="flex items-center justify-between py-1" style={{ borderBottom: '1px solid rgba(240,235,225,0.04)' }}>
      <span className="text-[11px]" style={{ color: 'rgba(240,235,225,0.5)' }}>{label}</span>
      <div className="flex items-center gap-3">
        <span
          className="text-[12px] font-mono"
          style={{ color: failed ? '#D47058' : '#34d399' }}
        >
          {value != null ? value.toFixed(3) : '—'}
          {suffix}
        </span>
        <span className="text-[10px] font-mono" style={{ color: 'rgba(240,235,225,0.2)' }}>
          / {threshold.toFixed(2)}
        </span>
        <span
          className="rounded px-1.5 py-0.5 text-[9px] font-mono uppercase"
          style={{
            background: failed ? 'rgba(212,112,88,0.12)' : 'rgba(52,211,153,0.12)',
            color: failed ? '#D47058' : '#34d399',
          }}
        >
          {failed ? 'FAIL' : 'PASS'}
        </span>
      </div>
    </div>
  )
}

// ── Memory row ──────────────────────────────────────────────
function MemoryRow({ memory }: {
  memory: { memory_id?: string | null; text?: string | null; trust?: number | null; score?: number | null }
}) {
  const trust = memory.trust ?? 0
  const trustColor = trust > 0.7 ? '#34d399' : trust > 0.4 ? '#c9a45c' : '#D47058'
  return (
    <div
      className="rounded p-2.5"
      style={{ border: '1px solid rgba(240,235,225,0.06)', background: 'rgba(240,235,225,0.02)' }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[10px] font-mono" style={{ color: trustColor }}>
          trust {trust.toFixed(2)}
        </span>
        {memory.score != null && (
          <span className="text-[10px] font-mono" style={{ color: 'rgba(240,235,225,0.25)' }}>
            sim {memory.score.toFixed(2)}
          </span>
        )}
        {memory.memory_id && (
          <span className="text-[9px] font-mono" style={{ color: 'rgba(240,235,225,0.15)' }}>
            {memory.memory_id.slice(0, 8)}
          </span>
        )}
      </div>
      <div className="text-[11px] leading-relaxed line-clamp-3" style={{ color: 'rgba(240,235,225,0.6)' }}>
        {memory.text || '(empty)'}
      </div>
    </div>
  )
}

// ── Action button ───────────────────────────────────────────
function ActionBtn({ label, onClick, color, variant }: {
  label: string
  onClick?: () => void
  color: string
  variant?: 'solid' | 'outline'
}) {
  const isSolid = variant === 'solid'
  return (
    <button
      onClick={onClick}
      disabled={!onClick}
      className="rounded-full px-3.5 py-1.5 text-[11px] font-medium transition-opacity hover:opacity-80 disabled:opacity-30"
      style={
        isSolid
          ? { background: `${color}20`, color, border: `1px solid ${color}40` }
          : { background: 'transparent', color: `${color}90`, border: `1px solid ${color}25` }
      }
    >
      {label}
    </button>
  )
}

// ── Main drawer ─────────────────────────────────────────────
export function GateFailDrawer({
  open,
  onClose,
  gateReason,
  gateDebug,
  retrievedMemories,
  contradictionCount,
  onRetrySend,
  onOpenContradictions,
}: GateFailDrawerProps) {
  const reason = gateReason || 'unknown'
  const label = REASON_LABEL[reason] ?? reason.replace(/_/g, ' ')
  const badgeColor = REASON_COLOR[reason] ?? '#D47058'
  const thresholds = THRESHOLDS[reason] ?? DEFAULT_THRESHOLD

  const intentVal = gateDebug?.intent_align
  const memoryVal = gateDebug?.memory_align
  const groundingVal = gateDebug?.grounding_score ?? gateDebug?.grounding
  const hasMetrics = intentVal != null || memoryVal != null || groundingVal != null
  const memories = (retrievedMemories ?? []).filter((m) => m.text)

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="gf-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-40"
            style={{ background: 'rgba(10,9,8,0.5)' }}
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.div
            key="gf-drawer"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="fixed right-0 top-0 bottom-0 z-50 flex flex-col"
            style={{
              width: 'min(440px, 92vw)',
              background: 'rgba(18,17,16,0.97)',
              borderLeft: '1px solid rgba(240,235,225,0.07)',
            }}
          >
            {/* ── Header ─────────────────────────────────────── */}
            <div
              className="flex items-center justify-between px-4 py-3"
              style={{ borderBottom: '1px solid rgba(240,235,225,0.06)' }}
            >
              <div className="flex items-center gap-2.5">
                <div className="text-sm font-medium text-white/80">Gate Failure</div>
                <span
                  className="rounded px-2 py-0.5 text-[10px] font-mono uppercase"
                  style={{ background: `${badgeColor}15`, color: badgeColor }}
                >
                  {label}
                </span>
              </div>
              <button
                onClick={onClose}
                className="rounded px-2 py-1 text-[11px] transition-opacity hover:opacity-70"
                style={{ color: 'rgba(240,235,225,0.3)', border: '1px solid rgba(240,235,225,0.08)' }}
              >
                close
              </button>
            </div>

            {/* ── Scrollable body ────────────────────────────── */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">

              {/* Explanation */}
              {gateDebug?.explanation && (
                <div
                  className="rounded p-3 text-[11px] leading-relaxed"
                  style={{ background: 'rgba(212,112,88,0.06)', border: '1px solid rgba(212,112,88,0.12)', color: 'rgba(240,235,225,0.7)' }}
                >
                  {gateDebug.explanation}
                </div>
              )}

              {/* Metrics section */}
              {hasMetrics && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider mb-2" style={{ color: 'rgba(240,235,225,0.25)' }}>
                    Gate Metrics
                  </div>
                  <div
                    className="rounded p-3"
                    style={{ border: '1px solid rgba(240,235,225,0.06)', background: 'rgba(240,235,225,0.02)' }}
                  >
                    <MetricRow label="Intent alignment" value={intentVal} threshold={thresholds.intent} />
                    <MetricRow label="Memory alignment" value={memoryVal} threshold={thresholds.memory} />
                    <MetricRow label="Grounding score" value={groundingVal} threshold={thresholds.grounding} />
                    {gateDebug?.hard_conflicts != null && gateDebug.hard_conflicts > 0 && (
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[11px]" style={{ color: 'rgba(240,235,225,0.5)' }}>Hard conflicts</span>
                        <span className="text-[12px] font-mono" style={{ color: '#D47058' }}>
                          {gateDebug.hard_conflicts}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Slot info */}
              {gateDebug?.slot && (
                <div className="flex items-center gap-2">
                  <span className="text-[10px] uppercase tracking-wider" style={{ color: 'rgba(240,235,225,0.25)' }}>
                    Affected slot
                  </span>
                  <span
                    className="rounded px-1.5 py-0.5 text-[11px] font-mono"
                    style={{ background: 'rgba(240,235,225,0.06)', color: '#c9a45c' }}
                  >
                    {gateDebug.slot}
                  </span>
                </div>
              )}

              {/* Stored vs Incoming */}
              {(gateDebug?.stored || gateDebug?.incoming) && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider mb-2" style={{ color: 'rgba(240,235,225,0.25)' }}>
                    Conflict Detail
                  </div>
                  <div className="space-y-1.5">
                    {gateDebug.stored && (
                      <div className="rounded p-2.5" style={{ border: '1px solid rgba(240,235,225,0.06)', background: 'rgba(240,235,225,0.02)' }}>
                        <div className="text-[9px] uppercase tracking-wider mb-1" style={{ color: 'rgba(240,235,225,0.2)' }}>Stored</div>
                        <div className="text-[11px] leading-relaxed line-clamp-3" style={{ color: 'rgba(240,235,225,0.6)' }}>{gateDebug.stored}</div>
                      </div>
                    )}
                    {gateDebug.incoming && (
                      <div className="rounded p-2.5" style={{ border: '1px solid rgba(212,112,88,0.12)', background: 'rgba(212,112,88,0.04)' }}>
                        <div className="text-[9px] uppercase tracking-wider mb-1" style={{ color: 'rgba(212,112,88,0.4)' }}>Incoming</div>
                        <div className="text-[11px] leading-relaxed line-clamp-3" style={{ color: 'rgba(240,235,225,0.6)' }}>{gateDebug.incoming}</div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Retrieved memories */}
              {memories.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider mb-2" style={{ color: 'rgba(240,235,225,0.25)' }}>
                    Affected Memories ({memories.length})
                  </div>
                  <div className="space-y-1.5 max-h-[240px] overflow-y-auto pr-1">
                    {memories.map((m, i) => (
                      <MemoryRow key={m.memory_id ?? i} memory={m} />
                    ))}
                  </div>
                </div>
              )}

              {/* Open contradictions note */}
              {(contradictionCount ?? 0) > 0 && (
                <div
                  className="rounded p-2.5 text-[11px]"
                  style={{ background: 'rgba(251,146,60,0.06)', border: '1px solid rgba(251,146,60,0.12)', color: '#fb923c' }}
                >
                  {contradictionCount} unresolved contradiction{contradictionCount !== 1 ? 's' : ''} may be contributing to this gate failure.
                </div>
              )}
            </div>

            {/* ── Actions footer ─────────────────────────────── */}
            <div
              className="flex items-center justify-end gap-2 px-4 py-3"
              style={{ borderTop: '1px solid rgba(240,235,225,0.06)' }}
            >
              {(contradictionCount ?? 0) > 0 && (
                <ActionBtn
                  label="View Contradictions"
                  onClick={onOpenContradictions}
                  color="#fb923c"
                  variant="outline"
                />
              )}
              <ActionBtn
                label="Retry"
                onClick={onRetrySend}
                color="#E0A080"
                variant="solid"
              />
              <ActionBtn
                label="Dismiss"
                onClick={onClose}
                color="rgba(240,235,225,0.5)"
                variant="outline"
              />
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
