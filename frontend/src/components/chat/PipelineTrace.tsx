import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AetherMascot } from '../AetherMascot'
import type { MascotAnimation } from '../AetherMascot'
import type { MoodType } from '../MoodBackground'

type StepMeta = { icon: string; tooltip: string; color: string }

export function classifyStatus(s: string): StepMeta {
  const l = s.toLowerCase()
  if (l.includes('reading context'))            return { icon: '◎', tooltip: 'Loading conversation history, user profile, and active session context', color: '#F0EBE1' }
  if (l.includes('searching memory'))           return { icon: '◈', tooltip: 'Querying trust-weighted memory store — retrieving relevant facts and past assertions', color: '#E0A080' }
  if (l.includes('checking contradict'))        return { icon: '⚡', tooltip: 'Cross-referencing new claims against stored facts to detect conflicts or drift', color: '#D47058' }
  if (l.includes('accessing tools'))            return { icon: '▷', tooltip: 'Preparing tool access — code interpreter, search, or external API calls', color: '#d4a84b' }
  if (l.includes('running agent'))              return { icon: '⟳', tooltip: 'Spawning a sub-agent to handle complex multi-step reasoning or task execution', color: '#E0A080' }
  if (l.includes('analyzing'))                  return { icon: '◇', tooltip: 'Parsing intent and mapping query against retrieved context and user facts', color: '#F0EBE1' }
  if (l.includes('reasoning'))                  return { icon: '◇', tooltip: 'Applying chain-of-thought reasoning over retrieved context to form an answer', color: '#F0EBE1' }
  if (l.includes('planning'))                   return { icon: '≡', tooltip: 'Structuring the response approach — deciding what to include and in what order', color: '#E0A080' }
  if (l.includes('verif'))                      return { icon: '⬡', tooltip: 'Running GroundCheck verification — checking response against stored memory for accuracy', color: '#d4a84b' }
  if (l.includes('drafting'))                   return { icon: '✦', tooltip: 'Generating the final response text based on the verified plan', color: '#F0EBE1' }
  if (l.includes('generating'))                 return { icon: '✦', tooltip: `Model generation — ${s}`, color: '#F0EBE1' }
  if (l.includes('classifying slot'))           return { icon: '⬡', tooltip: 'Classifying user input for personal fact slots (name, location, etc.)', color: '#d4a84b' }
  if (l.includes('gate'))                       return { icon: '⬡', tooltip: `Gate check result — ${s}`, color: '#d4a84b' }
  if (l.match(/\d+ mem/))                       return { icon: '◈', tooltip: 'Retrieved memory items used to ground this response', color: '#E0A080' }
  if (l.includes('agent activated'))            return { icon: '⟳', tooltip: 'Agent was invoked — check agent trace for step details', color: '#E0A080' }
  if (l.includes('contradict') && l.includes('detect')) return { icon: '⚡', tooltip: 'A contradiction was detected between new input and existing memories', color: '#D47058' }
  if (l.includes('belief') || l.includes('explanation')) return { icon: '◉', tooltip: 'Response type: grounded in stored beliefs with confidence scoring', color: '#E0A080' }
  return { icon: '·', tooltip: s, color: '#a09880' }
}

function stepToMascotState(s: string): { anim: MascotAnimation; mood: MoodType } {
  const l = s.toLowerCase()
  if (l.includes('reading context'))     return { anim: 'curious', mood: 'curious' }
  if (l.includes('searching memory'))    return { anim: 'curious', mood: 'curious' }
  if (l.includes('reasoning'))           return { anim: 'thinking', mood: 'curious' }
  if (l.includes('planning'))            return { anim: 'thinking', mood: 'curious' }
  if (l.includes('analyzing'))           return { anim: 'thinking', mood: 'curious' }
  if (l.includes('verif'))               return { anim: 'working', mood: 'warm' }
  if (l.includes('drafting'))            return { anim: 'working', mood: 'warm' }
  if (l.includes('generating'))          return { anim: 'working', mood: 'warm' }
  if (l.includes('contradict'))          return { anim: 'alert', mood: 'intense' }
  if (l.includes('classifying'))         return { anim: 'nod', mood: 'curious' }
  if (l.includes('gate'))               return { anim: 'nod', mood: 'uncertain' }
  if (l.includes('agent'))              return { anim: 'working', mood: 'intense' }
  return { anim: 'loading', mood: 'curious' }
}

