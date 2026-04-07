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

export interface ProductTab {
  slug: string
  name: string
  icon: string
  sections: ProfileGroup[]
}

export interface CompanyProfile {
  company_name: string | null
  domain: string | null
  groups: ProfileGroup[]
  product_tabs: ProductTab[]
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
    staleTime: 10_000,
    refetchInterval: (query: Query<CompanyProfile>) => {
      const data = query.state.data
      const status = data?.enrichment_status
      // Poll while enrichment is running OR while we have uploaded files but no groups yet
      if (status === 'pending' || status === 'running') return 3000
      if (data && data.uploaded_files.length > 0 && data.groups.length === 0 && (!data.product_tabs || data.product_tabs.length === 0)) return 5000
      return false
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
