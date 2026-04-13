import { useLocation } from 'react-router'
import { NavLink } from 'react-router'
import { Home, Mail, FolderKanban, Users, Shield } from 'lucide-react'
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
} from '@/components/ui/sidebar'

const BROKER_NAV = [
  { label: 'Dashboard', to: '/broker',          icon: Home,         match: (p: string) => p === '/broker' },
  { label: 'Email',     to: '/broker/email',     icon: Mail,         match: (p: string) => p.startsWith('/broker/email') },
  { label: 'Projects',  to: '/broker/projects',  icon: FolderKanban, match: (p: string) => p.startsWith('/broker/projects') },
  { label: 'Clients',   to: '/broker/clients',   icon: Users,        match: (p: string) => p.startsWith('/broker/clients') },
  { label: 'Carriers',  to: '/broker/carriers',  icon: Shield,       match: (p: string) => p.startsWith('/broker/carriers') },
] as const

export function BrokerSidebarContent() {
  const location = useLocation()

  return (
    <SidebarGroup>
      <SidebarGroupContent>
        <SidebarMenu>
          {BROKER_NAV.map(({ label, to, icon: Icon, match }) => (
            <SidebarMenuItem key={to}>
              <SidebarMenuButton
                isActive={match(location.pathname)}
                render={<NavLink to={to} />}
                tooltip={label}
              >
                <Icon className="size-4" />
                <span>{label}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}
