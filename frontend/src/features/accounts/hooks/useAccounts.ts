import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchAccounts } from '../api'
import type { AccountListParams } from '../types/accounts'

export function useAccounts(params: AccountListParams) {
  return useQuery({
    queryKey: ['accounts', params],
    queryFn: () => fetchAccounts(params),
    placeholderData: keepPreviousData,
  })
}
