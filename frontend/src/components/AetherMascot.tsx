import { motion, AnimatePresence } from 'framer-motion'
import { useMemo, useState, useEffect } from 'react'
import type { MoodType } from './MoodBackground'

interface AetherMascotProps {
  mood?: MoodType
  isThinking?: boolean
  size?: number
  className?: string
  onClick?: () => void
}

// Color palettes per mood
const moodColors: Record<MoodType, { body: string; glow: string; eye: string; antenna: string }> = {
  calm:      { body: '#D4845C', glow: '#D4845C33', eye: '#F0EBE1', antenna: '#E0A080' },
  warm:      { body: '#E0A080', glow: '#E0A08044', eye: '#FFF5E6', antenna: '#F0C090' },
  playful:   { body: '#D47088', glow: '#D4708844', eye: '#FFE0E8', antenna: '#FF90B0' },
  intense:   { body: '#D47058', glow: '#D4705844', eye: '#FFD0C0', antenna: '#FF8060' },
  curious:   { body: '#80B0A0', glow: '#80B0A044', eye: '#E0FFF0', antenna: '#60D0B0' },
  uncertain: { body: '#A09080', glow: '#A0908044', eye: '#D0C8C0', antenna: '#B0A090' },
}

// Expressions: eye shapes
type Expression = 'neutral' | 'happy' | 'thinking' | 'surprised' | 'sleepy'

function getExpression(mood: MoodType, isThinking: boolean): Expression {
  if (isThinking) return 'thinking'
  switch (mood) {
    case 'playful': return 'happy'
    case 'intense': return 'surprised'
    case 'uncertain': return 'sleepy'
    default: return 'neutral'
  }
}

