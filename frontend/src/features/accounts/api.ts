import { api } from '@/lib/api'
import type { AccountListParams, AccountListResponse, AccountDetail, TimelineResponse } from './types/accounts'

export function fetchAccounts(params: AccountListParams): Promise<AccountListResponse> {
  return api.get<AccountListResponse>('/accounts/', { params: params as Record<string, unknown> })
}

export function fetchAccountDetail(id: string): Promise<AccountDetail> {
  return api.get<AccountDetail>('/accounts/' + id)
}

export function fetchTimeline(accountId: string, params: { offset?: number; limit?: number }): Promise<TimelineResponse> {
  return api.get<TimelineResponse>('/accounts/' + accountId + '/timeline', { params: params as Record<string, unknown> })
}
