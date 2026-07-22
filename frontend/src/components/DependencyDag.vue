<script setup lang="ts">
import { FullScreen, ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { init, use, type ECharts, type EChartsCoreOption } from 'echarts/core'
import { LabelLayout } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { DependencyGraph, DependencyGraphNode, MasteryStatus } from '../types/student'

use([GraphChart, TooltipComponent, LabelLayout, CanvasRenderer])

const props = defineProps<{ data: DependencyGraph }>()
const emit = defineEmits<{ selectNode: [node: DependencyGraphNode] }>()
const container = ref<HTMLDivElement>()
let chart: ECharts | undefined
let zoom = 0.9

const statusColors: Record<MasteryStatus, string> = {
  mastered: '#d7eee8',
  learning: '#f5e5b6',
  weak: '#f2d2cf',
  unknown: '#e5e8ea',
}
const statusLabels: Record<MasteryStatus, string> = {
  mastered: '已掌握',
  learning: '学习中',
  weak: '薄弱',
  unknown: '未学习',
}

interface PositionedNode extends DependencyGraphNode {
  x: number
  y: number
}

function buildLayout(): { nodes: PositionedNode[]; width: number; height: number } {
  const nodes = props.data.nodes
  const nodeIds = new Set(nodes.map(node => node.knowledge_point_id))
  const predecessors = new Map<number, number[]>(nodes.map(node => [node.knowledge_point_id, []]))
  const successors = new Map<number, number[]>(nodes.map(node => [node.knowledge_point_id, []]))
  const indegree = new Map<number, number>(nodes.map(node => [node.knowledge_point_id, 0]))
  for (const edge of props.data.edges) {
    if (!nodeIds.has(edge.prerequisite_id) || !nodeIds.has(edge.knowledge_point_id)) continue
    predecessors.get(edge.knowledge_point_id)?.push(edge.prerequisite_id)
    successors.get(edge.prerequisite_id)?.push(edge.knowledge_point_id)
    indegree.set(edge.knowledge_point_id, (indegree.get(edge.knowledge_point_id) ?? 0) + 1)
  }

  const depth = new Map<number, number>()
  const ready = nodes
    .filter(node => indegree.get(node.knowledge_point_id) === 0)
    .map(node => node.knowledge_point_id)
    .sort((left, right) => left - right)
  while (ready.length) {
    const current = ready.shift()!
    const currentDepth = depth.get(current) ?? 0
    for (const successor of successors.get(current) ?? []) {
      depth.set(successor, Math.max(depth.get(successor) ?? 0, currentDepth + 1))
      const remaining = (indegree.get(successor) ?? 1) - 1
      indegree.set(successor, remaining)
      if (remaining === 0) ready.push(successor)
    }
    ready.sort((left, right) => left - right)
  }
  for (const node of nodes) {
    if (!depth.has(node.knowledge_point_id)) depth.set(node.knowledge_point_id, 0)
  }

  const layers = new Map<number, DependencyGraphNode[]>()
  for (const node of nodes) {
    const nodeDepth = depth.get(node.knowledge_point_id) ?? 0
    layers.set(nodeDepth, [...(layers.get(nodeDepth) ?? []), node])
  }
  const order = new Map<number, number>()
  for (const layerDepth of [...layers.keys()].sort((left, right) => left - right)) {
    const layer = layers.get(layerDepth)!
    layer.sort((left, right) => {
      const averageOrder = (node: DependencyGraphNode): number => {
        const parentOrder = (predecessors.get(node.knowledge_point_id) ?? [])
          .map(parentId => order.get(parentId))
          .filter((value): value is number => value !== undefined)
        return parentOrder.length
          ? parentOrder.reduce((total, value) => total + value, 0) / parentOrder.length
          : node.knowledge_point_id
      }
      return averageOrder(left) - averageOrder(right) || left.knowledge_point_id - right.knowledge_point_id
    })
    layer.forEach((node, index) => order.set(node.knowledge_point_id, index))
  }

  const maxDepth = Math.max(0, ...layers.keys())
  const largestLayer = Math.max(1, ...[...layers.values()].map(layer => layer.length))
  const width = Math.max(260, (maxDepth + 1) * 190)
  const height = Math.max(360, largestLayer * 86 + 80)
  const positioned = [...layers.entries()].flatMap(([layerDepth, layer]) =>
    layer.map((node, index) => ({
      ...node,
      x: maxDepth ? 80 + layerDepth * ((width - 160) / maxDepth) : width / 2,
      y: layer.length === 1 ? height / 2 : 50 + index * ((height - 100) / (layer.length - 1)),
    })),
  )
  return { nodes: positioned, width, height }
}

const chartHeight = computed(() => {
  const { height } = buildLayout()
  return `${Math.min(680, Math.max(420, height))}px`
})
const mobileCanvasWidth = computed(() => `${Math.min(980, buildLayout().width)}px`)

function graphOption(): EChartsCoreOption {
  const layout = buildLayout()
  return {
    animationDuration: 350,
    animationDurationUpdate: 250,
    tooltip: {
      renderMode: 'richText',
      formatter: (params: { dataType: string; data: { dependencyNode?: DependencyGraphNode } }) => {
        const node = params.data.dependencyNode
        if (params.dataType !== 'node' || !node) return '前置依赖'
        const active = node.is_active ? '' : '\n已停用'
        return `${node.name}\n掌握度 ${Math.round(node.mastery_score * 100)}% · ${statusLabels[node.mastery_status]}\n难度 ${node.difficulty} / 5${active}`
      },
    },
    series: [{
      type: 'graph',
      layout: 'none',
      left: 36,
      right: 36,
      top: 28,
      bottom: 28,
      roam: true,
      zoom,
      scaleLimit: { min: 0.5, max: 2.5 },
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: 8,
      lineStyle: { color: '#9ca8ae', width: 1.4, opacity: 0.85, curveness: 0.04 },
      emphasis: { focus: 'adjacency', lineStyle: { color: '#496b65', width: 2.2 } },
      data: layout.nodes.map(node => ({
        id: String(node.knowledge_point_id),
        name: node.name,
        x: node.x,
        y: node.y,
        value: node.mastery_score,
        dependencyNode: node,
        symbol: 'roundRect',
        symbolSize: node.is_target ? [132, 52] : [118, 46],
        itemStyle: {
          color: statusColors[node.mastery_status],
          borderColor: node.is_target ? '#c9362b' : node.in_recommended_path ? '#1f6b5c' : '#849098',
          borderWidth: node.is_target ? 4 : node.in_recommended_path ? 3 : 1,
          borderType: node.is_active ? 'solid' : 'dashed',
          opacity: node.is_active ? 1 : 0.68,
        },
        label: {
          show: true,
          position: 'inside',
          width: node.is_target ? 112 : 98,
          overflow: 'break',
          lineHeight: 14,
          color: '#253139',
          fontSize: 11,
          fontWeight: node.is_target ? 700 : 500,
        },
      })),
      links: props.data.edges.map(edge => ({
        source: String(edge.prerequisite_id),
        target: String(edge.knowledge_point_id),
      })),
    }],
  }
}

function render(): void {
  chart?.setOption(graphOption(), true)
}

function changeZoom(factor: number): void {
  zoom = Math.min(2.5, Math.max(0.5, Number((zoom * factor).toFixed(2))))
  chart?.setOption({ series: [{ zoom }] })
}

function fitGraph(): void {
  zoom = 0.9
  render()
}

function resize(): void {
  chart?.resize()
}

onMounted(async () => {
  await nextTick()
  if (!container.value) return
  chart = init(container.value)
  chart.on('click', params => {
    const node = (params.data as { dependencyNode?: DependencyGraphNode })?.dependencyNode
    if (params.dataType === 'node' && node) emit('selectNode', node)
  })
  render()
  window.addEventListener('resize', resize)
})
watch(() => props.data, () => { zoom = 0.9; render() }, { deep: true })
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
})
</script>

