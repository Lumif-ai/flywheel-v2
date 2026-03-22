import { NavLink, useLocation } from 'react-router'
import { Home, Layers, MessageSquare, Settings } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

const mobileNavItems = [
  { label: 'Briefing', icon: Home, path: '/' },
  { label: 'Streams', icon: Layers, path: '/streams' },
  { label: 'Chat', icon: MessageSquare, path: '/chat' },
  { label: 'Settings', icon: Settings, path: '/settings' },
]

export function MobileNav() {
  const location = useLocation()

  const { data: keyStatus } = useQuery({
    queryKey: ['api-key-status'],
    queryFn: () => api.get<{ has_api_key: boolean }>('/auth/api-key'),
  })

  const hasApiKey = keyStatus?.has_api_key ?? true

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex h-16 items-center justify-around border-t bg-background">
      {mobileNavItems.map((item) => {
        // Streams tab is active when on any /streams/* path
        const isActive = item.path === '/'
          ? location.pathname === '/'
          : location.pathname.startsWith(item.path)

        return (
          <NavLink
            key={item.path}
            to={item.path === '/streams' ? '/' : item.path}
            className={`relative flex flex-col items-center gap-0.5 text-xs ${
              isActive
                ? 'text-primary font-medium'
                : 'text-muted-foreground'
            }`}
          >
            <item.icon className="size-5" />
            <span>{item.label}</span>
            {item.path === '/settings' && !hasApiKey && (
              <span className="absolute -top-0.5 -right-1 w-2 h-2 rounded-full bg-amber-500" />
            )}
          </NavLink>
        )
      })}
    </nav>
  )
}
