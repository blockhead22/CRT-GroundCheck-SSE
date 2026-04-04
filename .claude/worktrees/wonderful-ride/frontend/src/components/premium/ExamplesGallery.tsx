import { motion } from 'framer-motion'

interface ExampleScenario {
  id: string
  title: string
  icon: string
  description: string
  steps: Array<{
    type: 'user' | 'system'
    message: string
  }>
  category: 'job' | 'location' | 'medical' | 'preference'
}

const exampleScenarios: ExampleScenario[] = [
  {
    id: 'job-change',
    title: 'Job Change',
    icon: '💼',
    description: 'Track employment history with full transparency',
    category: 'job',
    steps: [
      { type: 'user', message: 'I work at Microsoft' },
      { type: 'system', message: "Got it! I'll remember you work at Microsoft." },
      { type: 'user', message: 'I work at Amazon now' },
      {
        type: 'system',
        message:
          '⚠️ Contradiction detected! You previously said Microsoft. I\'ll update to Amazon and track this change.',
      },
      { type: 'user', message: 'Where do I work?' },
      {
        type: 'system',
        message: 'You work at Amazon (changed from Microsoft). This was updated in your profile.',
      },
    ],
  },
  {
    id: 'location-move',
    title: 'Location Move',
    icon: '🏠',
    description: 'Handle address updates without losing history',
    category: 'location',
    steps: [
      { type: 'user', message: 'I live in Seattle' },
      { type: 'system', message: "Noted! I'll remember Seattle as your location." },
      { type: 'user', message: 'I moved to Portland' },
      {
        type: 'system',
        message:
          '⚠️ Location update detected. Changing from Seattle to Portland and preserving the history in the ledger.',
      },
      { type: 'user', message: 'Where do I live?' },
      { type: 'system', message: 'You live in Portland (previously Seattle). Your location was updated recently.' },
    ],
  },
  {
    id: 'medical-update',
    title: 'Medical Update',
    icon: '🏥',
    description: 'Critical for tracking diagnosis changes',
    category: 'medical',
    steps: [
      { type: 'user', message: 'I was diagnosed with condition X' },
      { type: 'system', message: "I've recorded your diagnosis of condition X." },
      { type: 'user', message: 'The retest came back negative for condition X' },
      {
        type: 'system',
        message:
          '⚠️ Important medical update! Diagnosis changed from positive to negative. This is preserved in your medical history.',
      },
      { type: 'user', message: 'What was my diagnosis?' },
      {
        type: 'system',
        message:
          'Your current status is negative for condition X (changed from initial positive diagnosis). Always consult with your healthcare provider for medical decisions.',
      },
    ],
  },
  {
    id: 'preference-shift',
    title: 'Preference Change',
    icon: '🎨',
    description: 'Evolving tastes tracked transparently',
    category: 'preference',
    steps: [
      { type: 'user', message: 'My favorite color is blue' },
      { type: 'system', message: 'Blue is your favorite color. Got it!' },
      { type: 'user', message: 'Actually, I prefer green now' },
      {
        type: 'system',
        message: "⚠️ Preference updated! Changed from blue to green. I'll remember this new preference.",
      },
      { type: 'user', message: "What's my favorite color?" },
      { type: 'system', message: 'Your favorite color is green (changed from blue).' },
    ],
  },
]

interface ExamplesGalleryProps {
  onLoadExample?: (scenario: ExampleScenario) => void
}

