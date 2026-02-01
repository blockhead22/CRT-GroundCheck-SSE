import { motion, AnimatePresence } from 'framer-motion'
import { useMemo } from 'react'

export type MoodType = 'calm' | 'warm' | 'playful' | 'intense' | 'curious' | 'uncertain'

export interface MoodData {
  mood: MoodType
  intensity: number
  thinking_depth: number
  triggers: string[]
}

interface MoodBackgroundProps {
  mood: MoodData | null
  isThinking: boolean
  className?: string
}

const moodConfigs: Record<MoodType, {
  gradient: string
  pulseColor: string
  particleColor: string
  description: string
}> = {
  calm: {
    gradient: 'from-slate-900/0 via-slate-800/5 to-slate-900/0',
    pulseColor: 'bg-slate-400/10',
    particleColor: 'bg-slate-400/20',
    description: 'Neutral and balanced',
  },
  warm: {
    gradient: 'from-orange-900/10 via-amber-800/15 to-orange-900/5',
    pulseColor: 'bg-orange-400/15',
    particleColor: 'bg-amber-400/30',
    description: 'Friendly and inviting',
  },
  playful: {
    gradient: 'from-pink-900/10 via-purple-800/15 to-fuchsia-900/10',
    pulseColor: 'bg-pink-400/15',
    particleColor: 'bg-fuchsia-400/25',
    description: 'Fun and lighthearted',
  },
  intense: {
    gradient: 'from-red-900/15 via-orange-800/20 to-red-900/10',
    pulseColor: 'bg-red-500/20',
    particleColor: 'bg-orange-500/30',
    description: 'Deep thinking or challenging',
  },
  curious: {
    gradient: 'from-cyan-900/10 via-teal-800/15 to-cyan-900/5',
    pulseColor: 'bg-cyan-400/15',
    particleColor: 'bg-teal-400/25',
    description: 'Exploring and questioning',
  },
  uncertain: {
    gradient: 'from-gray-900/10 via-zinc-800/15 to-gray-900/5',
    pulseColor: 'bg-gray-400/15',
    particleColor: 'bg-zinc-400/20',
    description: 'Processing uncertainty',
  },
}

export function MoodBackground({ mood, isThinking, className = '' }: MoodBackgroundProps) {
  const moodType = mood?.mood || 'calm'
  const intensity = mood?.intensity || 0.3
  const thinkingDepth = mood?.thinking_depth || 0
  const config = moodConfigs[moodType]
  
  // Generate particle positions based on intensity
  const particles = useMemo(() => {
    const count = Math.floor(intensity * 8) + (isThinking ? 4 : 0)
    return Array.from({ length: count }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 60 + 40,
      duration: Math.random() * 10 + 15,
      delay: Math.random() * 5,
    }))
  }, [intensity, isThinking])
  
  // Pulse speed based on thinking depth
  const pulseSpeed = isThinking ? 2 - thinkingDepth : 4
  
  return (
    <div className={`fixed inset-0 pointer-events-none overflow-hidden ${className}`}>
      {/* Base gradient overlay */}
      <AnimatePresence mode="wait">
        <motion.div
          key={moodType}
          initial={{ opacity: 0 }}
          animate={{ opacity: intensity }}
          exit={{ opacity: 0 }}
          transition={{ duration: 1.5, ease: 'easeInOut' }}
          className={`absolute inset-0 bg-gradient-to-br ${config.gradient}`}
        />
      </AnimatePresence>
      
      {/* Pulsing center glow when thinking */}
      {isThinking && (
        <motion.div
          className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full ${config.pulseColor} blur-3xl`}
          animate={{
            scale: [1, 1.2 + thinkingDepth * 0.3, 1],
            opacity: [0.3, 0.5 + intensity * 0.3, 0.3],
          }}
          transition={{
            duration: pulseSpeed,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      )}
      
      {/* Floating particles */}
      {particles.map((p) => (
        <motion.div
          key={p.id}
          className={`absolute rounded-full ${config.particleColor} blur-2xl`}
          style={{
            width: p.size,
            height: p.size,
            left: `${p.x}%`,
            top: `${p.y}%`,
          }}
          animate={{
            x: [0, 30, -20, 0],
            y: [0, -40, 20, 0],
            opacity: [0.2, 0.4 * intensity, 0.2],
            scale: [1, 1.1, 0.9, 1],
          }}
          transition={{
            duration: p.duration,
            repeat: Infinity,
            delay: p.delay,
            ease: 'easeInOut',
          }}
        />
      ))}
      
      {/* Intense mode: additional energy waves */}
      {moodType === 'intense' && intensity > 0.5 && (
        <>
          <motion.div
            className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-orange-500/30 to-transparent"
            animate={{ 
              scaleX: [0, 1, 0],
              opacity: [0, 0.8, 0],
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
          <motion.div
            className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-red-500/30 to-transparent"
            animate={{ 
              scaleX: [0, 1, 0],
              opacity: [0, 0.8, 0],
            }}
            transition={{
              duration: 3,
              delay: 1.5,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
        </>
      )}
      
      {/* Playful mode: sparkle effects */}
      {moodType === 'playful' && (
        <div className="absolute inset-0">
          {[...Array(5)].map((_, i) => (
            <motion.div
              key={`sparkle-${i}`}
              className="absolute w-2 h-2 bg-pink-400/60 rounded-full"
              style={{
                left: `${20 + i * 15}%`,
                top: `${30 + (i % 3) * 20}%`,
              }}
              animate={{
                scale: [0, 1.5, 0],
                opacity: [0, 1, 0],
              }}
              transition={{
                duration: 2,
                delay: i * 0.4,
                repeat: Infinity,
              }}
            />
          ))}
        </div>
      )}
      
      {/* Warm mode: soft corner glows */}
      {moodType === 'warm' && (
        <>
          <motion.div
            className="absolute -top-20 -right-20 w-96 h-96 bg-amber-500/10 rounded-full blur-3xl"
            animate={{
              scale: [1, 1.1, 1],
              opacity: [0.3, 0.5, 0.3],
            }}
            transition={{ duration: 8, repeat: Infinity }}
          />
          <motion.div
            className="absolute -bottom-20 -left-20 w-96 h-96 bg-orange-500/10 rounded-full blur-3xl"
            animate={{
              scale: [1.1, 1, 1.1],
              opacity: [0.3, 0.5, 0.3],
            }}
            transition={{ duration: 8, repeat: Infinity }}
          />
        </>
      )}
    </div>
  )
}

// Mood indicator badge for debugging/display
export function MoodIndicator({ mood, className = '' }: { mood: MoodData | null, className?: string }) {
  if (!mood) return null
  
  const config = moodConfigs[mood.mood]
  const bgClass = {
    calm: 'bg-slate-500/20 text-slate-300',
    warm: 'bg-orange-500/20 text-orange-300',
    playful: 'bg-pink-500/20 text-pink-300',
    intense: 'bg-red-500/20 text-red-300',
    curious: 'bg-cyan-500/20 text-cyan-300',
    uncertain: 'bg-gray-500/20 text-gray-300',
  }[mood.mood]
  
  return (
    <div className={`inline-flex items-center gap-2 px-2 py-1 rounded-full text-xs ${bgClass} ${className}`}>
      <span className="capitalize font-medium">{mood.mood}</span>
      <span className="opacity-60">
        {Math.round(mood.intensity * 100)}%
      </span>
      {mood.thinking_depth > 0.3 && (
        <span className="opacity-60">
          🧠 {Math.round(mood.thinking_depth * 100)}%
        </span>
      )}
    </div>
  )
}
