import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

Object.defineProperty(window, 'aetherDesktop', {
  configurable: true,
  value: {
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
