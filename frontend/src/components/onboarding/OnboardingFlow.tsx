import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

export interface OnboardingData {
  displayName: string
  role: string
  interests: string[]
  frustrationLevel: number
  frustrations: string[]
  freeText: string
}

const INTEREST_OPTIONS = [
  'Work', 'Creative projects', 'Learning', 'Health',
  'Relationships', 'Philosophy', 'Coding', 'Other',
]

const FRUSTRATION_OPTIONS = [
  'Forgets what I said',
  'Makes things up',
  'Too agreeable',
  'Generic responses',
  "Can't do anything useful",
  'Privacy concerns',
]

const slideIn = {
  initial: { opacity: 0, x: 60 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -60 },
  transition: { duration: 0.3, ease: 'easeInOut' },
}

export function OnboardingFlow({ onComplete }: { onComplete: (data: OnboardingData) => void }) {
  const [step, setStep] = useState(0)
  const totalSteps = 5

  // Collected data
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState('')
  const [interests, setInterests] = useState<string[]>([])
  const [frustrationLevel, setFrustrationLevel] = useState(5)
  const [frustrations, setFrustrations] = useState<string[]>([])
  const [freeText, setFreeText] = useState('')

  const next = () => setStep((s) => Math.min(s + 1, totalSteps - 1))
  const back = () => setStep((s) => Math.max(s - 1, 0))

  const toggleChip = (list: string[], setList: (v: string[]) => void, value: string) => {
    setList(list.includes(value) ? list.filter((v2) => v2 !== value) : [...list, value])
  }

  const handleFinish = () => {
    const data: OnboardingData = { displayName, role, interests, frustrationLevel, frustrations, freeText }
    localStorage.setItem('crt-onboarding-data', JSON.stringify(data))
    localStorage.setItem('crt-onboarding-complete', 'true')
    onComplete(data)
  }

  const progress = ((step + 1) / totalSteps) * 100

  return (
    <div className="aetheris-dark min-h-screen w-full flex items-center justify-center p-4 select-none"
         style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}>
      <div className="w-full max-w-2xl" style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
        {/* Progress dots */}
        <div className="flex items-center justify-center gap-2 mb-6">
          {Array.from({ length: totalSteps }).map((_, i) => (
            <div
              key={i}
              className={`h-2 rounded-full transition-all duration-300 ${
                i === step ? 'w-8 bg-violet-500' : i < step ? 'w-2 bg-violet-500/60' : 'w-2 bg-white/20'
              }`}
            />
          ))}
        </div>

        {/* Progress bar */}
        <div className="mb-8 mx-auto max-w-xs">
          <div className="h-1 rounded-full bg-white/10 overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-violet-500 to-purple-500 rounded-full"
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.4, ease: 'easeOut' }}
            />
          </div>
        </div>

        <AnimatePresence mode="wait">
          {/* ── Screen 1: What is Aether? ── */}
          {step === 0 && (
            <motion.div key="what" {...slideIn} className="glass-panel rounded-[28px] p-8 sm:p-10">
              {/* Hero placeholder */}
              <div className="mx-auto mb-6 flex h-32 w-32 items-center justify-center rounded-full bg-gradient-to-br from-violet-600/30 to-purple-600/30 border border-violet-500/20">
                <span className="text-6xl">&#x2728;</span>
              </div>

              <h1 className="text-center text-3xl sm:text-4xl font-bold text-white font-display mb-3">
                Aether
              </h1>
              <p className="text-center text-lg text-white/70 mb-8">
                An AI that remembers — and won't pretend it doesn't.
              </p>

              <div className="space-y-4 mb-8">
                <div className="flex items-start gap-3 rounded-xl bg-white/5 p-4">
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-violet-500/20 text-violet-300 text-sm font-bold">1</div>
                  <div>
                    <div className="text-sm font-semibold text-white">It tracks what you've told it</div>
                    <div className="text-sm text-white/50 mt-0.5">Every fact gets stored with a trust score you can inspect.</div>
                  </div>
                </div>
                <div className="flex items-start gap-3 rounded-xl bg-white/5 p-4">
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-violet-500/20 text-violet-300 text-sm font-bold">2</div>
                  <div>
                    <div className="text-sm font-semibold text-white">When you contradict yourself, it tells you</div>
                    <div className="text-sm text-white/50 mt-0.5">Instead of silently overwriting, it flags the change and keeps both versions.</div>
                  </div>
                </div>
              </div>

              <button onClick={next} className="w-full rounded-xl accent-button py-3.5 text-sm font-semibold text-white transition hover:opacity-90">
                Next
              </button>
            </motion.div>
          )}

          {/* ── Screen 2: How it works ── */}
          {step === 1 && (
            <motion.div key="how" {...slideIn} className="glass-panel rounded-[28px] p-8 sm:p-10">
              <h2 className="text-center text-2xl font-bold text-white font-display mb-2">How it works</h2>
              <p className="text-center text-sm text-white/50 mb-8">A quick look at what happens under the hood.</p>

              <div className="flex flex-col sm:flex-row gap-4 mb-8">
                {/* Step A */}
                <div className="flex-1 rounded-xl border border-blue-500/20 bg-blue-500/5 p-5 text-center">
                  <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-blue-500/20 text-2xl">
                    &#x1F4AC;
                  </div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-blue-300 mb-1">You say</div>
                  <div className="text-sm text-white/80 font-mono">"I work at Microsoft"</div>
                  <div className="mt-2 text-xs text-white/40">Stored as a belief</div>
                </div>

                {/* Arrow */}
                <div className="hidden sm:flex items-center justify-center text-white/20 text-2xl">&#x2192;</div>
                <div className="flex sm:hidden items-center justify-center text-white/20 text-xl">&#x2193;</div>

                {/* Step B */}
                <div className="flex-1 rounded-xl border border-orange-500/20 bg-orange-500/5 p-5 text-center">
                  <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-orange-500/20 text-2xl">
                    &#x1F504;
                  </div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-orange-300 mb-1">Later you say</div>
                  <div className="text-sm text-white/80 font-mono">"I work at Amazon now"</div>
                  <div className="mt-2 text-xs text-white/40">Contradiction detected</div>
                </div>

                {/* Arrow */}
                <div className="hidden sm:flex items-center justify-center text-white/20 text-2xl">&#x2192;</div>
                <div className="flex sm:hidden items-center justify-center text-white/20 text-xl">&#x2193;</div>

                {/* Step C */}
                <div className="flex-1 rounded-xl border border-green-500/20 bg-green-500/5 p-5 text-center">
                  <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-green-500/20 text-2xl">
                    &#x2705;
                  </div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-green-300 mb-1">Aether says</div>
                  <div className="text-sm text-white/80">"You work at Amazon <span className="text-orange-300">(changed from Microsoft)</span>"</div>
                  <div className="mt-2 text-xs text-white/40">Full transparency</div>
                </div>
              </div>

              <div className="rounded-xl bg-white/5 p-4 mb-8 text-center">
                <p className="text-sm text-white/60">
                  No silent overwrites. No gaslighting. Every change is tracked and visible to you.
                </p>
              </div>

              <div className="flex gap-3">
                <button onClick={back} className="rounded-xl border border-white/10 bg-white/5 px-6 py-3.5 text-sm font-medium text-white/70 transition hover:bg-white/10">
                  Back
                </button>
                <button onClick={next} className="flex-1 rounded-xl accent-button py-3.5 text-sm font-semibold text-white transition hover:opacity-90">
                  Next
                </button>
              </div>
            </motion.div>
          )}

          {/* ── Screen 3: Tell us about you ── */}
          {step === 2 && (
            <motion.div key="about" {...slideIn} className="glass-panel rounded-[28px] p-8 sm:p-10">
              <h2 className="text-center text-2xl font-bold text-white font-display mb-2">Tell us about you</h2>
              <p className="text-center text-sm text-white/50 mb-8">
                This seeds your first memories. Everything is optional.
              </p>

              <div className="space-y-6 mb-8">
                {/* Name */}
                <div>
                  <label className="block text-xs font-medium text-white/60 mb-1.5">What should I call you?</label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="Your name or nickname"
                    className="w-full rounded-xl glass-field px-4 py-3 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-violet-500/40"
                  />
                </div>

                {/* Role */}
                <div>
                  <label className="block text-xs font-medium text-white/60 mb-1.5">What do you do?</label>
                  <input
                    type="text"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    placeholder="e.g. software engineer, student, designer..."
                    className="w-full rounded-xl glass-field px-4 py-3 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-violet-500/40"
                  />
                </div>

                {/* Interests */}
                <div>
                  <label className="block text-xs font-medium text-white/60 mb-2">What are you most interested in talking about?</label>
                  <div className="flex flex-wrap gap-2">
                    {INTEREST_OPTIONS.map((opt) => (
                      <button
                        key={opt}
                        onClick={() => toggleChip(interests, setInterests, opt)}
                        className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                          interests.includes(opt)
                            ? 'bg-violet-500/30 text-violet-200 border border-violet-500/40'
                            : 'bg-white/5 text-white/60 border border-white/10 hover:bg-white/10'
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex gap-3">
                <button onClick={back} className="rounded-xl border border-white/10 bg-white/5 px-6 py-3.5 text-sm font-medium text-white/70 transition hover:bg-white/10">
                  Back
                </button>
                <button onClick={next} className="flex-1 rounded-xl accent-button py-3.5 text-sm font-semibold text-white transition hover:opacity-90">
                  {displayName || role || interests.length ? 'Next' : 'Skip'}
                </button>
              </div>
            </motion.div>
          )}

          {/* ── Screen 4: Rate your AI experience ── */}
          {step === 3 && (
            <motion.div key="frustration" {...slideIn} className="glass-panel rounded-[28px] p-8 sm:p-10">
              <h2 className="text-center text-2xl font-bold text-white font-display mb-2">Your AI experience</h2>
              <p className="text-center text-sm text-white/50 mb-8">
                Help us understand where you're starting from.
              </p>

              <div className="space-y-8 mb-8">
                {/* Frustration slider */}
                <div>
                  <label className="block text-xs font-medium text-white/60 mb-3">
                    How frustrated are you with AI assistants today?
                  </label>
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-white/40 w-12 text-right">Not at all</span>
                    <div className="flex-1 relative">
                      <input
                        type="range"
                        min={1}
                        max={10}
                        value={frustrationLevel}
                        onChange={(e) => setFrustrationLevel(Number(e.target.value))}
                        className="w-full h-2 rounded-full appearance-none cursor-pointer accent-violet-500"
                        style={{
                          background: `linear-gradient(to right, rgb(139 92 246) 0%, rgb(139 92 246) ${((frustrationLevel - 1) / 9) * 100}%, rgba(255,255,255,0.1) ${((frustrationLevel - 1) / 9) * 100}%, rgba(255,255,255,0.1) 100%)`,
                        }}
                      />
                      <div className="flex justify-between mt-1 px-0.5">
                        {Array.from({ length: 10 }).map((_, i) => (
                          <span key={i} className={`text-[10px] ${i + 1 === frustrationLevel ? 'text-violet-300 font-bold' : 'text-white/20'}`}>
                            {i + 1}
                          </span>
                        ))}
                      </div>
                    </div>
                    <span className="text-xs text-white/40 w-12">Very</span>
                  </div>
                </div>

                {/* Frustration chips */}
                <div>
                  <label className="block text-xs font-medium text-white/60 mb-2">What bugs you most?</label>
                  <div className="flex flex-wrap gap-2">
                    {FRUSTRATION_OPTIONS.map((opt) => (
                      <button
                        key={opt}
                        onClick={() => toggleChip(frustrations, setFrustrations, opt)}
                        className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                          frustrations.includes(opt)
                            ? 'bg-rose-500/25 text-rose-200 border border-rose-500/40'
                            : 'bg-white/5 text-white/60 border border-white/10 hover:bg-white/10'
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Free text */}
                <div>
                  <label className="block text-xs font-medium text-white/60 mb-1.5">Anything else? (optional)</label>
                  <textarea
                    value={freeText}
                    onChange={(e) => setFreeText(e.target.value)}
                    placeholder="What would make an AI actually useful to you?"
                    rows={3}
                    className="w-full rounded-xl glass-field px-4 py-3 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-violet-500/40 resize-none"
                  />
                </div>
              </div>

              <div className="flex gap-3">
                <button onClick={back} className="rounded-xl border border-white/10 bg-white/5 px-6 py-3.5 text-sm font-medium text-white/70 transition hover:bg-white/10">
                  Back
                </button>
                <button onClick={next} className="flex-1 rounded-xl accent-button py-3.5 text-sm font-semibold text-white transition hover:opacity-90">
                  Almost done
                </button>
              </div>
            </motion.div>
          )}

          {/* ── Screen 5: You're ready ── */}
          {step === 4 && (
            <motion.div key="ready" {...slideIn} className="glass-panel rounded-[28px] p-8 sm:p-10 text-center">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.15, type: 'spring', stiffness: 200, damping: 15 }}
                className="mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-green-500/30 to-emerald-500/30 border border-green-500/20"
              >
                <span className="text-5xl">&#x2714;</span>
              </motion.div>

              <h2 className="text-2xl font-bold text-white font-display mb-2">You're ready</h2>

              {/* Summary of what was captured */}
              {(displayName || role || interests.length > 0) && (
                <div className="rounded-xl bg-white/5 p-5 mb-6 text-left space-y-2 mt-6">
                  {displayName && (
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-violet-400">&#x2022;</span>
                      <span className="text-white/70">We'll call you <span className="text-white font-medium">{displayName}</span></span>
                    </div>
                  )}
                  {role && (
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-violet-400">&#x2022;</span>
                      <span className="text-white/70">You're a <span className="text-white font-medium">{role}</span></span>
                    </div>
                  )}
                  {interests.length > 0 && (
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-violet-400">&#x2022;</span>
                      <span className="text-white/70">Interested in <span className="text-white font-medium">{interests.join(', ')}</span></span>
                    </div>
                  )}
                </div>
              )}

              <p className="text-sm text-white/50 mb-8 max-w-sm mx-auto">
                The more you talk, the more it learns. Give it a few conversations and it'll start to feel different from anything you've used before.
              </p>

              <div className="flex gap-3">
                <button onClick={back} className="rounded-xl border border-white/10 bg-white/5 px-6 py-3.5 text-sm font-medium text-white/70 transition hover:bg-white/10">
                  Back
                </button>
                <button
                  onClick={handleFinish}
                  className="flex-1 rounded-xl bg-gradient-to-r from-violet-600 to-purple-600 py-3.5 text-sm font-semibold text-white shadow-lg transition hover:shadow-xl hover:brightness-110"
                >
                  Get Started
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
