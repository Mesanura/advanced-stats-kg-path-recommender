<script setup lang="ts">
import { Delete, Edit, Key, Plus, Search, View } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { api } from '../api/client'
import AppShell from '../components/AppShell.vue'
import KnowledgeManagement from '../components/KnowledgeManagement.vue'
import RecommendationSettings from '../components/RecommendationSettings.vue'
import type { Classroom, Grade, ManagedUser, PaginatedUsers } from '../types/admin'
import type { Role } from '../types/auth'

const users = ref<ManagedUser[]>([])
const activeSection = ref<'users' | 'knowledge' | 'settings'>('users')
const grades = ref<Grade[]>([])
const classrooms = ref<Classroom[]>([])
const total = ref(0)
const query = ref('')
const role = ref<Role | ''>('')
const userDialog = ref(false)
const structureDialog = ref(false)
const detailDrawer = ref(false)
const loading = ref(false)
const detailLoading = ref(false)
const saving = ref(false)
const editMode = ref(false)
const selectedUser = ref<ManagedUser>()
const form = reactive({
  username: '', display_name: '', password: 'Student@123456', role: 'student' as Role,
  student_no: '', classroom_id: undefined as number | undefined, classroom_ids: [] as number[],
})
const editForm = reactive({
  username: '', display_name: '', student_no: '', classroom_id: undefined as number | undefined,
  classroom_ids: [] as number[], is_active: true,
})
const structure = reactive({ grade_name: '', class_name: '', grade_id: undefined as number | undefined })
const roleText: Record<Role, string> = { student: '学生', teacher: '教师', admin: '管理员' }
const sectionNames = { users: '用户与班级', knowledge: '知识图谱', settings: '推荐策略' }
const defaultPasswords: Record<Role, string> = {
  student: 'Student@123456', teacher: 'Teacher@123456', admin: 'Admin@123456',
}
const classOptions = computed(() => classrooms.value.map(item => ({
  label: `${item.grade_name} · ${item.name}`, value: item.id,
})))

function errorDetail(error: unknown, fallback: string): string {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || fallback
}

function classLabel(item: Classroom): string {
  return `${item.grade_name} · ${item.name}`
}

function teacherClasses(user: ManagedUser): Classroom[] {
  if (user.classrooms?.length) return user.classrooms
  return user.classroom_ids
    .map(id => classrooms.value.find(item => item.id === id))
    .filter((item): item is Classroom => Boolean(item))
}

function classroomSummary(user: ManagedUser): string {
  if (user.role === 'student') return user.classroom_name || '未分配班级'
  if (user.role === 'teacher') {
    const assigned = teacherClasses(user)
    return assigned.length ? assigned.map(classLabel).join('、') : '未分配班级'
  }
  return '—'
}

async function loadUsers(): Promise<void> {
  loading.value = true
  try {
    const response = await api.get<PaginatedUsers>('/admin/users', {
      params: {
        query: query.value || undefined,
        role: role.value || undefined,
        page_size: 100,
      },
    })
    users.value = response.data.items
    total.value = response.data.total
  } finally {
    loading.value = false
  }
}

async function loadStructures(): Promise<void> {
  const [gradeResponse, classResponse] = await Promise.all([
    api.get<Grade[]>('/admin/grades'),
    api.get<Classroom[]>('/admin/classes'),
  ])
  grades.value = gradeResponse.data
  classrooms.value = classResponse.data
}

function openCreateUser(): void {
  Object.assign(form, {
    username: '', display_name: '', password: 'Student@123456', role: 'student',
    student_no: '', classroom_id: undefined, classroom_ids: [],
  })
  userDialog.value = true
}

async function createUser(): Promise<void> {
  const payload: Record<string, unknown> = {
    username: form.username,
    display_name: form.display_name,
    password: form.password,
    role: form.role,
  }
  if (form.role === 'student') {
    Object.assign(payload, { student_no: form.student_no, classroom_id: form.classroom_id })
  }
  if (form.role === 'teacher') payload.classroom_ids = form.classroom_ids
  try {
    await api.post('/admin/users', payload)
    ElMessage.success('账号已创建')
    userDialog.value = false
    await loadUsers()
  } catch (error: unknown) {
    ElMessage.error(errorDetail(error, '账号信息冲突或不完整'))
  }
}

