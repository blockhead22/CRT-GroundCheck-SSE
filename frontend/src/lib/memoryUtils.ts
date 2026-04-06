/**
 * Memory display utilities — clean raw memory text for UI rendering.
 *
 * Strips internal metadata ([SYSTEM NOTE], FACT: prefixes, self_model tags)
 * so users see clean text in PCA graph labels, memory cards, and trust bars.
 */

/** Strip [SYSTEM NOTE — self-correction...] blocks and internal prefixes from memory text */
export function cleanMemoryText(raw: string): string {
  return raw
    .replace(/\[SYSTEM NOTE[^\]]*\][^]*/i, '')      // strip [SYSTEM NOTE ...] and everything after
    .replace(/^\s*FACT:\s*/i, '')                     // strip leading "FACT: "
    .replace(/\[self_model:\w+\]\s*/i, '')            // strip [self_model:slot]
    .replace(/\n+/g, ' ')                             // collapse newlines
    .trim()
}
