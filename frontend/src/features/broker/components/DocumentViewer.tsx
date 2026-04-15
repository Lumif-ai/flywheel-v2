import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import type { ProjectCoverage } from '../types/broker'

interface DocumentViewerProps {
  coverages: ProjectCoverage[]
}

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
        <TabsContent value="msa" className="flex-1 overflow-y-auto p-4 space-y-4">
          {insuranceCoverages.length === 0 ? (
            <EmptyExcerpts label="MSA Contract" />
          ) : (
            insuranceCoverages.map((cov) => (
              <ExcerptBlock key={cov.id} coverage={cov} highlightColor="coral" />
            ))
          )}
        </TabsContent>
        <TabsContent value="surety" className="flex-1 overflow-y-auto p-4 space-y-4">
          {suretyCoverages.length === 0 ? (
            <EmptyExcerpts label="Surety" />
          ) : (
            suretyCoverages.map((cov) => (
              <ExcerptBlock key={cov.id} coverage={cov} highlightColor="blue" />
            ))
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function ExcerptBlock({
  coverage,
  highlightColor,
}: {
  coverage: ProjectCoverage
  highlightColor: 'coral' | 'blue'
}) {
  const bgClass =
    highlightColor === 'coral'
      ? 'bg-[rgba(233,77,53,0.08)] border-l-[#E94D35]'
      : 'bg-[rgba(37,99,235,0.08)] border-l-[#2563EB]'

  return (
    <div className={`rounded-lg border-l-4 p-3 text-sm ${bgClass}`}>
      {coverage.contract_clause && (
        <p className="text-xs font-medium text-muted-foreground mb-1 uppercase tracking-wide">
          {coverage.contract_clause}
        </p>
      )}
      <p className="text-foreground leading-relaxed">{coverage.source_excerpt}</p>
      {coverage.source_section && (
        <p className="text-xs text-muted-foreground mt-1">§ {coverage.source_section}</p>
      )}
    </div>
  )
}

function EmptyExcerpts({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center py-12 text-muted-foreground">
      <p className="text-sm">No {label} excerpts extracted yet</p>
    </div>
  )
}
