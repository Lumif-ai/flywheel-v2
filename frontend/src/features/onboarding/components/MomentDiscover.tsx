/**
 * MomentDiscover - Second onboarding moment.
 *
 * Two phases:
 * 1. Cascade: shimmer skeletons, stagger animation, auto-scroll as crawl runs
 * 2. Edit mode: users can remove, add, and inline-edit discovered items.
 *    "Looks good" CTA confirms edits and advances to Align.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Building2,
  Package,
  Users,
  TrendingUp,
  Swords,
  Cpu,
  UserCheck,
  DollarSign,
  Pencil,
  X,
  Plus,
  type LucideIcon,
} from 'lucide-react'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { animationClasses, staggerDelay } from '@/lib/animations'
import type { CrawlItem, CrawlItemMeta, EditedCategory } from '../hooks/useOnboarding'

// ---------------------------------------------------------------------------
// Category icon mapping
// ---------------------------------------------------------------------------

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  company_info: Building2,
  product: Package,
  team: Users,
  market: TrendingUp,
  competitive: Swords,
  technology: Cpu,
  customer: UserCheck,
  financial: DollarSign,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Check if any items are long enough to need list layout instead of pills */
function hasLongItems(items: string[]): boolean {
  return items.some(item => item.length > 60)
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface MomentDiscoverProps {
  crawlItems: CrawlItem[]
  crawlTotal: number
  crawlStatus: string | null
  isComplete: boolean
  editMode: boolean
  editedItems: Record<string, EditedCategory>
  onComplete: () => void
  onRemoveItem: (category: string, itemIndex: number) => void
  onAddItem: (category: string, text: string) => void
  onEditItem: (category: string, itemIndex: number, newText: string) => void
  onConfirmEdits: () => void
}

// ---------------------------------------------------------------------------
// Shimmer skeleton for loading categories
// ---------------------------------------------------------------------------

function ShimmerSkeleton() {
  return (
    <div className="rounded-md border border-border/30 p-3 space-y-2">
      <div className={`h-4 w-32 rounded bg-muted/50 ${animationClasses.shimmer}`} />
      <div className="flex gap-1.5">
        <div className={`h-6 w-20 rounded-full bg-muted/30 ${animationClasses.shimmer}`} />
        <div className={`h-6 w-16 rounded-full bg-muted/30 ${animationClasses.shimmer}`} />
        <div className={`h-6 w-24 rounded-full bg-muted/30 ${animationClasses.shimmer}`} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inline Add Input
// ---------------------------------------------------------------------------

function InlineAddInput({ onAdd }: { onAdd: (text: string) => void }) {
  const [active, setActive] = useState(false)
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim()
    if (trimmed) {
      onAdd(trimmed)
    }
    setValue('')
    setActive(false)
  }, [value, onAdd])

  useEffect(() => {
    if (active) inputRef.current?.focus()
  }, [active])

  if (!active) {
    return (
      <button
        type="button"
        onClick={() => setActive(true)}
        className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 transition-colors hover:bg-black/5"
        style={{
          fontSize: typography.caption.size,
          color: colors.secondaryText,
          cursor: 'pointer',
        }}
      >
        <Plus className="h-3 w-3" />
        Add
      </button>
    )
  }

  return (
    <input
      ref={inputRef}
      type="text"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') handleSubmit()
        if (e.key === 'Escape') { setValue(''); setActive(false) }
      }}
      onBlur={handleSubmit}
      className="inline-block rounded-full px-2.5 py-0.5 outline-none ring-1"
      style={{
        fontSize: typography.caption.size,
        color: colors.bodyText,
        background: colors.cardBg,
        borderColor: colors.brandCoral,
        minWidth: '100px',
        maxWidth: '200px',
      }}
      placeholder="Type and press Enter"
    />
  )
}

// ---------------------------------------------------------------------------
// Editable Item Pill
// ---------------------------------------------------------------------------

