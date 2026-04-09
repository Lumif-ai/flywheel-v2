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

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export interface UpdateAccountPayload {
  name?: string
  domain?: string | null
  status?: string
  stage?: string
  fit_score?: number | null
  fit_tier?: string | null
  intel?: Record<string, unknown>
  next_action_date?: string | null
  next_action_note?: string | null
}

export function updateAccount(id: string, payload: UpdateAccountPayload): Promise<unknown> {
  return api.patch(`/accounts/${id}`, payload)
}

export function updateRelationshipType(id: string, types: string[]): Promise<unknown> {
  return api.patch(`/relationships/${id}/type`, { types })
}

export interface UpdateContactPayload {
  name?: string
  email?: string | null
  title?: string | null
  role?: string | null
  linkedin_url?: string | null
  notes?: string | null
}

export function updateContact(
  accountId: string,
  contactId: string,
  payload: UpdateContactPayload,
): Promise<unknown> {
  return api.patch(`/accounts/${accountId}/contacts/${contactId}`, payload)
}

export interface CreateContactPayload {
  name: string
  email?: string | null
  title?: string | null
  role?: string | null
  linkedin_url?: string | null
  notes?: string | null
}

export function createContact(accountId: string, payload: CreateContactPayload): Promise<unknown> {
  return api.post(`/accounts/${accountId}/contacts`, payload)
}

export function deleteContact(accountId: string, contactId: string): Promise<unknown> {
  return api.delete(`/accounts/${accountId}/contacts/${contactId}`)
}
