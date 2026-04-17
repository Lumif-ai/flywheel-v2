import { useState, useRef, useEffect, useCallback } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { useDocumentRendition } from '../hooks/useDocumentRendition'
import {
  shouldHighlightItem,
  escapeHtml,
  findPageContainingExcerpt,
} from '../utils/excerptMatch'

pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'

export interface FullDocumentViewerDoc {
  fileId: string
  name: string
}

/**
 * Controlled PDF viewer (Phase 143 / SPEC §4.8).
 *
 * Highlight rendering uses react-pdf's `customTextRenderer` prop — this is an
 * explicit override of SPEC §4.7's DOM-post-render approach, documented in
 * 143-RESEARCH.md. customTextRenderer is the officially documented pattern and
 * auto-reruns on page/excerpt change, eliminating the need for manual DOM
 * manipulation in `onRenderTextLayerSuccess`.
 *
 * Known limitation: phrases that span multiple pdfjs text items cannot match
 * per-item — bidirectional substring match achieves ~90% visual coverage
 * (GH wojtekmaj/react-pdf#306). Sub-item excerpt highlighting is out of scope
 * for Phase 143.
 *
 * Decay semantics: the 5s timer and scroll-away IntersectionObserver both
 * trigger `onHighlightClear` which clears ONLY the highlight state. The active
 * card state (activeCoverageId in AnalysisTab) is independent and persists.
 * This viewer never clears active card state — that's a parent concern.
 *
 * Guard on `highlight?.excerpt` (not `highlight`): a page-only jump (excerpt=null,
 * scanned-PDF graceful degradation) MUST NOT schedule decay machinery because no
 * <mark> was ever rendered. The page jump + active card state give the user
 * enough feedback in that case.
 */
