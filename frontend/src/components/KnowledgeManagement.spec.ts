import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import KnowledgeManagement from './KnowledgeManagement.vue'

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const points = [
  { id: 1, code: 'descriptive_statistics', name: '描述性统计', chapter: '第一章 统计基础', dimension: 'statistics_foundation', difficulty: 1, resource_url: 'https://example.com/1', description: null, is_active: true },
  { id: 2, code: 'probability_distributions', name: '概率分布', chapter: '第一章 统计基础', dimension: 'statistics_foundation', difficulty: 2, resource_url: 'https://example.com/2', description: null, is_active: true },
]
const relation = { knowledge_point_id: 2, prerequisite_id: 1, knowledge_point_name: '概率分布', prerequisite_name: '描述性统计' }

describe('KnowledgeManagement', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    vi.clearAllMocks()
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    vi.mocked(api.get).mockImplementation(async url => url === '/knowledge/graph'
      ? { data: { nodes: points, edges: [relation] } }
      : { data: points })
    vi.mocked(api.post).mockResolvedValue({ data: {} })
    vi.mocked(api.put).mockResolvedValue({ data: relation })
    vi.mocked(api.patch).mockResolvedValue({ data: points[0] })
    vi.mocked(api.delete).mockResolvedValue({ data: { message: 'ok' } })
  })

  it('filters points through the API and completes relation update/delete', async () => {
    const wrapper = mount(KnowledgeManagement, {
      attachTo: document.body,
      global: { plugins: [ElementPlus], stubs: { KnowledgeGraph: true, teleport: true } },
    })
    await flushPromises()

    const input = wrapper.find('input[placeholder="搜索名称或编码"]')
    await input.setValue('概率')
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', '第一章 统计基础')
    selects[0].vm.$emit('change', '第一章 统计基础')
    selects[1].vm.$emit('update:modelValue', 2)
    selects[1].vm.$emit('change', 2)
    await flushPromises()
    const queryButton = wrapper.findAll('button').find(item => item.text() === '查询')
    await queryButton!.trigger('click')
    await flushPromises()
    expect(api.get).toHaveBeenCalledWith('/knowledge/points', {
      params: { active_only: false, query: '概率', chapter: '第一章 统计基础', difficulty: 2 },
    })

    wrapper.findComponent({ name: 'ElSegmented' }).vm.$emit('update:modelValue', 'relations')
    await flushPromises()
    const setup = (wrapper.vm as unknown as { $: { setupState: Record<string, (...args: unknown[]) => Promise<void> | void> } }).$.setupState
    setup.openEdgeEdit(relation)
    await setup.saveEdge()
    expect(api.put).toHaveBeenCalledWith('/knowledge/prerequisites/2/1', {
      prerequisite_id: 1,
      knowledge_point_id: 2,
    })

    await setup.removeEdge(relation)
    expect(api.delete).toHaveBeenCalledWith('/knowledge/prerequisites/2/1')
    wrapper.unmount()
  })

  it('covers point lifecycle, default import and relation creation', async () => {
    const wrapper = mount(KnowledgeManagement, {
      global: { plugins: [ElementPlus], stubs: { KnowledgeGraph: true, teleport: true } },
    })
    await flushPromises()
    const setup = (wrapper.vm as any).$.setupState

    await setup.importDefaults()
    setup.openCreate()
    await setup.savePoint()
    expect(api.post).toHaveBeenCalledWith('/knowledge/points', expect.any(Object))
    setup.openEdit(points[0])
    await setup.savePoint()
    expect(api.patch).toHaveBeenCalledWith('/knowledge/points/1', expect.any(Object))
    await setup.removePoint(points[0])
    expect(api.delete).toHaveBeenCalledWith('/knowledge/points/1', { params: { confirm: true } })

    setup.openEdgeCreate()
    setup.edge.prerequisite_id = 1
    setup.edge.knowledge_point_id = 2
    await setup.saveEdge()
    expect(api.post).toHaveBeenCalledWith('/knowledge/prerequisites', {
      prerequisite_id: 1,
      knowledge_point_id: 2,
    })
    wrapper.unmount()
  })
})
