import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import { fetchRelationshipDetail, queryKeys } from '../api'

export function useRelationshipDetail(id: string) {
  const user = useAuthStore((s) => s.user)

  return useQuery({
    queryKey: queryKeys.relationships.detail(id),
    queryFn: () => fetchRelationshipDetail(id),
    enabled: !!id && !!user,
  })
}
