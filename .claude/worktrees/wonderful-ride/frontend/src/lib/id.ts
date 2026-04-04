export function newId(prefix = 'id'): string {
  const anyCrypto = globalThis.crypto as Crypto | undefined
  if (anyCrypto?.randomUUID) return `${prefix}_${anyCrypto.randomUUID()}`
  return `${prefix}_${Math.random().toString(16).slice(2)}_${Date.now().toString(16)}`
}
