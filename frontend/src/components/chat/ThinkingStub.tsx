import { motion } from 'framer-motion'

/**
 * Inline thinking stub — shows orchestrator reasoning between tool calls.
 *
 * Renders as muted, slightly indented text with a thought icon.
 * Visible during streaming, collapses into PipelineCollapse after done.
 */
export function ThinkingStub({ content, streaming }: { content: string; streaming?: boolean }) {
  if (!content.trim()) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: 3 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.12 }}
      className="my-1.5 flex items-start gap-2 text-[12px] leading-relaxed"
    >
      <span
        className="flex-shrink-0 mt-0.5"
        style={{ color: 'rgba(224,160,128,0.5)' }}
      >
        {'\uD83D\uDCAD'}
      </span>
      <span
        className="italic"
        style={{ color: 'rgba(240,235,225,0.4)' }}
      >
        {content}
        {streaming && (
          <span
            className="inline-block w-[2px] h-[0.85em] align-middle ml-0.5 animate-[blink_1s_step-end_infinite]"
            style={{ background: 'rgba(224,160,128,0.4)' }}
          />
        )}
      </span>
    </motion.div>
  )
}
