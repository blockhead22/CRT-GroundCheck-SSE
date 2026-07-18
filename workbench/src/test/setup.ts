import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

Object.defineProperty(window, 'aetherDesktop', {
  configurable: true,
  value: {
    apiBase: 'http://127.0.0.1:8765',
    setExpanded: vi.fn().mockResolvedValue({}),
    setFloating: vi.fn().mockResolvedValue(false),
    setAlwaysOnTop: vi.fn().mockResolvedValue(true),
    minimize: vi.fn(),
    close: vi.fn(),
    onSidecarStatus: vi.fn(() => () => undefined),
  },
})

Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
  configurable: true,
  value: vi.fn(),
})
