/**
 * usePredictiveText — Ghost text autocomplete for textarea.
 *
 * Returns a suggestion suffix based on the current partial word at cursor.
 * Debounced to avoid excessive dictionary lookups.
 *
 * Usage:
 *   const { suggestion, accept, dismiss } = usePredictiveText(text, cursorPos)
 *   // suggestion = "ello" when user typed "h" and "hello" is predicted
 *   // accept() → inserts the suggestion into text
 *   // dismiss() → clears the suggestion
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { getGhostSuffix } from '../lib/dictionary'

const DEBOUNCE_MS = 120

export function usePredictiveText(
  text: string,
  cursorPos: number,
  enabled: boolean = true,
) {
  const [suggestion, setSuggestion] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastTextRef = useRef(text)

  useEffect(() => {
    if (!enabled) {
      setSuggestion(null)
      return
    }

    // Only predict when cursor is at the end of text (no mid-text predictions)
    if (cursorPos !== text.length) {
      setSuggestion(null)
      return
    }

    // Clear on empty or if text got shorter (deletion)
    if (!text.trim() || text.length < lastTextRef.current.length) {
      setSuggestion(null)
      lastTextRef.current = text
      return
    }
    lastTextRef.current = text

    // Debounce lookup
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      try {
        const suffix = await getGhostSuffix(text, cursorPos)
        setSuggestion(suffix)
      } catch {
        setSuggestion(null)
      }
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [text, cursorPos, enabled])

  const dismiss = useCallback(() => setSuggestion(null), [])

  return { suggestion, dismiss }
}
