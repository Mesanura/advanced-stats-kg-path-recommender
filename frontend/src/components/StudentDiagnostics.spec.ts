import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import StudentDiagnostics from './StudentDiagnostics.vue'

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

const student = {
  student_id: 1, student_no: '20260001', display_name: '学生01', classroom_id: 1,
  classroom_name: '高级统计01班', average_mastery: 0.4, weak_count: 8,
}
const target = { id: 2, code: 'roc_auc', name: 'ROC与AUC', chapter: '第五章', dimension: 'evaluation_ensemble', difficulty: 3, resource_url: 'https://example.com', description: null, is_active: true }
let diagnosisDirections: string[] = []

describe('StudentDiagnostics', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    vi.clearAllMocks()
    diagnosisDirections = ['classification']
    vi.mocked(api.get).mockImplementation(async url => {
      if (url === '/teacher/scope') return { data: { classes: [{ id: 1, name: '高级统计01班', grade_id: 1, grade_name: '2026级' }] } }
      if (url === '/knowledge/points') return { data: [target] }
      if (url === '/teacher/students') return { data: { items: [student], total: 1, page: 1, page_size: 100 } }
      return {
        data: {
          student_id: 1, student_no: '20260001', display_name: '学生01', algorithm: 'bkt',
          weak_points: ['回归诊断'], suggested_directions: diagnosisDirections,
          items: [{ knowledge_point_id: 1, name: '回归诊断', chapter: '第二章', dimension: 'linear_models', difficulty: 4, score: 0.2, status: 'weak', evidence_count: 2 }],
        },
      }
    })
    vi.mocked(api.post).mockResolvedValue({
      data: {
        id: 3, student_id: 1, target_knowledge_point_id: 2, target_name: 'ROC与AUC', algorithm: 'bkt', state: 'current', score: 0.4,
        stage_count: 2, length_exception: 'staged_dependency', created_at: '2026-07-15T00:00:00Z',
        nodes: [
          { sequence: 1, stage: 1, knowledge_point_id: 1, name: '回归诊断', difficulty: 4, resource_url: 'https://example.com/1', prerequisites: [], status: 'recommended', mastery_score: 0.2 },
          { sequence: 2, stage: 2, knowledge_point_id: 2, name: 'ROC与AUC', difficulty: 3, resource_url: 'https://example.com/2', prerequisites: ['回归诊断'], status: 'target', mastery_score: 0.2 },
        ],
      },
    })
  })

  it('shows suggested directions and groups a generated plan by stage', async () => {
    const wrapper = mount(StudentDiagnostics, {
      attachTo: document.body,
      global: { plugins: [ElementPlus], stubs: { ElDrawer: { template: '<div><slot /></div>' }, teleport: true } },
    })
    await flushPromises()
    wrapper.findComponent({ name: 'ElSegmented' }).vm.$emit('update:modelValue', 'rule')
    wrapper.findComponent({ name: 'ElSegmented' }).vm.$emit('change', 'rule')
    wrapper.findComponent({ name: 'ElInput' }).vm.$emit('update:modelValue', '20260001')
    wrapper.findComponent({ name: 'ElSelect' }).vm.$emit('update:modelValue', 1)
    await wrapper.findAll('button').find(item => item.text() === '详情')!.trigger('click')
    await flushPromises()
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[selects.length - 1].vm.$emit('update:modelValue', 2)
    await flushPromises()
    await wrapper.findAll('button').find(item => item.text() === '生成')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('分类方法')
    expect(wrapper.text()).toContain('完整必修依赖已拆分为 2 个阶段')
    expect(wrapper.text()).toContain('阶段 1 / 2')
    expect(wrapper.text()).toContain('阶段 2 / 2')
    expect(api.post).toHaveBeenCalledWith('/recommendations/students/1', { target_knowledge_point_id: 2 })
    wrapper.unmount()
  })

  it('shows empty suggestions and explains a shallow generated plan', async () => {
    diagnosisDirections = []
    vi.mocked(api.post).mockResolvedValue({
      data: {
        id: 4, student_id: 1, target_knowledge_point_id: 2, target_name: 'ROC与AUC', algorithm: 'bkt', state: 'current', score: 0.4,
        stage_count: 1, length_exception: 'shallow_target', created_at: '2026-07-15T00:00:00Z',
        nodes: [{ sequence: 1, stage: 1, knowledge_point_id: 2, name: 'ROC与AUC', difficulty: 3, resource_url: 'https://example.com/2', prerequisites: [], status: 'target', mastery_score: 0.2 }],
      },
    })
    const wrapper = mount(StudentDiagnostics, {
      attachTo: document.body,
      global: { plugins: [ElementPlus], stubs: { ElDrawer: { template: '<div><slot /></div>' }, teleport: true } },
    })
    await flushPromises()
    await wrapper.findAll('button').find(item => item.text() === '详情')!.trigger('click')
    await flushPromises()
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[selects.length - 1].vm.$emit('update:modelValue', 2)
    await flushPromises()
    await wrapper.findAll('button').find(item => item.text() === '生成')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('暂无专项建议')
    expect(wrapper.text()).toContain('目标前置层级较浅，已返回完整短路径')
    wrapper.unmount()
  })

  it('explains a mastered target as a single-node review stage', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: {
        id: 5, student_id: 1, target_knowledge_point_id: 2, target_name: 'ROC与AUC', algorithm: 'bkt', state: 'current', score: 1,
        stage_count: 1, length_exception: 'target_mastered', created_at: '2026-07-15T00:00:00Z',
        nodes: [{ sequence: 1, stage: 1, knowledge_point_id: 2, name: 'ROC与AUC', difficulty: 3, resource_url: 'https://example.com/2', prerequisites: [], status: 'target', mastery_score: 0.9 }],
      },
    })
    const wrapper = mount(StudentDiagnostics, {
      attachTo: document.body,
      global: { plugins: [ElementPlus], stubs: { ElDrawer: { template: '<div><slot /></div>' }, teleport: true } },
    })
    await flushPromises()
    await wrapper.findAll('button').find(item => item.text() === '详情')!.trigger('click')
    await flushPromises()
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[selects.length - 1].vm.$emit('update:modelValue', 2)
    await flushPromises()
    await wrapper.findAll('button').find(item => item.text() === '生成')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('目标已掌握，当前为单节点复习计划')
    expect(wrapper.text()).toContain('阶段 1 / 1')
    expect(wrapper.findAll('.teacher-staged-plan .compact-path span')).toHaveLength(1)
    expect(wrapper.find('.teacher-staged-plan .compact-path span').text()).toBe('ROC与AUC')
    wrapper.unmount()
  })
})
