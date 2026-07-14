import type { AbilityDimension } from './knowledge'

export type MasteryAlgorithm = 'rule' | 'bkt'
export interface ScopeClass { id: number; name: string; grade_id: number; grade_name: string }
export interface TeacherScope { classes: ScopeClass[] }
export interface KnowledgeStatistic {
  knowledge_point_id: number
  name: string
  average: number
  minimum: number
  maximum: number
  distribution: { unknown: number; weak: number; learning: number; mastered: number }
}
export interface TeacherOverviewData {
  algorithm: MasteryAlgorithm
  student_count: number
  average_mastery: number
  dimensions: { dimension: AbilityDimension; average: number }[]
  knowledge_points: KnowledgeStatistic[]
  weak_top5: KnowledgeStatistic[]
  attention_students: {
    student_id: number
    student_no: string
    display_name: string
    classroom_name: string
    average: number
    weak_count: number
  }[]
}

