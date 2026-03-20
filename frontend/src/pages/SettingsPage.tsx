import { useAuthStore } from '@/stores/auth'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { ApiKeyManager } from '@/features/settings/components/ApiKeyManager'
import { TenantSettings } from '@/features/settings/components/TenantSettings'
import { TeamManager } from '@/features/settings/components/TeamManager'

export function SettingsPage() {
  const user = useAuthStore((s) => s.user)

  // Non-anonymous users with admin role see all tabs; others see only API Key
  // For now, assume non-anonymous users are admins (role check can be refined later)
  const isAdmin = user && !user.is_anonymous

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Manage your account and workspace settings.
        </p>
      </div>

      <div className="max-w-2xl">
        <Tabs defaultValue="api-key">
          <TabsList>
            <TabsTrigger value="api-key">API Key</TabsTrigger>
            {isAdmin && <TabsTrigger value="workspace">Workspace</TabsTrigger>}
            {isAdmin && <TabsTrigger value="team">Team</TabsTrigger>}
          </TabsList>

          <TabsContent value="api-key" className="mt-6">
            <ApiKeyManager />
          </TabsContent>

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
        </Tabs>
      </div>
    </div>
  )
}
