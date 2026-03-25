import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export type LifecycleState = 'S1' | 'S2' | 'S3' | 'S4' | 'S5'

interface LifecycleResponse {
  state: LifecycleState
  is_anonymous: boolean
  has_api_key: boolean
  run_count: number
  run_limit: number
  has_calendar: boolean
  has_email: boolean
  is_first_visit: boolean
}

/**
 * Fetch the user's lifecycle state (S1-S5) from /auth/lifecycle.
 *
 * S1 = First Magic (anonymous, first run)
 * S2 = Signup Moment (anonymous, approaching gate)
 * S3 = Exploring (authenticated, < 3 runs, no API key)
 * S4 = Power Threshold (authenticated, >= 3 runs, no API key)
 * S5 = Power User (authenticated, has API key)
 *
 * Default while loading: assume S1 (hide everything -- safest default).
 * Refetch interval: 60 seconds.
 */
export function useLifecycleState() {
  const { data, isLoading } = useQuery({
    queryKey: ['lifecycle-state'],
    queryFn: () => api.get<LifecycleResponse>('/auth/lifecycle'),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  return {
    state: data?.state ?? 'S1',
    isAnonymous: data?.is_anonymous ?? true,
    hasApiKey: data?.has_api_key ?? false,
    runCount: data?.run_count ?? 0,
    runLimit: data?.run_limit ?? 3,
    hasCalendar: data?.has_calendar ?? false,
    hasEmail: data?.has_email ?? false,
    isFirstVisit: data?.is_first_visit ?? false,
    isLoading,
  }
}
