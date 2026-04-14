import { FileText, Clock } from 'lucide-react'
import type { BrokerProjectDetail } from '../../types/broker'
import { ClientProfile } from '../ClientProfile'
import { ActivityTimeline } from '../ActivityTimeline'

interface OverviewTabProps {
  project: BrokerProjectDetail
}

interface DocumentEntry {
  name?: string
  type?: string
  uploaded_at?: string
}

export function OverviewTab({ project }: OverviewTabProps) {
  const documents = (
    (project.metadata?.documents as DocumentEntry[]) ?? []
  ).filter(Boolean)

  return (
    <div className="space-y-6">
      {/* Section A: Client Profile */}
      <ClientProfile metadata={project.metadata ?? null} />

      {/* Section B: Documents */}
      <div className="rounded-xl border p-4">
        <div className="flex items-center gap-2 mb-3">
          <FileText className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Documents</h3>
        </div>
        {documents.length === 0 ? (
          <div className="flex flex-col items-center py-6 text-muted-foreground">
            <FileText className="h-8 w-8 mb-2 opacity-40" />
            <p className="text-sm">No documents uploaded yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {documents.map((doc, idx) => (
              <div
                key={doc.name ?? idx}
                className="flex items-center gap-3 py-1.5"
              >
                <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <span className="text-sm font-medium truncate flex-1">
                  {doc.name ?? 'Untitled'}
                </span>
                {doc.type && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-muted flex-shrink-0">
                    {doc.type}
                  </span>
                )}
                {doc.uploaded_at && (
                  <span className="text-xs text-muted-foreground flex-shrink-0">
                    {new Date(doc.uploaded_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Section C: Recent Activity */}
      <div className="rounded-xl border p-4">
        <div className="flex items-center gap-2 mb-3">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Recent Activity</h3>
        </div>
        <ActivityTimeline activities={project.activities} />
      </div>
    </div>
  )
}
