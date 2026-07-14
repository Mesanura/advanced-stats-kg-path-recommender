<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'

import { api } from '../api/client'
import type { AbilityDimension } from '../types/knowledge'
import type { MasteryAlgorithm, TeacherOverviewData, TeacherScope } from '../types/teacher'
import BaseChart from './BaseChart.vue'

const scope = ref<TeacherScope>({ classes: [] })
const overview = ref<TeacherOverviewData>()
const selectedScope = ref('')
const algorithm = ref<MasteryAlgorithm>('bkt')
const loading = ref(false)
const dimensionLabels: Record<AbilityDimension, string> = {
  statistics_foundation: '统计基础', linear_models: '线性模型', selection_regularization: '选择与正则化',
  classification: '分类方法', evaluation_ensemble: '评估与集成',
}
const scopeOptions = computed(() => {
  const grades = new Map(scope.value.classes.map(item => [item.grade_id, item.grade_name]))
  return [
    ...scope.value.classes.map(item => ({ label: item.name, value: `class:${item.id}` })),
    ...Array.from(grades, ([id, name]) => ({ label: `${name}全年级`, value: `grade:${id}` })),
  ]
})

async function loadOverview(): Promise<void> {
  if (!selectedScope.value) return
  loading.value = true
  const [kind, id] = selectedScope.value.split(':')
  try {
    const response = await api.get<TeacherOverviewData>('/teacher/overview', {
      params: { [`${kind}_id`]: Number(id), algorithm: algorithm.value },
    })
    overview.value = response.data
  } finally { loading.value = false }
}

const radarOption = computed(() => {
  const dimensions = overview.value?.dimensions ?? []
  if (!dimensions.length) return {}
  return {
    tooltip: {},
    radar: { radius: '52%', indicator: dimensions.map(item => ({ name: dimensionLabels[item.dimension], max: 1 })), splitNumber: 4, axisName: { color: '#4f5d67' }, splitArea: { areaStyle: { color: ['#f7f9fa', '#eef3f2'] } } },
    series: [{ type: 'radar', data: [{ value: dimensions.map(item => item.average), areaStyle: { color: 'rgba(36,122,104,.25)' }, lineStyle: { color: '#247a68' }, itemStyle: { color: '#247a68' } }] }],
  }
})
const weakBarOption = computed(() => {
  const data = overview.value?.weak_top5 ?? []
  return {
    tooltip: { trigger: 'axis' }, grid: { left: 100, right: 24, top: 18, bottom: 28 },
    xAxis: { type: 'value', min: 0, max: 1, splitLine: { lineStyle: { color: '#edf0f2' } } },
    yAxis: { type: 'category', inverse: true, data: data.map(item => item.name), axisTick: { show: false }, axisLine: { show: false } },
    series: [{ type: 'bar', data: data.map(item => item.average), barWidth: 16, itemStyle: { color: '#c94b3f', borderRadius: [0, 2, 2, 0] } }],
  }
})

onMounted(async () => {
  scope.value = (await api.get<TeacherScope>('/teacher/scope')).data
  selectedScope.value = scopeOptions.value[0]?.value ?? ''
  await loadOverview()
})
</script>

<template>
  <main v-loading="loading" class="page-content">
    <div class="page-title-row">
      <div><p class="section-label">LEARNING ANALYTICS</p><h1>班级学情概览</h1><p>掌握度分布与需要关注的学习状态</p></div>
      <div class="page-actions"><el-select v-model="selectedScope" @change="loadOverview"><el-option v-for="item in scopeOptions" :key="item.value" v-bind="item" /></el-select><el-segmented v-model="algorithm" :options="[{label:'BKT',value:'bkt'},{label:'规则法',value:'rule'}]" @change="loadOverview" /><el-button :icon="Refresh" title="刷新" @click="loadOverview" /></div>
    </div>
    <section class="metric-strip">
      <div><span>学生数</span><strong>{{ overview?.student_count ?? 0 }}</strong></div>
      <div><span>平均掌握度</span><strong>{{ Math.round((overview?.average_mastery ?? 0) * 100) }}%</strong></div>
      <div><span>薄弱知识点</span><strong>{{ overview?.weak_top5.length ?? 0 }}</strong></div>
      <div><span>需关注学生</span><strong>{{ overview?.attention_students.length ?? 0 }}</strong></div>
    </section>
    <section class="analytics-grid">
      <div class="analytics-panel"><div class="panel-heading"><h2>能力维度</h2><span>0–1 掌握度</span></div><BaseChart :option="radarOption" /></div>
      <div class="analytics-panel"><div class="panel-heading"><h2>薄弱知识点 TOP5</h2><span>平均掌握度</span></div><BaseChart :option="weakBarOption" /></div>
    </section>
    <section class="attention-section">
      <div class="panel-heading"><h2>需关注学生</h2><span>{{ overview?.attention_students.length ?? 0 }} 人</span></div>
      <el-table :data="overview?.attention_students ?? []" class="data-table">
        <el-table-column prop="display_name" label="姓名" min-width="100" />
        <el-table-column prop="student_no" label="学号" min-width="130" />
        <el-table-column prop="classroom_name" label="班级" min-width="140" />
        <el-table-column label="平均掌握度" width="150"><template #default="scope"><el-progress :percentage="Math.round(scope.row.average * 100)" :stroke-width="8" :show-text="false" /><span class="progress-value">{{ Math.round(scope.row.average * 100) }}%</span></template></el-table-column>
        <el-table-column prop="weak_count" label="薄弱 / 未学习" width="130" />
      </el-table>
    </section>
  </main>
</template>
