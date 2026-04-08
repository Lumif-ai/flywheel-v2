import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { Mail, Clock, FileText, X } from 'lucide-react'
import { BrandedCard } from '@/components/ui/branded-card'
import { Skeleton } from '@/components/ui/skeleton'
import { typography, colors, spacing } from '@/lib/design-tokens'
import { useApproveDraft, useDismissDraft } from '@/features/email/hooks/useDraftActions'
import type { AttentionItem, AttentionSection } from '@/features/briefing/types/briefing-v2'

interface NeedsAttentionSectionProps {
  attention: AttentionSection | undefined
  isLoading: boolean
}

// ---------------------------------------------------------------------------
// Section title style (matches TasksSection / TodaySection h2 pattern)
// ---------------------------------------------------------------------------

const sectionTitleStyle: React.CSSProperties = {
  fontSize: typography.sectionTitle.size,
  fontWeight: typography.sectionTitle.weight,
  lineHeight: typography.sectionTitle.lineHeight,
  color: colors.headingText,
  margin: 0,
  marginBottom: spacing.element,
}

// ---------------------------------------------------------------------------
// Attention type config (inspired by PulseSignals SIGNAL_CONFIG)
// ---------------------------------------------------------------------------

const ATTENTION_CONFIG = {
  reply: { icon: Mail, iconColor: colors.success, label: 'Replies' },
  follow_up: { icon: Clock, iconColor: colors.warning, label: 'Follow-ups' },
  draft: { icon: FileText, iconColor: '#3b82f6', label: 'Drafts to Review' },
} as const

// ---------------------------------------------------------------------------
// NeedsAttentionSection — main exported component
// ---------------------------------------------------------------------------

export function NeedsAttentionSection({ attention, isLoading }: NeedsAttentionSectionProps) {
  const isLoadingState = isLoading || attention === undefined

  // Loading state
  if (isLoadingState) {
    return (
      <BrandedCard hoverable={false}>
        <h2 style={sectionTitleStyle}>Needs Attention</h2>
        <div className="space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </BrandedCard>
    )
  }

  const totalItems =
    attention.replies.length + attention.follow_ups.length + attention.drafts.length

  // Empty state
  if (totalItems === 0) {
    return (
      <BrandedCard hoverable={false}>
        <h2 style={sectionTitleStyle}>Needs Attention</h2>
        <p
          style={{
            fontSize: typography.caption.size,
            lineHeight: typography.caption.lineHeight,
            color: colors.secondaryText,
            margin: 0,
          }}
        >
          Nothing needs your attention right now.
        </p>
      </BrandedCard>
    )
  }

  // Count how many sub-sections have items (for deciding whether to show labels)
  const activeTypes = [
    attention.replies.length > 0,
    attention.follow_ups.length > 0,
    attention.drafts.length > 0,
  ].filter(Boolean).length
  const showLabels = activeTypes > 1

  // Loaded state
  return (
    <BrandedCard hoverable={false}>
      <h2 style={sectionTitleStyle}>Needs Attention</h2>
      <div>
        {attention.replies.length > 0 && (
          <AttentionSubSection
            type="reply"
            items={attention.replies}
            showLabel={showLabels}
          />
        )}
        {attention.follow_ups.length > 0 && (
          <AttentionSubSection
            type="follow_up"
            items={attention.follow_ups}
            showLabel={showLabels}
          />
        )}
        {attention.drafts.length > 0 && (
          <DraftSubSection
            items={attention.drafts}
            showLabel={showLabels}
          />
        )}
      </div>
    </BrandedCard>
  )
}

// ---------------------------------------------------------------------------
// AttentionSubSection — renders reply or follow_up items with client-side dismiss
// ---------------------------------------------------------------------------

