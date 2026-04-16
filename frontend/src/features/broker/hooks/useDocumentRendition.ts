import { useQuery } from '@tanstack/react-query'
import { getDocumentRendition } from '../api'

interface DocumentRendition {
  pdfData: Uint8Array | null
  filename: string | null
  isLoading: boolean
  error: Error | null
}

async function fetchPdfBytes(fileId: string): Promise<{ pdfData: Uint8Array; filename: string }> {
  const { download_url, filename } = await getDocumentRendition(fileId)
  const response = await fetch(download_url)
  if (!response.ok) {
    throw new Error(`Failed to fetch PDF: ${response.status}`)
  }
  const buffer = await response.arrayBuffer()
  return { pdfData: new Uint8Array(buffer), filename }
}

export function useDocumentRendition(fileId: string | null | undefined): DocumentRendition {
  const { data, isLoading, error } = useQuery({
    queryKey: ['document-rendition', fileId],
    queryFn: () => fetchPdfBytes(fileId!),
    enabled: !!fileId,
    staleTime: 45 * 60 * 1000,
    gcTime: 50 * 60 * 1000,
    retry: 1,
  })

  return {
    pdfData: data?.pdfData ?? null,
    filename: data?.filename ?? null,
    isLoading,
    error: error as Error | null,
  }
}
