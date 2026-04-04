/**
 * Dictionary — Word frequency lookup + user vocabulary for predictive text.
 *
 * Loads a static word-frequency JSON (top ~3500 words) and maintains a
 * per-user vocabulary built from their sent messages in localStorage.
 */

// Lazy-loaded word frequency map: word → frequency rank (lower = more common)
let _freqMap: Record<string, number> | null = null
let _freqLoading = false
let _freqReady = false

// Sorted array of words for prefix search (built once from freqMap)
let _sortedWords: string[] = []

const USER_DICT_KEY = 'aether_user_dictionary'
const USER_DICT_MAX = 2000

// ── Load static dictionary ───────────────────────────────────────────

async function ensureLoaded(): Promise<void> {
  if (_freqReady) return
  if (_freqLoading) {
    // Wait for existing load
    await new Promise<void>((resolve) => {
      const check = setInterval(() => {
        if (_freqReady) { clearInterval(check); resolve() }
      }, 50)
    })
    return
  }
  _freqLoading = true
  try {
    const mod = await import('../data/word-freq.json')
    _freqMap = mod.default || mod
    // Pre-sort words by frequency (most common first)
    _sortedWords = Object.keys(_freqMap!).sort(
      (a, b) => (_freqMap![a] ?? 99999) - (_freqMap![b] ?? 99999)
    )
    _freqReady = true
  } catch (e) {
    console.warn('[dictionary] Failed to load word-freq.json:', e)
    _freqMap = {}
    _sortedWords = []
    _freqReady = true
  }
  _freqLoading = false
}

// ── User dictionary (localStorage) ──────────────────────────────────

function getUserDict(): Record<string, number> {
  try {
    const raw = localStorage.getItem(USER_DICT_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function saveUserDict(dict: Record<string, number>) {
  try {
    // Prune to max size — keep most frequently used
    const entries = Object.entries(dict)
    if (entries.length > USER_DICT_MAX) {
      entries.sort((a, b) => b[1] - a[1])
      dict = Object.fromEntries(entries.slice(0, USER_DICT_MAX))
    }
    localStorage.setItem(USER_DICT_KEY, JSON.stringify(dict))
  } catch { /* quota exceeded, ignore */ }
}

/**
 * Learn new words from a sent message.
 * Tokenizes, filters short/numeric words, increments frequency.
 */
export function learnFromMessage(text: string) {
  const dict = getUserDict()
  const words = text
    .toLowerCase()
    .split(/[\s,.!?;:'"()\[\]{}<>\/\\|@#$%^&*+=~`]+/)
    .filter((w) => w.length >= 3 && !/^\d+$/.test(w))

  for (const word of words) {
    dict[word] = (dict[word] || 0) + 1
  }
  saveUserDict(dict)
}

// ── Prefix search ───────────────────────────────────────────────────

/**
 * Find the best completion for a partial word.
 * Returns the full word (not just the suffix) or null.
 *
 * Priority: user dictionary (by usage count) > static dictionary (by frequency rank).
 * Only returns words longer than the prefix.
 */
export async function findCompletion(prefix: string): Promise<string | null> {
  if (prefix.length < 2) return null
  await ensureLoaded()

  const lowerPrefix = prefix.toLowerCase()

  // 1. Check user dictionary first (most relevant)
  const userDict = getUserDict()
  let bestUser: string | null = null
  let bestUserCount = 0
  for (const [word, count] of Object.entries(userDict)) {
    if (
      word.startsWith(lowerPrefix) &&
      word.length > lowerPrefix.length &&
      count > bestUserCount
    ) {
      bestUser = word
      bestUserCount = count
    }
  }

  // Strong user preference (used 3+ times) — prefer it
  if (bestUser && bestUserCount >= 3) return bestUser

  // 2. Check static dictionary (sorted by frequency)
  for (const word of _sortedWords) {
    if (word.startsWith(lowerPrefix) && word.length > lowerPrefix.length) {
      // If user dict had a weaker match, prefer static for common words
      if (bestUser && bestUserCount >= 1) {
        // User typed it before — prefer user's word
        return bestUser
      }
      return word
    }
  }

  // 3. Fall back to any user dict match
  return bestUser
}

/**
 * Get the suffix to display as ghost text.
 * e.g., prefix="hel" → completion="hello" → suffix="lo"
 */
export async function getGhostSuffix(
  text: string,
  cursorPos: number,
): Promise<string | null> {
  // Extract the partial word at cursor
  const before = text.slice(0, cursorPos)
  const match = before.match(/[a-zA-Z]+$/)
  if (!match || match[0].length < 2) return null

  const prefix = match[0]
  const completion = await findCompletion(prefix)
  if (!completion) return null

  // Return only the suffix (part after what's already typed)
  return completion.slice(prefix.length)
}

// Pre-load dictionary on import
ensureLoaded()
