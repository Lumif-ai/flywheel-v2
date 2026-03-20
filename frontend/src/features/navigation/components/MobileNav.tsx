import { NavLink } from 'react-router'
import { navItems } from './AppSidebar'

export function MobileNav() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex h-16 items-center justify-around border-t bg-background">
      {navItems.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          className={({ isActive }) =>
            `flex flex-col items-center gap-0.5 text-xs ${
              isActive
                ? 'text-primary font-medium'
                : 'text-muted-foreground'
            }`
          }
        >
          <item.icon className="size-5" />
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
