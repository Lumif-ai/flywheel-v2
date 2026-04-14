import { api } from '@/lib/api'
import type {
  BrokerProject,
  BrokerProjectDetail,
  BrokerProjectListResponse,
  CarrierConfig,
  CarrierMatchResponse,
  CarrierQuote,
  ComparisonMatrix,
  CreateCarrierPayload,
  CreateProjectPayload,
  DashboardTasksResponse,
  DraftSolicitationsResponse,
  FollowupResponse,
  GapAnalysisResponse,
  GateCounts,
  ManualQuotePayload,
  RecommendationDraftResponse,
  UpdateCarrierPayload,
} from './types/broker'

export function fetchBrokerProjects(params: {
  limit?: number
  offset?: number
  status?: string
  search?: string
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

export function fetchCarriers(): Promise<CarrierConfig[]> {
  return api.get<CarrierConfig[]>('/broker/carriers')
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

export function editSolicitationDraft(quoteId: string, payload: { draft_subject?: string; draft_body?: string }): Promise<CarrierQuote> {
  return api.put<CarrierQuote>(`/broker/quotes/${quoteId}/draft`, payload)
}

export function approveSendSolicitation(quoteId: string): Promise<CarrierQuote> {
  return api.post<CarrierQuote>(`/broker/quotes/${quoteId}/approve-send`)
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
  projectId: string,
  data: { subject?: string; body?: string; recipient_email?: string }
): Promise<RecommendationDraftResponse> {
  return api.put<RecommendationDraftResponse>(`/broker/projects/${projectId}/recommendation-draft`, data)
}

export function sendRecommendation(projectId: string): Promise<{ status: string; sent_at: string; document_id: string }> {
  return api.post<{ status: string; sent_at: string; document_id: string }>(`/broker/projects/${projectId}/approve-send-recommendation`)
}