export function PipelineTrace({
  statuses,
  streaming = false,
  defaultOpen,
}: {
  statuses: string[]
  streaming?: boolean
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen ?? streaming)

  const deduped = statuses
    .filter((s) => !s.startsWith('ctrl:') && s !== 'Processing message...')
    .filter((s, i, arr) => i === 0 || s !== arr[i - 1])

  if (deduped.length === 0) return null

  const activeStep = deduped[deduped.length - 1]

  const progressPct = streaming ? `${Math.min(((deduped.length) / Math.max(deduped.length + 2, 6)) * 100, 90)}%` : '100%'

  const { anim: mascotAnim, mood: mascotMood } = stepToMascotState(activeStep)

  return (
    <div className="mb-3">
      {/* Progress bar + walking mascot */}
      <div className="relative mb-2">
        {/* Mascot walking along the bar */}
        <AnimatePresence>
          {streaming && (
            <motion.div
              key="pipeline-mascot"
              className="absolute z-10"
              style={{ bottom: 2, marginLeft: -12 }}
              initial={{ left: '0%', opacity: 0 }}
              animate={{ left: progressPct, opacity: 1 }}
              exit={{
                left: '0%',
                bottom: -180,
                opacity: 0,
                transition: { duration: 1, ease: [0.25, 0.1, 0.25, 1] },
              }}
              transition={{ left: { duration: 0.6, ease: 'easeOut' }, opacity: { duration: 0.3 } }}
            >
              <AetherMascot
                mood={mascotMood}
                animation={mascotAnim}
                size={24}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Progress bar — thin accent line */}
        <div className="h-[2px] rounded-full overflow-hidden" style={{ background: 'rgba(240,235,225,0.04)' }}>
        <motion.div
          className="h-full rounded-full"
          style={{
            background: streaming
              ? 'linear-gradient(90deg, #D4845C, #E0A080)'
              : 'rgba(106,191,123,0.5)',
            boxShadow: streaming ? '0 0 8px rgba(212,132,92,0.4)' : 'none',
          }}
          initial={{ width: '0%' }}
          animate={{ width: progressPct }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        />
        </div>
      </div>

      {/* Header row */}
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 mb-1.5 w-full text-left group"
      >
        {streaming ? (
          <span className="font-display text-base tracking-wide" style={{ color: '#F0EBE1' }}>
            {activeStep.charAt(0).toUpperCase() + activeStep.slice(1)}
            <span className="ml-2 inline-flex gap-1 items-center">
              {[0, 0.18, 0.36].map((d, i) => (
                <span
                  key={i}
                  className="h-[4px] w-[4px] rounded-full animate-bounce inline-block"
                  style={{ background: '#E0A080', opacity: 0.7, animationDelay: `${d}s`, animationDuration: '0.75s' }}
                />
              ))}
            </span>
          </span>
        ) : (
          <span className="text-[11px] font-mono" style={{ color: '#5a5445' }}>
            {open ? '▲' : '▼'} {deduped.length} pipeline steps
          </span>
        )}
      </button>

      {/* Collapsible step list */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="flex flex-col gap-[3px] pl-2 ml-1" style={{ borderLeft: '1px solid rgba(240,235,225,0.06)' }}>
              {deduped.map((s, i) => {
                const { icon, tooltip, color } = classifyStatus(s)
                const isLast = i === deduped.length - 1
                const isActive = isLast && streaming
                return (
                  <div
                    key={`${s}-${i}`}
                    className="flex items-center gap-2 pl-1.5 py-[1px] rounded group/step cursor-default transition-colors hover:bg-white/4"
                    title={tooltip}
                  >
                    <span
                      className="text-[10px] font-mono w-3 flex-shrink-0 transition-colors"
                      style={{ color: isActive ? color : isLast ? color + '99' : '#332e22' }}
                    >
                      {icon}
                    </span>
                    <span
                      className="text-[11px] font-mono transition-colors"
                      style={{ color: isActive ? '#F0EBE1' : isLast ? '#a09880' : '#3d3626' }}
                    >
                      {s}
                    </span>
                    {isActive && (
                      <span
                        className="h-[5px] w-[5px] rounded-full animate-ping flex-shrink-0"
                        style={{ background: color, opacity: 0.6 }}
                      />
                    )}
                    {/* Tooltip shown on hover via title, plus inline on hover */}
                    <span
                      className="hidden group-hover/step:block text-[9px] italic truncate max-w-[200px] ml-auto"
                      style={{ color: '#5a5445' }}
                    >
                      {tooltip}
                    </span>
                  </div>
                )
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
