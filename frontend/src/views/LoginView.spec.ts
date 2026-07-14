import { mount } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import LoginView from './LoginView.vue'

const replace = vi.fn()
vi.mock('vue-router', async (importOriginal) => {
  const original = await importOriginal<typeof import('vue-router')>()
  return { ...original, useRouter: () => ({ replace }) }
})
vi.mock('../api/client', () => ({ api: { post: vi.fn() } }))

describe('LoginView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('validates required credentials', async () => {
    const warning = vi.spyOn(ElMessage, 'warning').mockImplementation(() => undefined as never)
    const wrapper = mount(LoginView, { global: { plugins: [createPinia(), ElementPlus] } })

    await wrapper.get('.login-button').trigger('click')

    expect(warning).toHaveBeenCalledWith('请输入用户名和密码')
    expect(api.post).not.toHaveBeenCalled()
  })

  it('submits credentials and enters the matching role page', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: { user: { id: 1, username: '20260001', display_name: '学生01', role: 'student' } },
    })
    const wrapper = mount(LoginView, { global: { plugins: [createPinia(), ElementPlus] } })
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('20260001')
    await inputs[1].setValue('Student@123456')

    await wrapper.get('.login-button').trigger('click')
    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith('/student'))
  })

  it('reports invalid credentials without navigating', async () => {
    vi.mocked(api.post).mockRejectedValue(new Error('invalid credentials'))
    const error = vi.spyOn(ElMessage, 'error').mockImplementation(() => undefined as never)
    const wrapper = mount(LoginView, { global: { plugins: [createPinia(), ElementPlus] } })
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('unknown')
    await inputs[1].setValue('bad-password')

    await wrapper.get('.login-button').trigger('click')
    await vi.waitFor(() => expect(error).toHaveBeenCalledWith('用户名或密码错误'))
    expect(replace).not.toHaveBeenCalled()
  })
})
