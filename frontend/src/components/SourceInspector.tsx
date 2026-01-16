import { useEffect, useState } from 'react'
import type { Citation } from '../types'
import * as api from '../lib/api'

type SourceInspectorProps = {
  memoryId: string | null
  threadId: string
  onClose: () => void
  onPromote?: (memoryId: string) => void
}

export function SourceInspector({
  memoryId,
  threadId,
  onClose,
  onPromote,
}: SourceInspectorProps) {
  const [citations, setCitations] = useState<Citation[]>([])
  const [loading, setLoading] = useState(false)
  const [promoting, setPromoting] = useState(false)

  useEffect(() => {
    if (!memoryId) {
      setCitations([])
      return
    }

    setLoading(true)
    api
      .getCitations({ memoryId, threadId })
      .then((result) => {
        setCitations(result.citations || [])
      })
      .catch((err) => {
        console.error('Failed to load citations:', err)
        setCitations([])
      })
      .finally(() => {
        setLoading(false)
      })
  }, [memoryId, threadId])

  if (!memoryId) {
    return null
  }

  const handlePromote = async () => {
    if (!memoryId) return

    setPromoting(true)
    try {
      const result = await api.promoteResearch({
        threadId,
        memoryId,
        userConfirmed: true,
      })

      if (result.promoted) {
        onPromote?.(memoryId)
        onClose()
      }
    } catch (err) {
      console.error('Failed to promote research:', err)
      alert('Failed to promote research to beliefs')
    } finally {
      setPromoting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Source Evidence
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="text-center text-gray-500 py-8">Loading citations...</div>
          ) : citations.length === 0 ? (
            <div className="text-center text-gray-500 py-8">No citations found</div>
          ) : (
            <div className="space-y-4">
              {citations.map((cite, idx) => (
                <div
                  key={idx}
                  className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-800"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-blue-600 dark:text-blue-300 font-semibold text-sm">
                      {idx + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <blockquote className="text-gray-700 dark:text-gray-300 mb-3 italic border-l-4 border-blue-400 pl-4">
                        "{cite.quote_text}"
                      </blockquote>
                      <div className="space-y-1 text-sm">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-gray-600 dark:text-gray-400">
                            Source:
                          </span>
                          <a
                            href={cite.source_url.startsWith('http') ? cite.source_url : undefined}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 dark:text-blue-400 hover:underline truncate"
                            title={cite.source_url}
                          >
                            {cite.source_url}
                          </a>
                        </div>
                        <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                          <span className="font-semibold">Fetched:</span>
                          <span>{new Date(cite.fetched_at).toLocaleString()}</span>
                        </div>
                        <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                          <span className="font-semibold">Confidence:</span>
                          <span>{(cite.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between gap-4">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            This research is currently in the <strong>notes lane</strong> (trust: 0.4).
            Promote to <strong>belief lane</strong> if you trust these sources.
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
            >
              Close
            </button>
            <button
              onClick={handlePromote}
              disabled={promoting}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {promoting ? (
                <>
                  <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Promoting...
                </>
              ) : (
                <>✓ Promote to Beliefs</>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
