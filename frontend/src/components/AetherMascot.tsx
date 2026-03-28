import { motion, AnimatePresence } from 'framer-motion'
import { useMemo, useState, useEffect } from 'react'
import type { MoodType } from './MoodBackground'

// ── Animation types ────────────────────────────────────────────
export type MascotAnimation =
  | 'idle'
  | 'greeting'    // wave right arm on new conversation
  | 'thinking'    // antenna pulse, particles, eyes up
  | 'curious'     // lean/tilt, looking around
  | 'working'     // arms busy, chest light rapid
  | 'nod'         // quick head bob
  | 'celebrate'   // bounce + arms up
  | 'headshake'   // horizontal shake
  | 'surprised'   // jump back + wide eyes
  | 'nervous'     // jitter
  | 'sleepy'      // droop, half-closed eyes
  | 'alert'       // antenna flash red
  | 'loading'     // pulse/spin

type Expression = 'neutral' | 'happy' | 'thinking' | 'surprised' | 'sleepy'

interface AetherMascotProps {
  mood?: MoodType
  animation?: MascotAnimation
  /** @deprecated Use animation='thinking' instead */
  isThinking?: boolean
  size?: number
  className?: string
  onClick?: () => void
}

// ── Color palettes per mood ────────────────────────────────────
const moodColors: Record<MoodType, { body: string; glow: string; eye: string; antenna: string }> = {
  calm:      { body: '#D4845C', glow: '#D4845C33', eye: '#F0EBE1', antenna: '#E0A080' },
  warm:      { body: '#E0A080', glow: '#E0A08044', eye: '#FFF5E6', antenna: '#F0C090' },
  playful:   { body: '#D47088', glow: '#D4708844', eye: '#FFE0E8', antenna: '#FF90B0' },
  intense:   { body: '#D47058', glow: '#D4705844', eye: '#FFD0C0', antenna: '#FF8060' },
  curious:   { body: '#80B0A0', glow: '#80B0A044', eye: '#E0FFF0', antenna: '#60D0B0' },
  uncertain: { body: '#A09080', glow: '#A0908044', eye: '#D0C8C0', antenna: '#B0A090' },
}

// ── Expression from animation state ────────────────────────────
function getExpression(anim: MascotAnimation, mood: MoodType): Expression {
  switch (anim) {
    case 'thinking':
    case 'curious':
    case 'working':
      return 'thinking'
    case 'celebrate':
    case 'greeting':
      return 'happy'
    case 'surprised':
    case 'alert':
      return 'surprised'
    case 'sleepy':
      return 'sleepy'
    case 'nervous':
    case 'headshake':
      return 'neutral'
    default:
      // idle/nod/loading — derive from mood
      switch (mood) {
        case 'playful': return 'happy'
        case 'intense': return 'surprised'
        case 'uncertain': return 'sleepy'
        default: return 'neutral'
      }
  }
}

// ── Animation configs ──────────────────────────────────────────
// Each animation defines motion properties for: head, body, arms, antenna, glow

function headMotion(anim: MascotAnimation, s: number) {
  const base = 16 * s
  switch (anim) {
    case 'thinking':
      return { animate: { y: [base, base - 2 * s, base] }, transition: { duration: 1, repeat: Infinity, ease: 'easeInOut' as const } }
    case 'nod':
      return { animate: { y: [base, base + 3 * s, base - 1 * s, base] }, transition: { duration: 0.5, ease: 'easeInOut' as const } }
    case 'headshake':
      return { animate: { x: [0, -3 * s, 3 * s, -2 * s, 2 * s, 0] }, transition: { duration: 0.6, ease: 'easeInOut' as const } }
    case 'celebrate':
      return { animate: { y: [base, base - 8 * s, base] }, transition: { duration: 0.6, repeat: 2, ease: 'easeOut' as const } }
    case 'surprised':
      return { animate: { y: [base, base - 5 * s, base] }, transition: { duration: 0.4, ease: 'easeOut' as const } }
    case 'curious':
      return { animate: { rotate: [-3, 3, -3], y: [base, base - 1 * s, base] }, transition: { duration: 2.5, repeat: Infinity, ease: 'easeInOut' as const } }
    case 'nervous':
      return { animate: { x: [0, -1.5 * s, 1.5 * s, -1 * s, 1 * s, 0] }, transition: { duration: 0.3, repeat: Infinity, ease: 'linear' as const } }
    case 'sleepy':
      return { animate: { y: [base, base + 2 * s, base + 2 * s, base] }, transition: { duration: 4, repeat: Infinity, ease: 'easeInOut' as const } }
    case 'loading':
      return { animate: { scale: [1, 1.05, 1] }, transition: { duration: 1.2, repeat: Infinity, ease: 'easeInOut' as const } }
    case 'working':
      return { animate: { y: [base, base - 1 * s, base] }, transition: { duration: 0.8, repeat: Infinity, ease: 'easeInOut' as const } }
    case 'greeting':
      return { animate: { y: [base, base - 2 * s, base] }, transition: { duration: 1.5, repeat: Infinity, ease: 'easeInOut' as const } }
    default: // idle
      return { animate: { y: [base, base - 1 * s, base] }, transition: { duration: 2.5, repeat: Infinity, ease: 'easeInOut' as const } }
  }
}

