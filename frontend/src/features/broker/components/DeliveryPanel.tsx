import { useState, useMemo, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { CheckCircle, Mail, Send, AlertTriangle } from 'lucide-react'
import { useProjectRecommendation, useDraftRecommendation, useEditRecommendation, useSendRecommendation } from '../hooks/useDelivery'
import { useBrokerQuotes } from '../hooks/useBrokerQuotes'
import { ClaudeCommandModal } from './shared/ClaudeCommandModal'
import type { BrokerProjectDetail } from '../types/broker'

interface DeliveryPanelProps {
  project: BrokerProjectDetail
}

function formatCurrency(val: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val)
}

export function DeliveryPanel({ project }: DeliveryPanelProps) {
  const [recipientEmail, setRecipientEmail] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [showConfirm, setShowConfirm] = useState(false)
  const [handoffCommand, setHandoffCommand] = useState<string | null>(null)

  const { data: recommendation, isLoading: recLoading } = useProjectRecommendation(project.id)
  const { data: quotes } = useBrokerQuotes(project.id)
  const draftMutation = useDraftRecommendation(project.id, {
    onHandoff: (command) => setHandoffCommand(command),
  })
  const editMutation = useEditRecommendation(project.id)
  const sendMutation = useSendRecommendation(project.id)

  // Sync local state when recommendation loads
  useEffect(() => {
    if (recommendation) {
      setRecipientEmail(recommendation.recipient_email ?? '')
      setSubject(recommendation.subject)
      setBody(recommendation.body_html)
    }
  }, [recommendation?.id])

  // DELV-02: Premium breakdown computed from useBrokerQuotes
  const premiumBreakdown = useMemo(() => {
    const extracted = (quotes ?? []).filter(q => q.status === 'extracted' && q.premium != null)
    const insurancePremium = extracted
      .filter(q => q.carrier_type === 'insurance')
      .reduce((sum, q) => sum + (q.premium ?? 0), 0)
    const suretyPremium = extracted
      .filter(q => q.carrier_type === 'surety')
      .reduce((sum, q) => sum + (q.premium ?? 0), 0)
    const totalPremium = insurancePremium + suretyPremium
    return { insurancePremium, suretyPremium, totalPremium, hasData: totalPremium > 0 }
  }, [quotes])

  const status = recommendation?.status ?? null

  // --- LOADING STATE ---
  if (recLoading) {
    return (
      <div className="rounded-xl border p-5 space-y-3 animate-pulse">
        <div className="h-4 bg-muted rounded w-1/2" />
        <div className="h-4 bg-muted rounded w-3/4" />
        <div className="h-4 bg-muted rounded w-2/3" />
      </div>
    )
  }

  // --- PREMIUM BREAKDOWN CARD ---
  const PremiumBreakdownCard = premiumBreakdown.hasData ? (
    <div className="rounded-lg border bg-muted/30 p-4 space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Package Summary</p>
      <div className="space-y-1">
        {premiumBreakdown.insurancePremium > 0 && (
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Insurance</span>
            <span className="font-medium">{formatCurrency(premiumBreakdown.insurancePremium)}</span>
          </div>
        )}
        {premiumBreakdown.suretyPremium > 0 && (
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Surety</span>
            <span className="font-medium">{formatCurrency(premiumBreakdown.suretyPremium)}</span>
          </div>
        )}
        <div className="flex justify-between text-sm border-t pt-1 mt-1">
          <span className="font-semibold">Total Premium</span>
          <span className="font-bold text-emerald-700">{formatCurrency(premiumBreakdown.totalPremium)}</span>
        </div>
      </div>
    </div>
  ) : null

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
          {recommendation?.subject && <p className="font-medium text-foreground">{recommendation.subject}</p>}
          {recommendation?.sent_at && (
            <p>Sent {new Date(recommendation.sent_at).toLocaleString()}</p>
          )}
          {recommendation?.recipient_email && (
            <p>To: {recommendation.recipient_email}</p>
          )}
        </div>
        {PremiumBreakdownCard}
      </div>
    )
  }

  // --- DRAFT / APPROVED STATE (edit + send form) ---
  if (status === 'draft' || status === 'approved') {
    return (
      <div className="rounded-xl border p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-blue-500" />
            <h3 className="font-medium">Client Recommendation</h3>
          </div>
          <Badge variant="outline" className="text-xs">Draft</Badge>
        </div>

        {PremiumBreakdownCard}

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
                recommendationId: recommendation!.id,
                data: {
                  subject,
                  body,
                  recipient_email: recipientEmail,
                },
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
                  sendMutation.mutate(recommendation!.id)
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

  // --- NO DRAFT STATE (generate form) ---
  return (
    <div className="rounded-xl border p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Mail className="h-5 w-5 text-muted-foreground" />
        <h3 className="font-medium">Client Recommendation</h3>
      </div>

      {PremiumBreakdownCard}

      {!premiumBreakdown.hasData && (
        <div className="flex items-center gap-2 text-sm text-amber-600 bg-amber-50 rounded-lg p-3">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>No extracted quotes with premiums yet. Extract at least one quote before generating a recommendation.</span>
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

      <ClaudeCommandModal
        open={handoffCommand !== null}
        onOpenChange={(open) => {
          if (!open) setHandoffCommand(null)
        }}
        command={handoffCommand ?? ''}
        skillName="broker-draft-recommendation"
        actionLabel="Draft Client Recommendation"
      />
    </div>
  )
}