interface FullDocumentViewerProps {
  documents: FullDocumentViewerDoc[]
  // Controlled by parent (Plan 02). Parent is AnalysisTab.
  activeFileId: string | null
  onFileChange: (fileId: string) => void
  currentPage: number
  onPageChange: (page: number) => void
  // Highlight intent from parent. Plan 03 consumes .excerpt via customTextRenderer
  // and calls onHighlightClear from a 5s timer + IntersectionObserver.
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
  highlight,
  onHighlightClear,
}: FullDocumentViewerProps) {
  // NOTE: parent (AnalysisTab) owns activeFileId validity. If documents changes and
  // parent's activeFileId becomes stale, parent resets it. We just render "No PDF
  // available" gracefully when `url` is absent.

  const { url, isLoading, error } = useDocumentRendition(activeFileId)

  const [numPages, setNumPages] = useState(0)
  const [pageInputValue, setPageInputValue] = useState(String(currentPage))
  const [zoom, setZoom] = useState<ZoomLevel>('fit-width')
  const [containerWidth, setContainerWidth] = useState(0)
  // pdfjs proxy captured from <Document onLoadSuccess> for NAV-04 all-pages search.
  // Typed as PDFDocumentProxy (not any) — top-level pdfjs-dist re-exports this type.
  const [pdfProxy, setPdfProxy] = useState<PDFDocumentProxy | null>(null)
  // Monotonic render tick so the scroll-away IntersectionObserver effect re-attaches
  // on each fresh text-layer render (new page, new highlight, new pdfjs rasterization).
  const [textLayerTick, setTextLayerTick] = useState(0)

  // Reset doc-local state when switching documents.
  // CRITICAL: do NOT call onPageChange(1) here — the parent may have synchronously
  // set a target page via onFileChange + onPageChange (cross-doc clause click).
  // Resetting currentPage here would clobber the parent's target page. Instead, the
  // out-of-range guard lives inside onDocumentLoadSuccess below.
  useEffect(() => {
    setNumPages(0)
    setPageInputValue(String(currentPage))
    setPdfProxy(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFileId])

  // `containerRef` plays two roles: (a) width source for ResizeObserver (fit-width zoom),
  // (b) scroll viewport for the IntersectionObserver that detects "scroll-away from mark".
  // `pageContainerRef` scopes DOM queries (`mark.excerpt-highlight`) to the current <Page>.
  const containerRef = useRef<HTMLDivElement>(null)
  const pageContainerRef = useRef<HTMLDivElement | null>(null)

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

  function onDocumentLoadSuccess(pdf: PDFDocumentProxy): void {
    setNumPages(pdf.numPages)
    setPdfProxy(pdf) // expose full proxy for NAV-04 all-pages search
    // If the parent-set target page is out of range for this newly-loaded doc,
    // fall back to page 1. Otherwise preserve the parent's target page.
    if (currentPage > pdf.numPages || currentPage < 1) {
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

  // ---- Highlight rendering (Phase 143 NAV-02) ----
  // Memoized textRenderer: react-pdf calls this per text-item. The return value is
  // spliced into the text layer as HTML, so we MUST escape < > & on EVERY code path
  // (including the non-highlight branch) to prevent XSS from malicious PDF content.
  // Deps are ONLY [highlight?.excerpt] — NOT [highlight] — so the renderer doesn't
  // re-create when .key or .page alone changes (those don't affect the per-item decision).
  const textRenderer = useCallback(
    (textItem: { str: string; itemIndex: number }): string => {
      if (!highlight?.excerpt) return escapeHtml(textItem.str)
      if (shouldHighlightItem(textItem.str, highlight.excerpt)) {
        return `<mark class="excerpt-highlight">${escapeHtml(textItem.str)}</mark>`
      }
      return escapeHtml(textItem.str)
    },
    [highlight?.excerpt],
  )

  // onRenderTextLayerSuccess — fires after the text layer DOM is in place, so
  // `querySelector('mark')` is guaranteed to see the marks produced by textRenderer.
  // Also bumps textLayerTick so the scroll-away observer effect re-attaches on each
  // fresh render (page change, highlight change, re-click on same card).
  const handleTextLayerRendered = useCallback(() => {
    setTextLayerTick((n) => n + 1)
    if (!highlight?.excerpt) return
    const root = pageContainerRef.current
    if (!root) return
    const firstMark = root.querySelector<HTMLElement>('mark.excerpt-highlight')
    if (firstMark) {
      // block: 'center' places the mark mid-viewport; smooth for UX.
      firstMark.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
    // Depend on highlight.key so a re-click on the SAME excerpt still re-fires scroll.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlight?.excerpt, highlight?.key])

  // 5-second auto-clear (NAV-03 timer branch).
  // Guard on highlight?.excerpt (not just highlight) — page-only jumps (excerpt=null,
  // scanned-PDF path) must NOT schedule a decay timer: there's no visible highlight
  // to decay, and the state churn of clearing a non-visual highlight is wasteful.
  useEffect(() => {
    if (!highlight?.excerpt) return
    const t = window.setTimeout(() => {
      onHighlightClear?.()
    }, 5000)
    return () => window.clearTimeout(t)
    // Depend on highlight.key so re-click resets the 5s window.
  }, [highlight?.key, highlight?.excerpt, onHighlightClear])

  // Scroll-away clear (NAV-03 scroll-away branch).
  // Runs AFTER each text-layer render (keyed on textLayerTick) so the mark is in the DOM.
  // Same excerpt guard as the timer — no excerpt means no <mark> was ever rendered.
  // 500ms attach delay mitigates Pitfall 7: smooth-scrollIntoView would otherwise fire
  // a spurious "not intersecting" on initial mount before the scroll completes.
  useEffect(() => {
    if (!highlight?.excerpt) return
    const root = pageContainerRef.current
    const scroller = containerRef.current // the overflow-y-auto viewport
    if (!root || !scroller) return
    const firstMark = root.querySelector<HTMLElement>('mark.excerpt-highlight')
    if (!firstMark) return

    let observer: IntersectionObserver | null = null
    const timerId = window.setTimeout(() => {
      observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (!entry.isIntersecting) {
              onHighlightClear?.()
            }
          }
        },
        { root: scroller, threshold: 0 },
      )
      observer.observe(firstMark)
    }, 500)

    return () => {
      window.clearTimeout(timerId)
      observer?.disconnect()
    }
    // Re-fire when a new highlight arrives, OR when the text layer re-rendered
    // (user clicked a different card → new marks → re-observe).
  }, [highlight?.key, highlight?.excerpt, textLayerTick, onHighlightClear])

  // NAV-04 all-pages search: trigger when we have an excerpt, no page, and the PDF is loaded.
  // On match → jump to the found page (parent-owned highlight state still drives customTextRenderer,
  // which re-runs when <Page pageNumber=foundPage> mounts). On miss → toast + clear highlight.
  useEffect(() => {
    if (!highlight?.excerpt) return
    if (highlight.page != null) return
    if (!pdfProxy) return

    let cancelled = false
    findPageContainingExcerpt(pdfProxy, highlight.excerpt).then((foundPage) => {
      if (cancelled) return
      if (foundPage != null) {
        onPageChange(foundPage)
      } else {
        toast.info('Clause not found in document')
        onHighlightClear?.()
      }
    })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlight?.key, pdfProxy, onPageChange, onHighlightClear])

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
                customTextRenderer={textRenderer}
                onRenderTextLayerSuccess={handleTextLayerRendered}
                inputRef={pageContainerRef}
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
