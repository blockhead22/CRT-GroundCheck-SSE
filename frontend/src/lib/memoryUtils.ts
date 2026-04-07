/**
 * Memory display utilities — clean raw memory text for UI rendering.
 *
 * Strips internal metadata ([SYSTEM NOTE], FACT: prefixes, self_model tags)
 * so users see clean text in PCA graph labels, memory cards, and trust bars.
 */

/** Strip [SYSTEM NOTE — self-correction...] blocks, internal prefixes, and injection patterns from memory text */
export function cleanMemoryText(raw: string): string {
  return raw
    .replace(/,?\s*\[SYSTEM NOTE[\s\S]*/i, '')       // strip ", [SYSTEM NOTE" and everything after (handles truncated/unclosed brackets)
    .replace(/\[SYSTEM NOTE[^\]]*\]/gi, '')           // strip complete [SYSTEM NOTE ...] blocks
    .replace(/^\s*FACT:\s*/i, '')                     // strip leading "FACT: "
    .replace(/\[self_model:\w+\]\s*/gi, '')           // strip [self_model:slot]
    // Injection pattern cleanup — matches backend sanitize_memory_for_prompt()
    .replace(/(?:^|\n)\s*(?:System|Assistant|Human)\s*:/gi, '')  // role markers
    .replace(/\[?\/?INST\]?/gi, '')                              // [INST] / [/INST]
    .replace(/<<?\/?\s*SYS>>/gi, '')                              // <<SYS>>
    .replace(/<\|\/?\s*(?:system|user|assistant|im_start|im_end)\s*\|>/gi, '') // <|system|>
    .replace(/(?:^|[.!?\n])\s*(?:ignore\s+(?:above|previous|all|prior)\s+(?:instructions?|prompts?|rules?))/gi, '')
    .replace(/(?:^|[.!?\n])\s*(?:you\s+are\s+now\s+(?:a|an|the)\b)/gi, '')
    .replace(/(?:^|[.!?\n])\s*(?:always\s+respond\s+(?:with|as|in)\b)/gi, '')
    .replace(/(?:^|[.!?\n])\s*(?:forget\s+(?:all|your|the)\s+(?:previous|prior|above)\b)/gi, '')
    .replace(/(?:^|[.!?\n])\s*(?:from\s+now\s+on\s*,?\s+you\b)/gi, '')
    .replace(/(?:^|[.!?\n])\s*(?:new\s+instructions?\s*:)/gi, '')
    .replace(/\n+/g, ' ')                             // collapse newlines
    .replace(/\s{2,}/g, ' ')                          // collapse double spaces from removals
    .trim()
}
