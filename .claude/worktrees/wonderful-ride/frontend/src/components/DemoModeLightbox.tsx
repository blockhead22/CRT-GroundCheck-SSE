import { motion, AnimatePresence } from 'framer-motion'
import { useState } from 'react'

const DEMO_TURNS = [
  {
    id: 1,
    label: 'Turn 1: Initial Fact',
    message: 'My name is Alex Chen and I work at DataCore.',
    description: 'Sets initial facts'
  },
  {
    id: 2,
    label: 'Turn 2: Create Contradiction',
    message: 'Actually, I made a mistake - I work at TechFlow, not DataCore.',
    description: 'Creates employer contradiction'
  },
  {
    id: 3,
    label: 'Turn 3: Recall Contradicted Fact',
    message: 'Where do I work?',
    description: 'Should show caveat + badge'
  },
  {
    id: 4,
    label: 'Turn 4: Confirm Other Fact',
    message: 'What\'s my name?',
    description: 'Non-contradicted fact'
  },
  {
    id: 5,
    label: 'Turn 5: Memory Summary',
    message: 'What do you know about me?',
    description: 'Shows all facts with disclosure'
  }
]

export function DemoModeLightbox(props: { open: boolean; onClose: () => void; onSendMessage: (text: string) => void }) {
  const [copiedId, setCopiedId] = useState<number | null>(null)

  async function copyToClipboard(text: string, id: number) {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    } catch (err) {
      console.error('Copy failed:', err)
    }
  }

  function sendTurn(message: string) {
    props.onSendMessage(message)
    props.onClose()
  }

  return (
    <AnimatePresence>
      {props.open ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={props.onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-2xl rounded-3xl border border-white/20 bg-slate-900/95 p-6 shadow-2xl backdrop-blur-xl"
          >
            {/* Header */}
            <div className="mb-6 flex items-start justify-between">
              <div>
                <h2 className="text-2xl font-bold text-white">Demo Mode</h2>
                <p className="mt-1 text-sm text-white/60">
                  5-turn contradiction demonstration (~2 minutes)
                </p>
              </div>
              <button
                onClick={props.onClose}
                className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white/70 hover:bg-white/10"
              >
                ✕
              </button>
            </div>

            {/* Demo Turns */}
            <div className="space-y-3">
              {DEMO_TURNS.map((turn) => (
                <div
                  key={turn.id}
                  className="rounded-2xl border border-white/10 bg-white/5 p-4 transition-all hover:border-white/20 hover:bg-white/10"
                >
                  <div className="mb-2 flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold text-white">{turn.label}</div>
                      <div className="text-xs text-white/50">{turn.description}</div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => copyToClipboard(turn.message, turn.id)}
                        className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/70 hover:bg-white/10"
                        title="Copy to clipboard"
                      >
                        {copiedId === turn.id ? '✓ Copied' : '📋 Copy'}
                      </button>
                      <button
                        onClick={() => sendTurn(turn.message)}
                        className="rounded-lg border border-violet-500/30 bg-violet-500/20 px-3 py-1.5 text-xs text-violet-200 hover:bg-violet-500/30"
                        title="Send this message"
                      >
                        ▶ Send
                      </button>
                    </div>
                  </div>
                  <div className="mt-2 rounded-lg bg-black/20 p-3">
                    <code className="text-xs text-emerald-300">{turn.message}</code>
                  </div>
                </div>
              ))}
            </div>

            {/* Footer */}
            <div className="mt-6 rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4">
              <div className="flex items-start gap-3">
                <span className="text-lg">💡</span>
                <div className="text-xs text-amber-200">
                  <strong>Expected behavior:</strong> Turn 3 should show "⚠️ CONTRADICTED CLAIMS (2)" badge and caveat
                  like "TechFlow (most recent update)". Enable X-Ray mode to see which memories are flagged.
                </div>
              </div>
            </div>

            {/* Close button */}
            <div className="mt-6 flex justify-end">
              <button
                onClick={props.onClose}
                className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/80 hover:bg-white/10"
              >
                Close
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
