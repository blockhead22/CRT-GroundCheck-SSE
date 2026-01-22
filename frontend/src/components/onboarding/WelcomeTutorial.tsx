import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'

export type TutorialStep = 'intro' | 'create-fact' | 'update-fact' | 'see-disclosure' | 'explore-ledger' | 'complete'

interface WelcomeTutorialProps {
  open: boolean
  onClose: () => void
  onSendMessage: (text: string) => void
  onNavigateToDashboard?: () => void
}

export function WelcomeTutorial(props: WelcomeTutorialProps) {
  const [step, setStep] = useState<TutorialStep>('intro')
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    if (!props.open) {
      setStep('intro')
      setProgress(0)
    }
  }, [props.open])

  useEffect(() => {
    // Update progress based on step
    const progressMap: Record<TutorialStep, number> = {
      intro: 0,
      'create-fact': 20,
      'update-fact': 40,
      'see-disclosure': 60,
      'explore-ledger': 80,
      complete: 100,
    }
    setProgress(progressMap[step])
  }, [step])

  function handleNext() {
    const stepOrder: TutorialStep[] = ['intro', 'create-fact', 'update-fact', 'see-disclosure', 'explore-ledger', 'complete']
    const currentIndex = stepOrder.indexOf(step)
    if (currentIndex < stepOrder.length - 1) {
      setStep(stepOrder[currentIndex + 1])
    }
  }

  function handleSkip() {
    // Mark tutorial as completed in localStorage
    localStorage.setItem('crt-tutorial-completed', 'true')
    props.onClose()
  }

  function handleComplete() {
    localStorage.setItem('crt-tutorial-completed', 'true')
    props.onClose()
  }

  function handleSendTutorialMessage(text: string) {
    props.onSendMessage(text)
    handleNext()
  }

  if (!props.open) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[1300] flex items-center justify-center bg-black/60 backdrop-blur-sm"
        onClick={handleSkip}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className="relative mx-4 w-full max-w-3xl rounded-3xl border border-white/10 bg-gradient-to-br from-gray-900/95 to-gray-800/95 p-8 shadow-2xl backdrop-blur-xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Progress Bar */}
          <div className="mb-6">
            <div className="mb-2 flex items-center justify-between text-sm text-white/60">
              <span>Quick Tutorial</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="progress-bar">
              <motion.div
                className="progress-fill"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
            </div>
          </div>

          {/* Step Content */}
          <AnimatePresence mode="wait">
            {step === 'intro' && (
              <motion.div
                key="intro"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                <div className="text-center">
                  <div className="mb-4 inline-flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 text-4xl shadow-lg">
                    🧠
                  </div>
                  <h2 className="mb-2 bg-gradient-to-r from-violet-300 via-purple-200 to-white bg-clip-text text-4xl font-bold text-transparent">
                    Welcome to CRT
                  </h2>
                  <p className="text-xl text-white/80">The AI Memory That Never Lies</p>
                </div>

                <div className="space-y-4 rounded-2xl bg-white/5 p-6">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
                      <div className="mb-2 text-sm font-semibold text-red-300">Traditional AI</div>
                      <div className="text-sm text-white/70">"You work at Amazon" ✓</div>
                      <div className="mt-2 text-xs text-red-400">❌ Hides that you also said Microsoft</div>
                    </div>
                    <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-4">
                      <div className="mb-2 text-sm font-semibold text-green-300">CRT AI</div>
                      <div className="text-sm text-white/70">"You work at Amazon (changed from Microsoft)"</div>
                      <div className="mt-2 text-xs text-green-400">✅ Full transparency</div>
                    </div>
                  </div>
                </div>

                <p className="text-center text-white/60">
                  In the next 60 seconds, you'll see how CRT tracks contradictions and maintains honest AI memory.
                </p>

                <div className="flex gap-3">
                  <button
                    onClick={handleSkip}
                    className="flex-1 rounded-xl border border-white/10 bg-white/5 px-6 py-3 font-medium text-white/70 transition hover:bg-white/10"
                  >
                    Skip Tutorial
                  </button>
                  <button
                    onClick={handleNext}
                    className="flex-1 rounded-xl bg-gradient-to-r from-violet-600 to-purple-600 px-6 py-3 font-semibold text-white shadow-lg transition hover:shadow-xl hover:brightness-110"
                  >
                    Start Tutorial →
                  </button>
                </div>
              </motion.div>
            )}

            {step === 'create-fact' && (
              <motion.div
                key="create-fact"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                <div>
                  <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-xl bg-blue-500/20 text-3xl">
                    1️⃣
                  </div>
                  <h3 className="mb-2 text-2xl font-bold text-white">Create a Fact</h3>
                  <p className="text-white/70">Let's start by telling CRT where you work.</p>
                </div>

                <div className="rounded-2xl border border-blue-500/30 bg-blue-500/10 p-6">
                  <div className="mb-3 text-sm font-semibold text-blue-300">Try This:</div>
                  <div className="mb-4 rounded-xl bg-black/30 p-4 font-mono text-sm text-white">
                    I work at Microsoft
                  </div>
                  <button
                    onClick={() => handleSendTutorialMessage('I work at Microsoft')}
                    className="w-full rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white shadow-lg transition hover:bg-blue-700"
                  >
                    Send Message
                  </button>
                </div>

                <div className="rounded-xl bg-white/5 p-4">
                  <div className="mb-2 flex items-center gap-2 text-sm font-medium text-white/80">
                    <span className="text-green-400">✓</span> What happens:
                  </div>
                  <p className="text-sm text-white/60">
                    CRT stores this in the <strong>stable lane</strong> (high-trust memory). It will remember this fact
                    going forward.
                  </p>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={handleSkip}
                    className="rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-sm font-medium text-white/70 transition hover:bg-white/10"
                  >
                    Skip
                  </button>
                </div>
              </motion.div>
            )}

            {step === 'update-fact' && (
              <motion.div
                key="update-fact"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                <div>
                  <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-xl bg-orange-500/20 text-3xl">
                    2️⃣
                  </div>
                  <h3 className="mb-2 text-2xl font-bold text-white">Update the Fact</h3>
                  <p className="text-white/70">Now let's change where you work and see what CRT does.</p>
                </div>

                <div className="rounded-2xl border border-orange-500/30 bg-orange-500/10 p-6">
                  <div className="mb-3 text-sm font-semibold text-orange-300">Try This:</div>
                  <div className="mb-4 rounded-xl bg-black/30 p-4 font-mono text-sm text-white">
                    I work at Amazon now
                  </div>
                  <button
                    onClick={() => handleSendTutorialMessage('I work at Amazon now')}
                    className="w-full rounded-xl bg-orange-600 px-6 py-3 font-semibold text-white shadow-lg transition hover:bg-orange-700"
                  >
                    Send Message
                  </button>
                </div>

                <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-4">
                  <div className="mb-2 flex items-center gap-2 text-sm font-medium text-yellow-300">
                    <span>⚠️</span> Contradiction Detected!
                  </div>
                  <p className="text-sm text-white/60">
                    CRT detected a conflict: <strong>Microsoft ≠ Amazon</strong>. Instead of overwriting, it preserves
                    both values in the contradiction ledger.
                  </p>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={handleSkip}
                    className="rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-sm font-medium text-white/70 transition hover:bg-white/10"
                  >
                    Skip
                  </button>
                </div>
              </motion.div>
            )}

            {step === 'see-disclosure' && (
              <motion.div
                key="see-disclosure"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                <div>
                  <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-xl bg-green-500/20 text-3xl">
                    3️⃣
                  </div>
                  <h3 className="mb-2 text-2xl font-bold text-white">See Disclosure in Action</h3>
                  <p className="text-white/70">Ask CRT where you work and see the magic happen.</p>
                </div>

                <div className="rounded-2xl border border-green-500/30 bg-green-500/10 p-6">
                  <div className="mb-3 text-sm font-semibold text-green-300">Try This:</div>
                  <div className="mb-4 rounded-xl bg-black/30 p-4 font-mono text-sm text-white">Where do I work?</div>
                  <button
                    onClick={() => handleSendTutorialMessage('Where do I work?')}
                    className="w-full rounded-xl bg-green-600 px-6 py-3 font-semibold text-white shadow-lg transition hover:bg-green-700"
                  >
                    Ask Question
                  </button>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-red-300">Regular AI</div>
                    <div className="mb-2 text-sm text-white/90">"You work at Amazon"</div>
                    <div className="text-xs text-red-400">❌ Hides Microsoft history</div>
                  </div>
                  <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-4">
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-green-300">CRT AI</div>
                    <div className="mb-2 text-sm text-white/90">"You work at Amazon (changed from Microsoft)"</div>
                    <div className="text-xs text-green-400">✅ Full transparency</div>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={handleSkip}
                    className="rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-sm font-medium text-white/70 transition hover:bg-white/10"
                  >
                    Skip
                  </button>
                </div>
              </motion.div>
            )}

            {step === 'explore-ledger' && (
              <motion.div
                key="explore-ledger"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                <div>
                  <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-xl bg-purple-500/20 text-3xl">
                    4️⃣
                  </div>
                  <h3 className="mb-2 text-2xl font-bold text-white">Explore the Ledger</h3>
                  <p className="text-white/70">See the full contradiction history in the audit trail.</p>
                </div>

                <div className="rounded-2xl border border-purple-500/30 bg-purple-500/10 p-6">
                  <div className="mb-3 text-sm font-semibold text-purple-300">Contradiction Ledger:</div>
                  <div className="space-y-3 rounded-xl bg-black/30 p-4">
                    <div className="border-l-4 border-orange-500 pl-3">
                      <div className="mb-1 text-xs text-white/50">Contradiction #c001</div>
                      <div className="mb-1 text-sm font-medium text-white">Slot: employer</div>
                      <div className="text-xs text-white/70">
                        <div>Old: Microsoft (trust: 0.9)</div>
                        <div>New: Amazon (trust: 0.9)</div>
                      </div>
                      <div className="mt-2 inline-block rounded-full bg-green-500/20 px-2 py-0.5 text-xs text-green-400">
                        DISCLOSED ✓
                      </div>
                    </div>
                  </div>
                  <p className="mt-3 text-xs text-white/60">
                    This is your audit trail. Every contradiction tracked forever.
                  </p>
                </div>

                <div className="rounded-xl bg-white/5 p-4">
                  <div className="mb-2 text-sm font-semibold text-white">🎉 You've completed the tutorial!</div>
                  <p className="text-sm text-white/60">
                    You now understand how CRT prevents AI gaslighting through contradiction tracking and mandatory
                    disclosure.
                  </p>
                </div>

                <div className="flex gap-3">
                  {props.onNavigateToDashboard && (
                    <button
                      onClick={() => {
                        props.onNavigateToDashboard?.()
                        handleComplete()
                      }}
                      className="flex-1 rounded-xl border border-purple-500/30 bg-purple-500/10 px-6 py-3 font-medium text-purple-300 transition hover:bg-purple-500/20"
                    >
                      View Full Ledger
                    </button>
                  )}
                  <button
                    onClick={handleNext}
                    className="flex-1 rounded-xl bg-gradient-to-r from-violet-600 to-purple-600 px-6 py-3 font-semibold text-white shadow-lg transition hover:shadow-xl hover:brightness-110"
                  >
                    Complete Tutorial
                  </button>
                </div>
              </motion.div>
            )}

            {step === 'complete' && (
              <motion.div
                key="complete"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5 }}
                className="space-y-6 text-center"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
                  className="mx-auto inline-flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-green-500 to-emerald-600 text-5xl shadow-xl"
                >
                  ✓
                </motion.div>

                <div>
                  <h3 className="mb-2 text-3xl font-bold text-white">You're All Set!</h3>
                  <p className="text-lg text-white/70">Start using CRT's honest AI memory in your chats.</p>
                </div>

                <div className="mx-auto max-w-md space-y-3 rounded-2xl bg-white/5 p-6">
                  <div className="flex items-center gap-3 text-left">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-500/20 text-green-400">
                      ✓
                    </div>
                    <div className="text-sm text-white/80">Contradictions are tracked</div>
                  </div>
                  <div className="flex items-center gap-3 text-left">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-500/20 text-green-400">
                      ✓
                    </div>
                    <div className="text-sm text-white/80">Disclosures are enforced</div>
                  </div>
                  <div className="flex items-center gap-3 text-left">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-500/20 text-green-400">
                      ✓
                    </div>
                    <div className="text-sm text-white/80">Full audit trail available</div>
                  </div>
                </div>

                <button
                  onClick={handleComplete}
                  className="w-full max-w-xs rounded-xl bg-gradient-to-r from-violet-600 to-purple-600 px-8 py-4 text-lg font-semibold text-white shadow-lg transition hover:shadow-xl hover:brightness-110"
                >
                  Start Chatting
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
