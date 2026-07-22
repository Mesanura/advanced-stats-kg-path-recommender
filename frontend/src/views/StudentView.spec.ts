import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import StudentView from './StudentView.vue'

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}))

const AppShellStub = defineComponent({
  setup(_, { slots }) { return () => h('div', slots.default?.()) },
})

const dashboard = {
  student_id: 1,
  student_no: '20260001',
  display_name: '学生01',
  classroom_name: '高级统计01班',
  algorithm: 'bkt',
  average_mastery: 0.62,
  dimensions: [{ dimension: 'statistics_foundation', average: 0.62 }],
  mastery_items: [{ knowledge_point_id: 1, name: '描述性统计', chapter: '统计基础', dimension: 'statistics_foundation', difficulty: 1, score: 0.62, status: 'learning', evidence_count: 3 }],
  weak_points: ['描述性统计'],
  suggested_directions: ['classification'],
  available_targets: [{ id: 2, code: 'svm', name: '支持向量机', chapter: '分类方法', dimension: 'classification', difficulty: 5, resource_url: 'https://example.com', description: null, is_active: true }],
  current_paths: [{
    id: 8, student_id: 1, target_knowledge_point_id: 2, target_name: '支持向量机', algorithm: 'bkt', state: 'current', score: 0.5,
    stage_count: 2, length_exception: 'staged_dependency', created_at: '2026-07-14T00:00:00Z',
    nodes: [
      { sequence: 1, stage: 1, knowledge_point_id: 1, name: '描述性统计', difficulty: 1, resource_url: 'https://example.com/1', prerequisites: [], status: 'recommended', mastery_score: 0.2 },
      { sequence: 2, stage: 2, knowledge_point_id: 2, name: '支持向量机', difficulty: 5, resource_url: 'https://example.com/2', prerequisites: ['描述性统计'], status: 'target', mastery_score: 0.2 },
    ],
  }],
}

describe('StudentView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.get).mockResolvedValue({ data: dashboard })
  })

  it('loads the learning profile and generates the selected target path', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: { id: 9, student_id: 1, target_knowledge_point_id: 2, target_name: '支持向量机', algorithm: 'bkt', state: 'current', score: 0.5, stage_count: 1, length_exception: null, created_at: '2026-07-14T00:00:00Z', nodes: [] },
    })
    const wrapper = mount(StudentView, {
      global: {
        plugins: [ElementPlus],
        stubs: { AppShell: AppShellStub, BaseChart: true },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('学生01的学习画像')
    expect(wrapper.text()).toContain('综合掌握度')
    expect(wrapper.text()).toContain('分类方法')
    expect(wrapper.text()).toContain('阶段 1 / 2')
    expect(wrapper.text()).toContain('阶段 2 / 2')
    expect(wrapper.findAll('.mastery-cell')).toHaveLength(1)

    wrapper.findComponent({ name: 'ElSelect' }).vm.$emit('update:modelValue', 2)
    await flushPromises()

    const generate = wrapper.findAll('button').find(button => button.text().includes('生成路径'))
    expect(generate).toBeDefined()
    await generate!.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/recommendations/me', { target_knowledge_point_id: 2 })
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('opens a path node and submits all feedback types', async () => {
    const updatedPath = {
      ...dashboard.current_paths[0],
      id: 10,
      stage_count: 1,
      length_exception: null,
      nodes: [{ ...dashboard.current_paths[0].nodes[1], sequence: 1, stage: 1, mastery_score: 0.35 }],
    }
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: { updated_path: null } })
      .mockResolvedValueOnce({ data: { updated_path: updatedPath } })
    vi.mocked(api.put).mockResolvedValue({ data: { updated_path: null } })
    const wrapper = mount(StudentView, {
      global: {
        plugins: [ElementPlus],
        stubs: { AppShell: AppShellStub, BaseChart: true, ElDrawer: { template: '<div><slot /></div>' } },
      },
    })
    await flushPromises()
    await wrapper.find('.path-node').trigger('click')
    wrapper.findComponent({ name: 'ElInputNumber' }).vm.$emit('update:modelValue', 12)
    wrapper.findComponent({ name: 'ElSlider' }).vm.$emit('update:modelValue', 80)
    wrapper.findComponent({ name: 'ElSegmented' }).vm.$emit('update:modelValue', false)
    await flushPromises()
    await wrapper.findAll('button').find(item => item.text() === '记录')!.trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(item => item.text() === '更新进度')!.trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(item => item.text() === '提交结果')!.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/students/me/behavior/visits', { knowledge_point_id: 1, duration_seconds: 720 })
    expect(api.put).toHaveBeenCalledWith('/students/me/behavior/video-progress', { knowledge_point_id: 1, progress_percent: 80 })
    expect(api.post).toHaveBeenCalledWith('/students/me/behavior/exercises', { knowledge_point_id: 1, is_correct: false })
    expect(wrapper.find('.path-section .path-node strong').text()).toBe('支持向量机')
    expect(wrapper.find('.path-section').text()).toContain('阶段 1 / 1')
    wrapper.unmount()
  })

  it.each([
    ['target_mastered', '目标已掌握，当前为单节点复习计划'],
    ['shallow_target', '目标前置层级较浅，已返回完整短路径'],
  ] as const)('shows the %s exception and the empty direction state', async (lengthException, note) => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        ...dashboard,
        suggested_directions: [],
        current_paths: [{
          ...dashboard.current_paths[0],
          stage_count: 1,
          length_exception: lengthException,
          nodes: [dashboard.current_paths[0].nodes[0]],
        }],
      },
    })
    const wrapper = mount(StudentView, {
      global: { plugins: [ElementPlus], stubs: { AppShell: AppShellStub, BaseChart: true } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain(note)
    expect(wrapper.text()).toContain('暂无专项建议')
    wrapper.unmount()
  })
})
