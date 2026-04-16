import { useState, useRef, useEffect, useCallback } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useDocumentRendition } from '../hooks/useDocumentRendition'

pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'

interface FullDocumentViewerProps {
  fileId: string
  filename?: string
  onError?: () => void
}

type ZoomLevel = 'fit-width' | '75' | '100' | '125'

const ZOOM_OPTIONS: { value: ZoomLevel; label: string }[] = [
  { value: 'fit-width', label: 'Fit Width' },
  { value: '75', label: '75%' },
  { value: '100', label: '100%' },
  { value: '125', label: '125%' },
]

/** Standard US Letter width in PDF points */
const PDF_LETTER_WIDTH = 612

export function FullDocumentViewer({ fileId, filename, onError }: FullDocumentViewerProps) {
  const { url, isLoading, error } = useDocumentRendition(fileId)

  const [currentPage, setCurrentPage] = useState(1)
  const [numPages, setNumPages] = useState(0)
  const [pageInputValue, setPageInputValue] = useState('1')
  const [zoom, setZoom] = useState<ZoomLevel>('fit-width')
  const [containerWidth, setContainerWidth] = useState(0)

  const containerRef = useRef<HTMLDivElement>(null)

  // Track container width for fit-width zoom
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width)
      }
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  // Keep page input in sync with currentPage
  useEffect(() => {
    setPageInputValue(String(currentPage))
  }, [currentPage])

  const computedWidth = useCallback(() => {
    switch (zoom) {
      case 'fit-width':
        return Math.max(containerWidth - 32, 200) // 16px padding each side
      case '75':
        return PDF_LETTER_WIDTH * 0.75
      case '100':
        return PDF_LETTER_WIDTH
      case '125':
        return PDF_LETTER_WIDTH * 1.25
    }
  }, [zoom, containerWidth])

  function onDocumentLoadSuccess({ numPages: total }: { numPages: number }) {
    setNumPages(total)
    setCurrentPage(1)
    setPageInputValue('1')
  }

  function goToPage(page: number) {
    const clamped = Math.max(1, Math.min(page, numPages))
    setCurrentPage(clamped)
  }

  function handlePageInputCommit() {
    const parsed = parseInt(pageInputValue, 10)
    if (!isNaN(parsed)) {
      goToPage(parsed)
    } else {
      setPageInputValue(String(currentPage))
    }
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Error state — notify parent to fall back to excerpt view
  useEffect(() => {
    if (!isLoading && (error || !url)) {
      onError?.()
    }
  }, [isLoading, error, url, onError])

  if (error || !url) {
    return null
  }

  const pageWidth = computedWidth()
  const needsHorizontalScroll = zoom !== 'fit-width'

  return (
    <div className="flex flex-col h-full">
      {/* Header with filename */}
      {filename && (
        <div className="px-4 py-2 border-b bg-muted/30">
          <p className="text-xs font-medium text-muted-foreground truncate">
            {filename}
          </p>
        </div>
      )}

      {/* Page area */}
      <div
        ref={containerRef}
        className={`flex-1 overflow-y-auto ${needsHorizontalScroll ? 'overflow-x-auto' : 'overflow-x-hidden'}`}
      >
        <div className={needsHorizontalScroll ? 'min-w-max' : ''}>
          <div className="flex justify-center py-4">
            <Document
              file={url}
              onLoadSuccess={onDocumentLoadSuccess}
              loading={
                <div className="flex items-center justify-center py-20">
                  <Loader2 className="size-6 animate-spin text-muted-foreground" />
                </div>
              }
              error={
                <div className="flex items-center justify-center py-20">
                  <p className="text-sm text-muted-foreground">
                    Failed to render PDF
                  </p>
                </div>
              }
            >
              <Page
                pageNumber={currentPage}
                width={pageWidth}
                renderTextLayer={true}
                renderAnnotationLayer={true}
                loading={
                  <div
                    className="flex items-center justify-center bg-white"
                    style={{ width: pageWidth, height: pageWidth * 1.3 }}
                  >
                    <Loader2 className="size-5 animate-spin text-muted-foreground" />
                  </div>
                }
              />
            </Document>
          </div>
        </div>
      </div>

      {/* Navigation bar */}
      {numPages > 0 && (
        <div className="border-t bg-muted/30 px-4 py-2 flex items-center justify-between">
          {/* Page navigation */}
          <div className="flex items-center gap-1.5">
            <Button
              variant="ghost"
              size="icon-xs"
              disabled={currentPage <= 1}
              onClick={() => goToPage(currentPage - 1)}
            >
              <ChevronLeft className="size-4" />
            </Button>

            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <input
                type="text"
                value={pageInputValue}
                onChange={(e) => setPageInputValue(e.target.value)}
                onBlur={handlePageInputCommit}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handlePageInputCommit()
                }}
                className="w-8 h-5 text-center text-xs border rounded bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <span>of {numPages}</span>
            </div>

            <Button
              variant="ghost"
              size="icon-xs"
              disabled={currentPage >= numPages}
              onClick={() => goToPage(currentPage + 1)}
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>

          {/* Zoom controls */}
          <div className="flex items-center gap-0.5">
            {ZOOM_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setZoom(opt.value)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  zoom === opt.value
                    ? 'bg-foreground/10 text-foreground font-medium'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
