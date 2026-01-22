import { motion } from 'framer-motion'

interface MemoryItem {
  id: string
  text: string
  trust: number
  timestamp?: number
  source?: string
}

interface MemoryLaneVisualizerProps {
  stableMemories: MemoryItem[]
  candidateMemories: MemoryItem[]
  onPromoteMemory?: (memoryId: string) => void
}

export function MemoryLaneVisualizer(props: MemoryLaneVisualizerProps) {
  function getTrustColor(trust: number): string {
    if (trust >= 0.75) return 'green'
    if (trust >= 0.5) return 'yellow'
    if (trust >= 0.3) return 'orange'
    return 'red'
  }

  function getTrustLabel(trust: number): string {
    if (trust >= 0.75) return 'High'
    if (trust >= 0.5) return 'Medium'
    if (trust >= 0.3) return 'Low'
    return 'Very Low'
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-lg font-semibold text-white/90">Two-Lane Memory Architecture</h3>
        <p className="text-sm text-white/60">Stable facts vs. Pending candidates</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Stable Lane */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="overflow-hidden rounded-2xl border border-green-500/30 bg-gradient-to-br from-green-500/5 to-emerald-500/5"
        >
          <div className="border-b border-green-500/30 bg-green-500/10 px-4 py-3">
            <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-green-300">
              <span>🛡️</span>
              <span>STABLE LANE</span>
            </div>
            <div className="text-xs text-white/60">High-trust, confirmed facts</div>
            <div className="mt-2 text-xs text-green-400">
              {props.stableMemories.length} {props.stableMemories.length === 1 ? 'item' : 'items'}
            </div>
          </div>

          <div className="p-4">
            {props.stableMemories.length === 0 ? (
              <div className="py-8 text-center">
                <div className="mb-2 text-4xl opacity-20">🛡️</div>
                <div className="text-sm text-white/40">No stable memories yet</div>
              </div>
            ) : (
              <div className="space-y-3">
                {props.stableMemories.map((memory, index) => (
                  <motion.div
                    key={memory.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="rounded-xl border border-green-500/20 bg-black/20 p-3 shadow-sm"
                  >
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <div className="flex-1 text-sm text-white/90">{memory.text}</div>
                      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-green-500/20 text-green-400">
                        ✓
                      </div>
                    </div>

                    {/* Trust Bar */}
                    <div className="mb-2">
                      <div className="mb-1 flex items-center justify-between text-xs">
                        <span className="text-white/50">Trust: {getTrustLabel(memory.trust)}</span>
                        <span className="text-white/50">{(memory.trust * 100).toFixed(0)}%</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${memory.trust * 100}%` }}
                          transition={{ duration: 0.5, delay: index * 0.05 + 0.2 }}
                          className={`h-full ${
                            getTrustColor(memory.trust) === 'green'
                              ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]'
                              : 'bg-yellow-500'
                          }`}
                        />
                      </div>
                    </div>

                    {/* Metadata */}
                    {(memory.timestamp || memory.source) && (
                      <div className="flex flex-wrap gap-2 text-xs text-white/40">
                        {memory.timestamp && (
                          <span>Added: {new Date(memory.timestamp).toLocaleDateString()}</span>
                        )}
                        {memory.source && <span className="rounded-full bg-green-500/10 px-2 py-0.5">{memory.source}</span>}
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        </motion.div>

        {/* Candidate Lane */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="overflow-hidden rounded-2xl border border-blue-500/30 bg-gradient-to-br from-blue-500/5 to-indigo-500/5"
        >
          <div className="border-b border-blue-500/30 bg-blue-500/10 px-4 py-3">
            <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-blue-300">
              <span>🔄</span>
              <span>CANDIDATE LANE</span>
            </div>
            <div className="text-xs text-white/60">Pending verification</div>
            <div className="mt-2 text-xs text-blue-400">
              {props.candidateMemories.length} {props.candidateMemories.length === 1 ? 'item' : 'items'}
            </div>
          </div>

          <div className="p-4">
            {props.candidateMemories.length === 0 ? (
              <div className="py-8 text-center">
                <div className="mb-2 text-4xl opacity-20">🔄</div>
                <div className="text-sm text-white/40">No candidate memories</div>
              </div>
            ) : (
              <div className="space-y-3">
                {props.candidateMemories.map((memory, index) => (
                  <motion.div
                    key={memory.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="rounded-xl border border-blue-500/20 bg-black/20 p-3 shadow-sm"
                  >
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <div className="flex-1 text-sm text-white/90">{memory.text}</div>
                      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-500/20 text-blue-400">
                        ?
                      </div>
                    </div>

                    {/* Trust Bar */}
                    <div className="mb-2">
                      <div className="mb-1 flex items-center justify-between text-xs">
                        <span className="text-white/50">Trust: {getTrustLabel(memory.trust)}</span>
                        <span className="text-white/50">{(memory.trust * 100).toFixed(0)}%</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${memory.trust * 100}%` }}
                          transition={{ duration: 0.5, delay: index * 0.05 + 0.2 }}
                          className={`h-full ${
                            getTrustColor(memory.trust) === 'green'
                              ? 'bg-blue-500'
                              : getTrustColor(memory.trust) === 'yellow'
                                ? 'bg-yellow-500'
                                : getTrustColor(memory.trust) === 'orange'
                                  ? 'bg-orange-500'
                                  : 'bg-red-500'
                          }`}
                        />
                      </div>
                    </div>

                    {/* Metadata */}
                    {(memory.timestamp || memory.source) && (
                      <div className="flex flex-wrap gap-2 text-xs text-white/40">
                        {memory.timestamp && (
                          <span>Added: {new Date(memory.timestamp).toLocaleDateString()}</span>
                        )}
                        {memory.source && <span className="rounded-full bg-blue-500/10 px-2 py-0.5">{memory.source}</span>}
                      </div>
                    )}

                    {/* Promote Button */}
                    {props.onPromoteMemory && memory.trust >= 0.75 && (
                      <div className="mt-2 border-t border-blue-500/20 pt-2">
                        <button
                          onClick={() => props.onPromoteMemory?.(memory.id)}
                          className="w-full rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-700"
                        >
                          Promote to Stable →
                        </button>
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      </div>

      {/* Legend */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="rounded-xl bg-white/5 p-4"
      >
        <div className="mb-2 text-sm font-semibold text-white/80">How It Works:</div>
        <div className="grid gap-3 text-xs text-white/60 md:grid-cols-2">
          <div className="flex items-start gap-2">
            <span className="text-green-400">🛡️</span>
            <div>
              <strong className="text-white/80">Stable Lane:</strong> Facts with trust ≥ 0.75. Used in responses. High
              confidence.
            </div>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-blue-400">🔄</span>
            <div>
              <strong className="text-white/80">Candidate Lane:</strong> Facts with trust &lt; 0.75. Need confirmation.
              Not used yet.
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

// Example with sample data
export function MemoryLaneVisualizerExample() {
  const stableMemories: MemoryItem[] = [
    {
      id: 'm1',
      text: 'User works at Amazon',
      trust: 0.9,
      timestamp: Date.now() - 86400000 * 7,
      source: 'user_stated',
    },
    {
      id: 'm2',
      text: 'User lives in Seattle',
      trust: 0.85,
      timestamp: Date.now() - 86400000 * 14,
      source: 'user_stated',
    },
    {
      id: 'm3',
      text: 'User knows Python',
      trust: 0.8,
      timestamp: Date.now() - 86400000 * 30,
      source: 'inferred',
    },
  ]

  const candidateMemories: MemoryItem[] = [
    {
      id: 'm4',
      text: 'User likes hiking',
      trust: 0.6,
      timestamp: Date.now() - 86400000 * 2,
      source: 'mentioned_once',
    },
    {
      id: 'm5',
      text: 'User has 2 kids',
      trust: 0.4,
      timestamp: Date.now() - 86400000,
      source: 'uncertain',
    },
  ]

  return (
    <MemoryLaneVisualizer
      stableMemories={stableMemories}
      candidateMemories={candidateMemories}
      onPromoteMemory={(id) => console.log('Promote memory:', id)}
    />
  )
}
