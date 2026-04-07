import { useQuery } from '@tanstack/react-query'
import { fetchContactActivities } from '../api'

export function useContactActivities(
  entryId: string | null,
  contactId: string | null,
) {
  return useQuery({
    queryKey: ['contact-activities', contactId],
    queryFn: () => fetchContactActivities(entryId!, contactId!),
    enabled: !!entryId && !!contactId,
  })
}