function AttentionSubSection({
  type,
  items,
  showLabel,
}: {
  type: 'reply' | 'follow_up'
  items: AttentionItem[]
  showLabel: boolean
}) {
  const navigate = useNavigate()
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set())
  const config = ATTENTION_CONFIG[type]
  const Icon = config.icon

  const visibleItems = items.filter((item) => !dismissedIds.has(item.id))
  if (visibleItems.length === 0) return null

  const handleDismiss = (id: string) => {
    setDismissedIds((prev) => new Set(prev).add(id))
  }

  const handleAction = (item: AttentionItem) => {
    if (type === 'reply') {
      navigate('/pipeline', { state: { highlightActivity: item.id } })
    } else {
      navigate('/chat', {
        state: { prefill: `Follow up with ${item.contact_name || item.title}` },
      })
    }
  }

  return (
    <div>
      {showLabel && (
        <div
          style={{
            fontSize: typography.caption.size,
            fontWeight: 600,
            color: colors.secondaryText,
            marginBottom: '8px',
            marginTop: '8px',
          }}
        >
          {config.label}
        </div>
      )}
      {visibleItems.map((item, index) => (
        <div
          key={item.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingTop: '12px',
            paddingBottom: '12px',
            borderBottom:
              index === visibleItems.length - 1
                ? 'none'
                : `1px solid ${colors.subtleBorder}`,
          }}
        >
          {/* Left side: icon + text */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', flex: '1 1 0%', minWidth: 0 }}>
            <Icon
              size={16}
              style={{ color: config.iconColor, flexShrink: 0, marginTop: '2px' }}
            />
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontSize: '15px',
                  fontWeight: 500,
                  color: colors.headingText,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {item.title}
              </div>
              <AttentionSubtitle item={item} type={type} />
            </div>
          </div>

          {/* Right side: action + dismiss */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '12px', flexShrink: 0 }}>
            <button
              type="button"
              onClick={() => handleAction(item)}
              style={{
                fontSize: '13px',
                padding: '6px 12px',
                borderRadius: '8px',
                border: `1px solid ${colors.subtleBorder}`,
                backgroundColor: 'transparent',
                color: colors.headingText,
                cursor: 'pointer',
                fontWeight: 500,
                lineHeight: '1',
              }}
            >
              {type === 'reply' ? 'Open' : 'Follow up'}
            </button>
            <button
              type="button"
              onClick={() => handleDismiss(item.id)}
              aria-label="Dismiss"
              style={{
                padding: '4px',
                borderRadius: '4px',
                border: 'none',
                backgroundColor: 'transparent',
                color: colors.secondaryText,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <X size={14} />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// DraftSubSection — renders draft items with Approve/Dismiss server mutations
// ---------------------------------------------------------------------------

function DraftSubSection({
  items,
  showLabel,
}: {
  items: AttentionItem[]
  showLabel: boolean
}) {
  const queryClient = useQueryClient()
  const approveDraft = useApproveDraft()
  const dismissDraft = useDismissDraft()
  const config = ATTENTION_CONFIG.draft
  const Icon = config.icon

  const handleApprove = (draftId: string) => {
    approveDraft.mutate(
      { draftId },
      {
        onSettled: () => queryClient.invalidateQueries({ queryKey: ['briefing-v2'] }),
      },
    )
  }

  const handleDismiss = (draftId: string) => {
    dismissDraft.mutate(
      { draftId },
      {
        onSettled: () => queryClient.invalidateQueries({ queryKey: ['briefing-v2'] }),
      },
    )
  }

  return (
    <div>
      {showLabel && (
        <div
          style={{
            fontSize: typography.caption.size,
            fontWeight: 600,
            color: colors.secondaryText,
            marginBottom: '8px',
            marginTop: '8px',
          }}
        >
          {config.label}
        </div>
      )}
      {items.map((item, index) => (
        <div
          key={item.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingTop: '12px',
            paddingBottom: '12px',
            borderBottom:
              index === items.length - 1
                ? 'none'
                : `1px solid ${colors.subtleBorder}`,
          }}
        >
          {/* Left side: icon + text */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', flex: '1 1 0%', minWidth: 0 }}>
            <Icon
              size={16}
              style={{ color: config.iconColor, flexShrink: 0, marginTop: '2px' }}
            />
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontSize: '15px',
                  fontWeight: 500,
                  color: colors.headingText,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {item.title}
              </div>
              <AttentionSubtitle item={item} type="draft" />
            </div>
          </div>

          {/* Right side: Approve + Dismiss buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '12px', flexShrink: 0 }}>
            <button
              type="button"
              onClick={() => handleApprove(item.id)}
              disabled={approveDraft.isPending}
              style={{
                fontSize: '13px',
                padding: '6px 12px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: '#E94D35',
                color: '#fff',
                cursor: approveDraft.isPending ? 'not-allowed' : 'pointer',
                fontWeight: 500,
                lineHeight: '1',
                opacity: approveDraft.isPending ? 0.6 : 1,
              }}
            >
              Approve
            </button>
            <button
              type="button"
              onClick={() => handleDismiss(item.id)}
              disabled={dismissDraft.isPending}
              style={{
                fontSize: '13px',
                padding: '6px 12px',
                borderRadius: '8px',
                border: `1px solid ${colors.subtleBorder}`,
                backgroundColor: 'transparent',
                color: colors.headingText,
                cursor: dismissDraft.isPending ? 'not-allowed' : 'pointer',
                fontWeight: 500,
                lineHeight: '1',
                opacity: dismissDraft.isPending ? 0.6 : 1,
              }}
            >
              Dismiss
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AttentionSubtitle — contact name, company, preview, days overdue
// ---------------------------------------------------------------------------

function AttentionSubtitle({
  item,
  type,
}: {
  item: AttentionItem
  type: 'reply' | 'follow_up' | 'draft'
}) {
  const parts: string[] = []

  if (item.contact_name) {
    let contactPart = item.contact_name
    if (item.company_name) {
      contactPart += ` at ${item.company_name}`
    }
    parts.push(contactPart)
  } else if (item.company_name) {
    parts.push(item.company_name)
  }

  if (item.preview) {
    parts.push(item.preview)
  }

  if (parts.length === 0 && type !== 'follow_up') return null

  return (
    <div
      style={{
        fontSize: '13px',
        color: colors.secondaryText,
        marginTop: '2px',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}
    >
      {parts.join(' \u2014 ')}
      {type === 'follow_up' && item.days_overdue != null && item.days_overdue > 0 && (
        <span style={{ color: colors.error }}>
          {parts.length > 0 ? ' \u00B7 ' : ''}
          {item.days_overdue} day{item.days_overdue === 1 ? '' : 's'} overdue
        </span>
      )}
    </div>
  )
}
