import { Link } from 'react-router'
import { Building2, Package, Users, Target, TrendingUp, Layers } from 'lucide-react'
import { spacing, typography, colors } from '@/lib/design-tokens'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface IntelCategory {
  file_name: string
  item_count: number
}

interface IntelSummary {
  total_items: number
  categories: IntelCategory[]
}

interface FirstVisitHeroProps {
  briefingHtml: string | null
  intelSummary: IntelSummary | null
  companyName: string | null
}

// ---------------------------------------------------------------------------
// File name display mapping
// ---------------------------------------------------------------------------

const FILE_ICONS: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  positioning: Building2,
  'product-modules': Package,
  buyers: Users,
  'icp-profile': Target,
  'go-to-market': TrendingUp,
  competitors: Layers,
}

const DEFAULT_ICON = Building2

function formatFileLabel(fileName: string): string {
  return fileName
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CategoryCard({ category }: { category: IntelCategory }) {
  const IconComponent = FILE_ICONS[category.file_name] ?? DEFAULT_ICON

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '12px 16px',
        borderRadius: '10px',
        border: `1px solid ${colors.subtleBorder}`,
        background: colors.cardBg,
      }}
    >
      <IconComponent
        className="shrink-0"
        style={{
          width: '16px',
          height: '16px',
          color: colors.brandCoral,
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <p
          className="truncate"
          style={{
            fontSize: typography.body.size,
            fontWeight: '500',
            color: colors.headingText,
            margin: 0,
          }}
        >
          {formatFileLabel(category.file_name)}
        </p>
      </div>
      <span
        style={{
          fontSize: typography.caption.size,
          color: colors.secondaryText,
          whiteSpace: 'nowrap',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {category.item_count} items
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function FirstVisitHero({ briefingHtml, intelSummary, companyName }: FirstVisitHeroProps) {
  // Empty state: nothing to show
  if (!briefingHtml && !intelSummary) {
    return null
  }

  // Path A: Briefing HTML exists (meeting prep was completed)
  if (briefingHtml) {
    return (
      <div
        style={{
          borderRadius: '12px',
          border: `1px solid ${colors.subtleBorder}`,
          background: 'rgba(233, 77, 53, 0.03)',
          overflow: 'hidden',
        }}
      >
        {/* Card header */}
        <div
          style={{
            padding: '20px 24px 16px',
            borderBottom: `1px solid ${colors.subtleBorder}`,
          }}
        >
          <h2
            style={{
              fontSize: typography.sectionTitle.size,
              fontWeight: typography.sectionTitle.weight,
              color: colors.headingText,
              margin: 0,
            }}
          >
            Your briefing is ready
          </h2>
          <p
            style={{
              fontSize: typography.body.size,
              color: colors.secondaryText,
              margin: '4px 0 0',
            }}
          >
            Prepared from your meeting prep during setup.
          </p>
        </div>

        {/* Briefing HTML */}
        <div
          className="prose prose-sm dark:prose-invert"
          style={{
            maxHeight: '400px',
            overflowY: 'auto',
            padding: '20px 24px',
            fontSize: typography.body.size,
          }}
          dangerouslySetInnerHTML={{ __html: briefingHtml }}
        />

        {/* Footer links */}
        <div
          style={{
            padding: '12px 24px 20px',
            borderTop: `1px solid ${colors.subtleBorder}`,
            display: 'flex',
            gap: '20px',
          }}
        >
          <Link
            to="/documents"
            className="no-underline hover:underline"
            style={{
              fontSize: typography.body.size,
              color: colors.brandCoral,
              fontWeight: '500',
            }}
          >
            Open full briefing &rarr;
          </Link>
          <Link
            to="/profile"
            className="no-underline hover:underline"
            style={{
              fontSize: typography.body.size,
              color: colors.secondaryText,
            }}
          >
            View company profile
          </Link>
        </div>
      </div>
    )
  }

  // Path B: No briefing, show intel summary
  return (
    <div
      style={{
        borderRadius: '12px',
        border: `1px solid ${colors.subtleBorder}`,
        background: 'rgba(233, 77, 53, 0.03)',
        padding: '24px',
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: spacing.element }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '12px' }}>
          <h2
            style={{
              fontSize: typography.sectionTitle.size,
              fontWeight: typography.sectionTitle.weight,
              color: colors.headingText,
              margin: 0,
            }}
          >
            Your Company Profile
          </h2>
          {intelSummary && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '2px 10px',
                borderRadius: '999px',
                background: 'rgba(233, 77, 53, 0.1)',
                color: colors.brandCoral,
                fontSize: typography.caption.size,
                fontWeight: '600',
                whiteSpace: 'nowrap',
              }}
            >
              {intelSummary.total_items} items discovered
            </span>
          )}
        </div>
        {companyName && (
          <p
            style={{
              fontSize: typography.body.size,
              color: colors.secondaryText,
              margin: '4px 0 0',
            }}
          >
            {companyName}
          </p>
        )}
      </div>

      {/* Category grid */}
      {intelSummary && intelSummary.categories.length > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: '10px',
            marginBottom: spacing.element,
          }}
        >
          {intelSummary.categories.map((cat) => (
            <CategoryCard key={cat.file_name} category={cat} />
          ))}
        </div>
      )}

      {/* Footer link */}
      <Link
        to="/profile"
        className="no-underline hover:underline"
        style={{
          fontSize: typography.body.size,
          color: colors.brandCoral,
          fontWeight: '500',
        }}
      >
        View full profile &rarr;
      </Link>
    </div>
  )
}
