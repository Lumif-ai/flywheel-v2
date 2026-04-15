import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Mail, CheckCircle, Edit3, Send } from 'lucide-react'
import { useProjectQuotes } from '../hooks/useSolicitations'
import { useApproveSend, useEditDraft } from '../hooks/useSolicitations'
import type { CarrierQuote } from '../types/broker'

// TODO(phase-138): Migrate to SolicitationDraft data instead of reading draft fields from CarrierQuote
// During transition, backend still sends draft_subject/draft_body/draft_status on quote objects.
// Access via metadata_ to avoid TS errors after field removal from type.
type QuoteWithLegacyDraft = CarrierQuote & {
  draft_subject?: string | null
  draft_body?: string | null
  draft_status?: string | null
}

interface EmailApprovalProps {
  projectId: string
}

function DraftCard({
  quote: rawQuote,
  projectId,
}: {
  quote: CarrierQuote
  projectId: string
}) {
  const quote = rawQuote as QuoteWithLegacyDraft
  const [editing, setEditing] = useState(false)
  const [subject, setSubject] = useState(quote.draft_subject || '')
  const [body, setBody] = useState(quote.draft_body || '')
  const approveSend = useApproveSend(projectId)
  const editDraft = useEditDraft(projectId)

  function handleSave() {
    editDraft.mutate(
      { draftId: quote.id, payload: { subject, body } },
      { onSuccess: () => setEditing(false) }
    )
  }

  if (quote.draft_status === 'sent') {
    return (
      <div className="rounded-xl border p-4 space-y-2 bg-green-50/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <span className="font-medium">{quote.carrier_name}</span>
          </div>
          <Badge variant="outline" className="bg-green-50 text-green-700 border-0 text-xs">
            Sent
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          Sent {quote.solicited_at ? new Date(quote.solicited_at).toLocaleString() : ''}
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Mail className="h-4 w-4 text-blue-500" />
          <span className="font-medium">{quote.carrier_name}</span>
        </div>
        <Badge variant="outline" className="text-xs">
          {quote.draft_status || 'pending'}
        </Badge>
      </div>

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
            rows={6}
            className="w-full rounded-lg border px-3 py-2 text-sm font-mono"
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
          <p className="text-sm font-medium">{quote.draft_subject}</p>
          <p className="text-sm text-muted-foreground line-clamp-3">
            {quote.draft_body?.replace(/<[^>]*>/g, '').slice(0, 200)}
          </p>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              <Edit3 className="h-3 w-3 mr-1" />
              Edit
            </Button>
            <Button
              size="sm"
              onClick={() => approveSend.mutate(quote.id)}
              disabled={approveSend.isPending}
            >
              <Send className="h-3 w-3 mr-1" />
              {approveSend.isPending ? 'Sending...' : 'Approve & Send'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

export function EmailApproval({ projectId }: EmailApprovalProps) {
  const { data: quotes, isLoading } = useProjectQuotes(projectId)

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-32 w-full rounded-xl" />
        ))}
      </div>
    )
  }

  // TODO(phase-138): Use SolicitationDraft data instead of legacy quote fields
  const emailDrafts = (quotes || []).filter((q) => (q as QuoteWithLegacyDraft).draft_subject != null)
  const sentCount = emailDrafts.filter((q) => (q as QuoteWithLegacyDraft).draft_status === 'sent').length

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
        {emailDrafts.map((quote) => (
          <DraftCard key={quote.id} quote={quote} projectId={projectId} />
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
