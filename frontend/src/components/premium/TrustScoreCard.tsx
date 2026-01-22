import { motion } from 'framer-motion'

interface TrustHistoryPoint {
  timestamp: number
  trust: number
  event?: string
}

interface TrustScoreCardProps {
  label: string
  currentValue: string
  currentTrust: number
  history?: TrustHistoryPoint[]
  source?: string
  confirmations?: number
  lastUpdated?: number
  superseded?: boolean
  supersededBy?: string
}

export function TrustScoreCard(props: TrustScoreCardProps) {
  function getTrustColor(trust: number): string {
    if (trust >= 0.75) return 'green'
    if (trust >= 0.5) return 'yellow'
    if (trust >= 0.3) return 'orange'
    return 'red'
  }

  function getTrustColorClass(trust: number): string {
    if (trust >= 0.75) return 'text-green-400 bg-green-500/20'
    if (trust >= 0.5) return 'text-yellow-400 bg-yellow-500/20'
    if (trust >= 0.3) return 'text-orange-400 bg-orange-500/20'
    return 'text-red-400 bg-red-500/20'
  }

  function getTrustBarClass(trust: number): string {
    if (trust >= 0.75) return 'bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]'
    if (trust >= 0.5) return 'bg-yellow-500 shadow-[0_0_10px_rgba(234,179,8,0.5)]'
    if (trust >= 0.3) return 'bg-orange-500 shadow-[0_0_10px_rgba(249,115,22,0.5)]'
    return 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]'
  }

  const color = getTrustColor(props.currentTrust)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      className={`overflow-hidden rounded-2xl border ${
        props.superseded
          ? 'border-white/10 bg-white/5 opacity-70'
          : `border-${color}-500/30 bg-${color}-500/5`
      }`}
    >
      {/* Header */}
      <div className={`border-b px-4 py-3 ${props.superseded ? 'border-white/10 bg-white/5' : `border-${color}-500/30 bg-${color}-500/10`}`}>
        <div className="mb-1 flex items-center justify-between">
          <div className="text-sm font-semibold text-white/90">{props.label}</div>
          {props.superseded && <div className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-400">Superseded</div>}
        </div>
        <div className="text-lg font-bold text-white">{props.currentValue}</div>
        {props.supersededBy && (
          <div className="mt-1 text-xs text-white/50">Replaced by: {props.supersededBy}</div>
        )}
      </div>

      {/* Trust Score */}
      <div className="p-4">
        <div className="mb-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-sm font-medium text-white/80">Trust Score</div>
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.2, type: 'spring' }}
              className={`rounded-full px-2.5 py-1 text-sm font-bold ${getTrustColorClass(props.currentTrust)}`}
            >
              {(props.currentTrust * 100).toFixed(0)}%
            </motion.div>
          </div>

          {/* Animated Trust Bar */}
          <div className="h-3 overflow-hidden rounded-full bg-white/10">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${props.currentTrust * 100}%` }}
              transition={{ duration: 1, ease: 'easeOut', delay: 0.3 }}
              className={`h-full ${getTrustBarClass(props.currentTrust)}`}
            />
          </div>
        </div>

        {/* Metadata Grid */}
        <div className="grid grid-cols-2 gap-3 rounded-xl bg-black/20 p-3 text-xs">
          {props.source && (
            <div>
              <div className="mb-1 text-white/50">Source</div>
              <div className="font-medium text-white/80">{props.source}</div>
            </div>
          )}
          {props.confirmations !== undefined && (
            <div>
              <div className="mb-1 text-white/50">Confirmations</div>
              <div className="font-medium text-white/80">{props.confirmations}</div>
            </div>
          )}
          {props.lastUpdated && (
            <div className="col-span-2">
              <div className="mb-1 text-white/50">Last Updated</div>
              <div className="font-medium text-white/80">
                {new Date(props.lastUpdated).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })}
              </div>
            </div>
          )}
        </div>

        {/* Trust Evolution Chart (if history provided) */}
        {props.history && props.history.length > 1 && (
          <div className="mt-4 rounded-xl bg-black/20 p-3">
            <div className="mb-2 text-xs font-medium text-white/70">Trust Evolution</div>
            <div className="flex h-20 items-end justify-between gap-1">
              {props.history.map((point, index) => (
                <div key={index} className="group relative flex-1">
                  <motion.div
                    initial={{ height: 0 }}
                    animate={{ height: `${point.trust * 100}%` }}
                    transition={{ delay: index * 0.1, duration: 0.5 }}
                    className={`w-full rounded-t-sm ${getTrustBarClass(point.trust)}`}
                    style={{ minHeight: '4px' }}
                  />
                  {/* Tooltip */}
                  <div className="pointer-events-none absolute bottom-full left-1/2 mb-2 hidden -translate-x-1/2 rounded-lg bg-black/90 px-2 py-1 text-xs text-white/90 shadow-lg group-hover:block">
                    <div>{(point.trust * 100).toFixed(0)}%</div>
                    {point.event && <div className="text-white/60">{point.event}</div>}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-2 flex justify-between text-xs text-white/40">
              <span>
                {new Date(props.history[0].timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </span>
              <span>
                {new Date(props.history[props.history.length - 1].timestamp).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                })}
              </span>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}

// Example showing trust evolution
export function TrustScoreCardExample() {
  const now = Date.now()
  const dayMs = 86400000

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <TrustScoreCard
        label="Employer"
        currentValue="Amazon"
        currentTrust={0.9}
        source="User stated directly"
        confirmations={3}
        lastUpdated={now - dayMs * 5}
        history={[
          { timestamp: now - dayMs * 30, trust: 0.5, event: 'Initial mention' },
          { timestamp: now - dayMs * 20, trust: 0.7, event: 'Confirmed' },
          { timestamp: now - dayMs * 10, trust: 0.85, event: 'Re-confirmed' },
          { timestamp: now - dayMs * 5, trust: 0.9, event: 'Third confirmation' },
        ]}
      />

      <TrustScoreCard
        label="Employer"
        currentValue="Microsoft"
        currentTrust={0.6}
        source="User stated directly"
        confirmations={1}
        lastUpdated={now - dayMs * 35}
        superseded
        supersededBy="Amazon"
        history={[
          { timestamp: now - dayMs * 60, trust: 0.9, event: 'Initial trust' },
          { timestamp: now - dayMs * 45, trust: 0.85, event: 'Slight decay' },
          { timestamp: now - dayMs * 35, trust: 0.7, event: 'Superseded' },
          { timestamp: now - dayMs * 5, trust: 0.6, event: 'Further decay' },
        ]}
      />
    </div>
  )
}
