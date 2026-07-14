<script setup lang="ts">
import { Link, RefreshRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { api } from '../api/client'
import AppShell from '../components/AppShell.vue'
import BaseChart from '../components/BaseChart.vue'
import type { AbilityDimension } from '../types/knowledge'
import type { LearningPath, PathNode, StudentDashboardData } from '../types/student'

const dashboard = ref<StudentDashboardData>()
const selectedTarget = ref<number>()
const selectedNode = ref<PathNode>()
const drawer = ref(false)
const generating = ref(false)
const dimensionLabels: Record<AbilityDimension, string> = {
  statistics_foundation: '统计基础', linear_models: '线性模型', selection_regularization: '选择与正则化',
  classification: '分类方法', evaluation_ensemble: '评估与集成',
}
const currentPath = computed(() => dashboard.value?.current_paths[0])
const radarOption = computed(() => ({
  tooltip: {}, radar: { indicator: (dashboard.value?.dimensions ?? []).map(item => ({ name: dimensionLabels[item.dimension], max: 1 })), splitNumber: 4, axisName: { color: '#4f5d67' }, splitArea: { areaStyle: { color: ['#f7f9fa', '#eef3f2'] } } },
  series: [{ type: 'radar', data: [{ value: (dashboard.value?.dimensions ?? []).map(item => item.average), areaStyle: { color: 'rgba(36,122,104,.24)' }, lineStyle: { color: '#247a68' }, itemStyle: { color: '#247a68' } }] }],
}))

async function load(): Promise<void> {
  dashboard.value = (await api.get<StudentDashboardData>('/students/me/dashboard')).data
  if (!selectedTarget.value) selectedTarget.value = dashboard.value.available_targets[0]?.id
}

async function generatePath(): Promise<void> {
  if (!selectedTarget.value) return
  generating.value = true
  try {
    const path = (await api.post<LearningPath>('/recommendations/me', { target_knowledge_point_id: selectedTarget.value })).data
    await load()
    const index = dashboard.value?.current_paths.findIndex(item => item.id === path.id) ?? -1
    if (index > 0 && dashboard.value) dashboard.value.current_paths.unshift(...dashboard.value.current_paths.splice(index, 1))
    ElMessage.success(path.length_exception === 'target_mastered' ? '该目标已掌握' : '学习路径已生成')
  } catch { ElMessage.error('当前知识图谱无法生成该目标的有效路径') }
  finally { generating.value = false }
}

function openNode(node: PathNode): void { selectedNode.value = node; drawer.value = true }
onMounted(load)
</script>

<template>
  <AppShell section="个人学习中心">
    <main class="page-content student-dashboard">
      <div class="page-title-row">
        <div><p class="section-label">PERSONAL LEARNING PROFILE</p><h1>{{ dashboard?.display_name }}的学习画像</h1><p>{{ dashboard?.classroom_name }} · {{ dashboard?.student_no }} · {{ dashboard?.algorithm.toUpperCase() }}</p></div>
        <div class="target-action"><el-select v-model="selectedTarget" filterable placeholder="选择目标知识点"><el-option v-for="item in dashboard?.available_targets ?? []" :key="item.id" :label="`${item.name} · 难度${item.difficulty}`" :value="item.id" /></el-select><el-button type="primary" :icon="RefreshRight" :loading="generating" @click="generatePath">生成路径</el-button></div>
      </div>
      <section class="student-summary-band">
        <div class="profile-score"><span>综合掌握度</span><strong>{{ Math.round((dashboard?.average_mastery ?? 0) * 100) }}%</strong><el-progress :percentage="Math.round((dashboard?.average_mastery ?? 0) * 100)" :stroke-width="8" :show-text="false" /></div>
        <div class="student-radar"><BaseChart :option="radarOption" /></div>
        <div class="weak-summary"><span>当前薄弱点</span><strong>{{ dashboard?.weak_points.length ?? 0 }}</strong><div><el-tag v-for="item in dashboard?.weak_points.slice(0, 4) ?? []" :key="item" type="danger" effect="plain">{{ item }}</el-tag></div></div>
      </section>

      <section class="mastery-section">
        <div class="panel-heading"><h2>知识点掌握热力图</h2><div class="heat-legend"><span class="mastered"></span>掌握<span class="learning"></span>学习中<span class="weak"></span>薄弱<span class="unknown"></span>未学习</div></div>
        <div class="mastery-heatmap"><button v-for="item in dashboard?.mastery_items ?? []" :key="item.knowledge_point_id" type="button" :class="['mastery-cell', item.status]" :title="`${item.name} ${Math.round(item.score * 100)}%`"><span>{{ item.name }}</span><strong>{{ Math.round(item.score * 100) }}</strong></button></div>
      </section>

      <section class="path-section">
        <div class="panel-heading"><h2>当前学习路径</h2><span>{{ currentPath?.target_name ?? '尚未生成' }}</span></div>
        <div v-if="currentPath" class="learning-path">
          <button v-for="node in currentPath.nodes" :key="node.sequence" type="button" :class="['path-node', node.status]" @click="openNode(node)"><span class="path-index">{{ node.sequence }}</span><span class="path-copy"><strong>{{ node.name }}</strong><small>{{ node.status === 'mastered' ? '已掌握' : node.status === 'target' ? '目标' : '待学习' }} · {{ Math.round(node.mastery_score * 100) }}%</small></span></button>
        </div>
        <el-empty v-else description="暂无学习路径" :image-size="80" />
      </section>
    </main>

    <el-drawer v-model="drawer" title="知识点详情" size="380px">
      <template v-if="selectedNode"><p class="section-label">STEP {{ selectedNode.sequence }}</p><h2>{{ selectedNode.name }}</h2><div class="detail-list"><div><span>当前掌握度</span><strong>{{ Math.round(selectedNode.mastery_score * 100) }}%</strong></div><div><span>难度</span><strong>{{ selectedNode.difficulty }} / 5</strong></div></div><h3>前置条件</h3><div class="prerequisite-list"><el-tag v-for="item in selectedNode.prerequisites" :key="item" effect="plain">{{ item }}</el-tag><span v-if="!selectedNode.prerequisites.length">基础知识点</span></div><el-link class="resource-link" type="primary" :href="selectedNode.resource_url" target="_blank" :icon="Link">打开学习资源</el-link></template>
    </el-drawer>
  </AppShell>
</template>
