import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { colors, typography } from '@/lib/design-tokens'
import { useApproveDraft, useDismissDraft, useEditDraft, useRegenerateDraft } from '../hooks/useDraftActions'
import { VoiceAnnotation } from './VoiceAnnotation'
import { RegenerateDropdown } from './RegenerateDropdown'
import type { Draft, RegenerateRequest } from '../types/email'

interface DraftReviewProps {
  draft: Draft
}

export function DraftReview({ draft }: DraftReviewProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editedBody, setEditedBody] = useState('')
  const [approveSuccess, setApproveSuccess] = useState(false)

  const approveMutation = useApproveDraft()
  const dismissMutation = useDismissDraft()
  const editMutation = useEditDraft()
  const regenerateMutation = useRegenerateDraft(draft.id)

  const isRegenerating = regenerateMutation.isPending

  function handleRegenerate(request: RegenerateRequest) {
    regenerateMutation.mutate(request)
  }

  const displayBody = draft.user_edits ?? draft.draft_body ?? ''
  const isPending = draft.status === 'pending'

  useEffect(() => {
    if (isEditing) {
      setEditedBody(displayBody)
    }
  }, [isEditing, displayBody])

  function handleApprove() {
    approveMutation.mutate(
      { draftId: draft.id },
      {
        onSuccess: () => {
          setApproveSuccess(true)
          setTimeout(() => setApproveSuccess(false), 2000)
        },
      },
    )
  }

  function handleDismiss() {
    dismissMutation.mutate({ draftId: draft.id })
  }

  function handleSaveEdit() {
    editMutation.mutate(
      { draftId: draft.id, draft_body: editedBody },
      { onSuccess: () => setIsEditing(false) },
    )
  }

  function handleCancelEdit() {
    setIsEditing(false)
    setEditedBody('')
  }

  return (
    <div
      className="rounded-xl border p-4 flex flex-col gap-3"
      style={{ borderColor: 'var(--subtle-border)', backgroundColor: 'var(--card-bg)' }}
    >
      <div className="flex items-center justify-between">
        <span
          style={{
            fontSize: typography.caption.size,
            fontWeight: '600',
            color: colors.secondaryText,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          Draft Reply
        </span>
        {!isPending && (
          <span
            className="rounded-full px-2 py-0.5 text-xs font-medium"
            style={{
              backgroundColor: draft.status === 'sent' ? 'rgba(34,197,94,0.1)' : 'rgba(107,114,128,0.1)',
              color: draft.status === 'sent' ? '#22C55E' : '#6B7280',
            }}
          >
            {draft.status === 'sent' ? 'Sent' : 'Dismissed'}
          </span>
        )}
      </div>

      {/* Draft body */}
      <textarea
        value={isEditing ? editedBody : displayBody}
        onChange={(e) => isEditing && setEditedBody(e.target.value)}
        readOnly={!isEditing}
        rows={6}
        className="w-full resize-none rounded-lg border p-3 text-sm outline-none"
        style={{
          borderColor: isEditing ? 'var(--brand-coral)' : 'var(--subtle-border)',
          backgroundColor: isEditing ? 'var(--card-bg)' : 'rgba(0,0,0,0.02)',
          color: colors.bodyText,
          fontFamily: 'inherit',
          lineHeight: '1.6',
        }}
      />

      {/* Voice annotation */}
      {isPending && <VoiceAnnotation snapshot={draft.voice_snapshot} />}

      {/* Action buttons */}
      {isPending && !isEditing && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <button
              onClick={handleApprove}
              disabled={approveMutation.isPending || isRegenerating}
              className="flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ background: 'var(--brand-coral)' }}
            >
              {approveMutation.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : null}
              {approveSuccess ? 'Sent!' : 'Approve & Send'}
            </button>

            <button
              onClick={() => setIsEditing(true)}
              disabled={isRegenerating}
              className="rounded-xl border px-4 py-2 text-sm font-medium transition-colors hover:bg-[rgba(0,0,0,0.04)] disabled:opacity-50"
              style={{ borderColor: 'var(--subtle-border)', color: colors.headingText }}
            >
              Edit
            </button>

            <RegenerateDropdown
              draftId={draft.id}
              hasUserEdits={!!draft.user_edits}
              isRegenerating={isRegenerating}
              onRegenerate={handleRegenerate}
            />

            <button
              onClick={handleDismiss}
              disabled={dismissMutation.isPending || isRegenerating}
              className="rounded-xl px-4 py-2 text-sm font-medium transition-colors hover:bg-[rgba(239,68,68,0.08)] disabled:opacity-50"
              style={{ color: '#EF4444' }}
            >
              {dismissMutation.isPending ? (
                <Loader2 className="size-3.5 animate-spin inline mr-1" />
              ) : null}
              Dismiss
            </button>
          </div>
        </div>
      )}

      {isPending && isEditing && (
        <div className="flex items-center gap-2">
          <button
            onClick={handleSaveEdit}
            disabled={editMutation.isPending}
            className="flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            style={{ background: 'var(--brand-coral)' }}
          >
            {editMutation.isPending ? <Loader2 className="size-3.5 animate-spin" /> : null}
            Save
          </button>

          <button
            onClick={handleCancelEdit}
            className="rounded-xl border px-4 py-2 text-sm font-medium transition-colors hover:bg-[rgba(0,0,0,0.04)]"
            style={{ borderColor: 'var(--subtle-border)', color: colors.secondaryText }}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  )
}
