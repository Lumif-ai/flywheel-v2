import { useQuery } from '@tanstack/react-query'
import { fetchCarriers } from '../api'
import type { CarrierConfig } from '../types/broker'

export function useCarriers() {
  return useQuery({
    queryKey: ['broker-carriers'],
    queryFn: () => fetchCarriers(),
    select: (data): CarrierConfig[] => data.items,
    staleTime: 30_000,
  })
}
