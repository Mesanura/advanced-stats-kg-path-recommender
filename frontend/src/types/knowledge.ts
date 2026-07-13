export type AbilityDimension =
  | 'statistics_foundation'
  | 'linear_models'
  | 'selection_regularization'
  | 'classification'
  | 'evaluation_ensemble'

export interface KnowledgePoint {
  id: number
  code: string
  name: string
  chapter: string
  dimension: AbilityDimension
  difficulty: number
  resource_url: string
  description: string | null
  is_active: boolean
}

export interface Prerequisite {
  knowledge_point_id: number
  prerequisite_id: number
  knowledge_point_name: string
  prerequisite_name: string
}

export interface KnowledgeGraphData {
  nodes: KnowledgePoint[]
  edges: Prerequisite[]
}

