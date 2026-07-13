<script setup lang="ts">
import { Lock, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function submit(): Promise<void> {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const role = await auth.login(form.username, form.password)
    await router.replace(`/${role}`)
  } catch {
    ElMessage.error('用户名或密码错误')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-brand">
      <p class="eyebrow">ADVANCED STATISTICS</p>
      <h1>知识图谱学习路径</h1>
      <p>诊断掌握状态，连接知识前置关系，为每位学生生成清晰的下一步。</p>
      <div class="brand-lines" aria-hidden="true"><span></span><span></span><span></span></div>
    </section>
    <section class="login-panel">
      <div class="login-form">
        <p class="section-label">课程系统</p>
        <h2>登录</h2>
        <el-form :model="form" size="large" @submit.prevent="submit">
          <el-form-item>
            <el-input v-model="form.username" autocomplete="username" placeholder="用户名" :prefix-icon="User" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.password" type="password" autocomplete="current-password" placeholder="密码" :prefix-icon="Lock" show-password @keyup.enter="submit" />
          </el-form-item>
          <el-button class="login-button" type="primary" :loading="loading" @click="submit">进入系统</el-button>
        </el-form>
      </div>
    </section>
  </main>
</template>

