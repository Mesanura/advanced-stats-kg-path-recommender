<script setup lang="ts">
import { useAuthStore } from '../stores/auth'

defineProps<{ title: string; description: string }>()
const auth = useAuthStore()
</script>

<template>
  <main class="role-placeholder">
    <p class="eyebrow">ADVANCED STATISTICS</p>
    <h1>{{ title }}</h1>
    <p>{{ description }}</p>
    <el-tag effect="plain">{{ auth.user?.display_name }}</el-tag>
  </main>
</template>

