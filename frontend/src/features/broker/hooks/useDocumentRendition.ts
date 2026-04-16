import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import { useFocusStore } from '@/stores/focus'

interface DocumentRendition {
  pdfData: Uint8Array | null
  filename: string | null
  isLoading: boolean
  error: Error | null
}

async function fetchPdfContent(fileId: string): Promise<{ pdfData: Uint8Array; filename: string }> {
  const token = useAuthStore.getState().token
  const focusId = useFocusStore.getState().activeFocus?.id
  const res = await fetch(`/api/v1/files/${fileId}/content`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(focusId ? { 'X-Focus-Id': focusId } : {}),
    },
  })
  if (!res.ok) {
    throw new Error(`Failed to fetch PDF: ${res.status}`)
  }
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = disposition.match(/filename="(.+?)"/)
  const filename = match?.[1] ?? 'document.pdf'
  const buffer = await res.arrayBuffer()
  return { pdfData: new Uint8Array(buffer), filename }
}

export function useDocumentRendition(fileId: string | null | undefined): DocumentRendition {
  const { data, isLoading, error } = useQuery({
    queryKey: ['document-rendition', fileId],
    queryFn: () => fetchPdfContent(fileId!),
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
