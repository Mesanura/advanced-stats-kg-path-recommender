<script setup lang="ts">
import { Connection, Delete, Edit, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { api } from '../api/client'
import AppShell from '../components/AppShell.vue'
import KnowledgeGraph from '../components/KnowledgeGraph.vue'
import TeacherOverview from '../components/TeacherOverview.vue'
import type { AbilityDimension, KnowledgeGraphData, KnowledgePoint } from '../types/knowledge'

const points = ref<KnowledgePoint[]>([])
const activeSection = ref<'overview' | 'knowledge'>('overview')
const graph = ref<KnowledgeGraphData>({ nodes: [], edges: [] })
const mode = ref<'table' | 'graph'>('table')
const query = ref('')
const difficulty = ref<number | ''>('')
const pointDialog = ref(false)
const edgeDialog = ref(false)
const editingId = ref<number>()
const form = reactive({ code: '', name: '', chapter: '', dimension: 'statistics_foundation' as AbilityDimension, difficulty: 1, resource_url: 'https://', description: '' })
const edge = reactive({ prerequisite_id: undefined as number | undefined, knowledge_point_id: undefined as number | undefined })
const dimensions: { value: AbilityDimension; label: string }[] = [
  { value: 'statistics_foundation', label: '统计基础' }, { value: 'linear_models', label: '线性模型' },
  { value: 'selection_regularization', label: '选择与正则化' }, { value: 'classification', label: '分类方法' },
  { value: 'evaluation_ensemble', label: '评估与集成' },
]
const dimensionLabels = Object.fromEntries(dimensions.map(item => [item.value, item.label]))
const filteredPoints = computed(() => points.value.filter(item => (!query.value || item.name.includes(query.value) || item.code.includes(query.value)) && (!difficulty.value || item.difficulty === difficulty.value)))

async function load(): Promise<void> {
  const [pointResponse, graphResponse] = await Promise.all([
    api.get<KnowledgePoint[]>('/knowledge/points', { params: { active_only: false } }),
    api.get<KnowledgeGraphData>('/knowledge/graph'),
  ])
  points.value = pointResponse.data
  graph.value = graphResponse.data
}

async function importDefaults(): Promise<void> {
  const response = await api.post('/knowledge/import-defaults')
  ElMessage.success(`新增 ${response.data.knowledge_points_created} 个知识点`)
  await load()
}

function openCreate(): void {
  editingId.value = undefined
  Object.assign(form, { code: '', name: '', chapter: '', dimension: 'statistics_foundation', difficulty: 1, resource_url: 'https://', description: '' })
  pointDialog.value = true
}

function openEdit(item: KnowledgePoint): void {
  editingId.value = item.id
  Object.assign(form, item)
  pointDialog.value = true
}

async function savePoint(): Promise<void> {
  try {
    if (editingId.value) await api.patch(`/knowledge/points/${editingId.value}`, form)
    else await api.post('/knowledge/points', form)
    ElMessage.success(editingId.value ? '知识点已更新' : '知识点已创建')
    pointDialog.value = false
    await load()
  } catch { ElMessage.error('知识点信息不完整或重复') }
}

async function removePoint(item: KnowledgePoint): Promise<void> {
  await ElMessageBox.confirm(`删除“${item.name}”会同步删除相关学习数据，是否继续？`, '确认删除', { type: 'warning' })
  await api.delete(`/knowledge/points/${item.id}`, { params: { confirm: true } })
  ElMessage.success('知识点已删除')
  await load()
}

async function addEdge(): Promise<void> {
  try {
    await api.post('/knowledge/prerequisites', edge)
    ElMessage.success('前置关系已添加')
    edgeDialog.value = false
    await load()
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
    ElMessage.error(detail || '无法添加前置关系')
  }
}

onMounted(load)
</script>

<template>
  <AppShell :section="activeSection === 'overview' ? '学情概览' : '知识图谱'">
    <div class="teacher-section-tabs"><el-segmented v-model="activeSection" :options="[{label:'学情概览',value:'overview'},{label:'知识图谱',value:'knowledge'}]" /></div>
    <TeacherOverview v-if="activeSection === 'overview'" />
    <main v-else class="page-content">
      <div class="page-title-row">
        <div><p class="section-label">KNOWLEDGE GRAPH</p><h1>知识点与前置关系</h1><p>{{ points.length }} 个知识点，{{ graph.edges.length }} 条前置关系</p></div>
        <div class="page-actions"><el-button :icon="Refresh" @click="importDefaults">载入默认图谱</el-button><el-button :icon="Connection" @click="edgeDialog = true">添加关系</el-button><el-button type="primary" :icon="Plus" @click="openCreate">新增知识点</el-button></div>
      </div>
      <div class="knowledge-toolbar">
        <el-segmented v-model="mode" :options="[{label:'知识点列表',value:'table'},{label:'关系图',value:'graph'}]" />
        <template v-if="mode === 'table'"><el-input v-model="query" clearable placeholder="搜索名称或编码" :prefix-icon="Search" /><el-select v-model="difficulty" clearable placeholder="全部难度"><el-option v-for="level in 5" :key="level" :label="`难度 ${level}`" :value="level" /></el-select></template>
      </div>
      <el-table v-if="mode === 'table'" :data="filteredPoints" class="data-table">
        <el-table-column prop="name" label="知识点" min-width="150"><template #default="scope"><strong>{{ scope.row.name }}</strong><span class="table-subtitle">{{ scope.row.code }}</span></template></el-table-column>
        <el-table-column prop="chapter" label="章节" min-width="160" />
        <el-table-column label="能力维度" min-width="130"><template #default="scope">{{ dimensionLabels[scope.row.dimension] }}</template></el-table-column>
        <el-table-column label="难度" width="140"><template #default="scope"><el-rate :model-value="scope.row.difficulty" disabled /></template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="scope"><el-tag :type="scope.row.is_active ? 'success' : 'info'" effect="plain">{{ scope.row.is_active ? '启用' : '停用' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="120" align="right"><template #default="scope"><el-button link :icon="Edit" title="编辑" @click="openEdit(scope.row)" /><el-button link type="danger" :icon="Delete" title="删除" @click="removePoint(scope.row)" /></template></el-table-column>
      </el-table>
      <div v-else class="graph-band"><KnowledgeGraph :data="graph" /></div>
    </main>

    <el-dialog v-model="pointDialog" :title="editingId ? '编辑知识点' : '新增知识点'" width="600px">
      <el-form label-position="top"><div class="form-grid"><el-form-item label="名称"><el-input v-model="form.name" /></el-form-item><el-form-item label="编码"><el-input v-model="form.code" :disabled="Boolean(editingId)" /></el-form-item></div><el-form-item label="所属章节"><el-input v-model="form.chapter" /></el-form-item><div class="form-grid"><el-form-item label="能力维度"><el-select v-model="form.dimension"><el-option v-for="item in dimensions" :key="item.value" v-bind="item" /></el-select></el-form-item><el-form-item label="难度"><el-input-number v-model="form.difficulty" :min="1" :max="5" /></el-form-item></div><el-form-item label="学习资源链接"><el-input v-model="form.resource_url" /></el-form-item><el-form-item label="简介"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item></el-form>
      <template #footer><el-button @click="pointDialog = false">取消</el-button><el-button type="primary" @click="savePoint">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="edgeDialog" title="添加前置关系" width="500px">
      <el-form label-position="top"><el-form-item label="前置知识点"><el-select v-model="edge.prerequisite_id" filterable><el-option v-for="item in points" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item><el-form-item label="目标知识点"><el-select v-model="edge.knowledge_point_id" filterable><el-option v-for="item in points" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item></el-form>
      <template #footer><el-button @click="edgeDialog = false">取消</el-button><el-button type="primary" @click="addEdge">添加</el-button></template>
    </el-dialog>
  </AppShell>
</template>
