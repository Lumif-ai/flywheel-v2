import { useState } from 'react'
import { Inbox } from 'lucide-react'
import { AllCommunityModule, themeQuartz } from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import { usePipeline } from '../hooks/usePipeline'
import { usePipelineColumns } from '../hooks/usePipelineColumns'
import { ShimmerSkeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { spacing, typography, colors } from '@/lib/design-tokens'

const PAGE_SIZE = 50

const pipelineTheme = themeQuartz.withParams({
  backgroundColor: 'var(--card-bg)',
  foregroundColor: 'var(--body-text)',
  headerBackgroundColor: 'var(--card-bg)',
  headerTextColor: 'var(--secondary-text)',
  borderColor: 'var(--subtle-border)',
  accentColor: 'var(--brand-coral)',
  rowHoverColor: 'rgba(0,0,0,0.02)',
  fontSize: 14,
  rowHeight: 56,
  headerHeight: 40,
  fontFamily: "'Geist Variable', ui-sans-serif, system-ui, sans-serif",
})

const selectStyle: React.CSSProperties = {
  fontSize: typography.caption.size,
  padding: '6px 10px',
  borderRadius: '8px',
  border: `1px solid ${colors.subtleBorder}`,
  background: colors.cardBg,
  color: colors.headingText,
  cursor: 'pointer',
}

export function PipelinePage() {
  const [fitTier, setFitTier] = useState<string | undefined>(undefined)
  const [outreachStatus, setOutreachStatus] = useState<string | undefined>(undefined)

  const { data, isLoading } = usePipeline({
    offset: 0,
    limit: PAGE_SIZE,
    fit_tier: fitTier,
    outreach_status: outreachStatus,
  })

  const items = data?.items ?? []

  const { columnDefs, initialState, onColumnStateChanged, gridApiRef } = usePipelineColumns()

  return (
    <div
      className="page-enter"
      style={{ padding: spacing.pageDesktop, background: colors.pageBg }}
    >
      <div className="mx-auto" style={{ maxWidth: spacing.maxGrid }}>
        {/* Header */}
        <div style={{ marginBottom: spacing.section }}>
          <h1
            style={{
              fontSize: typography.pageTitle.size,
              fontWeight: typography.pageTitle.weight,
              lineHeight: typography.pageTitle.lineHeight,
              letterSpacing: typography.pageTitle.letterSpacing,
              color: colors.headingText,
              marginBottom: '4px',
            }}
          >
            Pipeline
          </h1>
          <p style={{ fontSize: typography.body.size, color: colors.secondaryText, margin: 0 }}>
            Prospect accounts ready for outreach
          </p>
        </div>

        {/* Filters */}
        <div
          className="flex items-center gap-3 flex-wrap"
          style={{ marginBottom: spacing.element }}
        >
          <select
            value={fitTier ?? ''}
            onChange={(e) => setFitTier(e.target.value || undefined)}
            style={selectStyle}
          >
            <option value="">All Tiers</option>
            <option value="Excellent">Excellent</option>
            <option value="Good">Good</option>
            <option value="Fair">Fair</option>
            <option value="Poor">Poor</option>
          </select>
          <select
            value={outreachStatus ?? ''}
            onChange={(e) => setOutreachStatus(e.target.value || undefined)}
            style={selectStyle}
          >
            <option value="">All Statuses</option>
            <option value="sent">Sent</option>
            <option value="opened">Opened</option>
            <option value="replied">Replied</option>
            <option value="bounced">Bounced</option>
          </select>
        </div>

        {/* Grid area */}
        {isLoading ? (
          <div
            style={{
              background: colors.cardBg,
              borderRadius: '12px',
              border: `1px solid ${colors.subtleBorder}`,
              overflow: 'hidden',
            }}
          >
            {/* Header shimmer */}
            <div
              style={{
                height: '40px',
                borderBottom: `1px solid ${colors.subtleBorder}`,
                padding: '0 16px',
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
              }}
            >
              {[1.5, 1, 1, 0.6, 0.8, 0.8, 0.8, 0.6, 0.6].map((flex, i) => (
                <ShimmerSkeleton key={i} style={{ flex, height: '12px', borderRadius: '4px' }} />
              ))}
            </div>
            {/* Row shimmers */}
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                style={{
                  height: '56px',
                  borderBottom: `1px solid ${colors.subtleBorder}`,
                  padding: '0 16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px',
                }}
              >
                {[1.5, 1, 1, 0.6, 0.8, 0.8, 0.8, 0.6, 0.6].map((flex, j) => (
                  <ShimmerSkeleton key={j} style={{ flex, height: '14px', borderRadius: '4px' }} />
                ))}
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div
            style={{
              background: colors.cardBg,
              borderRadius: '12px',
              border: `1px solid ${colors.subtleBorder}`,
            }}
          >
            <EmptyState
              icon={Inbox}
              title="No prospects in pipeline"
              description="Add accounts to start building your pipeline"
            />
          </div>
        ) : (
          <div
            style={{
              height: 'calc(100vh - 280px)',
              width: '100%',
              borderRadius: '12px',
              overflow: 'hidden',
              border: `1px solid ${colors.subtleBorder}`,
            }}
          >
            <AgGridReact
              modules={[AllCommunityModule]}
              theme={pipelineTheme}
              rowData={items}
              columnDefs={columnDefs}
              initialState={initialState}
              onColumnResized={onColumnStateChanged}
              onColumnMoved={onColumnStateChanged}
              onColumnVisible={onColumnStateChanged}
              onGridReady={(e) => {
                gridApiRef.current = e.api
              }}
              defaultColDef={{ resizable: true, sortable: true }}
              context={{
                onGraduate: (id: string, name: string) =>
                  console.log('Graduate', id, name),
              }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
