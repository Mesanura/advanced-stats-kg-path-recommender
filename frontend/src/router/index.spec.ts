import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import router from './index'

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

describe('route authorization', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(api.get).mockRejectedValue(new Error('anonymous'))
    await router.replace('/login')
  })

  it('redirects an anonymous visitor to login', async () => {
    await router.push('/student')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('redirects a signed-in user away from another role page', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { id: 2, username: 'teacher01', display_name: '教师01', role: 'teacher' },
    })
    setActivePinia(createPinia())

    await router.push('/admin')

    expect(router.currentRoute.value.path).toBe('/teacher')
  })

  it('redirects an authenticated login visit to the role home', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { id: 3, username: 'admin', display_name: '系统管理员', role: 'admin' },
    })
    setActivePinia(createPinia())

    await router.push('/login?from=test')

    expect(router.currentRoute.value.path).toBe('/admin')
  })
})
