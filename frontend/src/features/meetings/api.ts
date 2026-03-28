import { api } from '@/lib/api'
import type { MeetingListItem, MeetingDetail, SyncResult } from './types/meetings'

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const queryKeys = {
  meetings: {
    all: ['meetings'] as const,
    list: (status?: string) => ['meetings', 'list', status ?? 'all'] as const,
    detail: (id: string) => ['meetings', 'detail', id] as const,
  },
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface MeetingListResponse {
  items: MeetingListItem[]
  total: number
  offset: number
  limit: number
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export function fetchMeetings(status?: string): Promise<MeetingListResponse> {
  return api.get<MeetingListResponse>('/meetings/', {
    params: status ? { status, limit: 50 } : { limit: 50 },
  })
}

export function fetchMeetingDetail(id: string): Promise<MeetingDetail> {
  return api.get<MeetingDetail>(`/meetings/${id}`)
}

export function syncMeetings(): Promise<SyncResult> {
  return api.post<SyncResult>('/meetings/sync')
}

export function processMeeting(id: string): Promise<{ run_id: string }> {
  return api.post<{ run_id: string }>(`/meetings/${id}/process`)
}
