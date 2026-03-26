import { useQuery } from '@tanstack/react-query'
import { fetchAccountDetail } from '../api'

export function useAccountDetail(id: string) {
  return useQuery({
    queryKey: ['account', id],
    queryFn: () => fetchAccountDetail(id),
    enabled: !!id,
  })
}
