import { useState } from 'react'

/** Extract the filename from a full path */
function basename(path: string): string {
  const parts = path.replace(/\\/g, '/').split('/')
  return parts[parts.length - 1] || path
}

/** Detect if a path looks like a directory (no file extension) */
function isDir(path: string): boolean {
  const name = basename(path)
  return !name.includes('.')
}

export function FilePill({
  path,
  type,
  size = 'sm',
}: {
  path: string
  type?: 'file' | 'dir'
  size?: 'sm' | 'md'
}) {
  const [copied, setCopied] = useState(false)
  const resolvedType = type ?? (isDir(path) ? 'dir' : 'file')
  const name = basename(path)
  const isSm = size === 'sm'

  function handleClick(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    navigator.clipboard.writeText(path).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <button
      onClick={handleClick}
      title={copied ? 'Copied!' : path}
      className={`
        inline-flex items-center gap-1 rounded-full border font-mono
        transition-all cursor-pointer select-none
        hover:border-[rgba(212,132,92,0.4)] hover:bg-[rgba(212,132,92,0.08)]
        active:scale-[0.97]
        ${isSm ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-[12px]'}
      `}
      style={{
        borderColor: copied ? 'rgba(80,200,120,0.4)' : 'rgba(240,235,225,0.1)',
        background: copied ? 'rgba(80,200,120,0.08)' : 'rgba(240,235,225,0.04)',
        color: copied ? 'rgba(80,200,120,0.9)' : 'rgba(240,235,225,0.7)',
      }}
    >
      {/* Icon */}
      <svg
        width={isSm ? 11 : 13}
        height={isSm ? 11 : 13}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ opacity: 0.6, flexShrink: 0 }}
      >
        {resolvedType === 'dir' ? (
          <>
            <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
          </>
        ) : (
          <>
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </>
        )}
      </svg>

      {/* Filename */}
      <span style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {name}
      </span>

      {/* Copy indicator */}
      {copied && (
        <svg
          width={10}
          height={10}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ color: 'rgba(80,200,120,0.9)', flexShrink: 0 }}
        >
          <polyline points="20 6 9 17 4 12" />
        </svg>
      )}
    </button>
  )
}
