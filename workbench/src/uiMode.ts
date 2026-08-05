/** Product surface mode: Simple (default) vs Lab (full internals). */

export type UiMode = 'simple' | 'lab'

export const UI_MODE_STORAGE_KEY = 'aether.uiMode'

export function readUiMode(): UiMode {
  const raw = localStorage.getItem(UI_MODE_STORAGE_KEY)
  return raw === 'lab' ? 'lab' : 'simple'
}

export function writeUiMode(mode: UiMode) {
  localStorage.setItem(UI_MODE_STORAGE_KEY, mode)
}

/** Human label for a substrate slot id. */
export function humanSlotLabel(slotId: string): string {
  const raw = String(slotId || '').replace(/^user:/i, '').replaceAll('_', ' ').trim()
  if (!raw) return 'Unknown fact'
  return raw.replace(/\b\w/g, (c) => c.toUpperCase())
}

export function memoryGroupForSlot(slotId: string): 'identity' | 'favorites' | 'work' | 'other' {
  const name = String(slotId || '').replace(/^user:/i, '').toLowerCase()
  if (name === 'name' || name === 'nickname') return 'identity'
  if (name.startsWith('favorite_') && !name.includes('reason') && !name.includes('meaning')) {
    return 'favorites'
  }
  if (
    name.includes('employer')
    || name.includes('occupation')
    || name.includes('job')
    || name.includes('project')
  ) {
    return 'work'
  }
  return 'other'
}
