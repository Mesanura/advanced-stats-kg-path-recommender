import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { DependencyGraph } from '../types/student'
import DependencyDag from './DependencyDag.vue'

const mocks = vi.hoisted(() => ({
  chart: {
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    on: vi.fn(),
  },
  init: vi.fn(),
  use: vi.fn(),
}))

vi.mock('echarts/core', () => ({
  init: mocks.init,
  use: mocks.use,
}))
vi.mock('echarts/charts', () => ({ GraphChart: {} }))
vi.mock('echarts/components', () => ({ TooltipComponent: {} }))
vi.mock('echarts/features', () => ({ LabelLayout: {} }))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))

const graph: DependencyGraph = {
  nodes: [
    { knowledge_point_id: 1, name: '统计基础', difficulty: 1, resource_url: 'https://example.com/1', prerequisites: [], is_active: true, mastery_score: 0.8, mastery_status: 'mastered', in_recommended_path: false, is_target: false },
    { knowledge_point_id: 2, name: '概率论', difficulty: 2, resource_url: 'https://example.com/2', prerequisites: [], is_active: false, mastery_score: 0.6, mastery_status: 'learning', in_recommended_path: false, is_target: false },
    { knowledge_point_id: 3, name: '线性模型', difficulty: 3, resource_url: 'https://example.com/3', prerequisites: ['统计基础'], is_active: true, mastery_score: 0.4, mastery_status: 'weak', in_recommended_path: true, is_target: false },
    { knowledge_point_id: 4, name: '目标知识点', difficulty: 5, resource_url: 'https://example.com/4', prerequisites: ['概率论', '线性模型'], is_active: true, mastery_score: 0.2, mastery_status: 'unknown', in_recommended_path: true, is_target: true },
  ],
  edges: [
    { prerequisite_id: 1, knowledge_point_id: 3 },
    { prerequisite_id: 2, knowledge_point_id: 4 },
    { prerequisite_id: 3, knowledge_point_id: 4 },
    { prerequisite_id: 99, knowledge_point_id: 4 },
  ],
}

describe('DependencyDag', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.init.mockReturnValue(mocks.chart)
  })

  it('renders a layered dependency graph and exposes graph controls', async () => {
    const wrapper = mount(DependencyDag, {
      props: { data: graph },
      global: {
        plugins: [ElementPlus],
        stubs: { ElTooltip: { template: '<span><slot /></span>' } },
      },
    })
    await nextTick()

    expect(mocks.init).toHaveBeenCalledOnce()
    const option = mocks.chart.setOption.mock.calls[0][0] as {
      tooltip: { formatter: (params: object) => string }
      series: Array<{ data: Array<Record<string, any>>; links: object[] }>
    }
    const nodes = option.series[0].data
    expect(nodes).toHaveLength(4)
    expect(option.series[0].links).toHaveLength(4)
    expect(new Set(nodes.map(node => node.x)).size).toBe(3)
    expect(nodes.find(node => node.id === '2')?.itemStyle.borderType).toBe('dashed')
    expect(nodes.find(node => node.id === '3')?.itemStyle.borderWidth).toBe(3)
    expect(nodes.find(node => node.id === '4')?.itemStyle.borderColor).toBe('#c9362b')
    expect(option.tooltip.formatter({ dataType: 'edge', data: {} })).toBe('前置依赖')
    expect(option.tooltip.formatter({ dataType: 'node', data: nodes[1] })).toContain('已停用')
    expect(option.tooltip.formatter({ dataType: 'node', data: nodes[0] })).not.toContain('已停用')

    await wrapper.get('[aria-label="放大依赖图"]').trigger('click')
    await wrapper.get('[aria-label="缩小依赖图"]').trigger('click')
    await wrapper.get('[aria-label="适应依赖图画布"]').trigger('click')
    expect(mocks.chart.setOption).toHaveBeenCalledWith({ series: [{ zoom: 1.08 }] })
    expect(mocks.chart.setOption).toHaveBeenCalledWith({ series: [{ zoom: 0.9 }] })

    const click = mocks.chart.on.mock.calls.find(call => call[0] === 'click')?.[1]
    click({ dataType: 'edge', data: {} })
    expect(wrapper.emitted('selectNode')).toBeUndefined()
    click({ dataType: 'node', data: nodes[2] })
    expect(wrapper.emitted('selectNode')?.[0][0]).toMatchObject({ knowledge_point_id: 3 })

    window.dispatchEvent(new Event('resize'))
    expect(mocks.chart.resize).toHaveBeenCalledOnce()

    await wrapper.setProps({
      data: { nodes: [graph.nodes[3]], edges: [] },
    })
    await nextTick()
    const singleNodeOption = mocks.chart.setOption.mock.calls.at(-1)?.[0] as {
      series: Array<{ data: Array<{ x: number }> }>
    }
    expect(singleNodeOption.series[0].data[0].x).toBe(130)
    expect(wrapper.get('.dependency-dag-canvas').attributes('style')).toContain('--dependency-dag-width: 260px')

    wrapper.unmount()
    expect(mocks.chart.dispose).toHaveBeenCalledOnce()
  })
})
