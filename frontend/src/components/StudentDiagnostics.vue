<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import { api } from '../api/client'
import type { KnowledgePoint } from '../types/knowledge'
import type { LearningPath, MasteryItem } from '../types/student'
import type { MasteryAlgorithm, PaginatedTeacherStudents, TeacherScope, TeacherStudent } from '../types/teacher'

interface Diagnosis {
  student_id: number
  student_no: string
  display_name: string
  algorithm: MasteryAlgorithm
  items: MasteryItem[]
  weak_points: string[]
  suggested_directions: string[]
}

const students = ref<TeacherStudent[]>([])
const scope = ref<TeacherScope>({ classes: [] })
const targets = ref<KnowledgePoint[]>([])
const total = ref(0)
const query = ref('')
const classroomId = ref<number>()
const algorithm = ref<MasteryAlgorithm>('bkt')
const selected = ref<TeacherStudent>()
const diagnosis = ref<Diagnosis>()
const targetId = ref<number>()
const generatedPath = ref<LearningPath>()
const drawer = ref(false)
const loading = ref(false)
const detailLoading = ref(false)

async function loadStudents(): Promise<void> {
  loading.value = true
  try {
    const response = await api.get<PaginatedTeacherStudents>('/teacher/students', {
      params: { query: query.value || undefined, class_id: classroomId.value, algorithm: algorithm.value, page_size: 100 },
    })
    students.value = response.data.items
    total.value = response.data.total
  } finally { loading.value = false }
}

async function openStudent(student: TeacherStudent): Promise<void> {
  selected.value = student
  diagnosis.value = undefined
  generatedPath.value = undefined
  targetId.value = undefined
  drawer.value = true
  detailLoading.value = true
  try {
    diagnosis.value = (await api.get<Diagnosis>(`/teacher/students/${student.student_id}/diagnosis`, { params: { algorithm: algorithm.value } })).data
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
    drawer.value = false
    ElMessage.error(detail || '无法加载学生诊断')
  } finally {
    detailLoading.value = false
  }
}

async function generatePath(): Promise<void> {
  if (!selected.value || !targetId.value) return
  try {
    generatedPath.value = (await api.post<LearningPath>(`/recommendations/students/${selected.value.student_id}`, { target_knowledge_point_id: targetId.value })).data
    ElMessage.success('已生成该生学习路径')
  } catch { ElMessage.error('无法生成目标路径') }
}

onMounted(async () => {
  const [scopeResponse, targetResponse] = await Promise.all([
    api.get<TeacherScope>('/teacher/scope'), api.get<KnowledgePoint[]>('/knowledge/points'),
  ])
  scope.value = scopeResponse.data
  targets.value = targetResponse.data
  await loadStudents()
})
</script>

<template>
  <main class="page-content">
    <div class="page-title-row"><div><p class="section-label">STUDENT DIAGNOSTICS</p><h1>学生诊断</h1><p>{{ total }} 名可查看学生</p></div><el-segmented v-model="algorithm" :options="[{label:'BKT',value:'bkt'},{label:'规则法',value:'rule'}]" @change="loadStudents" /></div>
    <div class="filter-bar student-filter"><el-input v-model="query" clearable placeholder="姓名或学号" :prefix-icon="Search" @keyup.enter="loadStudents" @clear="loadStudents" /><el-select v-model="classroomId" clearable placeholder="全部负责班级" @change="loadStudents"><el-option v-for="item in scope.classes" :key="item.id" :label="item.name" :value="item.id" /></el-select><el-button @click="loadStudents">查询</el-button></div>
    <el-table v-loading="loading" :data="students" class="data-table" @row-click="openStudent">
      <el-table-column prop="display_name" label="姓名" min-width="110" />
      <el-table-column prop="student_no" label="学号" min-width="130" />
      <el-table-column prop="classroom_name" label="班级" min-width="140" />
      <el-table-column label="平均掌握度" min-width="180"><template #default="scope"><el-progress :percentage="Math.round(scope.row.average_mastery * 100)" :stroke-width="8" /><span></span></template></el-table-column>
      <el-table-column prop="weak_count" label="薄弱 / 未学习" width="130" />
      <el-table-column label="" width="80"><template #default="scope"><el-button link :loading="detailLoading && selected?.student_id === scope.row.student_id" @click.stop="openStudent(scope.row)">详情</el-button></template></el-table-column>
    </el-table>

    <el-drawer v-model="drawer" v-loading="detailLoading" :size="680" :title="`${selected?.display_name ?? ''} · 诊断报告`">
      <template v-if="diagnosis"><div class="diagnosis-meta"><span>{{ diagnosis.student_no }}</span><el-tag effect="plain">{{ diagnosis.algorithm.toUpperCase() }}</el-tag></div><h3>薄弱知识点</h3><div class="prerequisite-list"><el-tag v-for="item in diagnosis.weak_points" :key="item" type="danger" effect="plain">{{ item }}</el-tag><span v-if="!diagnosis.weak_points.length">暂无薄弱知识点</span></div><h3>知识掌握度</h3><div class="diagnosis-heatmap"><div v-for="item in diagnosis.items" :key="item.knowledge_point_id" :class="['diagnosis-cell', item.status]"><span>{{ item.name }}</span><strong>{{ Math.round(item.score * 100) }}%</strong></div></div><el-divider /><h3>生成学习路径</h3><div class="teacher-path-action"><el-select v-model="targetId" filterable placeholder="目标知识点"><el-option v-for="item in targets" :key="item.id" :label="item.name" :value="item.id" /></el-select><el-button type="primary" @click="generatePath">生成</el-button></div><div v-if="generatedPath" class="compact-path"><span v-for="node in generatedPath.nodes" :key="node.sequence">{{ node.name }}</span></div></template>
    </el-drawer>
  </main>
</template>
