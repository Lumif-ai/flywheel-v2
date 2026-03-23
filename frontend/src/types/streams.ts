export interface DensityDetails {
  entity_count: number
  entry_count: number
  meeting_count: number
  people_count: number
  gap_count: number
  strong_dimensions: string[]
  gap_dimensions: string[]
}

export interface WorkStream {
  id: string
  parent_id: string | null
  name: string
  description: string | null
  density_score: number
  density_details: DensityDetails | null
  entity_count?: number
  entry_count?: number
  meeting_count?: number
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

export interface GrowthWeek {
  week_start: string
  density_score: number
  sources: { meetings: number; research: number; integrations: number }
  highlights: string[]
}

export interface GrowthResponse {
  status: 'ok' | 'too_early'
  message?: string
  weeks: GrowthWeek[]
}

export interface SourceAttribution {
  type: string
  name: string
}

export interface BriefingCard {
  card_type: 'meeting' | 'suggestion' | 'stale' | 'personal_gap'
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

export interface NudgeResponse {
  type: 'integration_connect' | 'knowledge_gap' | 'context_enrichment'
  key: string
  title: string
  body: string
  provider?: string
  action_url?: string
  action_label?: string
  stream_id?: string
  stream_name?: string
  entity_id?: string
  entity_name?: string
  has_research_action?: boolean
}

export interface BriefingResponse {
  greeting: string
  cards: BriefingCard[]
  knowledge_health: KnowledgeHealth
  nudge: NudgeResponse | null
}
