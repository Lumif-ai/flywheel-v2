import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import type { ProjectCoverage } from '../types/broker'

interface DocumentViewerProps {
  coverages: ProjectCoverage[]
  onClauseHighlight?: (clause: string) => void
}

/**
 * Groups coverages by contract clause, rendering them as a styled "paper"
 * document with clause headers and color-coded left borders.
 */
export function DocumentViewer({ coverages }: DocumentViewerProps) {
  const insuranceCoverages = coverages.filter(
    (c) => c.category !== 'surety' && c.source_excerpt
  )
  const suretyCoverages = coverages.filter(
    (c) => c.category === 'surety' && c.source_excerpt
  )

  return (
    <div className="flex flex-col h-full">
      <Tabs defaultValue="msa" className="flex flex-col h-full">
        <div className="px-4 pt-4 border-b">
          <TabsList variant="line">
            <TabsTrigger value="msa">MSA Contract</TabsTrigger>
            <TabsTrigger value="surety">Surety</TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="msa" className="flex-1 overflow-y-auto p-4">
          {insuranceCoverages.length === 0 ? (
            <EmptyExcerpts label="MSA Contract" />
          ) : (
            <ContractPaper coverages={insuranceCoverages} highlightColor="coral" />
          )}
        </TabsContent>
        <TabsContent value="surety" className="flex-1 overflow-y-auto p-4">
          {suretyCoverages.length === 0 ? (
            <EmptyExcerpts label="Surety" />
          ) : (
            <ContractPaper coverages={suretyCoverages} highlightColor="blue" />
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

/** Group coverages by clause and render in clause order */
function ContractPaper({
  coverages,
  highlightColor,
}: {
  coverages: ProjectCoverage[]
  highlightColor: 'coral' | 'blue'
}) {
  // Group by contract_clause (or 'Uncategorized')
  const grouped = new Map<string, ProjectCoverage[]>()
  for (const cov of coverages) {
    const key = cov.contract_clause ?? 'General'
    if (!grouped.has(key)) grouped.set(key, [])
    grouped.get(key)!.push(cov)
  }

  const borderColor = highlightColor === 'coral' ? '#E94D35' : '#2563EB'
  const bgTint =
    highlightColor === 'coral'
      ? 'rgba(233,77,53,0.04)'
      : 'rgba(37,99,235,0.04)'

  return (
    <div
      className="rounded-lg bg-white shadow-[0_1px_8px_rgba(0,0,0,0.08)] overflow-hidden"
      style={{ fontFamily: "'Georgia', 'Times New Roman', serif" }}
    >
      {/* Paper header bar */}
      <div
        className="px-6 py-3 border-b"
        style={{ background: bgTint }}
      >
        <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: borderColor, fontFamily: 'Inter, system-ui, sans-serif' }}>
          {highlightColor === 'coral' ? 'Contract Excerpts' : 'Bond Requirement Excerpts'}
        </p>
      </div>

      <div className="px-6 py-5 space-y-6">
        {[...grouped.entries()].map(([clause, items]) => (
          <div key={clause} data-clause={clause}>
            {/* Clause header */}
            <div
              className="flex items-center gap-2 mb-3 pb-2"
              style={{ borderBottom: `2px solid ${borderColor}` }}
            >
              <span
                className="text-sm font-bold uppercase tracking-wide"
                style={{ color: borderColor, fontFamily: 'Inter, system-ui, sans-serif' }}
              >
                {clause}
              </span>
            </div>

            {/* Excerpt blocks under this clause */}
            <div className="space-y-3">
              {items.map((cov) => (
                <div
                  key={cov.id}
                  className="rounded-md border-l-4 px-4 py-3"
                  style={{
                    borderLeftColor: borderColor,
                    background: bgTint,
                  }}
                >
                  {cov.display_name && (
                    <p
                      className="text-xs font-semibold mb-1 uppercase tracking-wide"
                      style={{ color: borderColor, fontFamily: 'Inter, system-ui, sans-serif' }}
                    >
                      {cov.display_name}
                    </p>
                  )}
                  <p className="text-sm text-[#374151] leading-relaxed">
                    {cov.source_excerpt}
                  </p>
                  {cov.source_section && (
                    <p className="text-xs text-muted-foreground mt-2" style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>
                      Section {cov.source_section}
                      {cov.source_page != null && <> &middot; Page {cov.source_page}</>}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Paper footer */}
      <div className="px-6 py-3 border-t bg-[#FAFAFA] text-xs text-muted-foreground" style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>
        {coverages.length} excerpt{coverages.length !== 1 ? 's' : ''} extracted
      </div>
    </div>
  )
}

function EmptyExcerpts({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <div className="w-12 h-12 rounded-full bg-muted/50 flex items-center justify-center mb-3">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      </div>
      <p className="text-sm font-medium">No {label} excerpts extracted yet</p>
      <p className="text-xs mt-1">Upload contract documents and run analysis to see excerpts here.</p>
    </div>
  )
}
