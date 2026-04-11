import { Share2, ChevronRight } from 'lucide-react'
import { colors } from '@/lib/design-tokens'
import type { DocumentListItem } from '../api'
import { getTypeStyle, displayTitle, relativeTime, getDisplayEntities } from '../utils'

interface DocumentRowProps {
  document: DocumentListItem
  onView?: (doc: DocumentListItem) => void
  onShare?: (doc: DocumentListItem) => void
  onAddTag?: (doc: DocumentListItem) => void
  onDelete?: (doc: DocumentListItem) => void | Promise<void>
}

export function DocumentRow({ document, onView, onShare }: DocumentRowProps) {
  const style = getTypeStyle(document.document_type)
  const Icon = style.icon
  const entities = getDisplayEntities(document.metadata, 2)
  const title = displayTitle(document.title, document.document_type, document.metadata)

  return (
    <div
      className="group/row flex items-center gap-2.5 px-3 py-2 rounded-lg cursor-pointer transition-all duration-200 hover:bg-[rgba(233,77,53,0.04)]"
      onClick={() => onView?.(document)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onView?.(document)
        }
      }}
      role="button"
      tabIndex={0}
      aria-label={`View document: ${title}`}
    >
      {/* Type icon */}
      <div
        className="flex-shrink-0 flex items-center justify-center size-8 rounded-md"
        style={{ backgroundColor: style.iconBg }}
      >
        <Icon size={15} style={{ color: style.iconColor }} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <h3
          className="font-medium truncate"
          style={{
            fontSize: '14px',
            lineHeight: '1.4',
            color: colors.headingText,
          }}
        >
          {title}
        </h3>
        <div
          className="flex items-center gap-1 mt-px"
          style={{ fontSize: '12px', color: colors.secondaryText }}
        >
          {entities.map((e, i) => (
            <span key={e}>
              {i > 0 && <span className="mx-0.5" aria-hidden="true">&middot;</span>}
              {e}
            </span>
          ))}
          {entities.length > 0 && <span className="mx-0.5" aria-hidden="true">&middot;</span>}
          <span>{relativeTime(document.created_at)}</span>
        </div>
      </div>

      {/* Type badge */}
      <span
        className="flex-shrink-0 hidden sm:inline-flex items-center px-2 py-px rounded-full font-medium"
        style={{ fontSize: '11px', backgroundColor: style.badgeBg, color: style.badgeText }}
      >
        {style.label}
      </span>

      {/* Share button — appears on hover */}
      <button
        type="button"
        className="flex-shrink-0 opacity-0 group-hover/row:opacity-100 inline-flex items-center justify-center size-7 rounded-md transition-all duration-200 hover:bg-[var(--brand-tint)]"
        style={{ color: colors.secondaryText }}
        onClick={(e) => {
          e.stopPropagation()
          onShare?.(document)
        }}
        aria-label={`Share ${title}`}
      >
        <Share2 size={13} />
      </button>

      {/* Chevron — appears on hover */}
      <ChevronRight
        size={14}
        className="flex-shrink-0 opacity-0 group-hover/row:opacity-100 transition-opacity duration-200"
        style={{ color: colors.secondaryText }}
        aria-hidden="true"
      />
    </div>
  )
}

// Skeleton for loading state
export function DocumentRowSkeleton() {
  return (
    <div className="flex items-center gap-2.5 px-3 py-2">
      <div className="size-8 rounded-md animate-shimmer bg-[var(--skeleton-bg)]" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3.5 w-3/5 rounded animate-shimmer bg-[var(--skeleton-bg)]" />
        <div className="h-3 w-2/5 rounded animate-shimmer bg-[var(--skeleton-bg)]" />
      </div>
      <div className="h-4 w-16 rounded-full animate-shimmer bg-[var(--skeleton-bg)] hidden sm:block" />
    </div>
  )
}
