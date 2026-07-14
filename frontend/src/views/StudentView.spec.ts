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
  suggested_directions: [],
  available_targets: [{ id: 2, code: 'svm', name: '支持向量机', chapter: '分类方法', dimension: 'classification', difficulty: 5, resource_url: 'https://example.com', description: null, is_active: true }],
  current_paths: [],
}

describe('StudentView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.get).mockResolvedValue({ data: dashboard })
  })

  it('loads the learning profile and generates the selected target path', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: { id: 9, student_id: 1, target_knowledge_point_id: 2, target_name: '支持向量机', algorithm: 'bkt', state: 'current', score: 0.5, length_exception: null, created_at: '2026-07-14T00:00:00Z', nodes: [] },
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
    expect(wrapper.findAll('.mastery-cell')).toHaveLength(1)

    const generate = wrapper.findAll('button').find(button => button.text().includes('生成路径'))
    expect(generate).toBeDefined()
    await generate!.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/recommendations/me', { target_knowledge_point_id: 2 })
    expect(api.get).toHaveBeenCalledTimes(2)
  })
})
