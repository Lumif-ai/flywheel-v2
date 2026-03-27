import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import { fetchSignals, queryKeys } from '../api'

export function useSignals() {
  const user = useAuthStore((s) => s.user)

  return useQuery({
    queryKey: queryKeys.signals.all,
    queryFn: fetchSignals,
    enabled: !!user,
    staleTime: 30_000,  // 30s — sidebar badge counts don't need realtime precision
  })
}
