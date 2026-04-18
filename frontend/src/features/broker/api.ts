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
  DocumentZoneKind,
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

// Phase 150.1 Plan 03: migrated from deprecated POST /broker/projects/{id}/analyze
// to Pattern 3a /broker/extract/contract-analysis. Blocker-3 branch P3 — web UI
// cannot enqueue broker-* skills server-side because all broker-* skills are
// web_tier=3 and POST /skills/runs returns 422 for them ("requires the local
// Claude Code agent"). We therefore warm /extract to prove reachability +
// X-Flywheel-Skill + BYOK enforcement, and surface an explicit extract-only
// status. Full analysis runs in the user's local Claude Code via
// /broker:parse-contract. See .planning/phases/150.1-cc-as-brain-enforcement/
// 150.1-03-SUMMARY.md for the Blocker-3 pre-flight evidence.
// TODO(150.2): when a web_tier-safe broker enqueue path ships (e.g. a
// background job runner that invokes the same Pattern 3a helpers server-side),
// swap this for the full warm + enqueue pattern.
export function triggerAnalysis(projectId: string): Promise<{ status: string }> {
  return api
    .post<{ prompt: string; tool_schema: unknown; documents: unknown[]; metadata: Record<string, unknown> }>(
      `/broker/extract/contract-analysis`,
      { project_id: projectId },
      { headers: { 'X-Flywheel-Skill': 'broker-parse-contract' } },
    )
    .then(() => ({ status: 'extract-only' }))
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

// Phase 150.1 Plan 03: migrated from deprecated
// POST /broker/projects/{id}/draft-solicitations (which accepted a list of
// carriers and ran Anthropic server-side) to per-carrier Pattern 3a
// /broker/extract/solicitation-draft warming. Blocker-3 branch P3 — see
// triggerAnalysis comment above for the web_tier=3 rationale. Each carrier's
// draft is fetched as an extract-only payload so we can prove enforcement +
// BYOK + X-Flywheel-Skill emission. The empirical drafts are written via
// /broker:draft-emails in local Claude Code.
// TODO(150.2): replace with a warm + enqueue pattern once a web_tier-safe
// broker enqueue path ships.
export function draftSolicitations(projectId: string, carrierConfigIds: string[]): Promise<DraftSolicitationsResponse> {
  return Promise.all(
    carrierConfigIds.map((cid) =>
      api.post<{ prompt: string; tool_schema: unknown; documents: unknown[]; metadata: Record<string, unknown> }>(
        `/broker/extract/solicitation-draft`,
        { project_id: projectId, carrier_config_id: cid },
        { headers: { 'X-Flywheel-Skill': 'broker-draft-emails' } },
      ),
    ),
  ).then(() => ({ drafts: [], status: 'extract-only' }) as unknown as DraftSolicitationsResponse)
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

// Phase 150.1 Plan 03: migrated from deprecated POST /broker/quotes/{id}/extract
// to Pattern 3a /broker/extract/quote-extraction. Blocker-3 branch P3 — see
// triggerAnalysis comment above for the web_tier=3 rationale.
// TODO(150.2): replace with warm + enqueue once a web_tier-safe broker enqueue
// path ships.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function extractQuote(quoteId: string, _force?: boolean): Promise<{ status: string }> {
  return api
    .post<{ prompt: string; tool_schema: unknown; documents: unknown[]; metadata: Record<string, unknown> }>(
      `/broker/extract/quote-extraction`,
      { quote_id: quoteId },
      { headers: { 'X-Flywheel-Skill': 'broker-extract-quote' } },
    )
    .then(() => ({ status: 'extract-only' }))
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

// Phase 150.1 Plan 03: migrated from deprecated
// POST /broker/projects/{id}/draft-recommendation to Pattern 3a
// /broker/extract/recommendation-draft. Blocker-3 branch P3 — see
// triggerAnalysis comment above for the web_tier=3 rationale. The recipient
// email is not accepted by /extract (it's persisted later on /save), so we
// drop it here and let the local broker-draft-recommendation skill forward it
// through the save body.
// TODO(150.2): replace with warm + enqueue once a web_tier-safe broker enqueue
// path ships.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function draftRecommendation(projectId: string, _recipientEmail?: string): Promise<RecommendationDraftResponse> {
  return api
    .post<{ prompt: string; tool_schema: unknown; documents: unknown[]; metadata: Record<string, unknown> }>(
      `/broker/extract/recommendation-draft`,
      { project_id: projectId },
      { headers: { 'X-Flywheel-Skill': 'broker-draft-recommendation' } },
    )
    .then(() => ({ recommendation: null, status: 'extract-only' }) as unknown as RecommendationDraftResponse)
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

export function getDocumentRendition(fileId: string): Promise<{ download_url: string; filename: string }> {
  return api.get<{ download_url: string; filename: string }>(`/files/${fileId}/download`)
}

export async function uploadProjectDocuments(
  projectId: string,
  files: File[],
  documentType: DocumentZoneKind = 'requirements',
): Promise<{ documents: unknown[]; total: number }> {
  const token = useAuthStore.getState().token
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f))
  // Phase 145: single scalar document_type per request (research Pitfall 4).
  formData.append('document_type', documentType)
  const res = await fetch(`/api/v1/broker/projects/${projectId}/documents`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    // DO NOT set Content-Type — browser sets multipart/form-data boundary automatically
    body: formData,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * PATCH a single uploaded document's `document_type` (Phase 145 zone move).
 *
 * Backend (145-01) clears any `misrouted` flag as part of the update; caller
 * should invalidate the `broker-project` query on success so the UI re-renders
 * without the chip.
 */
export async function patchProjectDocument(
  projectId: string,
  fileId: string,
  documentType: DocumentZoneKind,
): Promise<{ file_id: string; document_type: DocumentZoneKind }> {
  const token = useAuthStore.getState().token
  const res = await fetch(
    `/api/v1/broker/projects/${projectId}/documents/${fileId}`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ document_type: documentType }),
    },
  )
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
