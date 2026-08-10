import { beforeEach, describe, expect, test } from 'vitest'
import {
  UI_MODE_SIMPLE_DEFAULT_KEY,
  UI_MODE_STORAGE_KEY,
  readUiMode,
  writeUiMode,
} from './uiMode'

describe('uiMode product default', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  test('forces Simple once even when Lab was stuck in storage', () => {
    localStorage.setItem(UI_MODE_STORAGE_KEY, 'lab')
    expect(readUiMode()).toBe('simple')
    expect(localStorage.getItem(UI_MODE_STORAGE_KEY)).toBe('simple')
    expect(localStorage.getItem(UI_MODE_SIMPLE_DEFAULT_KEY)).toBe('1')
  })

  test('keeps Lab after intentional write following migration', () => {
    expect(readUiMode()).toBe('simple')
    writeUiMode('lab')
    expect(readUiMode()).toBe('lab')
  })
})
