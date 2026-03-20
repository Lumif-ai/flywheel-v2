import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { PaginatedResponse, SkillRun, Skill } from '@/types/api'

export interface HistoryFilters {
  search?: string
  skill_name?: string
  status?: string
  date_from?: string
  date_to?: string
  offset: number
  limit: number
}

export function useHistory(filters: HistoryFilters) {
  return useQuery({
    queryKey: ['skill-runs', filters],
    queryFn: () =>
      api.get<PaginatedResponse<SkillRun>>('/skills/runs', {
        params: {
          offset: filters.offset,
          limit: filters.limit,
          skill_name: filters.skill_name || undefined,
          status: filters.status || undefined,
          search: filters.search || undefined,
          date_from: filters.date_from || undefined,
          date_to: filters.date_to || undefined,
        },
      }),
    placeholderData: keepPreviousData,
  })
}

export function useSkillRun(id: string | null) {
  return useQuery({
    queryKey: ['skill-run', id],
    queryFn: () => api.get<SkillRun>(`/skills/runs/${id}`),
    enabled: !!id,
  })
}

export function useSkillsList() {
  return useQuery({
    queryKey: ['skills'],
    queryFn: () => api.get<Skill[]>('/skills'),
    staleTime: 5 * 60 * 1000, // skills list rarely changes
  })
}
