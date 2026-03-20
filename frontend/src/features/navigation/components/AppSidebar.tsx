import { NavLink, useLocation } from 'react-router'
import { Home, Briefcase, Zap, Brain, History, Settings } from 'lucide-react'
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

const navItems = [
  { label: 'HQ', icon: Home, path: '/' },
  { label: 'Prep', icon: Briefcase, path: '/prep' },
  { label: 'Act', icon: Zap, path: '/act' },
  { label: 'Intel', icon: Brain, path: '/intel' },
  { label: 'History', icon: History, path: '/history' },
  { label: 'Settings', icon: Settings, path: '/settings' },
]

export { navItems }

export function AppSidebar() {
  const location = useLocation()

  return (
    <Sidebar>
      <SidebarHeader className="p-3">
        <TenantSwitcher />
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const isActive = item.path === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.path)

                return (
                  <SidebarMenuItem key={item.path}>
                    <SidebarMenuButton
                      isActive={isActive}
                      render={<NavLink to={item.path} />}
                      tooltip={item.label}
                    >
                      <item.icon className="size-4" />
                      <span>{item.label}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Avatar className="h-7 w-7">
              <AvatarFallback className="text-xs bg-muted">U</AvatarFallback>
            </Avatar>
            <span className="text-sm text-muted-foreground">User</span>
          </div>
          <kbd className="pointer-events-none hidden h-5 select-none items-center gap-1 rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground sm:inline-flex">
            <span className="text-xs">&#8984;</span>K
          </kbd>
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}
