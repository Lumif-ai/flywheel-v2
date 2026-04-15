import type { BrokerProjectDetail } from '../../types/broker'
import { ClientProfile } from '../ClientProfile'
import { DocumentUploadZone } from '../DocumentUploadZone'

interface OverviewTabProps {
  project: BrokerProjectDetail
}

interface DocumentEntry {
  name?: string
  type?: string
  mimetype?: string
  size?: number
  uploaded_at?: string
}

export function OverviewTab({ project }: OverviewTabProps) {
  const documents = ((project.metadata?.documents as DocumentEntry[]) ?? []).filter(Boolean)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left column: Client info */}
      <div className="space-y-4">
        <ClientProfile metadata={project.metadata ?? null} />
      </div>
      {/* Right column: Project description + upload */}
      <div className="space-y-4">
        {project.description && (
          <div className="rounded-xl border p-4">
            <h3 className="text-sm font-semibold mb-2">Project Request</h3>
            <p className="text-sm text-muted-foreground">{project.description}</p>
          </div>
        )}
        <DocumentUploadZone projectId={project.id} documents={documents} />
      </div>
    </div>
  )
}
