import { useState, useCallback, useEffect } from 'react'
import { toast } from 'sonner'
import { ShimmerSkeleton } from '@/components/ui/skeleton'
import { useAnalysisPolling } from '../../hooks/useAnalysisPolling'
import { DocumentViewer } from '../DocumentViewer'
import { FullDocumentViewer } from '../FullDocumentViewer'
import { RequirementsPanel } from '../RequirementsPanel'
import type { BrokerProjectDetail, ProjectCoverage } from '../../types/broker'

interface AnalysisTabProps {
  project: BrokerProjectDetail
}

export function AnalysisTab({ project }: AnalysisTabProps) {
  const { data } = useAnalysisPolling(project.id)
  const analysisStatus = data?.analysis_status ?? project.analysis_status
  const coverages = data?.coverages ?? project.coverages ?? []
  const isRunning = analysisStatus === 'running'

  interface DocumentEntry {
    file_id?: string
    name?: string
    mimetype?: string
  }
  const documents = (project.metadata?.documents as DocumentEntry[] | undefined) ?? []
  const pdfDocuments = documents
    .filter((d) => d.file_id && d.mimetype === 'application/pdf')
    .map((d) => ({ fileId: d.file_id!, name: d.name ?? 'document.pdf' }))
  const hasPdfDocument = pdfDocuments.length > 0

  // Lifted viewer + selection state (Phase 143 / spec §4.8)
  const [activeFileId, setActiveFileId] = useState<string | null>(
    pdfDocuments[0]?.fileId ?? null,
  )
  const [currentPage, setCurrentPage] = useState(1)
  const [activeCoverageId, setActiveCoverageId] = useState<string | null>(null)
  const [highlight, setHighlight] = useState<{
    excerpt: string | null
    page: number | null
    key: string
  } | null>(null)

  // Validity: if the document list changes and the current activeFileId is gone, pick the first.
  // Auto-migration is a context switch, so clear any stale highlight/active card too.
  useEffect(() => {
    if (pdfDocuments.length === 0) {
      if (activeFileId !== null) {
        setActiveFileId(null)
        setHighlight(null)
        setActiveCoverageId(null)
      }
      return
    }
    if (!pdfDocuments.some((d) => d.fileId === activeFileId)) {
      setActiveFileId(pdfDocuments[0].fileId)
      setHighlight(null)
      setActiveCoverageId(null)
    }
  }, [pdfDocuments, activeFileId])

  // User-initiated tab click: clear highlight + active card (deliberate context change).
  // NOTE: cross-doc clause clicks intentionally do NOT go through this path — they set
  // activeFileId + highlight + activeCoverageId together via handleClauseClick so the
  // highlight survives the switch.
  const handleFileChange = useCallback((fileId: string) => {
    setActiveFileId(fileId)
    setHighlight(null)
    setActiveCoverageId(null)
  }, [])

  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page)
  }, [])

  const handleHighlightClear = useCallback(() => {
    // NAV-03: Plan 03's 5s timer and scroll-away IntersectionObserver both call this.
    // DO NOT clear activeCoverageId here — active card persists past highlight decay.
    setHighlight(null)
  }, [])

  const handleClauseClick = useCallback(
    (coverage: ProjectCoverage) => {
      // NAV-06: mark this card active (only one active at a time).
      // Active state is independent of highlight decay — it persists until the
      // user clicks another card OR switches documents via the tab bar.
      setActiveCoverageId(coverage.id)

      const hasPage = coverage.source_page != null
      const hasExcerpt =
        !!coverage.source_excerpt && coverage.source_excerpt.trim().length > 0

      // NAV-05: both null → toast, no viewer state mutation.
      if (!hasPage && !hasExcerpt) {
        toast.info('Clause not linked')
        return
      }

      // If coverage belongs to a different PDF than what's currently showing, switch first.
      // Phase 143 note: Phase 144 fully implements multi-doc filtering; here we only switch
      // if source_document_id is non-null AND differs AND is a PDF we have.
      const targetFileId = coverage.source_document_id
      if (targetFileId && !pdfDocuments.some((d) => d.fileId === targetFileId)) {
        toast.info('Clause belongs to a document not available in the viewer')
        return
      }
      if (targetFileId && targetFileId !== activeFileId) {
        setActiveFileId(targetFileId)
      }

      // NAV-01: set the target page. If hasPage is false, Plan 03's all-pages search
      // will locate a page via the excerpt; leave currentPage alone until that runs.
      // Cross-doc caveat (fixed in Task 1): the viewer NO LONGER resets currentPage to 1
      // on activeFileId change — so this setCurrentPage call survives the cross-doc switch.
      if (hasPage) {
        setCurrentPage(coverage.source_page!)
      }

      // Signal to the viewer: here's what to mark on render. `key` forces effects to
      // re-fire even on a repeat click of the same card (card click is not idempotent).
      setHighlight({
        excerpt: hasExcerpt ? coverage.source_excerpt : null,
        page: hasPage ? coverage.source_page : null,
        key: `${coverage.id}:${Date.now()}`,
      })
    },
    [activeFileId, pdfDocuments],
  )

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-[calc(100vh-200px)]">
      {/* Left: Document viewer */}
      <div className="rounded-xl border overflow-hidden flex flex-col">
        <div className="flex-1 overflow-hidden">
          {isRunning ? (
            <div className="p-4 space-y-3 overflow-y-auto h-full">
              {Array.from({ length: 4 }).map((_, i) => (
                <ShimmerSkeleton key={i} className="h-20 w-full rounded-lg" />
              ))}
            </div>
          ) : hasPdfDocument ? (
            <FullDocumentViewer
              documents={pdfDocuments}
              activeFileId={activeFileId}
              onFileChange={handleFileChange}
              currentPage={currentPage}
              onPageChange={handlePageChange}
              highlight={highlight}
              onHighlightClear={handleHighlightClear}
            />
          ) : (
            <div className="overflow-y-auto h-full">
              <DocumentViewer coverages={coverages} />
            </div>
          )}
        </div>
      </div>

      {/* Right: Requirements panel */}
      <div className="rounded-xl border overflow-hidden flex flex-col">
        <div className="px-4 py-3 border-b bg-muted/30">
          <h3 className="text-sm font-semibold">Requirements</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <RequirementsPanel
            coverages={coverages}
            analysisStatus={analysisStatus}
            activeCoverageId={activeCoverageId}
            onClauseClick={handleClauseClick}
          />
        </div>
      </div>
    </div>
  )
}