function EditableItemPill({
  text,
  deleted,
  isUserAdded,
  onRemove,
  onEdit,
}: {
  text: string
  deleted?: boolean
  isUserAdded: boolean
  onRemove: () => void
  onEdit: (newText: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [editValue, setEditValue] = useState(text)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) inputRef.current?.focus()
  }, [editing])

  const handleSave = useCallback(() => {
    const trimmed = editValue.trim()
    if (trimmed && trimmed !== text) {
      onEdit(trimmed)
    }
    setEditing(false)
  }, [editValue, text, onEdit])

  if (editing) {
    return (
      <input
        ref={inputRef}
        type="text"
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleSave()
          if (e.key === 'Escape') { setEditValue(text); setEditing(false) }
        }}
        onBlur={handleSave}
        className="inline-block rounded-full px-2.5 py-0.5 outline-none ring-1"
        style={{
          fontSize: typography.caption.size,
          color: colors.bodyText,
          background: colors.cardBg,
          borderColor: colors.brandCoral,
          minWidth: '80px',
        }}
      />
    )
  }

  return (
    <span
      className="group relative inline-flex items-center rounded-full px-2.5 py-0.5 cursor-pointer"
      style={{
        fontSize: typography.caption.size,
        background: colors.cardBg,
        border: `1px solid ${colors.subtleBorder}`,
        color: deleted ? colors.secondaryText : colors.bodyText,
        textDecoration: deleted ? 'line-through' : 'none',
        opacity: deleted ? 0.5 : 1,
        borderLeft: isUserAdded ? `3px solid ${colors.brandCoral}` : undefined,
      }}
      onClick={() => { if (!deleted) setEditing(true) }}
    >
      {text}
      {!deleted && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onRemove() }}
          className="ml-1 opacity-0 group-hover:opacity-100 transition-opacity"
          style={{ color: colors.secondaryText }}
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MomentDiscover({
  crawlItems,
  crawlTotal,
  crawlStatus,
  isComplete,
  editMode,
  editedItems,
  onComplete,
  onRemoveItem,
  onAddItem,
  onEditItem,
  onConfirmEdits,
}: MomentDiscoverProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll as new items arrive (cascade phase only)
  useEffect(() => {
    if (!editMode) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [crawlItems.length, editMode])

  // How many shimmer slots to show while loading
  const shimmerCount = isComplete ? 0 : Math.max(0, 3 - crawlItems.length)

  const handleConfirmAndComplete = useCallback(() => {
    onConfirmEdits()
    onComplete()
  }, [onConfirmEdits, onComplete])

  return (
    <div
      className={animationClasses.fadeSlideUp}
      style={{
        maxWidth: spacing.maxReading,
        width: '100%',
        margin: '0 auto',
      }}
    >
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: spacing.section }}>
        <h1
          style={{
            fontSize: typography.pageTitle.size,
            fontWeight: typography.pageTitle.weight,
            lineHeight: typography.pageTitle.lineHeight,
            color: colors.headingText,
            marginBottom: spacing.tight,
          }}
        >
          {editMode ? 'Review what we found' : isComplete ? 'Discovery complete' : (
            <>
              Discovering intelligence
              <span className="inline-flex ml-1">
                <span className="animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
              </span>
            </>
          )}
        </h1>

        {editMode ? (
          <p
            style={{
              fontSize: typography.body.size,
              color: colors.secondaryText,
            }}
          >
            Add anything we missed.
          </p>
        ) : crawlTotal > 0 ? (
          <p
            className="tabular-nums"
            style={{
              fontSize: '24px',
              fontWeight: '600',
              color: colors.brandCoral,
            }}
          >
            {crawlTotal} items found
          </p>
        ) : crawlStatus ? (
          <p
            className="animate-pulse"
            style={{
              fontSize: typography.body.size,
              color: colors.secondaryText,
            }}
          >
            {crawlStatus}
          </p>
        ) : null}
      </div>

      {/* Category cards */}
      <div
        className="space-y-3 overflow-y-auto"
        style={{
          maxHeight: '28rem',
        }}
      >
        {crawlItems.map((group, i) => {
          const IconComponent = CATEGORY_ICONS[group.category] ?? Building2
          const edited = editedItems[group.category]
          const displayItems = editMode && edited ? edited.items : group.items
          const displayMeta = editMode && edited ? edited.meta : null

          return (
            <div
              key={i}
              className={`${animationClasses.fadeSlideUp} relative`}
              style={{
                animationDelay: staggerDelay(i),
                animationFillMode: 'both',
                borderRadius: '8px',
                border: editMode
                  ? `1px dashed ${colors.subtleBorder}`
                  : `1px solid ${colors.subtleBorder}`,
                background: colors.brandTint,
                padding: '12px 16px',
              }}
            >
              {/* Edit mode indicator */}
              {editMode && (
                <Pencil
                  className="absolute top-3 right-3 h-3.5 w-3.5"
                  style={{ color: colors.secondaryText, opacity: 0.5 }}
                />
              )}

              <div className="flex items-center gap-2 mb-1.5">
                <IconComponent className="h-4 w-4 shrink-0" style={{ color: colors.brandCoral }} />
                <span
                  style={{
                    fontSize: typography.body.size,
                    fontWeight: '500',
                    color: colors.headingText,
                  }}
                >
                  {group.label}
                </span>
                <span
                  className="ml-auto"
                  style={{
                    fontSize: typography.caption.size,
                    color: colors.secondaryText,
                  }}
                >
                  {editMode && displayMeta
                    ? displayItems.filter((_, idx) => !displayMeta[idx]?.deleted).length
                    : group.items.length}
                </span>
              </div>

              <div className={hasLongItems(displayItems) ? 'space-y-1.5' : 'flex flex-wrap gap-1.5'}>
                {displayItems.map((item, j) => {
                  const isLong = item.length > 60
                  if (editMode && displayMeta) {
                    const meta = displayMeta[j]
                    if (isLong) {
                      return (
                        <div
                          key={j}
                          className="group flex items-start gap-2"
                          style={{
                            opacity: meta?.deleted ? 0.4 : 1,
                            textDecoration: meta?.deleted ? 'line-through' : 'none',
                          }}
                        >
                          <span
                            className="flex-1 text-sm leading-snug cursor-pointer rounded px-2 py-1 hover:bg-black/5"
                            style={{
                              color: colors.bodyText,
                              borderLeft: meta?.source === 'user_input' ? `3px solid ${colors.brandCoral}` : '3px solid transparent',
                            }}
                            onClick={() => { if (!meta?.deleted) onEditItem(group.category, j, item) }}
                          >
                            {item}
                          </span>
                          {!meta?.deleted && (
                            <button
                              type="button"
                              onClick={() => onRemoveItem(group.category, j)}
                              className="shrink-0 mt-1 opacity-0 group-hover:opacity-100 transition-opacity"
                              style={{ color: colors.secondaryText }}
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </div>
                      )
                    }
                    return (
                      <EditableItemPill
                        key={j}
                        text={item}
                        deleted={meta?.deleted}
                        isUserAdded={meta?.source === 'user_input'}
                        onRemove={() => onRemoveItem(group.category, j)}
                        onEdit={(newText) => onEditItem(group.category, j, newText)}
                      />
                    )
                  }
                  if (isLong) {
                    return (
                      <div
                        key={j}
                        className="text-sm leading-snug rounded px-2 py-1"
                        style={{ color: colors.bodyText }}
                      >
                        {item}
                      </div>
                    )
                  }
                  return (
                    <span
                      key={j}
                      className="inline-block rounded-full px-2.5 py-0.5"
                      style={{
                        fontSize: typography.caption.size,
                        background: colors.cardBg,
                        border: `1px solid ${colors.subtleBorder}`,
                        color: colors.bodyText,
                      }}
                    >
                      {item}
                    </span>
                  )
                })}

                {/* Add button in edit mode */}
                {editMode && (
                  <InlineAddInput onAdd={(text) => onAddItem(group.category, text)} />
                )}
              </div>
            </div>
          )
        })}

        {/* Shimmer skeletons for not-yet-loaded categories */}
        {Array.from({ length: shimmerCount }).map((_, i) => (
          <ShimmerSkeleton key={`shimmer-${i}`} />
        ))}

        {/* Status spinner when no items yet */}
        {crawlItems.length === 0 && crawlStatus && (
          <div className="flex items-center justify-center gap-2 py-8" style={{ color: colors.secondaryText }}>
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            <span style={{ fontSize: typography.caption.size }}>{crawlStatus}</span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* "Looks good" CTA in edit mode */}
      {editMode && (
        <div style={{ marginTop: spacing.element, textAlign: 'center' }}>
          <button
            type="button"
            onClick={handleConfirmAndComplete}
            className="w-full rounded-lg py-3 px-6 text-white font-semibold transition-all hover:opacity-90"
            style={{
              background: `linear-gradient(135deg, ${colors.brandCoral}, ${colors.brandGradientEnd})`,
              fontSize: typography.body.size,
              border: 'none',
              cursor: 'pointer',
            }}
          >
            Looks good
          </button>
        </div>
      )}
    </div>
  )
}
