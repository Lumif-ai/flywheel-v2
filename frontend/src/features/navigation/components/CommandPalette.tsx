import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Home, Briefcase, Zap, Brain, History, Settings, Search } from 'lucide-react'
import { api } from '@/lib/api'
import { useUIStore } from '@/stores/ui'
import {
  CommandDialog,
  Command,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandSeparator,
} from '@/components/ui/command'
import type { Skill } from '@/types/api'

const navItems = [
  { label: 'HQ', icon: Home, path: '/' },
  { label: 'Prep', icon: Briefcase, path: '/prep' },
  { label: 'Act', icon: Zap, path: '/act' },
  { label: 'Intel', icon: Brain, path: '/intel' },
  { label: 'History', icon: History, path: '/history' },
  { label: 'Settings', icon: Settings, path: '/settings' },
]

export function CommandPalette() {
  const navigate = useNavigate()
  const open = useUIStore((s) => s.commandPaletteOpen)
  const setOpen = useUIStore((s) => s.setCommandPaletteOpen)

  const { data: skills } = useQuery({
    queryKey: ['skills'],
    queryFn: () => api.get<Skill[]>('/skills'),
    enabled: open,
  })

  // Global Cmd+K listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen(!open)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, setOpen])

  const handleSelect = (path: string) => {
    navigate(path)
    setOpen(false)
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <Command>
        <CommandInput placeholder="Type a command or search..." />
        <CommandList>
          <CommandEmpty>
            No results found.
          </CommandEmpty>

          <CommandGroup heading="Navigation">
            {navItems.map((item) => (
              <CommandItem
                key={item.path}
                onSelect={() => handleSelect(item.path)}
              >
                <item.icon className="size-4" />
                <span>{item.label}</span>
              </CommandItem>
            ))}
          </CommandGroup>

          {skills && skills.length > 0 && (
            <>
              <CommandSeparator />
              <CommandGroup heading="Skills">
                {skills.map((skill) => (
                  <CommandItem
                    key={skill.name}
                    onSelect={() => handleSelect(`/act?skill=${encodeURIComponent(skill.name)}`)}
                  >
                    <Zap className="size-4" />
                    <span>{skill.display_name}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          )}

          <CommandSeparator />
          <CommandGroup heading="Search">
            <CommandItem
              onSelect={() => {
                handleSelect('/history?search=')
              }}
            >
              <Search className="size-4" />
              <span>Search history...</span>
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  )
}
