/**
 * MessageFooter — compact metadata line after each response.
 *
 * ☁ Claude · ✓ Governance · 5 memories · 3 GPT logs · 2 trust shifts
 *
 * Clicking opens the collapsed pipeline trace.
 */
export function MessageFooter({
  generationSource,
  governancePassed,
  memoryCount,
  gptLogCount,
  trustShiftCount,
  toolCount,
  timestamp,
  onExpand,
}: {
  generationSource?: string
  governancePassed?: boolean
  memoryCount?: number
  gptLogCount?: number
  trustShiftCount?: number
  toolCount?: number
  timestamp?: string
  onExpand?: () => void
}) {
  const parts: Array<{ label: string; color: string }> = []

  // Source
  if (generationSource) {
    const src = generationSource.toLowerCase()
    if (src.includes('claude')) {
      parts.push({ label: '\u2601 Claude', color: 'rgba(240,235,225,0.4)' })
    } else if (src.includes('openai') || src.includes('gpt')) {
      parts.push({ label: '\u2601 GPT', color: 'rgba(240,235,225,0.4)' })
    } else if (src === 'local') {
      parts.push({ label: '\u2601 Local', color: 'rgba(52,211,153,0.6)' })
    } else {
      parts.push({ label: `\u2601 ${generationSource}`, color: 'rgba(240,235,225,0.3)' })
    }
  }

  // Governance
  if (governancePassed != null) {
    parts.push({
      label: governancePassed ? '\u2713 Gov' : '\u2717 Gov',
      color: governancePassed ? 'rgba(52,211,153,0.5)' : 'rgba(212,112,88,0.6)',
    })
  }

  // Counts
  if (memoryCount && memoryCount > 0) {
    parts.push({ label: `${memoryCount} mem`, color: 'rgba(240,235,225,0.3)' })
  }
  if (gptLogCount && gptLogCount > 0) {
    parts.push({ label: `${gptLogCount} GPT logs`, color: 'rgba(240,235,225,0.3)' })
  }
  if (trustShiftCount && trustShiftCount > 0) {
    parts.push({ label: `${trustShiftCount} trust shift${trustShiftCount !== 1 ? 's' : ''}`, color: 'rgba(224,160,128,0.5)' })
  }
  if (toolCount && toolCount > 0) {
    parts.push({ label: `${toolCount} tool${toolCount !== 1 ? 's' : ''}`, color: 'rgba(240,235,225,0.3)' })
  }

  if (parts.length === 0 && !timestamp) return null

  return (
    <div
      className="mt-2 flex items-center gap-1.5 text-[10px] font-mono cursor-pointer transition-opacity hover:opacity-80"
      onClick={onExpand}
      role={onExpand ? 'button' : undefined}
    >
      {timestamp && (
        <span style={{ color: 'rgba(240,235,225,0.2)' }}>{timestamp}</span>
      )}
      {parts.map((part, i) => (
        <span key={i}>
          {i > 0 && <span style={{ color: 'rgba(240,235,225,0.1)' }}> {'\u00B7'} </span>}
          <span style={{ color: part.color }}>{part.label}</span>
        </span>
      ))}
    </div>
  )
}
