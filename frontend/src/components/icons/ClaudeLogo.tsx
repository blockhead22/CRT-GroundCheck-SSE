/** Claude AI logo — simplified starburst mark, renders in Claude's brand color by default (#D97757) */
export function ClaudeLogo({ size = 12, color = '#D97757', className = '' }: { size?: number; color?: string; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      aria-label="Claude"
    >
      {/* Simplified Claude starburst — 6 rounded petals radiating from center */}
      <g fill={color}>
        <ellipse cx="12" cy="5" rx="2.2" ry="4.2" />
        <ellipse cx="12" cy="19" rx="2.2" ry="4.2" />
        <ellipse cx="5" cy="8.5" rx="2.2" ry="4.2" transform="rotate(60 5 8.5)" />
        <ellipse cx="19" cy="15.5" rx="2.2" ry="4.2" transform="rotate(60 19 15.5)" />
        <ellipse cx="5" cy="15.5" rx="2.2" ry="4.2" transform="rotate(-60 5 15.5)" />
        <ellipse cx="19" cy="8.5" rx="2.2" ry="4.2" transform="rotate(-60 19 8.5)" />
      </g>
    </svg>
  )
}
