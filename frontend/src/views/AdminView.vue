<script setup lang="ts">
import { Key, Plus, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { api } from '../api/client'
import AppShell from '../components/AppShell.vue'
import type { Classroom, Grade, ManagedUser, PaginatedUsers } from '../types/admin'
import type { Role } from '../types/auth'

const users = ref<ManagedUser[]>([])
const grades = ref<Grade[]>([])
const classrooms = ref<Classroom[]>([])
const total = ref(0)
const query = ref('')
const role = ref<Role | ''>('')
const userDialog = ref(false)
const structureDialog = ref(false)
const loading = ref(false)
const form = reactive({
  username: '', display_name: '', password: 'Student@123456', role: 'student' as Role,
  student_no: '', classroom_id: undefined as number | undefined, classroom_ids: [] as number[],
})
const structure = reactive({ grade_name: '', class_name: '', grade_id: undefined as number | undefined })
const roleText: Record<Role, string> = { student: '学生', teacher: '教师', admin: '管理员' }
const classOptions = computed(() => classrooms.value.map(item => ({ label: `${item.grade_name} · ${item.name}`, value: item.id })))

async function loadUsers(): Promise<void> {
  loading.value = true
  try {
    const response = await api.get<PaginatedUsers>('/admin/users', { params: { query: query.value || undefined, role: role.value || undefined, page_size: 100 } })
    users.value = response.data.items
    total.value = response.data.total
  } finally { loading.value = false }
}

async function loadStructures(): Promise<void> {
  const [gradeResponse, classResponse] = await Promise.all([
    api.get<Grade[]>('/admin/grades'), api.get<Classroom[]>('/admin/classes'),
  ])
  grades.value = gradeResponse.data
  classrooms.value = classResponse.data
}

async function createUser(): Promise<void> {
  const payload: Record<string, unknown> = { username: form.username, display_name: form.display_name, password: form.password, role: form.role }
  if (form.role === 'student') Object.assign(payload, { student_no: form.student_no, classroom_id: form.classroom_id })
  if (form.role === 'teacher') payload.classroom_ids = form.classroom_ids
  try {
    await api.post('/admin/users', payload)
    ElMessage.success('账号已创建')
    userDialog.value = false
    await loadUsers()
  } catch { ElMessage.error('账号信息冲突或不完整') }
}

async function toggleUser(user: ManagedUser): Promise<void> {
  await api.patch(`/admin/users/${user.id}`, { is_active: !user.is_active })
  user.is_active = !user.is_active
  ElMessage.success(user.is_active ? '账号已启用' : '账号已停用')
}

async function resetPassword(user: ManagedUser): Promise<void> {
  const password = user.role === 'student' ? 'Student@123456' : 'Teacher@123456'
  await api.post(`/admin/users/${user.id}/reset-password`, { password })
  ElMessage.success('密码已重置')
}

async function createStructure(): Promise<void> {
  if (structure.grade_name) await api.post('/admin/grades', { name: structure.grade_name })
  if (structure.class_name && structure.grade_id) await api.post('/admin/classes', { name: structure.class_name, grade_id: structure.grade_id })
  ElMessage.success('年级或班级已创建')
  structureDialog.value = false
  await loadStructures()
}

onMounted(async () => { await Promise.all([loadUsers(), loadStructures()]) })
</script>

<template>
  <AppShell section="用户与班级">
    <main class="page-content">
      <div class="page-title-row">
        <div><p class="section-label">SYSTEM ADMINISTRATION</p><h1>用户与教学组织</h1><p>共 {{ total }} 个账号，{{ grades.length }} 个年级，{{ classrooms.length }} 个班级</p></div>
        <div class="page-actions"><el-button @click="structureDialog = true">年级 / 班级</el-button><el-button type="primary" :icon="Plus" @click="userDialog = true">新增账号</el-button></div>
      </div>
      <div class="filter-bar">
        <el-input v-model="query" clearable placeholder="姓名或用户名" :prefix-icon="Search" @keyup.enter="loadUsers" @clear="loadUsers" />
        <el-select v-model="role" clearable placeholder="全部角色" @change="loadUsers"><el-option v-for="(label, key) in roleText" :key="key" :label="label" :value="key" /></el-select>
        <el-button @click="loadUsers">查询</el-button>
      </div>
      <el-table v-loading="loading" :data="users" class="data-table">
        <el-table-column prop="display_name" label="姓名" min-width="120" />
        <el-table-column prop="username" label="用户名 / 学号" min-width="150" />
        <el-table-column label="角色" width="100"><template #default="scope"><el-tag effect="plain">{{ roleText[scope.row.role as Role] }}</el-tag></template></el-table-column>
        <el-table-column prop="classroom_name" label="班级" min-width="160"><template #default="scope">{{ scope.row.classroom_name || (scope.row.classroom_ids.length ? `负责 ${scope.row.classroom_ids.length} 个班` : '—') }}</template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="scope"><span :class="['status-dot', scope.row.is_active ? 'online' : 'offline']"></span>{{ scope.row.is_active ? '启用' : '停用' }}</template></el-table-column>
        <el-table-column label="操作" width="200" align="right"><template #default="scope"><el-button link :icon="Key" @click="resetPassword(scope.row)">重置密码</el-button><el-button link @click="toggleUser(scope.row)">{{ scope.row.is_active ? '停用' : '启用' }}</el-button></template></el-table-column>
      </el-table>
    </main>

    <el-dialog v-model="userDialog" title="新增账号" width="520px">
      <el-form label-position="top">
        <div class="form-grid"><el-form-item label="姓名"><el-input v-model="form.display_name" /></el-form-item><el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item></div>
        <el-form-item label="角色"><el-segmented v-model="form.role" :options="[{label:'学生',value:'student'},{label:'教师',value:'teacher'},{label:'管理员',value:'admin'}]" /></el-form-item>
        <template v-if="form.role === 'student'"><div class="form-grid"><el-form-item label="学号"><el-input v-model="form.student_no" /></el-form-item><el-form-item label="班级"><el-select v-model="form.classroom_id"><el-option v-for="item in classOptions" :key="item.value" v-bind="item" /></el-select></el-form-item></div></template>
        <el-form-item v-if="form.role === 'teacher'" label="负责班级"><el-select v-model="form.classroom_ids" multiple><el-option v-for="item in classOptions" :key="item.value" v-bind="item" /></el-select></el-form-item>
        <el-form-item label="初始密码"><el-input v-model="form.password" type="password" show-password /></el-form-item>
      </el-form>
      <template #footer><el-button @click="userDialog = false">取消</el-button><el-button type="primary" @click="createUser">创建</el-button></template>
    </el-dialog>

    <el-dialog v-model="structureDialog" title="年级与班级" width="500px">
      <el-form label-position="top"><el-form-item label="新年级名称"><el-input v-model="structure.grade_name" placeholder="例如：2026级" /></el-form-item><el-divider /><el-form-item label="所属年级"><el-select v-model="structure.grade_id"><el-option v-for="item in grades" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item><el-form-item label="新班级名称"><el-input v-model="structure.class_name" placeholder="例如：高级统计01班" /></el-form-item></el-form>
      <template #footer><el-button @click="structureDialog = false">取消</el-button><el-button type="primary" @click="createStructure">保存</el-button></template>
    </el-dialog>
  </AppShell>
</template>

