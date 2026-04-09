import { api } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DocumentListItem {
  id: string
  title: string
  document_type: string
  mime_type: string
  file_size_bytes: number | null
  metadata: { contacts?: string[]; companies?: string[]; tags?: string[] }
  created_at: string
  skill_run_id: string | null
  tags: string[]
  account_id: string | null
  account_name: string | null
}

export interface DocumentDetail extends DocumentListItem {
  content_url: string
  output: string | null
  rendered_html: string | null
}

export interface DocumentListResponse {
  documents: DocumentListItem[]
  total: number
  next_cursor: string | null
}

export interface TagCountItem {
  tag: string
  count: number
}

export interface TypeCountItem {
  document_type: string
  count: number
}

export interface ShareResponse {
  share_token: string
  share_url: string
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export interface FetchDocumentsParams {
  document_type?: string
  account_id?: string
  tags?: string[]
  search?: string
  cursor?: string
  limit?: number
}

export async function fetchDocuments(
  params?: FetchDocumentsParams,
): Promise<DocumentListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.document_type) searchParams.set('document_type', params.document_type)
  if (params?.account_id) searchParams.set('account_id', params.account_id)
  if (params?.tags) {
    for (const tag of params.tags) searchParams.append('tags', tag)
  }
  if (params?.search) searchParams.set('search', params.search)
  if (params?.cursor) searchParams.set('cursor', params.cursor)
  if (params?.limit) searchParams.set('limit', String(params.limit))
  const qs = searchParams.toString()
  return api.get<DocumentListResponse>(`/documents/${qs ? `?${qs}` : ''}`)
}

export async function fetchDocumentTags(params?: {
  document_type?: string
  account_id?: string
  search?: string
}): Promise<TagCountItem[]> {
  return api.get<TagCountItem[]>('/documents/tags', { params })
}

export async function fetchDocumentCountsByType(params?: {
  account_id?: string
  tags?: string[]
  search?: string
}): Promise<TypeCountItem[]> {
  const searchParams = new URLSearchParams()
  if (params?.account_id) searchParams.set('account_id', params.account_id)
  if (params?.tags) {
    for (const tag of params.tags) searchParams.append('tags', tag)
  }
  if (params?.search) searchParams.set('search', params.search)
  const qs = searchParams.toString()
  return api.get<TypeCountItem[]>(`/documents/counts-by-type${qs ? `?${qs}` : ''}`)
}

export async function updateDocumentTags(
  id: string,
  body: { add?: string[]; remove?: string[] },
): Promise<{ tags: string[] }> {
  return api.patch<{ tags: string[] }>(`/documents/${id}/tags`, body)
}

export async function fetchDocument(id: string): Promise<DocumentDetail> {
  return api.get<DocumentDetail>(`/documents/${id}`)
}

export async function deleteDocument(id: string): Promise<void> {
  await api.delete(`/documents/${id}`)
}

export async function shareDocument(id: string): Promise<ShareResponse> {
  return api.post<ShareResponse>(`/documents/${id}/share`)
}

export async function fetchSharedDocument(
  shareToken: string,
): Promise<DocumentDetail> {
  const res = await fetch(`/api/v1/documents/shared/${shareToken}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({
      error: 'Unknown',
      message: res.statusText,
    }))
    throw new Error(body.message || 'Failed to load shared document')
  }
  return res.json()
}