async function openUser(user: ManagedUser): Promise<void> {
  selectedUser.value = user
  editMode.value = false
  detailDrawer.value = true
  detailLoading.value = true
  try {
    selectedUser.value = (await api.get<ManagedUser>(`/admin/users/${user.id}`)).data
  } catch (error: unknown) {
    ElMessage.error(errorDetail(error, '无法加载用户详情'))
  } finally {
    detailLoading.value = false
  }
}

function startEditing(): void {
  if (!selectedUser.value) return
  const user = selectedUser.value
  Object.assign(editForm, {
    username: user.username,
    display_name: user.display_name,
    student_no: user.student_no || '',
    classroom_id: user.classroom_id || undefined,
    classroom_ids: [...user.classroom_ids],
    is_active: user.is_active,
  })
  editMode.value = true
}

async function saveUser(): Promise<void> {
  if (!selectedUser.value) return
  const user = selectedUser.value
  const payload: Record<string, unknown> = {
    username: editForm.username,
    display_name: editForm.display_name,
    is_active: editForm.is_active,
  }
  if (user.role === 'student') {
    Object.assign(payload, {
      student_no: editForm.student_no,
      classroom_id: editForm.classroom_id,
    })
  }
  if (user.role === 'teacher') payload.classroom_ids = editForm.classroom_ids

  saving.value = true
  try {
    selectedUser.value = (await api.patch<ManagedUser>(`/admin/users/${user.id}`, payload)).data
    editMode.value = false
    ElMessage.success('用户信息已更新')
    await loadUsers()
  } catch (error: unknown) {
    ElMessage.error(errorDetail(error, '无法保存用户信息'))
  } finally {
    saving.value = false
  }
}

async function toggleUser(user: ManagedUser): Promise<void> {
  try {
    const updated = (await api.patch<ManagedUser>(`/admin/users/${user.id}`, {
      is_active: !user.is_active,
    })).data
    Object.assign(user, updated)
    if (selectedUser.value?.id === user.id) selectedUser.value = updated
    ElMessage.success(updated.is_active ? '账号已启用' : '账号已停用')
  } catch (error: unknown) {
    ElMessage.error(errorDetail(error, '无法更新账号状态'))
  }
}

async function resetPassword(user: ManagedUser): Promise<void> {
  try {
    await api.post(`/admin/users/${user.id}/reset-password`, {
      password: defaultPasswords[user.role],
    })
    ElMessage.success('密码已重置')
  } catch (error: unknown) {
    ElMessage.error(errorDetail(error, '无法重置密码'))
  }
}

