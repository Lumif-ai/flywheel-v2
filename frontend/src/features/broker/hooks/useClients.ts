import { useQuery } from '@tanstack/react-query'
import { fetchClients } from '../api'

export function useClients(params: { search?: string; page?: number; page_size?: number } = {}) {
  return useQuery({
    queryKey: ['broker-clients', params],
    queryFn: () => fetchClients(params),
  })
}
