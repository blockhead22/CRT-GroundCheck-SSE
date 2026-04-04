import type { Citation } from '../types'

type CitationViewerProps = {
  citations: Citation[]
  onCitationClick?: (citation: Citation) => void
}

export function CitationViewer({ citations, onCitationClick }: CitationViewerProps) {
  if (!citations || citations.length === 0) {
    return null
  }

  return (
    <div className="mt-3 space-y-2">
      <div className="text-xs font-semibold text-gray-600 dark:text-gray-400">
        Sources ({citations.length})
      </div>
      {citations.map((cite, idx) => (
        <div
          key={idx}
          className="rounded border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-3 text-sm cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          onClick={() => onCitationClick?.(cite)}
        >
          <div className="text-gray-700 dark:text-gray-300 mb-2 italic">
            "{cite.quote_text.substring(0, 150)}
            {cite.quote_text.length > 150 ? '...' : ''}"
          </div>
          <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
            <div className="flex items-center gap-2">
              <span className="font-mono bg-gray-200 dark:bg-gray-700 px-2 py-0.5 rounded">
                [{idx + 1}]
              </span>
              <span className="truncate max-w-md" title={cite.source_url}>
                {cite.source_url.split('/').pop() || cite.source_url}
              </span>
            </div>
            <span className="text-gray-400">
              {new Date(cite.fetched_at).toLocaleString()}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
