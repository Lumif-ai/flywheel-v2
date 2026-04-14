import { useQuery } from '@tanstack/react-query'
import { fetchClientContacts } from '../api'

export function useClientContacts(clientId: string) {
  return useQuery({
    queryKey: ['broker-client-contacts', clientId],
    queryFn: () => fetchClientContacts(clientId),
    enabled: !!clientId,
  })
}
