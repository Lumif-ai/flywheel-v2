import { api } from '@/lib/api'
import type {
  RelationshipListItem,
  RelationshipDetailItem,
  SignalsResponse,
  AskResponse,
} from './types/relationships'

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const queryKeys = {
  relationships: {
    all: ['relationships'] as const,
    list: (type: string) => ['relationships', 'list', type] as const,
    detail: (id: string) => ['relationships', 'detail', id] as const,
  },
  signals: {
    all: ['signals'] as const,
  },
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export interface RelationshipListResponse {
  items: RelationshipListItem[]
  total: number
  offset: number
  limit: number
}

export function fetchRelationships(type: string): Promise<RelationshipListResponse> {
  return api.get<RelationshipListResponse>('/relationships/', {
    params: { type, limit: 100 },
  })
}

export function fetchRelationshipDetail(id: string): Promise<RelationshipDetailItem> {
  return api.get<RelationshipDetailItem>(`/relationships/${id}`)
}

export function fetchSignals(): Promise<SignalsResponse> {
  return api.get<SignalsResponse>('/signals/')
}

export function createNote(id: string, content: string): Promise<unknown> {
  return api.post(`/relationships/${id}/notes`, { content })
}

export function synthesize(id: string): Promise<unknown> {
  return api.post(`/relationships/${id}/synthesize`)
}

export function askRelationship(id: string, question: string): Promise<AskResponse> {
  return api.post<AskResponse>(`/relationships/${id}/ask`, { question })
}

export interface PrepResponse {
  run_id: string
  stream_url: string
}

export function triggerRelationshipPrep(
  id: string,
  meetingId?: string,
): Promise<PrepResponse> {
  return api.post<PrepResponse>(`/relationships/${id}/prep`, {
    meeting_id: meetingId ?? null,
  })
}
