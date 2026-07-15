import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import AdminView from './AdminView.vue'

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

const AppShellStub = defineComponent({ setup(_, { slots }) { return () => h('div', slots.default?.()) } })

describe('AdminView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.get).mockImplementation(async url => {
      if (url === '/admin/users') return { data: { items: [{ id: 4, username: '20260001', display_name: '学生01', role: 'student', is_active: true, classroom_name: '高级统计01班', classroom_ids: [] }], total: 1, page: 1, page_size: 100 } }
      return { data: [] }
    })
    vi.mocked(api.post).mockResolvedValue({ data: {} })
    vi.mocked(api.patch).mockResolvedValue({ data: {} })
  })

  it('exposes shared knowledge and recommendation governance tabs', async () => {
    const wrapper = mount(AdminView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          AppShell: AppShellStub,
          KnowledgeManagement: { template: '<div>共享知识治理</div>' },
          RecommendationSettings: { template: '<div>共享推荐策略</div>' },
        },
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('用户与班级')

    const tabs = wrapper.findComponent({ name: 'ElSegmented' })
    tabs.vm.$emit('update:modelValue', 'knowledge')
    await flushPromises()
    expect(wrapper.text()).toContain('共享知识治理')
    tabs.vm.$emit('update:modelValue', 'settings')
    await flushPromises()
    expect(wrapper.text()).toContain('共享推荐策略')
  })

  it('runs account, password, status and structure operations', async () => {
    const wrapper = mount(AdminView, {
      global: {
        plugins: [ElementPlus],
        stubs: { AppShell: AppShellStub, KnowledgeManagement: true, RecommendationSettings: true, teleport: true },
      },
    })
    await flushPromises()
    const setup = (wrapper.vm as any).$.setupState
    Object.assign(setup.form, { username: 'new_student', display_name: '新学生', role: 'student', student_no: '20269999', classroom_id: 1 })
    await setup.createUser()
    expect(api.post).toHaveBeenCalledWith('/admin/users', expect.objectContaining({ role: 'student', student_no: '20269999' }))

    const actionButtons = wrapper.findAll('button')
    await actionButtons.find(item => item.text() === '停用')!.trigger('click')
    expect(api.patch).toHaveBeenCalledWith('/admin/users/4', { is_active: false })
    await actionButtons.find(item => item.text() === '重置密码')!.trigger('click')
    expect(api.post).toHaveBeenCalledWith('/admin/users/4/reset-password', { password: 'Student@123456' })

    Object.assign(setup.structure, { grade_name: '2027级', class_name: '高级统计03班', grade_id: 2 })
    await setup.createStructure()
    expect(api.post).toHaveBeenCalledWith('/admin/grades', { name: '2027级' })
    expect(api.post).toHaveBeenCalledWith('/admin/classes', { name: '高级统计03班', grade_id: 2 })
    wrapper.unmount()
  })
})
