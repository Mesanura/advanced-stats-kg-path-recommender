export type Role = 'student' | 'teacher' | 'admin'

export interface CurrentUser {
  id: number
  username: string
  display_name: string
  role: Role
}

export interface LoginResponse {
  user: CurrentUser
}

