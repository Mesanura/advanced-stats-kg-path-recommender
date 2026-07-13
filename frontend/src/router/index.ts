import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import type { Role } from '../types/auth'

const rolePaths: Record<Role, string> = {
  student: '/student',
  teacher: '/teacher',
  admin: '/admin',
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
    {
      path: '/student',
      name: 'student',
      component: () => import('../views/RoleHomeView.vue'),
      props: { title: '学生学习中心', description: '个人掌握度与推荐路径将在这里呈现。' },
      meta: { role: 'student' },
    },
    {
      path: '/teacher',
      name: 'teacher',
      component: () => import('../views/RoleHomeView.vue'),
      props: { title: '教师工作台', description: '班级学情与知识图谱管理将在这里呈现。' },
      meta: { role: 'teacher' },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
      meta: { role: 'admin' },
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.initialized) await auth.loadCurrentUser()
  if (to.name === 'login' && auth.user) return rolePaths[auth.user.role]
  if (to.meta.role && !auth.user) return '/login'
  if (to.meta.role && auth.user?.role !== to.meta.role) return rolePaths[auth.user!.role]
  return true
})

export default router