function leftArmMotion(anim: MascotAnimation, s: number) {
  const origin = `${17 * s}px ${54 * s}px`
  switch (anim) {
    case 'celebrate':
      return { animate: { rotate: [0, -70, -60, -70, 0] }, transition: { duration: 1.2, ease: 'easeInOut' as const }, style: { transformOrigin: origin } }
    case 'working':
      return { animate: { rotate: [-8, 8, -8] }, transition: { duration: 0.5, repeat: Infinity, ease: 'easeInOut' as const }, style: { transformOrigin: origin } }
    case 'greeting':
      // Left arm stays still during right wave
      return { animate: { rotate: [0, 2, 0] }, transition: { duration: 2, repeat: Infinity, ease: 'easeInOut' as const }, style: { transformOrigin: origin } }
    case 'thinking':
      return { animate: { rotate: [-5, 5, -5] }, transition: { duration: 0.8, repeat: Infinity, ease: 'easeInOut' as const }, style: { transformOrigin: origin } }
    case 'nervous':
      return { animate: { rotate: [-4, 4, -4] }, transition: { duration: 0.2, repeat: Infinity, ease: 'linear' as const }, style: { transformOrigin: origin } }
    default:
      return { animate: { rotate: [-2, 2, -2] }, transition: { duration: 2, repeat: Infinity, ease: 'easeInOut' as const }, style: { transformOrigin: origin } }
  }
}

function rightArmMotion(anim: MascotAnimation, s: number) {
  const origin = `${63 * s}px ${54 * s}px`
  switch (anim) {
    case 'greeting':
      return { animate: { rotate: [-70, -40, -70] }, transition: { duration: 0.4, repeat: 4, ease: 'easeInOut' as const }, style: { transformOrigin: origin } }
    case 'celebrate':
      return { animate: { rotate: [0, 70, 60, 70, 0] }, transition: { duration: 1.2, ease: 'easeInOut' as const }, style: { transformOrigin: origin } }
    case 'working':
      return { animate: { rotate: [8, -8, 8] }, transition: { duration: 0.5, repeat: Infinity, delay: 0.15, ease: 'easeInOut' as const }, style: { transformOrigin: origin } }
    case 'thinking':
      return { animate: { rotate: [5, -5, 5] }, transition: { duration: 0.8, delay: 0.2, repeat: Infinity, ease: 'easeInOut' as const }, style: { transformOrigin: origin } }
    case 'nervous':
      return { animate: { rotate: [4, -4, 4] }, transition: { duration: 0.2, delay: 0.1, repeat: Infinity, ease: 'linear' as const }, style: { transformOrigin: origin } }
    default:
      return { animate: { rotate: [2, -2, 2] }, transition: { duration: 2, delay: 0.2, repeat: Infinity, ease: 'easeInOut' as const }, style: { transformOrigin: origin } }
  }
}

