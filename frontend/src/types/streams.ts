export interface WorkStream {
  id: string
  parent_id: string | null
  name: string
  description: string | null
  density_score: number
  entity_count: number
  entry_count: number
  meeting_count: number
  is_archived: boolean
  created_at: string
  updated_at: string
}

export interface SubThread {
  id: string
  name: string
  description: string | null
  density_score: number
  entry_count: number
  created_at: string
}

export interface WorkStreamEntity {
  id: string
  entity_id: string
  entity_name: string
  linked_at: string
}

export interface StreamEntry {
  id: string
  source: string
  content: string
  created_at: string
}

export interface WorkStreamDetail extends WorkStream {
  entities: WorkStreamEntity[]
  recent_entries: StreamEntry[]
  sub_threads: SubThread[]
}

export interface SourceAttribution {
  type: string
  name: string
}

export interface BriefingCard {
  card_type: 'meeting' | 'suggestion' | 'stale'
  title: string
  body: string
  entity_name: string | null
  stream_id: string | null
  sort_order: number
  metadata: Record<string, unknown>
  reason: string | null
  source_attribution: SourceAttribution[] | null
  suggestion_key: string | null
  auto_classified: boolean
  change_option: boolean
  classification_confidence: 'high' | 'medium' | 'low' | null
}

export interface KnowledgeHealth {
  level: 'strong' | 'growing' | 'early'
  avg_density: number
  stream_count: number
  total_entries: number
}

export interface BriefingResponse {
  greeting: string
  cards: BriefingCard[]
  knowledge_health: KnowledgeHealth
  nudge: null
}
