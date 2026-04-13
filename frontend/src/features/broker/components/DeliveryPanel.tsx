import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { CheckCircle, Mail, Send, AlertTriangle } from 'lucide-react'
import { useDraftRecommendation, useEditRecommendation, useSendRecommendation } from '../hooks/useDelivery'
import type { BrokerProjectDetail } from '../types/broker'

interface DeliveryPanelProps {
  project: BrokerProjectDetail
}

export function DeliveryPanel({ project }: DeliveryPanelProps) {
  const [recipientEmail, setRecipientEmail] = useState(project.recommendation_recipient || '')
  const [subject, setSubject] = useState(project.recommendation_subject || '')
  const [body, setBody] = useState(project.recommendation_body || '')
  const [showConfirm, setShowConfirm] = useState(false)

  const draftMutation = useDraftRecommendation(project.id)
  const editMutation = useEditRecommendation(project.id)
  const sendMutation = useSendRecommendation(project.id)

  // Sync local state when project data updates
  const status = project.recommendation_status

  // Check if any quotes are recommended
  const hasRecommendedQuotes = project.coverages.length > 0 // Quotes are on the project, not coverages directly

  // --- SENT STATE ---
  if (status === 'sent') {
    return (
      <div className="rounded-xl border p-5 space-y-3 bg-green-50/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-green-600" />
            <h3 className="font-medium">Recommendation Delivered</h3>
          </div>
          <Badge variant="outline" className="bg-green-50 text-green-700 border-0">
            Sent
          </Badge>
        </div>
        <div className="text-sm space-y-1 text-muted-foreground">
          <p>
            <span className="font-medium text-foreground">To:</span>{' '}
            {project.recommendation_recipient}
          </p>
          <p>
            <span className="font-medium text-foreground">Subject:</span>{' '}
            {project.recommendation_subject}
          </p>
          {project.recommendation_sent_at && (
            <p>
              <span className="font-medium text-foreground">Sent:</span>{' '}
              {new Date(project.recommendation_sent_at).toLocaleString()}
            </p>
          )}
        </div>
      </div>
    )
  }

  // --- DRAFT PENDING STATE ---
  if (status === 'pending') {
    return (
      <div className="rounded-xl border p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-blue-500" />
            <h3 className="font-medium">Client Recommendation</h3>
          </div>
          <Badge variant="outline" className="text-xs">Draft</Badge>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium text-muted-foreground">Recipient</label>
            <Input
              type="email"
              value={recipientEmail}
              onChange={(e) => setRecipientEmail(e.target.value)}
              placeholder="client@example.com"
              className="mt-1"
            />
          </div>

          <div>
            <label className="text-sm font-medium text-muted-foreground">Subject</label>
            <Input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Recommendation subject"
              className="mt-1"
            />
          </div>

          <div>
            <label className="text-sm font-medium text-muted-foreground">Body</label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={8}
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
              placeholder="Recommendation body..."
            />
          </div>
        </div>

        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() =>
              editMutation.mutate({
                subject,
                body,
                recipient_email: recipientEmail,
              })
            }
            disabled={editMutation.isPending}
          >
            {editMutation.isPending ? 'Saving...' : 'Save Changes'}
          </Button>

          {!showConfirm ? (
            <Button
              onClick={() => setShowConfirm(true)}
              disabled={!recipientEmail}
            >
              <Send className="h-3.5 w-3.5 mr-1.5" />
              Send to Client
            </Button>
          ) : (
            <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
              <span className="text-sm">
                Send to <span className="font-medium">{recipientEmail}</span>?
              </span>
              <Button
                size="sm"
                onClick={() => {
                  sendMutation.mutate()
                  setShowConfirm(false)
                }}
                disabled={sendMutation.isPending}
              >
                {sendMutation.isPending ? 'Sending...' : 'Confirm'}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setShowConfirm(false)}
              >
                Cancel
              </Button>
            </div>
          )}
        </div>
      </div>
    )
  }

  // --- NO DRAFT STATE ---
  return (
    <div className="rounded-xl border p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Mail className="h-5 w-5 text-muted-foreground" />
        <h3 className="font-medium">Client Recommendation</h3>
      </div>

      {!hasRecommendedQuotes && (
        <div className="flex items-center gap-2 text-sm text-amber-600 bg-amber-50 rounded-lg p-3">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>No quotes marked as recommended yet. Mark at least one quote as recommended before generating.</span>
        </div>
      )}

      <div>
        <label className="text-sm font-medium text-muted-foreground">Recipient email (optional)</label>
        <Input
          type="email"
          value={recipientEmail}
          onChange={(e) => setRecipientEmail(e.target.value)}
          placeholder="client@example.com"
          className="mt-1"
        />
      </div>

      <Button
        onClick={() => draftMutation.mutate(recipientEmail || undefined)}
        disabled={draftMutation.isPending}
      >
        {draftMutation.isPending ? 'Generating...' : 'Generate Recommendation'}
      </Button>
    </div>
  )
}
