<script setup lang="ts">
import { DataAnalysis, House, SwitchButton, UserFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

defineProps<{ section: string }>()
const auth = useAuthStore()
const router = useRouter()

const roleLabels = { student: '学生端', teacher: '教师端', admin: '管理端' }
const roleIcons = { student: DataAnalysis, teacher: House, admin: UserFilled }

async function logout(): Promise<void> {
  await auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <div class="app-logo">AS</div>
      <div class="app-identity">
        <el-icon><component :is="roleIcons[auth.user?.role ?? 'student']" /></el-icon>
        <div><strong>{{ roleLabels[auth.user?.role ?? 'student'] }}</strong><span>高级统计方法</span></div>
      </div>
      <nav>
        <div class="nav-item active"><el-icon><House /></el-icon><span>{{ section }}</span></div>
      </nav>
      <button class="sidebar-logout" type="button" title="退出登录" @click="logout">
        <el-icon><SwitchButton /></el-icon><span>退出</span>
      </button>
    </aside>
    <div class="app-workspace">
      <header class="app-header">
        <span>{{ section }}</span>
        <div class="current-user"><strong>{{ auth.user?.display_name }}</strong><span>{{ auth.user?.username }}</span></div>
      </header>
      <slot />
    </div>
  </div>
</template>

