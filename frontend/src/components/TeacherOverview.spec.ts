import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import TeacherOverview from './TeacherOverview.vue'

vi.mock('../api/client', () => ({ api: { get: vi.fn() } }))

const ChartStub = defineComponent({
  props: { option: { type: Object, required: true } },
  setup(props) {
    return () => h('pre', { class: 'chart-option' }, JSON.stringify(props.option))
  },
})

describe('TeacherOverview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('maps overview dimensions and weak points into chart options', async () => {
    vi.mocked(api.get).mockImplementation(async (url) => {
      if (url === '/teacher/scope') {
        return { data: { classes: [{ id: 1, name: '高级统计01班', grade_id: 1, grade_name: '2026级' }] } }
      }
      return {
        data: {
          algorithm: 'bkt', student_count: 25, average_mastery: 0.61,
          dimensions: [
            { dimension: 'statistics_foundation', average: 0.7 },
            { dimension: 'linear_models', average: 0.52 },
          ],
          knowledge_points: [],
          weak_top5: [
            { knowledge_point_id: 1, name: '回归诊断', average: 0.31, minimum: 0.1, maximum: 0.6, distribution: { unknown: 1, weak: 12, learning: 8, mastered: 4 } },
          ],
          attention_students: [],
        },
      }
    })

    const wrapper = mount(TeacherOverview, {
      global: { plugins: [ElementPlus], stubs: { BaseChart: ChartStub } },
    })
    await flushPromises()

    expect(api.get).toHaveBeenCalledWith('/teacher/overview', {
      params: { class_id: 1, algorithm: 'bkt' },
    })
    const charts = wrapper.findAll('.chart-option')
    expect(charts).toHaveLength(2)
    expect(charts[0].text()).toContain('统计基础')
    expect(charts[0].text()).toContain('[0.7,0.52]')
    expect(charts[1].text()).toContain('回归诊断')
    expect(charts[1].text()).toContain('0.31')
  })
})
