import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { submitChatFeedback } from '../../lib/api'
import type { ChatMessage, MessageRating } from '../../types'

type RatingCategory = 'hallucination' | 'wrong_fact' | 'tone' | 'other'

const CATEGORIES: { id: RatingCategory; label: string }[] = [
  { id: 'hallucination', label: 'Made something up' },
  { id: 'wrong_fact', label: 'Wrong fact' },
  { id: 'tone', label: 'Tone/style' },
  { id: 'other', label: 'Other' },
]

function extractCitedMemoryIds(msg: ChatMessage): string[] {
  const ids = new Set<string>()
  const meta = msg.crt
  if (!meta) return []
  for (const m of meta.prompt_memories ?? []) {
    if (m.memory_id) ids.add(m.memory_id)
  }
  for (const m of meta.xray?.memories_used ?? []) {
    // xray memories don't carry an id directly, but prompt_memories covers them
  }
  for (const m of meta.retrieved_memories ?? []) {
    if (m.memory_id) ids.add(m.memory_id)
  }
  return Array.from(ids)
}

export function MessageRatingBar({
  msg,
  threadId,
  onRated,
}: {
  msg: ChatMessage
  threadId?: string
  onRated?: (rating: MessageRating, category?: string) => void
}) {
  const interactionId = msg.crt?.interaction_id
  const existingRating = msg.rating

  const [submitting, setSubmitting] = useState(false)
  const [localRating, setLocalRating] = useState<MessageRating | null>(existingRating ?? null)
  const [showCategories, setShowCategories] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<RatingCategory | null>(
    (msg.ratingCategory as RatingCategory) ?? null,
  )
  const [showMemories, setShowMemories] = useState(false)
  const [affectedMemories, setAffectedMemories] = useState<
    Array<{ memory_id: string; old_trust: number; new_trust: number }>
  >([])

  const memoryIds = extractCitedMemoryIds(msg)
  const memCount = memoryIds.length

  async function submitRating(thumbsUp: boolean, category?: RatingCategory) {
    if (!interactionId || submitting) return
    setSubmitting(true)
    try {
      const res = await submitChatFeedback({
        interaction_id: interactionId,
        thread_id: threadId ?? 'default',
        thumbs_up: thumbsUp,
        category: category ?? null,
        memory_ids_cited: memoryIds,
      })
      setLocalRating(thumbsUp ? 'up' : 'down')
      setSelectedCategory(category ?? null)
      if (res.memories_affected?.length) {
        setAffectedMemories(res.memories_affected)
      }
      onRated?.(thumbsUp ? 'up' : 'down', category)
      if (!thumbsUp && !category) {
        setShowCategories(true)
      } else {
        setShowCategories(false)
      }
    } catch (e) {
      console.error('[MessageRatingBar] submitRating failed', e)
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCategory(cat: RatingCategory) {
    await submitRating(false, cat)
  }

  const isUp = localRating === 'up'
  const isDown = localRating === 'down'

  return (
    <div className="mt-2 flex flex-col gap-1.5">
      {/* Rating buttons row */}
      <div className="flex items-center gap-2">
        {/* Thumbs up */}
        <button
          disabled={submitting || isUp}
          onClick={() => submitRating(true)}
          title="Good response"
          className={[
            'flex h-6 w-6 items-center justify-center rounded-full text-[13px] transition-all duration-150',
            isUp
              ? 'opacity-100'
              : 'opacity-0 group-hover:opacity-60 hover:!opacity-100',
            submitting ? 'cursor-wait' : 'cursor-pointer',
          ].join(' ')}
          style={
            isUp
              ? { background: 'rgba(52,211,153,0.18)', color: '#34d399' }
              : { background: 'rgba(240,235,225,0.05)', color: 'rgba(240,235,225,0.35)' }
          }
        >
          ↑
        </button>

        {/* Thumbs down */}
        <button
          disabled={submitting || isDown}
          onClick={() => submitRating(false)}
          title="Bad response"
          className={[
            'flex h-6 w-6 items-center justify-center rounded-full text-[13px] transition-all duration-150',
            isDown
              ? 'opacity-100'
              : 'opacity-0 group-hover:opacity-60 hover:!opacity-100',
            submitting ? 'cursor-wait' : 'cursor-pointer',
          ].join(' ')}
          style={
            isDown
              ? { background: 'rgba(251,113,133,0.18)', color: '#fb7185' }
              : { background: 'rgba(240,235,225,0.05)', color: 'rgba(240,235,225,0.35)' }
          }
        >
          ↓
        </button>

        {/* Memory count link */}
        {memCount > 0 && (
          <button
            onClick={() => setShowMemories((v) => !v)}
            className={[
              'text-[10px] transition-all duration-150',
              'opacity-0 group-hover:opacity-40 hover:!opacity-70',
              showMemories ? '!opacity-70' : '',
            ].join(' ')}
            style={{ color: 'rgba(240,235,225,0.5)' }}
          >
            {memCount} {memCount === 1 ? 'memory' : 'memories'} cited
          </button>
        )}

        {/* Rated indicator */}
        {isDown && selectedCategory && (
          <span className="text-[10px]" style={{ color: 'rgba(251,113,133,0.6)' }}>
            flagged · {selectedCategory.replace('_', ' ')}
          </span>
        )}
        {isUp && (
          <span
            className="text-[10px] opacity-0 group-hover:opacity-100 transition-opacity"
            style={{ color: 'rgba(52,211,153,0.5)' }}
          >
            rated helpful
          </span>
        )}
      </div>

      {/* Category picker — shown after thumbs down */}
      <AnimatePresence>
        {showCategories && isDown && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
              <span className="text-[10px]" style={{ color: 'rgba(240,235,225,0.3)' }}>
                What was wrong?
              </span>
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  disabled={submitting}
                  onClick={() => handleCategory(cat.id)}
                  className="rounded-full px-2 py-0.5 text-[10px] transition-all duration-100 hover:opacity-90"
                  style={
                    selectedCategory === cat.id
                      ? { background: 'rgba(251,113,133,0.2)', color: '#fb7185', border: '1px solid rgba(251,113,133,0.3)' }
                      : { background: 'rgba(240,235,225,0.05)', color: 'rgba(240,235,225,0.4)', border: '1px solid rgba(240,235,225,0.08)' }
                  }
                >
                  {cat.label}
                </button>
              ))}
              <button
                onClick={() => setShowCategories(false)}
                className="text-[10px] transition-opacity hover:opacity-70"
                style={{ color: 'rgba(240,235,225,0.2)' }}
              >
                skip
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Memory trust panel — expandable */}
      <AnimatePresence>
        {showMemories && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div
              className="mt-0.5 rounded-xl p-2.5 text-[10px]"
              style={{ border: '1px solid rgba(240,235,225,0.06)', background: 'rgba(0,0,0,0.2)' }}
            >
              <div className="mb-1.5 font-semibold uppercase tracking-wide" style={{ color: 'rgba(240,235,225,0.25)' }}>
                Cited memories
              </div>
              <div className="space-y-1.5">
                {(msg.crt?.prompt_memories ?? []).filter((m) => m.memory_id).map((m) => {
                  const affected = affectedMemories.find((a) => a.memory_id === m.memory_id)
                  return (
                    <div key={m.memory_id} className="flex items-start gap-2">
                      <span className="font-mono flex-shrink-0" style={{ color: '#E0A080' }}>
                        T:{(m.trust ?? 0).toFixed(2)}
                        {affected && (
                          <span style={{ color: '#fb7185' }}>
                            {' '}→{affected.new_trust.toFixed(2)}
                          </span>
                        )}
                      </span>
                      <span className="line-clamp-1" style={{ color: 'rgba(240,235,225,0.4)' }}>
                        {m.text}
                      </span>
                    </div>
                  )
                })}
                {memCount > 0 && (msg.crt?.prompt_memories ?? []).filter((m) => m.memory_id).length === 0 && (
                  <div style={{ color: 'rgba(240,235,225,0.3)' }}>
                    {memCount} memory ID(s) cited (details not available)
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
