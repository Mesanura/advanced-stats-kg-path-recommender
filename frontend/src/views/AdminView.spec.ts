import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import type { Classroom, ManagedUser } from '../types/admin'
import AdminView from './AdminView.vue'

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const AppShellStub = defineComponent({
  setup(_, { slots }) {
    return () => h('div', slots.default?.())
  },
})

const classrooms: Classroom[] = [
  { id: 1, grade_id: 1, grade_name: '2026级', name: '高级统计01班' },
  { id: 2, grade_id: 1, grade_name: '2026级', name: '高级统计02班' },
]
const student: ManagedUser = {
  id: 4,
  username: '20260001',
  display_name: '学生01',
  role: 'student',
  is_active: true,
  student_no: '20260001',
  classroom_id: 1,
  classroom_name: '高级统计01班',
  classroom_ids: [],
  classrooms: [],
}
const teacher: ManagedUser = {
  id: 5,
  username: 'teacher01',
  display_name: '教师01',
  role: 'teacher',
  is_active: true,
  student_no: null,
  classroom_id: null,
  classroom_name: null,
  classroom_ids: [1, 2],
  classrooms,
}

function mountView() {
  return mount(AdminView, {
    global: {
      plugins: [ElementPlus],
      stubs: {
        AppShell: AppShellStub,
        KnowledgeManagement: true,
        RecommendationSettings: true,
        teleport: true,
      },
    },
  })
}

describe('AdminView', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    vi.clearAllMocks()
    Object.assign(student, { display_name: '学生01', is_active: true })
    Object.assign(teacher, { display_name: '教师01', is_active: true, classroom_ids: [1, 2], classrooms })
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    vi.mocked(api.get).mockImplementation(async url => {
      if (url === '/admin/users') {
        return { data: { items: [student, teacher], total: 2, page: 1, page_size: 100 } }
      }
      if (url === '/admin/users/4') return { data: student }
      if (url === '/admin/users/5') return { data: teacher }
      if (url === '/admin/grades') return { data: [{ id: 1, name: '2026级' }] }
      if (url === '/admin/classes') return { data: classrooms }
      return { data: [] }
    })
    vi.mocked(api.post).mockResolvedValue({ data: {} })
    vi.mocked(api.patch).mockImplementation(async (url, payload) => {
      const original = url.endsWith('/5') ? teacher : student
      const changes = payload as Record<string, unknown>
      const classroomIds = changes.classroom_ids as number[] | undefined
      return {
        data: {
          ...original,
          ...changes,
          classrooms: classroomIds
            ? classrooms.filter(item => classroomIds.includes(item.id))
            : original.classrooms,
        },
      }
    })
    vi.mocked(api.delete).mockResolvedValue({ data: { message: '用户已删除' } })
  })

  it('exposes shared knowledge and recommendation governance tabs', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('用户与班级')

    const tabs = wrapper.findComponent({ name: 'ElSegmented' })
    tabs.vm.$emit('update:modelValue', 'knowledge')
    await flushPromises()
    tabs.vm.$emit('update:modelValue', 'settings')
    await flushPromises()
    wrapper.unmount()
  })

  it('shows concrete teacher classes and runs account operations', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('2026级 · 高级统计01班')
    expect(wrapper.text()).toContain('2026级 · 高级统计02班')

    const setup = (wrapper.vm as any).$.setupState
    Object.assign(setup.form, {
      username: 'new_student',
      display_name: '新学生',
      role: 'student',
      student_no: '20269999',
      classroom_id: 1,
    })
    await setup.createUser()
    expect(api.post).toHaveBeenCalledWith('/admin/users', expect.objectContaining({
      role: 'student', student_no: '20269999',
    }))

    await setup.toggleUser(student)
    expect(api.patch).toHaveBeenCalledWith('/admin/users/4', { is_active: false })
    await setup.resetPassword(student)
    expect(api.post).toHaveBeenCalledWith('/admin/users/4/reset-password', {
      password: 'Student@123456',
    })

    Object.assign(setup.structure, {
      grade_name: '2027级', class_name: '高级统计03班', grade_id: 2,
    })
    await setup.createStructure()
    expect(api.post).toHaveBeenCalledWith('/admin/grades', { name: '2027级' })
    expect(api.post).toHaveBeenCalledWith('/admin/classes', {
      name: '高级统计03班', grade_id: 2,
    })
    wrapper.unmount()
  })

  it('loads the detail drawer, edits assignments and deletes the user', async () => {
    const wrapper = mountView()
    await flushPromises()
    const detailButton = wrapper.findAll('button').find(item => item.text() === '详情')
    await detailButton!.trigger('click')
    await flushPromises()
    expect(api.get).toHaveBeenCalledWith('/admin/users/4')

    const setup = (wrapper.vm as any).$.setupState
    await setup.openUser(teacher)
    setup.startEditing()
    Object.assign(setup.editForm, {
      display_name: '教师甲',
      classroom_ids: [2],
    })
    await setup.saveUser()
    expect(api.patch).toHaveBeenCalledWith('/admin/users/5', {
      username: 'teacher01',
      display_name: '教师甲',
      is_active: true,
      classroom_ids: [2],
    })

    await setup.removeUser()
    expect(ElMessageBox.confirm).toHaveBeenCalledWith(
      expect.stringContaining('教师甲'),
      '确认删除用户',
      expect.objectContaining({ confirmButtonText: '删除' }),
    )
    expect(api.delete).toHaveBeenCalledWith('/admin/users/5')
    wrapper.unmount()
  })
})
