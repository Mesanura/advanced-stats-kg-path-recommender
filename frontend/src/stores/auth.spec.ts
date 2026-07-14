import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import { useAuthStore } from './auth'

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

const student = { id: 1, username: '20260001', display_name: '学生01', role: 'student' as const }

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads the current user and derives authenticated state', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: student })
    const auth = useAuthStore()

    await auth.loadCurrentUser()

    expect(api.get).toHaveBeenCalledWith('/auth/me')
    expect(auth.user).toEqual(student)
    expect(auth.initialized).toBe(true)
    expect(auth.isAuthenticated).toBe(true)
  })

  it('treats a failed current-user request as an anonymous session', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('unauthorized'))
    const auth = useAuthStore()

    await auth.loadCurrentUser()

    expect(auth.user).toBeNull()
    expect(auth.initialized).toBe(true)
  })

  it('logs in and logs out while keeping the local session synchronized', async () => {
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: { user: student } })
      .mockResolvedValueOnce({ data: { message: 'ok' } })
    const auth = useAuthStore()

    await expect(auth.login('20260001', 'Student@123456')).resolves.toBe('student')
    expect(auth.user).toEqual(student)
    await auth.logout()
    expect(api.post).toHaveBeenLastCalledWith('/auth/logout')
    expect(auth.user).toBeNull()
  })
})
