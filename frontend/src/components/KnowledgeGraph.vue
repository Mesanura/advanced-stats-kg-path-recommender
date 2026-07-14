<script setup lang="ts">
import { GraphChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { init, use, type ECharts } from 'echarts/core'
import { LabelLayout } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { KnowledgeGraphData } from '../types/knowledge'

use([GraphChart, TooltipComponent, LabelLayout, CanvasRenderer])
const props = defineProps<{ data: KnowledgeGraphData }>()
const container = ref<HTMLDivElement>()
let chart: ECharts | undefined
const colors = ['#247a68', '#3979a8', '#d29a32', '#b54c42', '#6b5b95']
const dimensions = ['statistics_foundation', 'linear_models', 'selection_regularization', 'classification', 'evaluation_ensemble']

function render(): void {
  if (!chart) return
  chart.setOption({
    tooltip: { formatter: (params: { dataType: string; data: { name?: string; difficulty?: number } }) => params.dataType === 'node' ? `${params.data.name}<br/>难度 ${params.data.difficulty}` : '前置关系' },
    series: [{
      type: 'graph', layout: 'force', roam: true, draggable: true,
      force: { repulsion: 350, edgeLength: [85, 140], gravity: 0.08 },
      symbolSize: (value: number[]) => 20 + value[0] * 3,
      label: { show: true, position: 'right', distance: 5, color: '#24313b', fontSize: 10 },
      labelLayout: { hideOverlap: true },
      edgeSymbol: ['none', 'arrow'], edgeSymbolSize: 7,
      lineStyle: { color: '#aab4ba', width: 1.2, curveness: 0.05 },
      data: props.data.nodes.map(node => ({ id: String(node.id), name: node.name, value: [node.difficulty], difficulty: node.difficulty, itemStyle: { color: colors[dimensions.indexOf(node.dimension)] } })),
      links: props.data.edges.map(edge => ({ source: String(edge.prerequisite_id), target: String(edge.knowledge_point_id) })),
    }],
  })
}

function resize(): void { chart?.resize() }
onMounted(async () => { await nextTick(); if (container.value) chart = init(container.value); render(); window.addEventListener('resize', resize) })
watch(() => props.data, render, { deep: true })
onBeforeUnmount(() => { window.removeEventListener('resize', resize); chart?.dispose() })
</script>

<template><div ref="container" class="knowledge-graph-canvas"></div></template>