async function removeUser(): Promise<void> {
  if (!selectedUser.value) return
  const user = selectedUser.value
  try {
    await ElMessageBox.confirm(
      `删除“${user.display_name}（${user.username}）”及其关联数据？此操作无法撤销。`,
      '确认删除用户',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await api.delete(`/admin/users/${user.id}`)
    detailDrawer.value = false
    selectedUser.value = undefined
    ElMessage.success('用户已删除')
    await loadUsers()
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(errorDetail(error, '无法删除用户'))
  }
}

async function createStructure(): Promise<void> {
  if (structure.grade_name) await api.post('/admin/grades', { name: structure.grade_name })
  if (structure.class_name && structure.grade_id) {
    await api.post('/admin/classes', {
      name: structure.class_name,
      grade_id: structure.grade_id,
    })
  }
  ElMessage.success('年级或班级已创建')
  structureDialog.value = false
  await loadStructures()
}

onMounted(async () => {
  await Promise.all([loadUsers(), loadStructures()])
})
</script>

<template>
  <AppShell :section="sectionNames[activeSection]">
    <div class="teacher-section-tabs">
      <el-segmented
        v-model="activeSection"
        :options="[
          { label: '用户与班级', value: 'users' },
          { label: '知识图谱', value: 'knowledge' },
          { label: '推荐策略', value: 'settings' },
        ]"
      />
    </div>
    <KnowledgeManagement v-if="activeSection === 'knowledge'" />
    <RecommendationSettings v-else-if="activeSection === 'settings'" />
    <template v-else>
      <main class="page-content">
        <div class="page-title-row">
          <div>
            <p class="section-label">SYSTEM ADMINISTRATION</p>
            <h1>用户与教学组织</h1>
            <p>共 {{ total }} 个账号，{{ grades.length }} 个年级，{{ classrooms.length }} 个班级</p>
          </div>
          <div class="page-actions">
            <el-button @click="structureDialog = true">年级 / 班级</el-button>
            <el-button type="primary" :icon="Plus" @click="openCreateUser">新增账号</el-button>
          </div>
        </div>

        <div class="filter-bar">
          <el-input
            v-model="query"
            clearable
            placeholder="姓名或用户名"
            :prefix-icon="Search"
            @keyup.enter="loadUsers"
            @clear="loadUsers"
          />
          <el-select v-model="role" clearable placeholder="全部角色" @change="loadUsers">
            <el-option
              v-for="(label, key) in roleText"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
          <el-button @click="loadUsers">查询</el-button>
        </div>

        <el-table v-loading="loading" :data="users" class="data-table">
          <el-table-column prop="display_name" label="姓名" min-width="120" />
          <el-table-column prop="username" label="用户名 / 学号" min-width="150" />
          <el-table-column label="角色" width="100">
            <template #default="scope">
              <el-tag effect="plain">{{ roleText[scope.row.role as Role] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="班级" min-width="240">
            <template #default="scope">
              <div v-if="scope.row.role === 'teacher' && teacherClasses(scope.row).length" class="admin-class-list">
                <el-tag
                  v-for="item in teacherClasses(scope.row)"
                  :key="item.id"
                  size="small"
                  type="info"
                  effect="plain"
                >
                  {{ classLabel(item) }}
                </el-tag>
              </div>
              <span v-else>{{ classroomSummary(scope.row) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="scope">
              <span :class="['status-dot', scope.row.is_active ? 'online' : 'offline']" />
              {{ scope.row.is_active ? '启用' : '停用' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="170" align="right">
            <template #default="scope">
              <el-button link :icon="View" @click="openUser(scope.row)">详情</el-button>
              <el-button link @click="toggleUser(scope.row)">
                {{ scope.row.is_active ? '停用' : '启用' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </main>

      <el-dialog v-model="userDialog" title="新增账号" width="520px">
        <el-form label-position="top">
          <div class="form-grid">
            <el-form-item label="姓名"><el-input v-model="form.display_name" /></el-form-item>
            <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
          </div>
          <el-form-item label="角色">
            <el-segmented
              v-model="form.role"
              :options="[
                { label: '学生', value: 'student' },
                { label: '教师', value: 'teacher' },
                { label: '管理员', value: 'admin' },
              ]"
            />
          </el-form-item>
          <template v-if="form.role === 'student'">
            <div class="form-grid">
              <el-form-item label="学号"><el-input v-model="form.student_no" /></el-form-item>
              <el-form-item label="班级">
                <el-select v-model="form.classroom_id">
                  <el-option v-for="item in classOptions" :key="item.value" v-bind="item" />
                </el-select>
              </el-form-item>
            </div>
          </template>
          <el-form-item v-if="form.role === 'teacher'" label="负责班级">
            <el-select v-model="form.classroom_ids" multiple>
              <el-option v-for="item in classOptions" :key="item.value" v-bind="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="初始密码">
            <el-input v-model="form.password" type="password" show-password />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="userDialog = false">取消</el-button>
          <el-button type="primary" @click="createUser">创建</el-button>
        </template>
      </el-dialog>

      <el-drawer
        v-model="detailDrawer"
        v-loading="detailLoading"
        class="admin-user-drawer"
        :size="560"
        :title="selectedUser ? `${selectedUser.display_name} · 用户详情` : '用户详情'"
      >
        <template v-if="selectedUser && !editMode">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="姓名">{{ selectedUser.display_name }}</el-descriptions-item>
            <el-descriptions-item label="用户名">{{ selectedUser.username }}</el-descriptions-item>
            <el-descriptions-item label="角色">{{ roleText[selectedUser.role] }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="selectedUser.is_active ? 'success' : 'info'" effect="plain">
                {{ selectedUser.is_active ? '启用' : '停用' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item v-if="selectedUser.role === 'student'" label="学号">
              {{ selectedUser.student_no }}
            </el-descriptions-item>
            <el-descriptions-item v-if="selectedUser.role === 'student'" label="所属班级">
              {{ selectedUser.classroom_name }}
            </el-descriptions-item>
            <el-descriptions-item v-if="selectedUser.role === 'teacher'" label="负责班级">
              <div v-if="teacherClasses(selectedUser).length" class="admin-class-list">
                <el-tag
                  v-for="item in teacherClasses(selectedUser)"
                  :key="item.id"
                  type="info"
                  effect="plain"
                >
                  {{ classLabel(item) }}
                </el-tag>
              </div>
              <span v-else>未分配班级</span>
            </el-descriptions-item>
          </el-descriptions>
        </template>

        <el-form v-else-if="selectedUser" label-position="top" class="drawer-form">
          <div class="form-grid">
            <el-form-item label="姓名"><el-input v-model="editForm.display_name" /></el-form-item>
            <el-form-item label="用户名"><el-input v-model="editForm.username" /></el-form-item>
          </div>
          <div class="form-grid">
            <el-form-item label="角色">
              <el-input :model-value="roleText[selectedUser.role]" disabled />
            </el-form-item>
            <el-form-item label="账号状态">
              <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="停用" />
            </el-form-item>
          </div>
          <template v-if="selectedUser.role === 'student'">
            <div class="form-grid">
              <el-form-item label="学号"><el-input v-model="editForm.student_no" /></el-form-item>
              <el-form-item label="所属班级">
                <el-select v-model="editForm.classroom_id">
                  <el-option v-for="item in classOptions" :key="item.value" v-bind="item" />
                </el-select>
              </el-form-item>
            </div>
          </template>
          <el-form-item v-if="selectedUser.role === 'teacher'" label="负责班级">
            <el-select v-model="editForm.classroom_ids" multiple>
              <el-option v-for="item in classOptions" :key="item.value" v-bind="item" />
            </el-select>
          </el-form-item>
        </el-form>

        <template #footer>
          <div v-if="selectedUser && !editMode" class="drawer-footer">
            <el-button type="danger" plain :icon="Delete" @click="removeUser">删除用户</el-button>
            <div>
              <el-button :icon="Key" @click="resetPassword(selectedUser)">重置密码</el-button>
              <el-button type="primary" :icon="Edit" @click="startEditing">编辑</el-button>
            </div>
          </div>
          <div v-else class="drawer-footer drawer-footer-end">
            <el-button @click="editMode = false">取消</el-button>
            <el-button type="primary" :loading="saving" @click="saveUser">保存修改</el-button>
          </div>
        </template>
      </el-drawer>

      <el-dialog v-model="structureDialog" title="年级与班级" width="500px">
        <el-form label-position="top">
          <el-form-item label="新年级名称">
            <el-input v-model="structure.grade_name" placeholder="例如：2026级" />
          </el-form-item>
          <el-divider />
          <el-form-item label="所属年级">
            <el-select v-model="structure.grade_id">
              <el-option v-for="item in grades" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="新班级名称">
            <el-input v-model="structure.class_name" placeholder="例如：高级统计01班" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="structureDialog = false">取消</el-button>
          <el-button type="primary" @click="createStructure">保存</el-button>
        </template>
      </el-dialog>
    </template>
  </AppShell>
</template>