export function ExamplesGallery(props: ExamplesGalleryProps) {
  function getCategoryColor(category: string): string {
    switch (category) {
      case 'job':
        return 'violet'
      case 'location':
        return 'blue'
      case 'medical':
        return 'red'
      case 'preference':
        return 'green'
      default:
        return 'gray'
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-lg font-semibold text-white/90">Example Scenarios</h3>
        <p className="text-sm text-white/60">Click any scenario to see it in action</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {exampleScenarios.map((scenario, index) => {
          const categoryColor = getCategoryColor(scenario.category)
          return (
            <motion.button
              key={scenario.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              whileHover={{ y: -4, scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => props.onLoadExample?.(scenario)}
              className={`group relative overflow-hidden rounded-2xl border border-${categoryColor}-500/30 bg-${categoryColor}-500/5 p-6 text-left shadow-lg transition hover:shadow-xl`}
            >
              {/* Icon */}
              <div
                className={`mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-${categoryColor}-500/20 text-3xl`}
              >
                {scenario.icon}
              </div>

              {/* Title */}
              <div className="mb-2 text-lg font-bold text-white">{scenario.title}</div>

              {/* Description */}
              <div className="mb-4 text-sm text-white/60">{scenario.description}</div>

              {/* Steps Count */}
              <div className="flex items-center gap-2 text-xs text-white/50">
                <span>📝</span>
                <span>{scenario.steps.length} steps</span>
              </div>

              {/* Hover Indicator */}
              <div className="absolute bottom-0 left-0 h-1 w-full bg-gradient-to-r from-transparent via-white/20 to-transparent opacity-0 transition group-hover:opacity-100" />
            </motion.button>
          )
        })}
      </div>

      {/* Info Box */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="rounded-xl border border-violet-500/30 bg-violet-500/10 p-4"
      >
        <div className="flex items-start gap-3">
          <div className="text-2xl">💡</div>
          <div className="flex-1">
            <div className="mb-1 text-sm font-semibold text-violet-300">Learn by Example</div>
            <div className="text-xs text-white/60">
              These scenarios demonstrate how CRT handles contradictions in real-world situations. Each example shows
              the full conversation flow, contradiction detection, and transparent disclosure.
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

// Expandable scenario viewer for when an example is loaded
interface ScenarioViewerProps {
  scenario: ExampleScenario
  onClose: () => void
}

export function ScenarioViewer(props: ScenarioViewerProps) {
  const categoryColor = getCategoryColor(props.scenario.category)

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="fixed inset-0 z-[1300] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={props.onClose}
    >
      <motion.div
        initial={{ y: 20 }}
        animate={{ y: 0 }}
        className="mx-4 w-full max-w-2xl rounded-3xl border border-white/10 bg-gradient-to-br from-gray-900/95 to-gray-800/95 shadow-2xl backdrop-blur-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className={`flex items-center justify-between border-b border-${categoryColor}-500/30 bg-${categoryColor}-500/10 p-6`}
        >
          <div className="flex items-center gap-4">
            <div
              className={`flex h-16 w-16 items-center justify-center rounded-2xl bg-${categoryColor}-500/20 text-4xl`}
            >
              {props.scenario.icon}
            </div>
            <div>
              <h3 className="text-xl font-bold text-white">{props.scenario.title}</h3>
              <p className="text-sm text-white/60">{props.scenario.description}</p>
            </div>
          </div>
          <button
            onClick={props.onClose}
            className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-white/60 transition hover:bg-white/10 hover:text-white"
          >
            ✕
          </button>
        </div>

        {/* Conversation Steps */}
        <div className="max-h-[60vh] overflow-auto p-6">
          <div className="space-y-4">
            {props.scenario.steps.map((step, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: step.type === 'user' ? -20 : 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className={`flex ${step.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                    step.type === 'user'
                      ? 'bg-violet-600/20 text-white'
                      : 'border border-white/10 bg-white/5 text-white/90'
                  }`}
                >
                  <div className="mb-1 text-xs font-medium opacity-60">
                    {step.type === 'user' ? 'You' : 'CRT AI'}
                  </div>
                  <div className="text-sm">{step.message}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-white/10 bg-black/20 p-4">
          <button
            onClick={props.onClose}
            className="w-full rounded-xl bg-gradient-to-r from-violet-600 to-purple-600 px-6 py-3 font-semibold text-white transition hover:brightness-110"
          >
            Close Example
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

function getCategoryColor(category: string): string {
  switch (category) {
    case 'job':
      return 'violet'
    case 'location':
      return 'blue'
    case 'medical':
      return 'red'
    case 'preference':
      return 'green'
    default:
      return 'gray'
  }
}
