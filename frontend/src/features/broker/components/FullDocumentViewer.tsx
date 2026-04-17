import { useState, useRef, useEffect, useCallback } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useDocumentRendition } from '../hooks/useDocumentRendition'

pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'

export interface FullDocumentViewerDoc {
  fileId: string
  name: string
}

/**
 * Controlled-props PDF viewer. State for activeFileId / currentPage / highlight intent
 * lives in the parent (AnalysisTab) so cross-panel navigation (clause card -> PDF page)
 * can coordinate the viewer. See spec §4.8 and .planning/phases/143-.../143-RESEARCH.md.
 */
interface FullDocumentViewerProps {
  documents: FullDocumentViewerDoc[]
  // Controlled by parent (Plan 02). Parent is AnalysisTab.
  activeFileId: string | null
  onFileChange: (fileId: string) => void
  currentPage: number
  onPageChange: (page: number) => void
  // Highlight intent from parent. Plan 02 reads .page to jump the viewer;
  // Plan 03 will consume .excerpt to render marks and call onHighlightClear.
  // `key` forces effects to re-fire on repeat clicks of the same card.
  highlight: { excerpt: string | null; page: number | null; key: string } | null
  onHighlightClear?: () => void
}

/** Shorten a filename for tab display: strip extension, clip to maxLen */
function shortenName(name: string, maxLen = 28): string {
  const stripped = name.replace(/\.[^.]+$/, '')
  if (stripped.length <= maxLen) return stripped
  return stripped.slice(0, maxLen - 1) + '…'
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

export function FullDocumentViewer({
  documents,
  activeFileId,
  onFileChange,
  currentPage,
  onPageChange,
  highlight: _highlight,
  onHighlightClear: _onHighlightClear,
}: FullDocumentViewerProps) {
  // NOTE: parent (AnalysisTab) owns activeFileId validity. If documents changes and
  // parent's activeFileId becomes stale, parent resets it. We just render "No PDF
  // available" gracefully when `url` is absent.

  const { url, isLoading, error } = useDocumentRendition(activeFileId)

  const [numPages, setNumPages] = useState(0)
  const [pageInputValue, setPageInputValue] = useState(String(currentPage))
  const [zoom, setZoom] = useState<ZoomLevel>('fit-width')
  const [containerWidth, setContainerWidth] = useState(0)

  // Reset doc-local state when switching documents.
  // CRITICAL: do NOT call onPageChange(1) here — the parent may have synchronously
  // set a target page via onFileChange + onPageChange (cross-doc clause click).
  // Resetting currentPage here would clobber the parent's target page. Instead, the
  // out-of-range guard lives inside onDocumentLoadSuccess below.
  useEffect(() => {
    setNumPages(0)
    setPageInputValue(String(currentPage))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFileId])

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

  // Keep page input in sync with currentPage from the parent
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
    // If the parent-set target page is out of range for this newly-loaded doc,
    // fall back to page 1. Otherwise preserve the parent's target page.
    if (currentPage > total || currentPage < 1) {
      onPageChange(1)
      setPageInputValue('1')
    } else {
      setPageInputValue(String(currentPage))
    }
  }

  function goToPage(page: number) {
    const clamped = Math.max(1, Math.min(page, numPages))
    onPageChange(clamped)
  }

  function handlePageInputCommit() {
    const parsed = parseInt(pageInputValue, 10)
    if (!isNaN(parsed)) {
      goToPage(parsed)
    } else {
      setPageInputValue(String(currentPage))
    }
  }

  const pageWidth = computedWidth()
  const needsHorizontalScroll = zoom !== 'fit-width'
  const showTabs = documents.length > 1

  return (
    <div className="flex flex-col h-full">
      {/* Document tabs */}
      {showTabs && (
        <div className="border-b bg-muted/30 px-2 py-1.5 flex items-center gap-1 overflow-x-auto">
          {documents.map((doc) => (
            <button
              key={doc.fileId}
              onClick={() => onFileChange(doc.fileId)}
              title={doc.name}
              className={`px-3 py-1.5 text-xs rounded-md whitespace-nowrap transition-colors ${
                doc.fileId === activeFileId
                  ? 'bg-background text-foreground font-medium shadow-sm'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted'
              }`}
            >
              {shortenName(doc.name)}
            </button>
          ))}
        </div>
      )}

      {/* Page area */}
      <div
        ref={containerRef}
        className={`flex-1 overflow-y-auto ${needsHorizontalScroll ? 'overflow-x-auto' : 'overflow-x-hidden'}`}
      >
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-full p-6 text-center">
            <p className="text-sm font-medium text-red-600 mb-2">Failed to load PDF</p>
            <p className="text-xs text-muted-foreground max-w-md break-words">{error.message}</p>
          </div>
        ) : !url ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-muted-foreground">No PDF available</p>
          </div>
        ) : (
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
        )}
      </div>

      {/* Navigation bar */}
      {url && numPages > 0 && (
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
