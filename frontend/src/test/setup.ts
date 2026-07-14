import { config } from '@vue/test-utils'
import { vi } from 'vitest'

class ResizeObserverMock {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

Object.defineProperty(window, 'ResizeObserver', { value: ResizeObserverMock })
Object.defineProperty(window, 'matchMedia', {
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

config.global.stubs = {
  transition: false,
  'transition-group': false,
}
