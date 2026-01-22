import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { ComparisonView } from '../components/premium/ComparisonView'
import { ExamplesGallery } from '../components/premium/ExamplesGallery'
import { IntegrationCodeWidget } from '../components/premium/IntegrationCodeWidget'
import { MemoryLaneVisualizer } from '../components/premium/MemoryLaneVisualizer'
import { TrustScoreCard } from '../components/premium/TrustScoreCard'
import { listRecentMemories, type MemoryListItem } from '../lib/api'

type ShowcaseSection = 'comparison' | 'examples' | 'integration' | 'memory-lanes' | 'trust-scores'

export function ShowcasePage() {
  const [activeSection, setActiveSection] = useState<ShowcaseSection>('comparison')
  const [stableMemories, setStableMemories] = useState<MemoryListItem[]>([])
  const [candidateMemories, setCandidateMemories] = useState<MemoryListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch real memories on mount
  useEffect(() => {
    fetchMemories()
  }, [])

  async function fetchMemories() {
    try {
      setLoading(true)
      setError(null)
      const memories = await listRecentMemories('default', 100)
      
      // Split by trust threshold (0.75)
      const stable = memories.filter((m) => m.trust >= 0.75)
      const candidate = memories.filter((m) => m.trust < 0.75)
      
      setStableMemories(stable)
      setCandidateMemories(candidate)
    } catch (err) {
      console.error('Failed to fetch memories:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch memories')
      // Use empty arrays on error
      setStableMemories([])
      setCandidateMemories([])
    } finally {
      setLoading(false)
    }
  }

  // Sample data for visualizations (keep for other sections)
  const sampleStableMemories = [
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

  const sampleCandidateMemories = [
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

  const now = Date.now()
  const dayMs = 86400000

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-white/10 bg-gradient-to-r from-violet-600/10 to-purple-600/10 px-6 py-4">
        <h1 className="mb-1 text-2xl font-bold text-white">Premium Features Showcase</h1>
        <p className="text-sm text-white/60">
          Explore CRT's advanced UX components for contradiction tracking and transparency
        </p>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-white/10 bg-white/5 px-6">
        <div className="flex gap-2 overflow-x-auto py-3">
          {[
            { id: 'comparison' as ShowcaseSection, label: 'Comparison View', icon: '⚖️' },
            { id: 'examples' as ShowcaseSection, label: 'Examples Gallery', icon: '📚' },
            { id: 'memory-lanes' as ShowcaseSection, label: 'Memory Lanes', icon: '🛡️' },
            { id: 'trust-scores' as ShowcaseSection, label: 'Trust Scores', icon: '📊' },
            { id: 'integration' as ShowcaseSection, label: 'Integration', icon: '💻' },
          ].map((section) => (
            <button
              key={section.id}
              onClick={() => setActiveSection(section.id)}
              className={`flex items-center gap-2 whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium transition ${
                activeSection === section.id
                  ? 'bg-violet-600 text-white shadow-lg'
                  : 'bg-white/5 text-white/60 hover:bg-white/10 hover:text-white/80'
              }`}
            >
              <span>{section.icon}</span>
              <span>{section.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <motion.div
          key={activeSection}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {activeSection === 'comparison' && (
            <div className="mx-auto max-w-5xl space-y-6">
              <div className="rounded-xl bg-white/5 p-4">
                <h2 className="mb-2 text-lg font-semibold text-white">Side-by-Side Comparison</h2>
                <p className="text-sm text-white/60">
                  Show users the difference between regular AI (hides contradictions) and CRT-enhanced AI (discloses
                  transparently).
                </p>
              </div>

              <ComparisonView
                userQuery="Where do I work?"
                regularResponse="You work at Amazon."
                crtResponse="You work at Amazon (changed from Microsoft in March 2024)."
                contradictions={[
                  {
                    slot: 'employer',
                    oldValue: 'Microsoft',
                    newValue: 'Amazon',
                  },
                ]}
              />
            </div>
          )}

          {activeSection === 'examples' && (
            <div className="mx-auto max-w-6xl space-y-6">
              <div className="rounded-xl bg-white/5 p-4">
                <h2 className="mb-2 text-lg font-semibold text-white">Pre-loaded Scenarios</h2>
                <p className="text-sm text-white/60">
                  Let users explore common contradiction scenarios: job changes, location moves, medical updates, and
                  preference shifts.
                </p>
              </div>

              <ExamplesGallery onLoadExample={(scenario) => console.log('Load scenario:', scenario.title)} />
            </div>
          )}

          {activeSection === 'memory-lanes' && (
            <div className="mx-auto max-w-6xl space-y-6">
              <div className="rounded-xl bg-white/5 p-4">
                <h2 className="mb-2 text-lg font-semibold text-white">Two-Lane Memory Architecture</h2>
                <p className="text-sm text-white/60">
                  Visualize the separation between high-trust stable facts and pending candidate facts. Facts with trust
                  ≥ 0.75 are promoted to stable lane.
                </p>
              </div>

              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="text-center">
                    <div className="mb-4 text-4xl">⏳</div>
                    <div className="text-white/60">Loading memories...</div>
                  </div>
                </div>
              ) : error ? (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
                  <div className="mb-2 text-sm font-semibold text-red-300">Failed to load memories</div>
                  <div className="mb-3 text-xs text-red-400">{error}</div>
                  <button
                    onClick={fetchMemories}
                    className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700"
                  >
                    Retry
                  </button>
                </div>
              ) : (
                <MemoryLaneVisualizer
                  stableMemories={stableMemories.map((m) => ({
                    id: m.memory_id,
                    text: m.text,
                    trust: m.trust,
                    timestamp: m.timestamp * 1000, // Convert to milliseconds
                    source: m.source,
                  }))}
                  candidateMemories={candidateMemories.map((m) => ({
                    id: m.memory_id,
                    text: m.text,
                    trust: m.trust,
                    timestamp: m.timestamp * 1000, // Convert to milliseconds
                    source: m.source,
                  }))}
                  onPromoteMemory={(id) => console.log('Promote memory:', id)}
                />
              )}
            </div>
          )}

          {activeSection === 'trust-scores' && (
            <div className="mx-auto max-w-4xl space-y-6">
              <div className="rounded-xl bg-white/5 p-4">
                <h2 className="mb-2 text-lg font-semibold text-white">Trust Score Evolution</h2>
                <p className="text-sm text-white/60">
                  Track how trust in facts evolves over time through confirmations, age decay, and supersession by newer
                  facts.
                </p>
              </div>

              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="text-center">
                    <div className="mb-4 text-4xl">⏳</div>
                    <div className="text-white/60">Loading memories...</div>
                  </div>
                </div>
              ) : error ? (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
                  <div className="mb-2 text-sm font-semibold text-red-300">Failed to load memories</div>
                  <div className="mb-3 text-xs text-red-400">{error}</div>
                  <button
                    onClick={fetchMemories}
                    className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700"
                  >
                    Retry
                  </button>
                </div>
              ) : stableMemories.length === 0 && candidateMemories.length === 0 ? (
                <div className="rounded-xl border border-white/10 bg-white/5 p-8 text-center">
                  <div className="mb-4 text-6xl opacity-20">📊</div>
                  <div className="text-lg font-medium text-white/60">No memories to display</div>
                  <div className="mt-2 text-sm text-white/40">
                    Start chatting with the CRT to create memories with trust scores
                  </div>
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2">
                  {stableMemories.slice(0, 2).map((memory) => (
                    <TrustScoreCard
                      key={memory.memory_id}
                      label={memory.source || 'Memory'}
                      currentValue={memory.text}
                      currentTrust={memory.trust}
                      source={memory.source}
                      confirmations={memory.confidence ? Math.round(memory.confidence * 10) : undefined}
                      lastUpdated={memory.timestamp * 1000}
                    />
                  ))}
                  {candidateMemories.slice(0, 2).map((memory) => (
                    <TrustScoreCard
                      key={memory.memory_id}
                      label={memory.source || 'Memory'}
                      currentValue={memory.text}
                      currentTrust={memory.trust}
                      source={memory.source}
                      confirmations={memory.confidence ? Math.round(memory.confidence * 10) : undefined}
                      lastUpdated={memory.timestamp * 1000}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {activeSection === 'integration' && (
            <div className="mx-auto max-w-4xl space-y-6">
              <div className="rounded-xl bg-white/5 p-4">
                <h2 className="mb-2 text-lg font-semibold text-white">Integration Code Examples</h2>
                <p className="text-sm text-white/60">
                  Copy-paste ready code snippets for Python, JavaScript, and cURL. Get started integrating CRT in
                  minutes.
                </p>
              </div>

              <IntegrationCodeWidget defaultLanguage="python" />

              <div className="rounded-xl border border-violet-500/30 bg-violet-500/10 p-4">
                <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-violet-300">
                  <span>📖</span>
                  <span>Full Documentation</span>
                </div>
                <div className="text-sm text-white/70">
                  For detailed integration guides with LangChain, LlamaIndex, and custom RAG pipelines, see:{' '}
                  <a href="/docs/integration" className="text-violet-400 hover:underline">
                    docs/integration/
                  </a>
                </div>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  )
}
