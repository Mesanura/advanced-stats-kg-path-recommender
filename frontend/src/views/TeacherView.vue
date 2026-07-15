<script setup lang="ts">
import { ref } from 'vue'

import AppShell from '../components/AppShell.vue'
import KnowledgeManagement from '../components/KnowledgeManagement.vue'
import RecommendationSettings from '../components/RecommendationSettings.vue'
import StudentDiagnostics from '../components/StudentDiagnostics.vue'
import TeacherOverview from '../components/TeacherOverview.vue'

const activeSection = ref<'overview' | 'students' | 'knowledge' | 'settings'>('overview')
const sectionNames = { overview: '学情概览', students: '学生诊断', knowledge: '知识图谱', settings: '推荐策略' }
</script>

<template>
  <AppShell :section="sectionNames[activeSection]">
    <div class="teacher-section-tabs"><el-segmented v-model="activeSection" :options="[{label:'学情概览',value:'overview'},{label:'学生诊断',value:'students'},{label:'知识图谱',value:'knowledge'},{label:'推荐策略',value:'settings'}]" /></div>
    <TeacherOverview v-if="activeSection === 'overview'" />
    <StudentDiagnostics v-else-if="activeSection === 'students'" />
    <KnowledgeManagement v-else-if="activeSection === 'knowledge'" />
    <RecommendationSettings v-else />
  </AppShell>
</template>
