import type { BrokerProjectDetail, DocumentEntry } from '../../types/broker'
import { ClientProfile } from '../ClientProfile'
import { DocumentUploadZone } from '../DocumentUploadZone'

interface OverviewTabProps {
  project: BrokerProjectDetail
}

export function OverviewTab({ project }: OverviewTabProps) {
  const allDocs = ((project.metadata?.documents as DocumentEntry[]) ?? []).filter(
    Boolean,
  )
  // Phase 145: Legacy docs without document_type default to 'requirements'
  // (matches backend default in projects.py:_get_project_pdfs).
  const requirementsDocs = allDocs.filter(
    (d) => (d.document_type ?? 'requirements') === 'requirements',
  )
  const coverageDocs = allDocs.filter((d) => d.document_type === 'coverage')

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left column: Client info */}
      <div className="space-y-4">
        <ClientProfile metadata={project.metadata ?? null} />
      </div>
      {/* Right column: Project description + two upload zones */}
      <div className="space-y-4">
        {project.description && (
          <div className="rounded-xl border p-4">
            <h3 className="text-sm font-semibold mb-2">Project Request</h3>
            <p className="text-sm text-muted-foreground">{project.description}</p>
          </div>
        )}
        <DocumentUploadZone
          projectId={project.id}
          kind="requirements"
          title="Requirements"
          description="MSA, surety annexes, bond schedules"
          documents={requirementsDocs}
        />
        <DocumentUploadZone
          projectId={project.id}
          kind="coverage"
          title="Current coverage & supplements"
          description="COIs, in-force policies, schedules of insurance"
          documents={coverageDocs}
        />
      </div>
    </div>
  )
}
