import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchBrokerProjects } from '../api'

interface UseBrokerProjectsParams {
  limit?: number
  offset?: number
  status?: string
  search?: string
  client_id?: string
}

export function useBrokerProjects(params: UseBrokerProjectsParams) {
  return useQuery({
    queryKey: ['broker-projects', params],
    queryFn: () => fetchBrokerProjects(params),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  })
}