function antennaMotion(anim: MascotAnimation, s: number) {
  switch (anim) {
    case 'thinking':
      return { rotate: { animate: { rotate: [-5, 5, -5] }, transition: { duration: 0.8, repeat: Infinity } }, ball: { animate: { opacity: [1, 0.3, 1], scale: [1, 1.3, 1] }, transition: { duration: 0.6, repeat: Infinity } } }
    case 'alert':
      return { rotate: { animate: { rotate: [-8, 8, -8] }, transition: { duration: 0.3, repeat: Infinity } }, ball: { animate: { opacity: [1, 0, 1] }, transition: { duration: 0.25, repeat: Infinity } } }
    case 'curious':
      return { rotate: { animate: { rotate: [-10, 10, -10] }, transition: { duration: 1.5, repeat: Infinity, ease: 'easeInOut' as const } }, ball: { animate: { opacity: [0.6, 1, 0.6] }, transition: { duration: 1.5, repeat: Infinity } } }
    case 'celebrate':
      return { rotate: { animate: { rotate: [-15, 15, -15] }, transition: { duration: 0.3, repeat: 4 } }, ball: { animate: { opacity: [0.8, 1, 0.8], scale: [1, 1.4, 1] }, transition: { duration: 0.3, repeat: 4 } } }
    case 'nervous':
      return { rotate: { animate: { rotate: [-3, 3, -3] }, transition: { duration: 0.15, repeat: Infinity } }, ball: { animate: { opacity: [0.5, 0.8, 0.5] }, transition: { duration: 0.3, repeat: Infinity } } }
    case 'sleepy':
      return { rotate: { animate: { rotate: [-1, 1, -1] }, transition: { duration: 4, repeat: Infinity } }, ball: { animate: { opacity: [0.2, 0.4, 0.2] }, transition: { duration: 4, repeat: Infinity } } }
    case 'loading':
      return { rotate: { animate: { rotate: [0, 360] }, transition: { duration: 1.5, repeat: Infinity, ease: 'linear' as const } }, ball: { animate: { opacity: [0.3, 1, 0.3] }, transition: { duration: 0.8, repeat: Infinity } } }
    case 'working':
      return { rotate: { animate: { rotate: [-3, 3, -3] }, transition: { duration: 0.6, repeat: Infinity } }, ball: { animate: { opacity: [0.5, 1, 0.5] }, transition: { duration: 0.4, repeat: Infinity } } }
    default:
      return { rotate: { animate: { rotate: [-2, 2, -2] }, transition: { duration: 2, repeat: Infinity, ease: 'easeInOut' as const } }, ball: { animate: { opacity: [0.6, 1, 0.6] }, transition: { duration: 2, repeat: Infinity } } }
  }
}

function glowConfig(anim: MascotAnimation) {
  switch (anim) {
    case 'thinking':
    case 'working':
      return { opacity: [0.4, 0.8, 0.4], scale: [1, 1.2, 1], duration: 1.5 }
    case 'celebrate':
      return { opacity: [0.3, 0.9, 0.3], scale: [1, 1.4, 1], duration: 0.6 }
    case 'alert':
      return { opacity: [0.2, 0.9, 0.2], scale: [1, 1.3, 1], duration: 0.3 }
    case 'nervous':
      return { opacity: [0.3, 0.5, 0.3], scale: [1, 1.1, 1], duration: 0.2 }
    case 'sleepy':
      return { opacity: [0.1, 0.2, 0.1], scale: [1, 1.02, 1], duration: 4 }
    default:
      return { opacity: [0.2, 0.4, 0.2], scale: [1, 1.05, 1], duration: 3 }
  }
}

function showParticles(anim: MascotAnimation): boolean {
  return anim === 'thinking' || anim === 'curious' || anim === 'celebrate'
}

// ── Eye component ──────────────────────────────────────────────
function Eye({ x, expression, color, size }: { x: number; expression: Expression; color: string; size: number }) {
  const s = size / 80
  const eyeW = 6 * s
  const eyeH = expression === 'happy' ? 2 * s : expression === 'sleepy' ? 3 * s : 6 * s

  return (
    <motion.rect
      x={x - eyeW / 2}
      y={30 * s - eyeH / 2}
      width={eyeW}
      height={eyeH}
      rx={expression === 'happy' || expression === 'sleepy' ? eyeH / 2 : 1.5 * s}
      fill={color}
      animate={
        expression === 'thinking'
          ? { y: [30 * s - eyeH / 2, 28 * s - eyeH / 2, 30 * s - eyeH / 2] }
          : {}
      }
      transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
    />
  )
}

