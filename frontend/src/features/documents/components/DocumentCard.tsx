import { Share2, ChevronRight } from 'lucide-react'
import { BrandedCard } from '@/components/ui/branded-card'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { staggerDelay } from '@/lib/animations'
import type { DocumentListItem } from '../api'
import { getTypeIcon, getTypeLabel, relativeTime } from '../utils'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface DocumentCardProps {
  document: DocumentListItem
  index?: number
  onShare?: (doc: DocumentListItem) => void
  onView?: (doc: DocumentListItem) => void
}

export function DocumentCard({
  document,
  index = 0,
  onShare,
  onView,
}: DocumentCardProps) {
  const Icon = getTypeIcon(document.document_type)
  const companies = document.metadata?.companies ?? []
  const contacts = document.metadata?.contacts ?? []
  const entities = [...companies, ...contacts].slice(0, 3)

  return (
    <div
      className="animate-fade-slide-up"
      style={{
        animationDelay: staggerDelay(index),
        animationFillMode: 'both',
      }}
    >
    <BrandedCard
      variant="info"
      hoverable
      onClick={() => onView?.(document)}
    >
      {/* Row 1: Icon + Title */}
      <div className="flex items-start gap-3">
        <div
          className="flex-shrink-0 mt-0.5 rounded-lg p-2"
          style={{ backgroundColor: colors.brandTint }}
        >
          <Icon size={18} style={{ color: colors.brandCoral }} />
        </div>
        <div className="flex-1 min-w-0">
          <h3
            className="font-semibold truncate"
            style={{
              fontSize: typography.body.size,
              lineHeight: typography.body.lineHeight,
              color: colors.headingText,
            }}
          >
            {document.title}
          </h3>
          {/* Row 2: Entities + time */}
          <div
            className="flex items-center gap-2 mt-1 flex-wrap"
            style={{
              fontSize: typography.caption.size,
              color: colors.secondaryText,
            }}
          >
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
              style={{
                backgroundColor: colors.brandTint,
                color: colors.brandCoral,
              }}
            >
              {getTypeLabel(document.document_type)}
            </span>
            {entities.map((e) => (
              <span key={e}>{e}</span>
            ))}
            <span className="text-[var(--secondary-text)]">
              {relativeTime(document.created_at)}
            </span>
          </div>
        </div>
      </div>

      {/* Row 3: Actions */}
      <div
        className="flex items-center justify-end gap-2 mt-3"
        style={{ paddingTop: spacing.tight }}
      >
        <button
          type="button"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors hover:bg-[var(--brand-tint)]"
          style={{ color: colors.secondaryText }}
          onClick={(e) => {
            e.stopPropagation()
            onShare?.(document)
          }}
        >
          <Share2 size={14} />
          Share
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg transition-colors hover:bg-[var(--brand-tint)]"
          style={{ color: colors.brandCoral }}
          onClick={(e) => {
            e.stopPropagation()
            onView?.(document)
          }}
        >
          View
          <ChevronRight size={14} />
        </button>
      </div>
    </BrandedCard>
    </div>
  )
}
