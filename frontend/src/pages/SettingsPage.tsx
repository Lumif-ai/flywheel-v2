import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAuthStore } from '@/stores/auth'
import { useLifecycleState } from '@/features/navigation/hooks/useLifecycleState'
import { ApiKeyManager } from '@/features/settings/components/ApiKeyManager'
import { TenantSettings } from '@/features/settings/components/TenantSettings'
import { TeamManager } from '@/features/settings/components/TeamManager'
import { GranolaSettings } from '@/features/settings/components/GranolaSettings'
import { IntegrationSettings } from '@/features/settings/components/IntegrationSettings'
import { VoiceProfileSettings } from '@/features/settings/components/VoiceProfileSettings'
import { ArrowLeft, Key, Building2, Users, Plug, Mic } from 'lucide-react'
import { cn } from '@/lib/cn'

type SettingsSection = 'api-key' | 'workspace' | 'team' | 'integrations' | 'voice-profile'

interface NavItem {
  id: SettingsSection
  label: string
  icon: React.ComponentType<{ className?: string }>
  adminOnly?: boolean
  s4Only?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { id: 'workspace', label: 'Workspace', icon: Building2, adminOnly: true },
  { id: 'team', label: 'Team', icon: Users, adminOnly: true },
  { id: 'integrations', label: 'Integrations', icon: Plug, adminOnly: true },
  { id: 'voice-profile', label: 'Voice Profile', icon: Mic, adminOnly: true },
  { id: 'api-key', label: 'API Key', icon: Key, s4Only: true },
]

export function SettingsPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const { isAnonymous, state } = useLifecycleState()

  const isAdmin = user && !user.is_anonymous
  const showApiKey = state === 'S4' || state === 'S5'

  // Filter nav items based on permissions
  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.s4Only && !showApiKey) return false
    if (item.adminOnly && !isAdmin) return false
    return true
  })

  const defaultSection = visibleItems[0]?.id ?? 'workspace'
  const [activeSection, setActiveSection] = useState<SettingsSection>(defaultSection)

  // Redirect anonymous users
  useEffect(() => {
    if (isAnonymous) {
      navigate('/', { replace: true })
    }
  }, [isAnonymous, navigate])

  if (isAnonymous) return null

  return (
    <div className="flex h-screen bg-background">
      {/* Left sidebar navigation */}
      <aside className="w-56 shrink-0 border-r border-border bg-sidebar flex flex-col">
        {/* Back button + title */}
        <div className="p-4 pb-2">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mb-4"
          >
            <ArrowLeft className="size-4" />
            <span>Back</span>
          </button>
          <h1 className="text-lg font-semibold text-foreground px-1">Settings</h1>
        </div>

        {/* Nav items */}
        <nav className="flex-1 px-3 py-2 space-y-0.5">
          {visibleItems.map((item) => {
            const Icon = item.icon
            return (
              <button
                key={item.id}
                onClick={() => setActiveSection(item.id)}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors',
                  activeSection === item.id
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
                )}
              >
                <Icon className="size-4 shrink-0" />
                {item.label}
              </button>
            )
          })}
        </nav>
      </aside>

      {/* Right content area */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-2xl p-8">
          {activeSection === 'api-key' && showApiKey && <ApiKeyManager />}
          {activeSection === 'workspace' && isAdmin && <TenantSettings />}
          {activeSection === 'team' && isAdmin && <TeamManager />}
          {activeSection === 'integrations' && isAdmin && (
            <div className="space-y-8">
              <IntegrationSettings />
              <GranolaSettings />
            </div>
          )}
          {activeSection === 'voice-profile' && isAdmin && <VoiceProfileSettings />}
        </div>
      </main>
    </div>
  )
}
