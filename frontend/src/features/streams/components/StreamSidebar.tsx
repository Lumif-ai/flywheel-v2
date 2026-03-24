import { NavLink, useLocation } from 'react-router'
import { Plus, Archive } from 'lucide-react'
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarMenuSkeleton,
} from '@/components/ui/sidebar'
import { useStreams } from '@/features/briefing/hooks/useStreams'
import { StreamDensityCard } from './DensityIndicator'

const streamItemStyle = {
  active: {
    borderLeft: '2px solid var(--brand-coral)',
    backgroundColor: 'rgba(233,77,53,0.06)',
    borderRadius: '0 6px 6px 0',
    transition: 'all 150ms ease-out',
  },
  inactive: {
    borderLeft: '2px solid transparent',
    borderRadius: '0 6px 6px 0',
    transition: 'all 150ms ease-out',
  },
} as const

const MAX_VISIBLE = 7

export function StreamSidebar() {
  const location = useLocation()
  const { data, isLoading } = useStreams()

  const streams = data?.items ?? []
  const activeStreams = streams.filter((s) => !s.is_archived)
  const dormantStreams = streams.filter((s) => s.is_archived)
  const visibleStreams = activeStreams.slice(0, MAX_VISIBLE)
  const overflowCount = activeStreams.length - MAX_VISIBLE

  if (isLoading) {
    return (
      <SidebarGroup>
        <SidebarGroupLabel className="text-xs uppercase tracking-wider" style={{ fontSize: '13px', color: 'var(--secondary-text)' }}>Focus Areas</SidebarGroupLabel>
        <SidebarGroupContent>
          <SidebarMenu>
            {Array.from({ length: 3 }).map((_, i) => (
              <SidebarMenuItem key={i}>
                <SidebarMenuSkeleton />
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
    )
  }

  return (
    <>
      <SidebarGroup>
        <SidebarGroupLabel className="text-xs uppercase tracking-wider" style={{ fontSize: '13px', color: 'var(--secondary-text)' }}>Focus Areas</SidebarGroupLabel>
        <SidebarGroupContent>
          <SidebarMenu>
            {activeStreams.length === 0 && (
              <p className="px-2 py-3 text-xs" style={{ color: 'var(--secondary-text)' }}>
                No focus areas yet
              </p>
            )}
            {visibleStreams.map((stream) => {
              const density = stream.density_score ?? 0
              const dotColor = density > 70 ? '#22C55E' : density >= 30 ? '#F59E0B' : '#9CA3AF'
              const isActive = location.pathname === `/streams/${stream.id}`
              return (
                <SidebarMenuItem
                  key={stream.id}
                  style={isActive ? streamItemStyle.active : streamItemStyle.inactive}
                  className={isActive ? '' : 'hover:bg-[rgba(233,77,53,0.03)]'}
                >
                  <SidebarMenuButton
                    isActive={isActive}
                    render={<NavLink to={`/streams/${stream.id}`} />}
                    tooltip={stream.name}
                  >
                    <span
                      className="shrink-0 rounded-full"
                      style={{ width: 8, height: 8, backgroundColor: dotColor }}
                    />
                    <span className="truncate flex-1">{stream.name}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )
            })}

            {overflowCount > 0 && (
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<NavLink to="/streams" />}
                  tooltip="View all streams"
                >
                  <span className="text-muted-foreground text-xs">
                    +{overflowCount} more
                  </span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )}

            <SidebarMenuItem>
              <SidebarMenuButton
                render={<NavLink to="/streams/new" />}
                tooltip="Create new stream"
              >
                <Plus className="size-4" />
                <span>New Focus Area</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>

      {dormantStreams.length > 0 && (
        <SidebarGroup>
          <SidebarGroupLabel>
            <Archive className="size-3 mr-1" />
            Dormant
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {dormantStreams.map((stream) => (
                <SidebarMenuItem key={stream.id}>
                  <SidebarMenuButton
                    render={<NavLink to={`/streams/${stream.id}`} />}
                    tooltip={stream.name}
                  >
                    <span className="truncate flex-1 text-muted-foreground">
                      {stream.name}
                    </span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      )}
    </>
  )
}
