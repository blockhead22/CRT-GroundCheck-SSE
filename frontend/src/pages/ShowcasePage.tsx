import { useState } from 'react'
import { motion } from 'framer-motion'
import { ComparisonView } from '../components/premium/ComparisonView'
import { ExamplesGallery } from '../components/premium/ExamplesGallery'
import { IntegrationCodeWidget } from '../components/premium/IntegrationCodeWidget'
import { MemoryLaneVisualizer } from '../components/premium/MemoryLaneVisualizer'
import { TrustScoreCard } from '../components/premium/TrustScoreCard'

type ShowcaseSection = 'comparison' | 'examples' | 'integration' | 'memory-lanes' | 'trust-scores'

export function ShowcasePage() {
  const [activeSection, setActiveSection] = useState<ShowcaseSection>('comparison')

  // Sample data for visualizations
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

              <MemoryLaneVisualizer
                stableMemories={sampleStableMemories}
                candidateMemories={sampleCandidateMemories}
                onPromoteMemory={(id) => console.log('Promote memory:', id)}
              />
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
