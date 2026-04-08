import { useBriefingV2 } from '@/features/briefing/hooks/useBriefingV2'
import { DailyBriefSection } from '@/features/briefing/components/DailyBriefSection'
import { TodaySection } from '@/features/briefing/components/TodaySection'
import { TasksSection } from '@/features/briefing/components/TasksSection'
import { ChatPanelV2 } from '@/features/briefing/components/ChatPanelV2'
import { spacing, typography, colors } from '@/lib/design-tokens'

/**
 * BriefingPageV2 — Two-column page shell for the v11.0 briefing redesign.
 *
 * Left column: scrollable briefing content (Daily Brief, Today, Attention, Tasks, Team Activity)
 * Right column: sticky chat panel placeholder (ChatPanelV2 mounts here in Plan 02)
 *
 * The outer flex container uses 100dvh and overflow:hidden so each column
 * scrolls independently. This works inside the sidebar shell because 100dvh
 * always resolves to the full viewport height.
 */
export function BriefingPageV2() {
  const { data, isLoading } = useBriefingV2()

  // Greeting based on time of day
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning.' : hour < 17 ? 'Good afternoon.' : 'Good evening.'

  return (
    <div
      style={{
        display: 'flex',
        height: '100dvh',
        overflow: 'hidden',
        background: colors.pageBg,
      }}
    >
      {/* Left column: scrollable briefing content */}
      <div
        style={{
          flex: '1 1 0%',
          overflowY: 'auto',
          padding: spacing.pageDesktop,
        }}
      >
        <div style={{ maxWidth: spacing.maxBriefing, margin: '0 auto' }}>
          {/* Greeting */}
          <h1
            style={{
              fontSize: typography.pageTitle.size,
              fontWeight: typography.pageTitle.weight,
              lineHeight: typography.pageTitle.lineHeight,
              letterSpacing: typography.pageTitle.letterSpacing,
              color: colors.headingText,
              margin: 0,
              paddingBottom: spacing.section,
            }}
          >
            {greeting}
          </h1>

          {/* Daily Brief narrative section */}
          <DailyBriefSection narrative={data?.narrative_summary} isLoading={isLoading} />

          {/* Today's meetings */}
          <div style={{ marginTop: spacing.section }}>
            <TodaySection meetings={data?.today?.meetings} isLoading={isLoading} />
          </div>

          {/* Tasks due today */}
          <div style={{ marginTop: spacing.section }}>
            <TasksSection tasks={data?.today?.tasks} isLoading={isLoading} />
          </div>

          {/* Phase 99: NeedsAttentionSection, TeamActivitySection */}
        </div>
      </div>

      {/* Right column: sticky chat panel — ChatPanelV2 mounts here in Plan 02 */}
      <div
        className="hidden lg:flex"
        style={{
          width: '350px',
          flexShrink: 0,
          borderLeft: `1px solid ${colors.subtleBorder}`,
          flexDirection: 'column',
        }}
      >
        <ChatPanelV2 data={data} />
      </div>
    </div>
  )
}
