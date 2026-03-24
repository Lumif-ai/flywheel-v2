import { NavLink, useLocation, Link } from 'react-router'
import { Home, Settings, FileText, Building2 } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarHeader,
  SidebarFooter,
} from '@/components/ui/sidebar'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { TenantSwitcher } from './TenantSwitcher'
import { StreamSidebar } from '@/features/streams/components/StreamSidebar'

export function AppSidebar() {
  const location = useLocation()

  const { data: keyStatus } = useQuery({
    queryKey: ['api-key-status'],
    queryFn: () => api.get<{ has_api_key: boolean }>('/auth/api-key'),
  })

  const hasApiKey = keyStatus?.has_api_key ?? true

  return (
    <Sidebar>
      <SidebarHeader className="p-3">
        <TenantSwitcher />
      </SidebarHeader>

      <SidebarContent>
        {!hasApiKey && (
          <div className="mx-3 mb-2">
            <Link
              to="/settings"
              className="block text-xs text-amber-600 bg-amber-50 rounded-md px-3 py-2 hover:bg-amber-100 transition-colors"
            >
              Add your API key to unlock AI features
            </Link>
          </div>
        )}

        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  isActive={location.pathname === '/'}
                  render={<NavLink to="/" />}
                  tooltip="Briefing"
                >
                  <Home className="size-4" />
                  <span>Briefing</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  isActive={location.pathname === '/profile'}
                  render={<NavLink to="/profile" />}
                  tooltip="Company Profile"
                >
                  <Building2 className="size-4" />
                  <span>Company Profile</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  isActive={location.pathname.startsWith('/documents')}
                  render={<NavLink to="/documents" />}
                  tooltip="Documents"
                >
                  <FileText className="size-4" />
                  <span>Documents</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupContent>
            <StreamSidebar />
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-4" style={{ borderTop: '1px solid var(--subtle-border)' }}>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              isActive={location.pathname === '/settings'}
              render={<NavLink to="/settings" />}
              tooltip="Settings"
            >
              <Settings className="size-4" />
              <span>Settings</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-2">
            <Avatar className="h-7 w-7">
              <AvatarFallback className="text-xs" style={{ backgroundColor: 'var(--brand-tint)', color: 'var(--brand-coral)' }}>U</AvatarFallback>
            </Avatar>
            <span className="text-sm text-muted-foreground">User</span>
          </div>
          <kbd className="pointer-events-none hidden h-5 select-none items-center gap-1 rounded border border-border px-1.5 font-mono text-[10px] font-medium sm:inline-flex" style={{ backgroundColor: 'var(--brand-tint)', color: 'var(--secondary-text)' }}>
            <span className="text-xs">&#8984;</span>K
          </kbd>
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}
