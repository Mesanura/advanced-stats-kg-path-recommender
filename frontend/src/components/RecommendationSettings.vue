<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { api } from '../api/client'
import type { MasteryAlgorithm } from '../types/teacher'

interface RecommendationConfig {
  id: number
  diagnostic_algorithm: MasteryAlgorithm
  min_path_length: number
  max_path_length: number
  mastery_threshold: number
  weak_threshold: number
  weak_priority_weight: number
  mastered_alignment_weight: number
  length_penalty_weight: number
  difficulty_jump_weight: number
}

const loading = ref(false)
const form = reactive<RecommendationConfig>({
  id: 1, diagnostic_algorithm: 'bkt', min_path_length: 5, max_path_length: 8,
  mastery_threshold: 0.7, weak_threshold: 0.5, weak_priority_weight: 0.45,
  mastered_alignment_weight: 0.25, length_penalty_weight: 0.15, difficulty_jump_weight: 0.15,
})

async function load(): Promise<void> {
  Object.assign(form, (await api.get<RecommendationConfig>('/teacher/recommendation-config')).data)
}

async function save(): Promise<void> {
  loading.value = true
  try {
    const { id: _id, ...payload } = form
    void _id
    Object.assign(form, (await api.put<RecommendationConfig>('/teacher/recommendation-config', payload)).data)
    ElMessage.success('推荐策略已保存，现有路径已标记为待更新')
  } catch { ElMessage.error('请检查阈值顺序和权重之和') }
  finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <main class="page-content settings-page">
    <div class="page-title-row"><div><p class="section-label">RECOMMENDATION POLICY</p><h1>推荐策略</h1><p>掌握度算法、路径边界与候选路径评分</p></div><el-button type="primary" :loading="loading" @click="save">保存策略</el-button></div>
    <section class="settings-band">
      <div class="settings-group"><h2>诊断与路径</h2><el-form label-position="top"><el-form-item label="默认诊断算法"><el-segmented v-model="form.diagnostic_algorithm" :options="[{label:'BKT',value:'bkt'},{label:'规则法',value:'rule'}]" /></el-form-item><div class="form-grid"><el-form-item label="最短路径"><el-input-number v-model="form.min_path_length" :min="1" :max="12" /></el-form-item><el-form-item label="最长路径"><el-input-number v-model="form.max_path_length" :min="1" :max="12" /></el-form-item></div><el-form-item label="掌握阈值"><el-slider v-model="form.mastery_threshold" :min="0" :max="1" :step="0.05" show-input /></el-form-item><el-form-item label="薄弱阈值"><el-slider v-model="form.weak_threshold" :min="0" :max="1" :step="0.05" show-input /></el-form-item></el-form></div>
      <div class="settings-group"><h2>路径评分权重</h2><el-form label-position="top"><el-form-item label="薄弱点优先"><el-slider v-model="form.weak_priority_weight" :min="0" :max="1" :step="0.05" show-input /></el-form-item><el-form-item label="已掌握衔接"><el-slider v-model="form.mastered_alignment_weight" :min="0" :max="1" :step="0.05" show-input /></el-form-item><el-form-item label="路径长度惩罚"><el-slider v-model="form.length_penalty_weight" :min="0" :max="1" :step="0.05" show-input /></el-form-item><el-form-item label="难度跳跃惩罚"><el-slider v-model="form.difficulty_jump_weight" :min="0" :max="1" :step="0.05" show-input /></el-form-item><div class="weight-total"><span>权重合计</span><strong>{{ (form.weak_priority_weight + form.mastered_alignment_weight + form.length_penalty_weight + form.difficulty_jump_weight).toFixed(2) }}</strong></div></el-form></div>
    </section>
  </main>
</template>

