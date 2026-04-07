import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { TrustBar } from '../components/chat/TrustBar'
import { listBeliefs, type BeliefsResponse, type BeliefEntry } from '../lib/api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(ts: number): string {
  const seconds = Math.floor(Date.now() / 1000 - ts)
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  const days = Math.floor(seconds / 86400)
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days}d ago`
  return `${Math.floor(days / 30)}mo ago`
}

const BELNAP_LABELS: Record<string, { label: string; color: string }> = {
  true:    { label: 'Affirmed',     color: '#34d399' },
  false:   { label: 'Contradicted', color: '#D47058' },
  both:    { label: 'Held',         color: '#E0A080' },
  neither: { label: 'Uncertain',    color: '#635c50' },
}

const AUTHORITY_COLORS: Record<string, string> = {
  locked:      '#34d399',
  confirmed:   '#a89d8a',
  provisional: '#635c50',
}

type SortMode = 'trust' | 'newest'

// ---------------------------------------------------------------------------
// Belief Card
// ---------------------------------------------------------------------------

function BeliefCard({ belief, expanded, onToggle }: {
  belief: BeliefEntry
  expanded: boolean
  onToggle: () => void
}) {
  const belnap = BELNAP_LABELS[belief.belnap_state] ?? BELNAP_LABELS.neither
  const prevTrust = belief.trust_trajectory.length > 0
    ? belief.trust_trajectory[0].from
    : undefined

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.2 }}
      onClick={onToggle}
      className="cursor-pointer"
      style={{
        background: 'var(--surface-2)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        padding: '14px 16px',
        marginBottom: 8,
      }}
    >
      {/* Main row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            color: 'var(--text)',
            fontSize: 14,
            lineHeight: 1.5,
            marginBottom: 8,
          }}>
            {belief.text}
          </div>

          <TrustBar
            trust={belief.trust}
            prevTrust={prevTrust}
            compact
          />
        </div>

        {/* Right badges */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          gap: 4,
          flexShrink: 0,
        }}>
          {/* Kind badge */}
          <span style={{
            fontSize: 10,
            fontFamily: 'var(--font-mono, monospace)',
            color: belief.kind === 'user_belief' ? '#D4845C' : '#a89d8a',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}>
            {belief.kind === 'user_belief' ? 'belief' : 'fact'}
          </span>

          {/* Authority */}
          <span style={{
            fontSize: 10,
            fontFamily: 'var(--font-mono, monospace)',
            color: AUTHORITY_COLORS[belief.authority] ?? '#635c50',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}>
            {belief.authority}
          </span>

          {/* Belnap state */}
          <span style={{
            fontSize: 10,
            fontFamily: 'var(--font-mono, monospace)',
            color: belnap.color,
            padding: '1px 6px',
            borderRadius: 4,
            background: `${belnap.color}15`,
          }}>
            {belnap.label}
          </span>

          {/* Contradictions */}
          {belief.contradiction_count > 0 && (
            <span style={{
              fontSize: 10,
              fontFamily: 'var(--font-mono, monospace)',
              color: '#D47058',
              padding: '1px 6px',
              borderRadius: 4,
              background: 'rgba(212,112,88,0.12)',
            }}>
              {belief.contradiction_count} conflict{belief.contradiction_count > 1 ? 's' : ''}
            </span>
          )}

          {/* Timestamp */}
          <span style={{
            fontSize: 10,
            color: 'var(--text-faint)',
          }}>
            {timeAgo(belief.created_at)}
          </span>
        </div>
      </div>

      {/* Domain tags */}
      {belief.domain_tags && belief.domain_tags.length > 0 && (
        <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
          {belief.domain_tags.map((tag) => (
            <span
              key={tag}
              style={{
                fontSize: 10,
                color: 'var(--text-muted)',
                padding: '1px 6px',
                borderRadius: 4,
                background: 'var(--surface-3)',
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Expanded detail */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{
              marginTop: 12,
              paddingTop: 12,
              borderTop: '1px solid var(--border)',
            }}>
              {/* Trust trajectory */}
              {belief.trust_trajectory.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <div style={{
                    fontSize: 11,
                    color: 'var(--text-muted)',
                    marginBottom: 6,
                    fontFamily: 'var(--font-mono, monospace)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}>
                    Trust History
                  </div>
                  {belief.trust_trajectory.map((change, i) => {
                    const delta = change.to - change.from
                    const arrow = delta > 0 ? '\u25B2' : delta < 0 ? '\u25BC' : '\u25CF'
                    const color = delta > 0 ? '#34d399' : delta < 0 ? '#D47058' : 'var(--text-faint)'
                    return (
                      <div key={i} style={{
                        display: 'flex',
                        gap: 8,
                        fontSize: 11,
                        color: 'var(--text-muted)',
                        marginBottom: 3,
                      }}>
                        <span style={{ color, width: 12, textAlign: 'center' }}>{arrow}</span>
                        <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>
                          {change.from.toFixed(2)} &rarr; {change.to.toFixed(2)}
                        </span>
                        <span style={{ color: 'var(--text-faint)' }}>{change.reason}</span>
                        <span style={{ color: 'var(--text-faint)', marginLeft: 'auto' }}>
                          {timeAgo(change.timestamp)}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Contradictions */}
              {belief.contradictions.length > 0 && (
                <div>
                  <div style={{
                    fontSize: 11,
                    color: 'var(--text-muted)',
                    marginBottom: 6,
                    fontFamily: 'var(--font-mono, monospace)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}>
                    Conflicts
                  </div>
                  {belief.contradictions.map((c) => (
                    <div key={c.ledger_id} style={{
                      display: 'flex',
                      gap: 8,
                      fontSize: 11,
                      color: 'var(--text-muted)',
                      marginBottom: 3,
                    }}>
                      <span style={{
                        color: '#D47058',
                        fontFamily: 'var(--font-mono, monospace)',
                      }}>
                        {c.disposition ?? 'unknown'}
                      </span>
                      <span style={{ color: 'var(--text-faint)' }}>
                        {c.status}
                      </span>
                      {c.drift != null && (
                        <span style={{
                          fontFamily: 'var(--font-mono, monospace)',
                          color: 'var(--text-faint)',
                        }}>
                          drift={c.drift.toFixed(2)}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Empty expanded state */}
              {belief.trust_trajectory.length === 0 && belief.contradictions.length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>
                  No trust changes or conflicts recorded yet.
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Stats bar
// ---------------------------------------------------------------------------

function StatPill({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '6px 14px',
      background: 'var(--surface-3)',
      borderRadius: 8,
      minWidth: 70,
    }}>
      <span style={{
        fontSize: 18,
        fontWeight: 600,
        color: color ?? 'var(--text)',
        fontFamily: 'var(--font-mono, monospace)',
      }}>
        {value}
      </span>
      <span style={{
        fontSize: 10,
        color: 'var(--text-faint)',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
      }}>
        {label}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function BeliefsPage({ threadId }: { threadId: string }) {
  const [data, setData] = useState<BeliefsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [sortMode, setSortMode] = useState<SortMode>('trust')
  const [contestedOnly, setContestedOnly] = useState(false)
  const [minTrust, setMinTrust] = useState(0)

  const fetchBeliefs = () => {
    setLoading(true)
    setError(null)
    listBeliefs(threadId, 100, minTrust)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchBeliefs() }, [threadId, minTrust])

  // Filter and sort
  let beliefs = data?.beliefs ?? []
  if (contestedOnly) {
    beliefs = beliefs.filter((b) => b.contradiction_count > 0)
  }
  if (sortMode === 'newest') {
    beliefs = [...beliefs].sort((a, b) => b.created_at - a.created_at)
  }
  // Default from API is trust-descending, no re-sort needed for 'trust'

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '20px 24px 0',
        flexShrink: 0,
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 16,
        }}>
          <h1 style={{
            fontSize: 22,
            fontWeight: 600,
            color: 'var(--text)',
            margin: 0,
          }}>
            Your Beliefs
          </h1>
          <button
            onClick={fetchBeliefs}
            style={{
              fontSize: 12,
              color: 'var(--text-muted)',
              background: 'var(--surface-3)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              padding: '4px 12px',
              cursor: 'pointer',
            }}
          >
            Refresh
          </button>
        </div>

        {/* Stats */}
        {data && (
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
            <StatPill label="Beliefs" value={data.total_beliefs} />
            <StatPill
              label="Avg Trust"
              value={data.average_trust.toFixed(2)}
              color={data.average_trust >= 0.7 ? '#34d399' : data.average_trust >= 0.4 ? '#E0A080' : '#D47058'}
            />
            <StatPill label="Contested" value={data.contested} color={data.contested > 0 ? '#D47058' : undefined} />
            <StatPill label="Held" value={data.held_contradictions} color={data.held_contradictions > 0 ? '#E0A080' : undefined} />
          </div>
        )}

        {/* Filters */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          marginBottom: 16,
          fontSize: 12,
          color: 'var(--text-muted)',
        }}>
          {/* Sort */}
          <button
            onClick={() => setSortMode(sortMode === 'trust' ? 'newest' : 'trust')}
            style={{
              fontSize: 11,
              color: 'var(--text-muted)',
              background: 'var(--surface-3)',
              border: '1px solid var(--border)',
              borderRadius: 5,
              padding: '3px 10px',
              cursor: 'pointer',
            }}
          >
            Sort: {sortMode === 'trust' ? 'Strongest' : 'Newest'}
          </button>

          {/* Contested filter */}
          <button
            onClick={() => setContestedOnly(!contestedOnly)}
            style={{
              fontSize: 11,
              color: contestedOnly ? '#D47058' : 'var(--text-muted)',
              background: contestedOnly ? 'rgba(212,112,88,0.12)' : 'var(--surface-3)',
              border: `1px solid ${contestedOnly ? 'rgba(212,112,88,0.3)' : 'var(--border)'}`,
              borderRadius: 5,
              padding: '3px 10px',
              cursor: 'pointer',
            }}
          >
            Contested only
          </button>

          {/* Trust slider */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 11 }}>Min trust:</span>
            <input
              type="range"
              min={0}
              max={100}
              value={minTrust * 100}
              onChange={(e) => setMinTrust(Number(e.target.value) / 100)}
              style={{ width: 80, accentColor: '#D4845C' }}
            />
            <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 11, width: 32 }}>
              {minTrust.toFixed(1)}
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '0 24px 24px',
      }}>
        {error && (
          <div style={{
            color: '#D47058',
            background: 'rgba(212,112,88,0.08)',
            padding: '10px 14px',
            borderRadius: 8,
            fontSize: 13,
            marginBottom: 12,
          }}>
            {error}
          </div>
        )}

        {loading && !data && (
          <div style={{ color: 'var(--text-faint)', fontSize: 13, padding: 20, textAlign: 'center' }}>
            Loading beliefs...
          </div>
        )}

        {data && beliefs.length === 0 && (
          <div style={{
            textAlign: 'center',
            padding: '48px 24px',
            color: 'var(--text-muted)',
          }}>
            <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.4 }}>&#9671;</div>
            <div style={{ fontSize: 15, marginBottom: 8 }}>No beliefs or facts tracked yet</div>
            <div style={{ fontSize: 13, color: 'var(--text-faint)', maxWidth: 360, margin: '0 auto' }}>
              Share facts, opinions, stances, and positions in conversation.
              They'll appear here with trust scores that evolve over time.
            </div>
          </div>
        )}

        <AnimatePresence>
          {beliefs.map((belief) => (
            <BeliefCard
              key={belief.memory_id}
              belief={belief}
              expanded={expandedId === belief.memory_id}
              onToggle={() => setExpandedId(
                expandedId === belief.memory_id ? null : belief.memory_id
              )}
            />
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
