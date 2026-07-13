<script setup lang="ts">
import { DataAnalysis, Share } from '@element-plus/icons-vue'
</script>

<template>
  <main class="welcome-shell">
    <section class="welcome-panel">
      <div class="brand-mark"><el-icon><Share /></el-icon></div>
      <p class="eyebrow">ADVANCED STATISTICS</p>
      <h1>课程知识图谱学习路径推荐系统</h1>
      <p class="summary">基于学习行为诊断掌握程度，以知识前置关系生成适合每位学生的学习路径。</p>
      <el-tag type="success" effect="plain" size="large">
        <el-icon><DataAnalysis /></el-icon>
        工程骨架已就绪
      </el-tag>
    </section>
  </main>
</template>

