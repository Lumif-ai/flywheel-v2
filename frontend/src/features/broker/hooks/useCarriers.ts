import { useQuery } from '@tanstack/react-query'
import { fetchCarriers } from '../api'

export function useCarriers() {
  return useQuery({
    queryKey: ['broker-carriers'],
    queryFn: () => fetchCarriers(),
    staleTime: 30_000,
  })
}