<template>
  <div class="dependency-dag">
    <div class="dependency-toolbar">
      <div class="dependency-legend" aria-label="节点图例">
        <span><i class="mastered"></i>已掌握</span>
        <span><i class="learning"></i>学习中</span>
        <span><i class="weak"></i>薄弱</span>
        <span><i class="unknown"></i>未学习</span>
        <span><i class="recommended"></i>推荐路径</span>
        <span><i class="target"></i>目标</span>
      </div>
      <div class="dependency-controls" role="group" aria-label="依赖图视图控制">
        <el-tooltip content="放大" placement="top"><el-button :icon="ZoomIn" circle aria-label="放大依赖图" @click="changeZoom(1.2)" /></el-tooltip>
        <el-tooltip content="缩小" placement="top"><el-button :icon="ZoomOut" circle aria-label="缩小依赖图" @click="changeZoom(1 / 1.2)" /></el-tooltip>
        <el-tooltip content="适应画布" placement="top"><el-button :icon="FullScreen" circle aria-label="适应依赖图画布" @click="fitGraph" /></el-tooltip>
      </div>
    </div>
    <div class="dependency-dag-scroll">
      <div
        ref="container"
        class="dependency-dag-canvas"
        :style="{ height: chartHeight, '--dependency-dag-width': mobileCanvasWidth }"
        role="img"
        :aria-label="`${data.nodes.length} 个节点的目标前置依赖图`"
      ></div>
    </div>
  </div>
</template>
