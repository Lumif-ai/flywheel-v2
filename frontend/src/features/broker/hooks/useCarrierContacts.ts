import { useQuery } from '@tanstack/react-query'
import { fetchCarrierContacts } from '../api'

export function useCarrierContacts(carrierId: string) {
  return useQuery({
    queryKey: ['broker-carrier-contacts', carrierId],
    queryFn: () => fetchCarrierContacts(carrierId),
    enabled: !!carrierId,
  })
}
