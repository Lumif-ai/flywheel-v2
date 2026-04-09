import { Share2, Trash2 } from 'lucide-react'
import { colors } from '@/lib/design-tokens'
import { staggerDelay } from '@/lib/animations'
import type { DocumentListItem } from '../api'
import { getTypeStyle, displayTitle, relativeTime } from '../utils'

interface DocumentGridCardProps {
  document: DocumentListItem
  index?: number
  onView?: (doc: DocumentListItem) => void
  onShare?: (doc: DocumentListItem) => void
  onDelete?: (doc: DocumentListItem) => void
}

export function DocumentGridCard({
  document,
  index = 0,
  onView,
  onShare,
  onDelete,
}: DocumentGridCardProps) {
  const style = getTypeStyle(document.document_type)
  const Icon = style.icon
  const title = displayTitle(document.title, document.document_type, document.metadata)
  const tags = document.tags ?? []
  const maxVisibleTags = 3
  const visibleTags = tags.slice(0, maxVisibleTags)
  const overflowCount = tags.length - maxVisibleTags

  return (
    <div
      className="group/card animate-fade-slide-up bg-[var(--card-bg)] border border-[var(--subtle-border)] rounded-xl p-4 cursor-pointer transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md hover:border-[rgba(233,77,53,0.2)] flex flex-col"
      style={{
        animationDelay: staggerDelay(index),
        animationFillMode: 'both',
        minHeight: '120px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      }}
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
      {/* Top: Icon + Title */}
      <div className="flex items-start gap-2.5">
        <div
          className="flex-shrink-0 flex items-center justify-center size-8 rounded-md"
          style={{ backgroundColor: style.iconBg }}
        >
          <Icon size={15} style={{ color: style.iconColor }} />
        </div>
        <div className="flex-1 min-w-0">
          <h3
            className="font-medium line-clamp-2"
            style={{
              fontSize: '14px',
              lineHeight: '1.4',
              color: colors.headingText,
            }}
          >
            {title}
          </h3>
          {document.account_name && (
            <p
              className="truncate mt-0.5"
              style={{ fontSize: '12px', color: colors.secondaryText }}
            >
              {document.account_name}
            </p>
          )}
        </div>
      </div>

      {/* Tag pills */}
      {visibleTags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2.5">
          {visibleTags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center px-2 py-px rounded-full"
              style={{
                fontSize: '11px',
                fontWeight: 500,
                backgroundColor: 'rgba(0,0,0,0.04)',
                color: colors.secondaryText,
              }}
            >
              {tag}
            </span>
          ))}
          {overflowCount > 0 && (
            <span
              className="inline-flex items-center px-1.5 py-px rounded-full"
              style={{ fontSize: '11px', color: colors.secondaryText, opacity: 0.7 }}
            >
              +{overflowCount}
            </span>
          )}
        </div>
      )}

      {/* Bottom: Time + Share */}
      <div className="flex items-center justify-between mt-auto pt-2.5">
        <span style={{ fontSize: '12px', color: colors.secondaryText }}>
          {relativeTime(document.created_at)}
        </span>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            className="opacity-0 group-hover/card:opacity-100 inline-flex items-center justify-center size-6 rounded-md transition-all duration-200 hover:bg-[var(--brand-tint)]"
            style={{ color: colors.secondaryText }}
            onClick={(e) => {
              e.stopPropagation()
              onShare?.(document)
            }}
            aria-label={`Share ${title}`}
          >
            <Share2 size={12} />
          </button>
          <button
            type="button"
            className="opacity-0 group-hover/card:opacity-100 inline-flex items-center justify-center size-6 rounded-md transition-all duration-200 hover:bg-[rgba(239,68,68,0.08)]"
            style={{ color: '#EF4444' }}
            onClick={(e) => {
              e.stopPropagation()
              onDelete?.(document)
            }}
            aria-label={`Delete ${title}`}
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>
    </div>
  )
}

// Skeleton for grid loading state
export function DocumentGridCardSkeleton() {
  return (
    <div
      className="bg-[var(--card-bg)] border border-[var(--subtle-border)] rounded-xl p-4 flex flex-col"
      style={{ minHeight: '120px', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}
    >
      <div className="flex items-start gap-2.5">
        <div className="size-8 rounded-md animate-shimmer bg-[var(--skeleton-bg)]" />
        <div className="flex-1 space-y-1.5">
          <div className="h-3.5 w-4/5 rounded animate-shimmer bg-[var(--skeleton-bg)]" />
          <div className="h-3.5 w-3/5 rounded animate-shimmer bg-[var(--skeleton-bg)]" />
        </div>
      </div>
      <div className="flex items-center justify-between mt-auto pt-2.5">
        <div className="h-3 w-14 rounded animate-shimmer bg-[var(--skeleton-bg)]" />
        <div className="h-4 w-16 rounded-full animate-shimmer bg-[var(--skeleton-bg)]" />
      </div>
    </div>
  )
}
