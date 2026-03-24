import { FileText, Building2, Share2, ChevronRight } from 'lucide-react'
import { BrandedCard } from '@/components/ui/branded-card'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { staggerDelay } from '@/lib/animations'
import type { DocumentListItem } from '../api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TYPE_ICONS: Record<string, typeof FileText> = {
  'meeting-prep': FileText,
  'company-intel': Building2,
}

function getTypeIcon(docType: string) {
  return TYPE_ICONS[docType] || FileText
}

function getTypeLabel(docType: string): string {
  switch (docType) {
    case 'meeting-prep':
      return 'Meeting Prep'
    case 'company-intel':
      return 'Company Intel'
    default:
      return docType.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  }
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

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
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors hover:bg-gray-100"
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
          className="inline-flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg transition-colors hover:bg-gray-100"
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
