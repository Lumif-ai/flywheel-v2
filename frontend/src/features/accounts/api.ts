import { api } from '@/lib/api'
import type { AccountListParams, AccountListResponse } from './types/accounts'

export function fetchAccounts(params: AccountListParams): Promise<AccountListResponse> {
  return api.get<AccountListResponse>('/accounts/', { params: params as Record<string, unknown> })
}
