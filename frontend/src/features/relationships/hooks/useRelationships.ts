import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import { fetchRelationships, queryKeys } from '../api'
import type { RelationshipListItem } from '../types/relationships'

export function useRelationships(type: string) {
  const user = useAuthStore((s) => s.user)

  return useQuery<RelationshipListItem[]>({
    queryKey: queryKeys.relationships.list(type),
    queryFn: async () => {
      const res = await fetchRelationships(type)
      return res.items
    },
    enabled: !!user,
  })
}
