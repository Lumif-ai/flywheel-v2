import { api } from '@/lib/api'
import type {
  ContactListResponse,
  ContactParams,
  PipelineActivity,
  PipelineContact,
  PipelineDetail,
  PipelineListItem,
  PipelineParams,
  PipelineResponse,
  PipelineTaskItem,
  SavedView,
  TimelineResponse,
} from './types/pipeline'

export function fetchPipeline(params: PipelineParams): Promise<PipelineResponse> {
  // Serialize array params as comma-separated strings so backend can split them
  const serialized: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v) && v.length > 0) {
      serialized[k] = v.join(',')
    } else if (v !== undefined && v !== null && !Array.isArray(v)) {
      serialized[k] = v
    }
  }
  return api.get<PipelineResponse>('/pipeline/', { params: serialized })
}

export function patchPipelineEntry(
  id: string,
  data: Record<string, unknown>,
): Promise<PipelineListItem> {
  return api.patch<PipelineListItem>(`/pipeline/${id}`, data)
}

export async function createPipelineEntry(data: {
  name: string
  entity_type?: string
  domain?: string
}): Promise<{ entry: PipelineListItem; dedup_matched: boolean }> {
  // The backend returns { entry, dedup_matched } in the body for both 200 and 201
  return api.post<{ entry: PipelineListItem; dedup_matched: boolean }>('/pipeline/', data)
}

export function searchPipeline(q: string): Promise<PipelineListItem[]> {
  return api
    .get<{ items: PipelineListItem[] }>('/pipeline/search', { params: { q } })
    .then((res) => res.items)
}

export function fetchContacts(params: ContactParams): Promise<ContactListResponse> {
  const { enabled, ...apiParams } = params  // strip non-API param
  const serialized: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(apiParams)) {
    if (v !== undefined && v !== null) {
      serialized[k] = v
    }
  }
  return api.get<ContactListResponse>('/pipeline/contacts/', { params: serialized })
}

export function fetchPipelineDetail(id: string): Promise<PipelineDetail> {
  return api.get<PipelineDetail>(`/pipeline/${id}`)
}

export function retirePipelineEntry(id: string): Promise<PipelineDetail> {
  return api.post<PipelineDetail>(`/pipeline/${id}/retire`)
}

export function reactivatePipelineEntry(id: string): Promise<PipelineDetail> {
  return api.post<PipelineDetail>(`/pipeline/${id}/reactivate`)
}

export function fetchPipelineTimeline(
  id: string,
  params?: { offset?: number; limit?: number },
): Promise<TimelineResponse> {
  return api.get<TimelineResponse>(`/pipeline/${id}/timeline`, { params })
}

export function fetchPipelineTasks(pipelineEntryId: string): Promise<PipelineTaskItem[]> {
  return api
    .get<{ tasks: PipelineTaskItem[]; total: number }>('/tasks/', {
      params: { pipeline_entry_id: pipelineEntryId },
    })
    .then((res) => res.tasks)
}

/* ------------------------------------------------------------------ */
/* Saved Views                                                         */
/* ------------------------------------------------------------------ */

interface SavedViewRaw {
  id: string
  name: string
  filters: Record<string, unknown>
  sort: { col_id: string; sort: 'asc' | 'desc' } | null
  columns: unknown[] | null
  is_default: boolean
  position: number
  created_at: string
  updated_at: string
}

function mapSavedView(raw: SavedViewRaw): SavedView {
  return {
    id: raw.id,
    name: raw.name,
    filters: {
      stage: raw.filters.stage as string[] | undefined,
      fitTier: (raw.filters.fit_tier ?? raw.filters.fitTier) as string[] | undefined,
      relationshipType: (raw.filters.relationship_type ?? raw.filters.relationshipType) as string[] | undefined,
      source: raw.filters.source as string | undefined,
      view: raw.filters.view as SavedView['filters']['view'],
      search: raw.filters.search as string | undefined,
    },
    sort: raw.sort ? { colId: raw.sort.col_id, sort: raw.sort.sort } : null,
    columns: raw.columns,
    isDefault: raw.is_default,
    position: raw.position,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  }
}

export async function fetchSavedViews(): Promise<SavedView[]> {
  const raw = await api.get<SavedViewRaw[]>('/pipeline/views/')
  return raw.map(mapSavedView)
}

export async function createSavedView(data: {
  name: string
  filters: SavedView['filters']
  sort?: SavedView['sort']
  columns?: SavedView['columns']
}): Promise<SavedView> {
  const payload = {
    name: data.name,
    filters: {
      ...(data.filters.stage && { stage: data.filters.stage }),
      ...(data.filters.fitTier && { fit_tier: data.filters.fitTier }),
      ...(data.filters.relationshipType && { relationship_type: data.filters.relationshipType }),
      ...(data.filters.source && { source: data.filters.source }),
      ...(data.filters.view && { view: data.filters.view }),
      ...(data.filters.search && { search: data.filters.search }),
    },
    ...(data.sort && { sort: { col_id: data.sort.colId, sort: data.sort.sort } }),
    ...(data.columns && { columns: data.columns }),
  }
  const raw = await api.post<SavedViewRaw>('/pipeline/views/', payload)
  return mapSavedView(raw)
}

export async function updateSavedView(
  id: string,
  data: Partial<{ name: string; filters: SavedView['filters']; sort: SavedView['sort']; columns: SavedView['columns']; position: number }>,
): Promise<SavedView> {
  const raw = await api.patch<SavedViewRaw>(`/pipeline/views/${id}`, data)
  return mapSavedView(raw)
}

export async function deleteSavedView(id: string): Promise<void> {
  await api.delete(`/pipeline/views/${id}`)
}

/* ------------------------------------------------------------------ */
/* Contact Detail Panel — data layer                                   */
/* ------------------------------------------------------------------ */

export function fetchContactActivities(
  entryId: string,
  contactId: string,
): Promise<{ items: PipelineActivity[]; total: number }> {
  return api.get<{ items: PipelineActivity[]; total: number }>(
    `/pipeline/${entryId}/activities`,
    { params: { contact_id: contactId, limit: 100 } },
  )
}

export function patchContact(
  entryId: string,
  contactId: string,
  data: Record<string, unknown>,
): Promise<PipelineContact> {
  return api.patch<PipelineContact>(
    `/pipeline/${entryId}/contacts/${contactId}`,
    data,
  )
}

export function patchActivity(
  entryId: string,
  activityId: string,
  data: Record<string, unknown>,
): Promise<PipelineActivity> {
  return api.patch<PipelineActivity>(
    `/pipeline/${entryId}/activities/${activityId}`,
    data,
  )
}

export function createActivity(
  entryId: string,
  data: {
    type: string
    channel?: string
    status?: string
    subject?: string
    body_preview?: string
    contact_id?: string
    metadata_?: Record<string, unknown>
  },
): Promise<PipelineActivity> {
  return api.post<PipelineActivity>(`/pipeline/${entryId}/activities`, data)
}
