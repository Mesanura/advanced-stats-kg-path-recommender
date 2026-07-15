import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api } from '../api/client'
import type { CurrentUser, LoginResponse, Role, SessionResponse } from '../types/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)
  const initialized = ref(false)
  const isAuthenticated = computed(() => user.value !== null)

  async function loadCurrentUser(): Promise<void> {
    try {
      const response = await api.get<SessionResponse>('/auth/session')
      user.value = response.data.user
    } catch {
      user.value = null
    } finally {
      initialized.value = true
    }
  }

  async function login(username: string, password: string): Promise<Role> {
    const response = await api.post<LoginResponse>('/auth/login', { username, password })
    user.value = response.data.user
    initialized.value = true
    return response.data.user.role
  }

  async function logout(): Promise<void> {
    await api.post('/auth/logout')
    user.value = null
  }

  return { user, initialized, isAuthenticated, loadCurrentUser, login, logout }
})
