import { useQuery, useMutation, useQueryClient, type Query } from '@tanstack/react-query'
import { api } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ProfileGroup {
  category: string
  icon: string
  label: string
  items: string[]
  entry_id: string
  raw_content: string
  count: number
}

export interface ProfileUploadedFile {
  id: string
  filename: string
  mimetype: string
  size_bytes: number
}

export interface CompanyProfile {
  company_name: string | null
  domain: string | null
  groups: ProfileGroup[]
  total_items: number
  last_updated: string | null
  uploaded_files: ProfileUploadedFile[]
  enrichment_status: string | null
}

// ---------------------------------------------------------------------------
// Fetch query
// ---------------------------------------------------------------------------

export function useCompanyProfile() {
  return useQuery({
    queryKey: ['company-profile'],
    queryFn: () => api.get<CompanyProfile>('/profile'),
    staleTime: 30_000,
    refetchInterval: (query: Query<CompanyProfile>) => {
      const status = query.state.data?.enrichment_status
      return (status === 'pending' || status === 'running') ? 3000 : false
    },
  })
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useUpdateCategory() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ entry_id, content }: { entry_id: string; content: string }) =>
      api.patch<{ group: ProfileGroup }>(`/profile/category/${entry_id}`, { content }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-profile'] })
    },
  })
}

export function useCreateCategory() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (body: { file_name: string; content: string; detail?: string }) =>
      api.post<{ group: ProfileGroup }>('/profile/category', body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-profile'] })
    },
  })
}

export function useLinkProfileFile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (file_id: string) =>
      api.post<{ success: boolean; file_id: string; filename: string }>('/profile/upload', {
        file_id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-profile'] })
    },
  })
}

export function useRetryEnrichment() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (fileId: string) =>
      api.post<{ success: boolean; enrichment_status: string }>('/profile/retry-enrichment', {
        file_id: fileId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-profile'] })
    },
  })
}
