import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { useAuthStore } from '@/stores/auth'
import { useLifecycleState } from '@/features/navigation/hooks/useLifecycleState'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { ApiKeyManager } from '@/features/settings/components/ApiKeyManager'
import { TenantSettings } from '@/features/settings/components/TenantSettings'
import { TeamManager } from '@/features/settings/components/TeamManager'
import { GranolaSettings } from '@/features/settings/components/GranolaSettings'

export function SettingsPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const { isAnonymous, state } = useLifecycleState()

  // Redirect anonymous users -- they have nothing to configure
  useEffect(() => {
    if (isAnonymous) {
      navigate('/', { replace: true })
    }
  }, [isAnonymous, navigate])

  // Non-anonymous users with admin role see all tabs; others see only API Key
  // For now, assume non-anonymous users are admins (role check can be refined later)
  const isAdmin = user && !user.is_anonymous

  // Show API Key tab only for S4+ (users who've hit the power threshold)
  const showApiKey = state === 'S4' || state === 'S5'

  // Determine default tab based on what's visible
  const defaultTab = showApiKey ? 'api-key' : isAdmin ? 'workspace' : 'api-key'

  if (isAnonymous) return null

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Manage your account and workspace settings.
        </p>
      </div>

      <div className="max-w-2xl">
        <Tabs defaultValue={defaultTab}>
          <TabsList>
            {showApiKey && <TabsTrigger value="api-key">API Key</TabsTrigger>}
            {isAdmin && <TabsTrigger value="workspace">Workspace</TabsTrigger>}
            {isAdmin && <TabsTrigger value="team">Team</TabsTrigger>}
            {isAdmin && <TabsTrigger value="integrations">Integrations</TabsTrigger>}
          </TabsList>

          {showApiKey && (
            <TabsContent value="api-key" className="mt-6">
              <ApiKeyManager />
            </TabsContent>
          )}

          {isAdmin && (
            <TabsContent value="workspace" className="mt-6">
              <TenantSettings />
            </TabsContent>
          )}

          {isAdmin && (
            <TabsContent value="team" className="mt-6">
              <TeamManager />
            </TabsContent>
          )}

          {isAdmin && (
            <TabsContent value="integrations" className="mt-6">
              <GranolaSettings />
            </TabsContent>
          )}
        </Tabs>
      </div>
    </div>
  )
}