// ── Main component ─────────────────────────────────────────────
export function AetherMascot({
  mood = 'calm',
  animation: animProp,
  isThinking = false,
  size = 80,
  className = '',
  onClick,
}: AetherMascotProps) {
  // Resolve animation: explicit prop > isThinking legacy > idle
  const anim: MascotAnimation = animProp ?? (isThinking ? 'thinking' : 'idle')

  const colors = anim === 'alert'
    ? { ...moodColors[mood], antenna: '#FF4040', glow: '#FF404044' }
    : moodColors[mood]
  const expression = getExpression(anim, mood)
  const s = size / 80

  // Blink (skip during sleepy/happy — eyes already narrowed)
  const [blinking, setBlinking] = useState(false)
  useEffect(() => {
    if (anim === 'sleepy') return
    const blink = () => {
      setBlinking(true)
      setTimeout(() => setBlinking(false), 150)
    }
    const interval = setInterval(blink, 3000 + Math.random() * 2000)
    return () => clearInterval(interval)
  }, [anim])

  // Particles
  const particles = useMemo(() => {
    if (!showParticles(anim)) return []
    return Array.from({ length: 3 }, (_, i) => ({
      id: i,
      x: 20 + i * 20,
      delay: i * 0.5,
    }))
  }, [anim])

  // Motion configs
  const head = headMotion(anim, s)
  const armL = leftArmMotion(anim, s)
  const armR = rightArmMotion(anim, s)
  const ant = antennaMotion(anim, s)
  const glow = glowConfig(anim)

  return (
    <motion.div
      className={`relative inline-flex items-center justify-center cursor-pointer select-none ${className}`}
      style={{ width: size, height: size + 12 * s }}
      onClick={onClick}
      whileHover={{ scale: 1.08 }}
      whileTap={{ scale: 0.95 }}
    >
      {/* Glow under the robot */}
      <motion.div
        className="absolute rounded-full blur-xl"
        style={{
          width: size * 0.7,
          height: size * 0.3,
          bottom: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          background: colors.glow,
        }}
        animate={{ opacity: glow.opacity, scale: glow.scale }}
        transition={{ duration: glow.duration, repeat: Infinity, ease: 'easeInOut' }}
      />

      <svg
        width={size}
        height={size + 12 * s}
        viewBox={`0 0 ${80 * s} ${92 * s}`}
        fill="none"
      >
        {/* Antenna */}
        <motion.g
          animate={ant.rotate.animate}
          transition={ant.rotate.transition}
          style={{ transformOrigin: `${40 * s}px ${16 * s}px` }}
        >
          <line
            x1={40 * s} y1={16 * s}
            x2={40 * s} y2={6 * s}
            stroke={colors.antenna}
            strokeWidth={2 * s}
            strokeLinecap="round"
          />
          <motion.circle
            cx={40 * s} cy={4 * s} r={3 * s}
            fill={colors.antenna}
            animate={ant.ball.animate}
            transition={ant.ball.transition}
          />
        </motion.g>

        {/* Head + face group — moves together */}
        <motion.g
          animate={head.animate}
          transition={head.transition}
        >
          {/* Head */}
          <rect
            x={12 * s} y={16 * s}
            width={56 * s} height={34 * s}
            rx={10 * s}
            fill={colors.body}
          />

          {/* Face visor */}
          <rect
            x={18 * s} y={22 * s}
            width={44 * s} height={22 * s}
            rx={6 * s}
            fill="#141210"
            opacity={0.6}
          />

          {/* Eyes */}
          {blinking && expression !== 'happy' ? (
            <>
              <rect x={28 * s} y={30 * s} width={6 * s} height={1.5 * s} rx={0.75 * s} fill={colors.eye} />
              <rect x={46 * s} y={30 * s} width={6 * s} height={1.5 * s} rx={0.75 * s} fill={colors.eye} />
            </>
          ) : (
            <>
              <Eye x={31 * s} expression={expression} color={colors.eye} size={size} />
              <Eye x={49 * s} expression={expression} color={colors.eye} size={size} />
            </>
          )}

          {/* Mouth */}
          {expression === 'happy' ? (
            <path
              d={`M${35 * s},${37 * s} Q${40 * s},${42 * s} ${45 * s},${37 * s}`}
              stroke={colors.eye}
              strokeWidth={1.5 * s}
              strokeLinecap="round"
              fill="none"
            />
          ) : expression === 'surprised' ? (
            <circle cx={40 * s} cy={38 * s} r={2.5 * s} fill={colors.eye} opacity={0.8} />
          ) : (
            <rect
              x={36 * s} y={37.5 * s}
              width={8 * s} height={1.5 * s}
              rx={0.75 * s}
              fill={colors.eye}
              opacity={0.6}
            />
          )}
        </motion.g>

        {/* Body */}
        <motion.rect
          x={22 * s} y={52 * s}
          width={36 * s} height={20 * s}
          rx={6 * s}
          fill={colors.body}
          opacity={0.85}
          animate={
            anim === 'celebrate'
              ? { y: [52 * s, 44 * s, 52 * s] }
              : { y: [52 * s, 51 * s, 52 * s] }
          }
          transition={{
            duration: anim === 'celebrate' ? 0.6 : 2.5,
            repeat: anim === 'celebrate' ? 2 : Infinity,
            delay: 0.1,
            ease: 'easeInOut',
          }}
        />

        {/* Chest screen */}
        <rect
          x={30 * s} y={56 * s}
          width={20 * s} height={10 * s}
          rx={3 * s}
          fill="#141210"
          opacity={0.4}
        />

        {/* Chest indicator light */}
        <motion.circle
          cx={40 * s} cy={61 * s} r={2 * s}
          fill={anim === 'alert' ? '#FF4040' : colors.antenna}
          animate={{
            opacity: anim === 'working' ? [0.4, 1, 0.4]
              : anim === 'alert' ? [1, 0, 1]
              : anim === 'loading' ? [0.3, 1, 0.3]
              : [0.3, 0.7, 0.3],
          }}
          transition={{
            duration: anim === 'working' ? 0.4
              : anim === 'alert' ? 0.25
              : anim === 'loading' ? 0.6
              : 3,
            repeat: Infinity,
          }}
        />

        {/* Left arm */}
        <motion.rect
          x={14 * s} y={54 * s}
          width={6 * s} height={14 * s}
          rx={3 * s}
          fill={colors.body}
          opacity={0.7}
          animate={armL.animate}
          transition={armL.transition}
          style={armL.style}
        />

        {/* Right arm */}
        <motion.rect
          x={60 * s} y={54 * s}
          width={6 * s} height={14 * s}
          rx={3 * s}
          fill={colors.body}
          opacity={0.7}
          animate={armR.animate}
          transition={armR.transition}
          style={armR.style}
        />

        {/* Feet */}
        <motion.g
          animate={
            anim === 'celebrate'
              ? { y: [0, -6 * s, 0] }
              : anim === 'nervous'
              ? { y: [0, -1 * s, 0, -1 * s, 0] }
              : { y: [0, -1 * s, 0] }
          }
          transition={{
            duration: anim === 'celebrate' ? 0.6 : anim === 'nervous' ? 0.3 : 2.5,
            repeat: anim === 'celebrate' ? 2 : Infinity,
            delay: 0.2,
            ease: 'easeInOut',
          }}
        >
          <rect x={26 * s} y={73 * s} width={10 * s} height={6 * s} rx={3 * s} fill={colors.body} opacity={0.7} />
          <rect x={44 * s} y={73 * s} width={10 * s} height={6 * s} rx={3 * s} fill={colors.body} opacity={0.7} />
        </motion.g>

        {/* Thinking/curious particles */}
        <AnimatePresence>
          {particles.map((p) => (
            <motion.circle
              key={p.id}
              cx={p.x * s}
              r={2 * s}
              fill={colors.antenna}
              initial={{ cy: 12 * s, opacity: 0 }}
              animate={{ cy: -10 * s, opacity: [0, 0.8, 0] }}
              exit={{ opacity: 0 }}
              transition={{
                duration: 1.5,
                delay: p.delay,
                repeat: Infinity,
                ease: 'easeOut',
              }}
            />
          ))}
        </AnimatePresence>
      </svg>
    </motion.div>
  )
}

// Small inline version
export function AetherMascotMini({
  mood = 'calm',
  animation,
  isThinking = false,
  className = '',
}: {
  mood?: MoodType
  animation?: MascotAnimation
  isThinking?: boolean
  className?: string
}) {
  return (
    <AetherMascot
      mood={mood}
      animation={animation}
      isThinking={isThinking}
      size={32}
      className={className}
    />
  )
}
