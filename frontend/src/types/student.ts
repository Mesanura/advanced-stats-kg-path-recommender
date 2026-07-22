import type { AbilityDimension, KnowledgePoint } from './knowledge'
import type { MasteryAlgorithm } from './teacher'

export type MasteryStatus = 'unknown' | 'weak' | 'learning' | 'mastered'
export type PathNodeStatus = 'mastered' | 'recommended' | 'target'
export interface MasteryItem {
  knowledge_point_id: number
  name: string
  chapter: string
  dimension: AbilityDimension
  difficulty: number
  score: number
  status: MasteryStatus
  evidence_count: number
}
export interface PathNode {
  sequence: number
  stage: number
  knowledge_point_id: number
  name: string
  difficulty: number
  resource_url: string
  prerequisites: string[]
  status: PathNodeStatus
  mastery_score: number
}
export interface LearningPath {
  id: number
  student_id: number
  target_knowledge_point_id: number
  target_name: string
  algorithm: MasteryAlgorithm
  state: 'current' | 'stale'
  score: number
  stage_count: number
  length_exception: 'target_mastered' | 'shallow_target' | 'staged_dependency' | null
  created_at: string
  nodes: PathNode[]
}
export interface BehaviorFeedback {
  message: string
  knowledge_point_id: number
  mastery_score: number
  mastery_status: MasteryStatus
  paths_marked_stale: number
  updated_path: LearningPath | null
}
export interface StudentDashboardData {
  student_id: number
  student_no: string
  display_name: string
  classroom_name: string
  algorithm: MasteryAlgorithm
  average_mastery: number
  dimensions: { dimension: AbilityDimension; average: number }[]
  mastery_items: MasteryItem[]
  weak_points: string[]
  suggested_directions: AbilityDimension[]
  available_targets: KnowledgePoint[]
  current_paths: LearningPath[]
}
