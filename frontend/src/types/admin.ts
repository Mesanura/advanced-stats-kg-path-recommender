import type { Role } from './auth'

export interface Grade { id: number; name: string }
export interface Classroom { id: number; grade_id: number; grade_name: string; name: string }
export interface ManagedUser {
  id: number
  username: string
  display_name: string
  role: Role
  is_active: boolean
  student_no: string | null
  classroom_id: number | null
  classroom_name: string | null
  classroom_ids: number[]
  classrooms: Classroom[]
}
export interface PaginatedUsers { items: ManagedUser[]; total: number; page: number; page_size: number }
