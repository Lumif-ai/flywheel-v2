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
}

export interface DocumentDetail extends DocumentListItem {
  content_url: string
  output: string | null
  rendered_html: string | null
}

export interface DocumentListResponse {
  documents: DocumentListItem[]
  total: number
}

export interface ShareResponse {
  share_token: string
  share_url: string
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function fetchDocuments(params?: {
  document_type?: string
  limit?: number
  offset?: number
}): Promise<DocumentListResponse> {
  return api.get<DocumentListResponse>('/documents/', { params })
}

export async function fetchDocument(id: string): Promise<DocumentDetail> {
  return api.get<DocumentDetail>(`/documents/${id}`)
}

export async function shareDocument(id: string): Promise<ShareResponse> {
  return api.post<ShareResponse>(`/documents/${id}/share`)
}

/**
 * Fetch a shared document by its public share token.
 * This calls a public endpoint -- no auth token is sent.
 */
export async function fetchSharedDocument(
  shareToken: string,
): Promise<DocumentDetail> {
  // Public endpoint: call directly without auth headers
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
