import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Mail, CheckCircle, Edit3, Send, Sparkles } from 'lucide-react'
import { useApproveSend, useEditDraft } from '../hooks/useSolicitations'
import { useSolicitationDrafts } from '../hooks/useSolicitationDrafts'
import { useCarrierMatches } from '../hooks/useCarrierMatches'
import type { SolicitationDraft, SolicitationDocument } from '../types/broker'
import { CarrierBadge } from './CarrierBadge'
import { useBrokerQuotes } from '../hooks/useBrokerQuotes'

interface EmailApprovalProps {
  projectId: string
}

/** File type icon chip for attachments */
function AttachmentChip({ doc }: { doc: SolicitationDocument }) {
  const ext = doc.display_name?.split('.').pop()?.toLowerCase() ?? ''
  const isPdf = ext === 'pdf'
  const isSpreadsheet = ['xls', 'xlsx', 'csv'].includes(ext)

  const bgColor = isPdf ? '#EA4335' : isSpreadsheet ? '#16a34a' : '#6B7280'
  const label = isPdf ? 'PDF' : isSpreadsheet ? ext.toUpperCase() : 'DOC'

  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded border border-gray-200 text-xs bg-white">
      <div
        className="flex items-center justify-center rounded-sm flex-shrink-0"
        style={{ width: 14, height: 14, backgroundColor: bgColor }}
      >
        <span style={{ color: 'white', fontSize: 6, fontWeight: 700 }}>{label}</span>
      </div>
      <span className="text-gray-700 truncate max-w-[180px]">{doc.display_name}</span>
    </div>
  )
}

function DraftCard({
  draft,
  emailAddress,
  projectId,
  attachments,
}: {
  draft: SolicitationDraft
  emailAddress: string | undefined
  projectId: string
  attachments: SolicitationDocument[]
}) {
  const [editing, setEditing] = useState(false)
  const [subject, setSubject] = useState(draft.subject || '')
  const [body, setBody] = useState(draft.body || '')
  const approveSend = useApproveSend(projectId)
  const editDraft = useEditDraft(projectId)

  function handleSave() {
    editDraft.mutate(
      { draftId: draft.id, payload: { subject, body } },
      { onSuccess: () => setEditing(false) }
    )
  }

  const plainBody = draft.body.replace(/<[^>]*>/g, '')

  if (draft.status === 'sent') {
    return (
      <div className="rounded-xl border p-4 space-y-2 bg-green-50/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <CarrierBadge name={draft.carrier_name} />
          </div>
          <Badge variant="outline" className="bg-green-50 text-green-700 border-0 text-xs">
            Sent
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          Sent {draft.sent_at ? new Date(draft.sent_at).toLocaleString() : ''}
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border p-4 space-y-3">
      {/* Header: carrier badge + type badge + status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CarrierBadge name={draft.carrier_name} />
          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">
            Via Email
          </span>
        </div>
        <Badge variant="outline" className="text-xs capitalize">
          {draft.status || 'pending'}
        </Badge>
      </div>

      <p className="text-xs text-muted-foreground">To: {emailAddress ?? '---'}</p>

      {editing ? (
        <div className="space-y-2">
          <input
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="w-full rounded-lg border px-3 py-2 text-sm"
            placeholder="Subject"
          />
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className="w-full rounded-lg border px-3 py-2 text-sm font-mono min-h-[400px]"
            placeholder="Email body"
          />
          <div className="flex gap-2">
            <Button size="sm" onClick={handleSave} disabled={editDraft.isPending}>
              Save
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {/* Email preview — styled like the demo */}
          <div className="border rounded-lg p-4 text-sm leading-relaxed bg-[#FAFAFA]" style={{ maxHeight: 280, overflow: 'auto' }}>
            <div className="mb-1 text-xs">
              <span className="font-medium text-foreground">Subject:</span>{' '}
              <span className="text-muted-foreground">{draft.subject}</span>
            </div>
            <div className="border-t pt-2 mt-2 whitespace-pre-line text-sm text-[#374151]">
              {plainBody}
            </div>
          </div>

          {/* Attachments section */}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-1.5 items-center">
              {attachments.map((doc) => (
                <AttachmentChip key={doc.file_id} doc={doc} />
              ))}
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              <Edit3 className="h-3 w-3 mr-1" />
              Edit
            </Button>
            <Button
              size="sm"
              onClick={() => approveSend.mutate(draft.id)}
              disabled={approveSend.isPending}
            >
              <Send className="h-3 w-3 mr-1" />
              {approveSend.isPending ? 'Sending...' : 'Approve & Send'}
            </Button>
          </div>
        </div>
      )}

      <span className="inline-flex items-center gap-1.5 rounded-full border border-[#E94D35]/30 bg-[#E94D35]/5 px-2 py-0.5 text-xs text-[#E94D35]">
        <Sparkles className="h-3 w-3" />
        Generated by Claude Code
      </span>
    </div>
  )
}

export function EmailApproval({ projectId }: EmailApprovalProps) {
  const { data: drafts, isLoading } = useSolicitationDrafts(projectId)
  const { data: matchData } = useCarrierMatches(projectId)
  const { data: quotes } = useBrokerQuotes(projectId)

  const emailByCarrierName = useMemo(() => {
    const map: Record<string, string> = {}
    ;(matchData?.matches ?? []).forEach((m) => {
      if (m.email_address) map[m.carrier_name] = m.email_address
    })
    return map
  }, [matchData])

  // Build a map of carrier_name -> documents from quotes
  const docsByCarrierName = useMemo(() => {
    const map: Record<string, SolicitationDocument[]> = {}
    ;(quotes ?? []).forEach((q) => {
      if (q.documents && q.documents.length > 0) {
        map[q.carrier_name] = q.documents.filter((d) => d.included)
      }
    })
    return map
  }, [quotes])

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-32 w-full rounded-xl" />
        ))}
      </div>
    )
  }

  const emailDrafts = drafts ?? []
  const sentCount = emailDrafts.filter((d) => d.status === 'sent').length

  if (emailDrafts.length === 0) return null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-muted-foreground">Email Solicitations</h4>
        <span className="text-sm text-muted-foreground">
          {sentCount}/{emailDrafts.length} sent
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-2 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-green-500 transition-all"
          style={{ width: `${emailDrafts.length > 0 ? (sentCount / emailDrafts.length) * 100 : 0}%` }}
        />
      </div>

      <div className="space-y-3">
        {emailDrafts.map((draft) => (
          <DraftCard
            key={draft.id}
            draft={draft}
            emailAddress={emailByCarrierName[draft.carrier_name]}
            projectId={projectId}
            attachments={docsByCarrierName[draft.carrier_name] ?? []}
          />
        ))}
      </div>

      {sentCount === emailDrafts.length && emailDrafts.length > 0 && (
        <div className="rounded-lg bg-green-50 p-3 text-center text-sm text-green-700">
          All email solicitations sent successfully.
        </div>
      )}
    </div>
  )
}
