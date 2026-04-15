import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import type {
  BrokerClient,
  BrokerClientContact,
  BrokerClientListResponse,
  BrokerProject,
  BrokerProjectDetail,
  BrokerProjectListResponse,
  BrokerRecommendation,
  CarrierConfig,
  CarrierContact,
  CarrierMatchResponse,
  CarrierQuote,
  ComparisonMatrix,
  CreateCarrierContactPayload,
  CreateCarrierPayload,
  CreateClientContactPayload,
  CreateClientPayload,
  CreateProjectPayload,
  DashboardStats,
  DashboardTasksResponse,
  DraftSolicitationsResponse,
  FollowupResponse,
  GapAnalysisResponse,
  GateCounts,
  ManualQuotePayload,
  RecommendationDraftResponse,
  SolicitationDraft,
  SolicitationDraftResponse,
  UpdateCarrierPayload,
  UpdateContactPayload,
} from './types/broker'

export function fetchBrokerProjects(params: {
  limit?: number
  offset?: number
  status?: string
  search?: string
  client_id?: string
}): Promise<BrokerProjectListResponse> {
  const serialized: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) serialized[k] = v
  }
  return api.get<BrokerProjectListResponse>('/broker/projects', { params: serialized })
}

export function fetchGateCounts(): Promise<GateCounts> {
  return api.get<GateCounts>('/broker/gate-counts')
}

export function fetchDashboardStats(): Promise<DashboardStats> {
  return api.get<DashboardStats>('/broker/dashboard-stats')
}

export function fetchDashboardTasks(): Promise<DashboardTasksResponse> {
  return api.get<DashboardTasksResponse>('/broker/dashboard-tasks')
}

export function fetchBrokerProject(projectId: string): Promise<BrokerProjectDetail> {
  return api.get<BrokerProjectDetail>(`/broker/projects/${projectId}`)
}

export function createProject(payload: CreateProjectPayload): Promise<BrokerProject> {
  return api.post<BrokerProject>('/broker/projects', payload)
}

export function triggerAnalysis(projectId: string): Promise<{ status: string }> {
  return api.post<{ status: string }>(`/broker/projects/${projectId}/analyze`)
}

export function analyzeGaps(projectId: string): Promise<GapAnalysisResponse> {
  return api.post<GapAnalysisResponse>(`/broker/projects/${projectId}/analyze-gaps`)
}

export function fetchCarriers(): Promise<{ items: CarrierConfig[]; total: number }> {
  return api.get<{ items: CarrierConfig[]; total: number }>('/broker/carriers')
}

export function createCarrier(payload: CreateCarrierPayload): Promise<CarrierConfig> {
  return api.post<CarrierConfig>('/broker/carriers', payload)
}

export function updateCarrier(id: string, payload: UpdateCarrierPayload): Promise<CarrierConfig> {
  return api.put<CarrierConfig>(`/broker/carriers/${id}`, payload)
}

export function deleteCarrier(id: string): Promise<void> {
  return api.delete<void>(`/broker/carriers/${id}`)
}

export function fetchCarrierMatches(projectId: string): Promise<CarrierMatchResponse> {
  return api.get<CarrierMatchResponse>(`/broker/projects/${projectId}/carrier-matches`)
}

export function fetchProjectQuotes(projectId: string): Promise<CarrierQuote[]> {
  return api.get<CarrierQuote[]>(`/broker/projects/${projectId}/quotes`)
}

export function draftSolicitations(projectId: string, carrierConfigIds: string[]): Promise<DraftSolicitationsResponse> {
  return api.post<DraftSolicitationsResponse>(`/broker/projects/${projectId}/draft-solicitations`, { carrier_config_ids: carrierConfigIds })
}

export function editSolicitationDraft(draftId: string, payload: { subject?: string; body?: string }): Promise<SolicitationDraftResponse> {
  return api.put<SolicitationDraftResponse>(`/broker/solicitation-drafts/${draftId}`, payload)
}

export function approveSendSolicitation(draftId: string): Promise<SolicitationDraftResponse> {
  return api.post<SolicitationDraftResponse>(`/broker/solicitation-drafts/${draftId}/approve-send`)
}

export function fetchSolicitationDrafts(projectId: string): Promise<SolicitationDraft[]> {
  return api.get<SolicitationDraft[]>(`/broker/projects/${projectId}/solicitation-drafts`)
}

export function confirmPortalSubmission(quoteId: string): Promise<CarrierQuote> {
  return api.post<CarrierQuote>(`/broker/quotes/${quoteId}/portal-confirm`)
}

export function extractQuote(quoteId: string, force?: boolean): Promise<{ status: string }> {
  return api.post<{ status: string }>(`/broker/quotes/${quoteId}/extract${force ? '?force=true' : ''}`)
}

export function markQuoteReceived(quoteId: string): Promise<CarrierQuote> {
  return api.post<CarrierQuote>(`/broker/quotes/${quoteId}/mark-received`)
}

export function updateQuoteManual(quoteId: string, payload: ManualQuotePayload): Promise<CarrierQuote> {
  return api.put<CarrierQuote>(`/broker/quotes/${quoteId}`, payload)
}

