import { useQuery } from '@tanstack/react-query'
import { getDocumentRendition } from '../api'

interface DocumentRendition {
  url: string | null
  filename: string | null
  isLoading: boolean
  error: Error | null
}

export function useDocumentRendition(fileId: string | null | undefined): DocumentRendition {
  const { data, isLoading, error } = useQuery({
    queryKey: ['document-rendition', fileId],
    queryFn: () => getDocumentRendition(fileId!),
    enabled: !!fileId,
    staleTime: 45 * 60 * 1000,  // 45 minutes -- signed URLs expire after ~60min
    gcTime: 50 * 60 * 1000,     // keep in cache slightly longer than stale
    retry: 1,
  })

  return {
    url: data?.download_url ?? null,
    filename: data?.filename ?? null,
    isLoading,
    error: error as Error | null,
  }
}
