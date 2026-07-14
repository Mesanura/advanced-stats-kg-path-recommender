<script setup lang="ts">
import { BarChart, RadarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, RadarComponent, TooltipComponent } from 'echarts/components'
import { init, use, type ECharts, type EChartsCoreOption } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

use([BarChart, RadarChart, GridComponent, LegendComponent, RadarComponent, TooltipComponent, CanvasRenderer])
const props = defineProps<{ option: EChartsCoreOption }>()
const container = ref<HTMLDivElement>()
let chart: ECharts | undefined
function resize(): void { chart?.resize() }
function render(): void { chart?.setOption(props.option, true) }
onMounted(async () => { await nextTick(); if (container.value) chart = init(container.value); render(); window.addEventListener('resize', resize) })
watch(() => props.option, render, { deep: true })
onBeforeUnmount(() => { window.removeEventListener('resize', resize); chart?.dispose() })
</script>

<template><div ref="container" class="base-chart"></div></template>