export function fetchComparison(projectId: string): Promise<ComparisonMatrix> {
  return api.get<ComparisonMatrix>(`/broker/projects/${projectId}/comparison`)
}

export async function exportComparison(projectId: string, quoteIds?: string[]): Promise<void> {
  const token = useAuthStore.getState().token
  const res = await fetch(`/api/v1/broker/projects/${projectId}/export-comparison`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: quoteIds?.length ? JSON.stringify({ quote_ids: quoteIds }) : undefined,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || 'Export failed')
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const disposition = res.headers.get('Content-Disposition')
  const match = disposition?.match(/filename="?([^"]+)"?/)
  a.download = match?.[1] || `comparison-${projectId}.xlsx`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export function draftFollowups(projectId: string): Promise<FollowupResponse> {
  return api.post<FollowupResponse>(`/broker/projects/${projectId}/draft-followups`)
}

export function draftRecommendation(projectId: string, recipientEmail?: string): Promise<RecommendationDraftResponse> {
  return api.post<RecommendationDraftResponse>(
    `/broker/projects/${projectId}/draft-recommendation`,
    recipientEmail ? { recipient_email: recipientEmail } : undefined
  )
}

export function editRecommendation(
  recommendationId: string,
  data: { subject?: string; body?: string; recipient_email?: string }
): Promise<RecommendationDraftResponse> {
  return api.put<RecommendationDraftResponse>(`/broker/recommendations/${recommendationId}`, data)
}

export function sendRecommendation(recommendationId: string): Promise<{ status: string; sent_at: string; document_id: string }> {
  return api.post<{ status: string; sent_at: string; document_id: string }>(`/broker/recommendations/${recommendationId}/approve-send`)
}

export function fetchProjectRecommendations(projectId: string): Promise<{ items: BrokerRecommendation[] }> {
  return api.get<{ items: BrokerRecommendation[] }>(`/broker/projects/${projectId}/recommendations`)
}

export function approveProject(projectId: string): Promise<BrokerProjectDetail> {
  return api.post<BrokerProjectDetail>(`/broker/projects/${projectId}/approve`)
}

// --- Client API ---
export function fetchClients(params: {
  search?: string
  page?: number
  page_size?: number
} = {}): Promise<BrokerClientListResponse> {
  const serialized: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) serialized[k] = v
  }
  return api.get<BrokerClientListResponse>('/broker/clients', { params: serialized })
}

export function fetchClient(clientId: string): Promise<BrokerClient> {
  return api.get<BrokerClient>(`/broker/clients/${clientId}`)
}

export function createClient(payload: CreateClientPayload): Promise<BrokerClient> {
  return api.post<BrokerClient>('/broker/clients', payload)
}

export function updateClient(id: string, payload: Partial<CreateClientPayload>): Promise<BrokerClient> {
  return api.put<BrokerClient>(`/broker/clients/${id}`, payload)
}

export function deleteClient(id: string): Promise<void> {
  return api.delete<void>(`/broker/clients/${id}`)
}

// --- Client Contact API ---
export function fetchClientContacts(clientId: string): Promise<{ items: BrokerClientContact[]; total: number }> {
  return api.get(`/broker/clients/${clientId}/contacts`)
}

export function createClientContact(clientId: string, payload: CreateClientContactPayload): Promise<BrokerClientContact> {
  return api.post(`/broker/clients/${clientId}/contacts`, payload)
}

export function updateClientContact(clientId: string, contactId: string, payload: UpdateContactPayload): Promise<BrokerClientContact> {
  return api.put(`/broker/clients/${clientId}/contacts/${contactId}`, payload)
}

export function deleteClientContact(clientId: string, contactId: string): Promise<void> {
  return api.delete(`/broker/clients/${clientId}/contacts/${contactId}`)
}

// --- Carrier Contact API ---
export function fetchCarrierContacts(carrierId: string): Promise<{ items: CarrierContact[]; total: number }> {
  return api.get(`/broker/carriers/${carrierId}/contacts`)
}

export function createCarrierContact(carrierId: string, payload: CreateCarrierContactPayload): Promise<CarrierContact> {
  return api.post(`/broker/carriers/${carrierId}/contacts`, payload)
}

export function updateCarrierContact(carrierId: string, contactId: string, payload: UpdateContactPayload): Promise<CarrierContact> {
  return api.put(`/broker/carriers/${carrierId}/contacts/${contactId}`, payload)
}

export function deleteCarrierContact(carrierId: string, contactId: string): Promise<void> {
  return api.delete(`/broker/carriers/${carrierId}/contacts/${contactId}`)
}

export async function uploadProjectDocuments(
  projectId: string,
  files: File[]
): Promise<{ documents: unknown[]; total: number }> {
  const token = useAuthStore.getState().token
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f))
  const res = await fetch(`/api/v1/broker/projects/${projectId}/documents`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    // DO NOT set Content-Type — browser sets multipart/form-data boundary automatically
    body: formData,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