// Eye component
function Eye({ x, expression, color, size }: { x: number; expression: Expression; color: string; size: number }) {
  const s = size / 80 // scale factor (base design is 80px)
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

export function AetherMascot({
  mood = 'calm',
  isThinking = false,
  size = 80,
  className = '',
  onClick,
}: AetherMascotProps) {
  const colors = moodColors[mood]
  const expression = getExpression(mood, isThinking)
  const s = size / 80

  // Blink state
  const [blinking, setBlinking] = useState(false)
  useEffect(() => {
    const blink = () => {
      setBlinking(true)
      setTimeout(() => setBlinking(false), 150)
    }
    const interval = setInterval(blink, 3000 + Math.random() * 2000)
    return () => clearInterval(interval)
  }, [])

  // Floating particles when thinking
  const particles = useMemo(() => {
    if (!isThinking) return []
    return Array.from({ length: 3 }, (_, i) => ({
      id: i,
      x: 20 + i * 20,
      delay: i * 0.5,
    }))
  }, [isThinking])

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
        animate={{
          opacity: isThinking ? [0.4, 0.8, 0.4] : [0.2, 0.4, 0.2],
          scale: isThinking ? [1, 1.2, 1] : [1, 1.05, 1],
        }}
        transition={{ duration: isThinking ? 1.5 : 3, repeat: Infinity, ease: 'easeInOut' }}
      />

      <svg
        width={size}
        height={size + 12 * s}
        viewBox={`0 0 ${80 * s} ${92 * s}`}
        fill="none"
      >
        {/* Antenna */}
        <motion.g
          animate={
            isThinking
              ? { rotate: [-5, 5, -5] }
              : mood === 'playful'
              ? { rotate: [-8, 8, -8] }
              : { rotate: [-2, 2, -2] }
          }
          transition={{ duration: isThinking ? 0.8 : 2, repeat: Infinity, ease: 'easeInOut' }}
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
            animate={
              isThinking
                ? { opacity: [1, 0.3, 1], scale: [1, 1.3, 1] }
                : { opacity: [0.6, 1, 0.6] }
            }
            transition={{ duration: isThinking ? 0.6 : 2, repeat: Infinity }}
          />
        </motion.g>

        {/* Head — rounded rectangle */}
        <motion.rect
          x={12 * s} y={16 * s}
          width={56 * s} height={34 * s}
          rx={10 * s}
          fill={colors.body}
          animate={
            isThinking
              ? { y: [16 * s, 14 * s, 16 * s] }
              : { y: [16 * s, 15 * s, 16 * s] }
          }
          transition={{
            duration: isThinking ? 1 : 2.5,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />

        {/* Face visor — darker inset */}
        <motion.rect
          x={18 * s} y={22 * s}
          width={44 * s} height={22 * s}
          rx={6 * s}
          fill="#141210"
          opacity={0.6}
          animate={
            isThinking
              ? { y: [22 * s, 20 * s, 22 * s] }
              : { y: [22 * s, 21 * s, 22 * s] }
          }
          transition={{
            duration: isThinking ? 1 : 2.5,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />

        {/* Eyes */}
        <motion.g
          animate={
            isThinking
              ? { y: [0, -2 * s, 0] }
              : { y: [0, -1 * s, 0] }
          }
          transition={{
            duration: isThinking ? 1 : 2.5,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        >
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
            isThinking
              ? { y: [52 * s, 50 * s, 52 * s] }
              : { y: [52 * s, 51 * s, 52 * s] }
          }
          transition={{
            duration: isThinking ? 1 : 2.5,
            delay: 0.1,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />

        {/* Body detail — screen/chest plate */}
        <motion.rect
          x={30 * s} y={56 * s}
          width={20 * s} height={10 * s}
          rx={3 * s}
          fill="#141210"
          opacity={0.4}
          animate={
            isThinking
              ? { y: [56 * s, 54 * s, 56 * s] }
              : { y: [56 * s, 55 * s, 56 * s] }
          }
          transition={{
            duration: isThinking ? 1 : 2.5,
            delay: 0.1,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />

        {/* Chest indicator light */}
        <motion.circle
          cx={40 * s} cy={61 * s} r={2 * s}
          fill={colors.antenna}
          animate={{
            opacity: isThinking ? [0.4, 1, 0.4] : [0.3, 0.7, 0.3],
          }}
          transition={{
            duration: isThinking ? 0.8 : 3,
            repeat: Infinity,
          }}
        />

        {/* Arms */}
        <motion.rect
          x={14 * s} y={54 * s}
          width={6 * s} height={14 * s}
          rx={3 * s}
          fill={colors.body}
          opacity={0.7}
          animate={
            isThinking
              ? { rotate: [-5, 5, -5], y: [54 * s, 52 * s, 54 * s] }
              : mood === 'playful'
              ? { rotate: [-10, 10, -10] }
              : { rotate: [-2, 2, -2] }
          }
          transition={{
            duration: isThinking ? 0.8 : 2,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          style={{ transformOrigin: `${17 * s}px ${54 * s}px` }}
        />
        <motion.rect
          x={60 * s} y={54 * s}
          width={6 * s} height={14 * s}
          rx={3 * s}
          fill={colors.body}
          opacity={0.7}
          animate={
            isThinking
              ? { rotate: [5, -5, 5], y: [54 * s, 52 * s, 54 * s] }
              : mood === 'playful'
              ? { rotate: [10, -10, 10] }
              : { rotate: [2, -2, 2] }
          }
          transition={{
            duration: isThinking ? 0.8 : 2,
            delay: 0.2,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          style={{ transformOrigin: `${63 * s}px ${54 * s}px` }}
        />

        {/* Feet */}
        <motion.g
          animate={
            isThinking
              ? { y: [0, -2 * s, 0] }
              : { y: [0, -1 * s, 0] }
          }
          transition={{
            duration: isThinking ? 1 : 2.5,
            delay: 0.2,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        >
          <rect
            x={26 * s} y={73 * s}
            width={10 * s} height={6 * s}
            rx={3 * s}
            fill={colors.body}
            opacity={0.7}
          />
          <rect
            x={44 * s} y={73 * s}
            width={10 * s} height={6 * s}
            rx={3 * s}
            fill={colors.body}
            opacity={0.7}
          />
        </motion.g>

        {/* Thinking particles */}
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

// Small inline version for message bubbles or status bars
export function AetherMascotMini({
  mood = 'calm',
  isThinking = false,
  className = '',
}: {
  mood?: MoodType
  isThinking?: boolean
  className?: string
}) {
  return (
    <AetherMascot
      mood={mood}
      isThinking={isThinking}
      size={32}
      className={className}
    />
  )
}
