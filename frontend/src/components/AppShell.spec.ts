import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'
import AppShell from './AppShell.vue'

const replace = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ replace }) }))
vi.mock('../api/client', () => ({ api: { post: vi.fn() } }))

describe('AppShell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('shows the current identity and logs out', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { message: 'ok' } })
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'teacher01', display_name: '教师01', role: 'teacher' }
    const wrapper = mount(AppShell, {
      props: { section: '学情概览' },
      slots: { default: '<p>页面内容</p>' },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.text()).toContain('教师端')
    expect(wrapper.text()).toContain('教师01')
    await wrapper.get('.sidebar-logout').trigger('click')
    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith('/login'))
    expect(auth.user).toBeNull()
  })
})
