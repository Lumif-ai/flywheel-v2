import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CalendarDays, Mail, CheckCircle2, Loader2, ExternalLink } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'

interface Integration {
  id: string
  provider: string
  status: string
  last_synced_at: string | null
}

interface IntegrationsResponse {
  items: Integration[]
}

const PROVIDER_LABELS: Record<string, { label: string; icon: typeof CalendarDays }> = {
  'google-calendar': { label: 'Google Calendar', icon: CalendarDays },
  'gmail-read': { label: 'Gmail', icon: Mail },
  'microsoft-outlook': { label: 'Microsoft Outlook', icon: Mail },
}

function formatLastSynced(lastSyncedAt: string | null): string {
  if (!lastSyncedAt) return 'Never'
  try {
    return formatDistanceToNow(new Date(lastSyncedAt), { addSuffix: true })
  } catch {
    return 'Unknown'
  }
}

function IntegrationCard({
  integration,
  onDisconnect,
  isDisconnecting,
}: {
  integration: Integration
  onDisconnect: () => void
  isDisconnecting: boolean
}) {
  const info = PROVIDER_LABELS[integration.provider]
  if (!info) return null
  const Icon = info.icon

  return (
    <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
      <div className="flex items-center gap-3">
        <Icon className="size-5 text-green-500" />
        <div>
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-foreground">{info.label}</p>
            <CheckCircle2 className="size-3.5 text-green-500" />
          </div>
          <p className="text-xs text-muted-foreground">
            Last synced: {formatLastSynced(integration.last_synced_at)}
          </p>
        </div>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={onDisconnect}
        disabled={isDisconnecting}
        className="text-destructive hover:text-destructive border-destructive/30 hover:border-destructive/60"
      >
        {isDisconnecting ? <Loader2 className="size-3 animate-spin" /> : 'Disconnect'}
      </Button>
    </div>
  )
}

function ConnectCard({
  provider,
  label,
  description,
  icon: Icon,
  authorizeEndpoint,
}: {
  provider: string
  label: string
  description: string
  icon: typeof CalendarDays
  authorizeEndpoint: string
}) {
  const [connecting, setConnecting] = useState(false)

  const handleConnect = async () => {
    setConnecting(true)
    try {
      const res = await api.get<{ auth_url: string }>(authorizeEndpoint)
      window.location.href = res.auth_url
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start OAuth flow')
      setConnecting(false)
    }
  }

  return (
    <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
      <div className="flex items-center gap-3">
        <Icon className="size-5 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium text-foreground">{label}</p>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={handleConnect}
        disabled={connecting}
      >
        {connecting ? (
          <Loader2 className="size-3 animate-spin" />
        ) : (
          <>
            <ExternalLink className="size-3 mr-1" />
            Connect
          </>
        )}
      </Button>
    </div>
  )
}

export function IntegrationSettings() {
  const queryClient = useQueryClient()

  const { data: integrations } = useQuery({
    queryKey: ['integrations'],
    queryFn: () => api.get<IntegrationsResponse>('/integrations/'),
    staleTime: 0, // Always refetch on mount (important after OAuth redirect)
  })

  const disconnectMutation = useMutation({
    mutationFn: (id: string) =>
      api.delete<{ disconnected: boolean }>(`/integrations/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations'] })
      toast.success('Integration disconnected')
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Failed to disconnect')
    },
  })

  const connected = integrations?.items?.filter((i) => i.status === 'connected') ?? []
  const connectedProviders = new Set(connected.map((i) => i.provider))

  const availableConnections = [
    {
      provider: 'google-calendar',
      label: 'Google Calendar',
      description: 'Sync your calendar events for meeting prep',
      icon: CalendarDays,
      authorizeEndpoint: '/integrations/google-calendar/authorize',
    },
    {
      provider: 'gmail-read',
      label: 'Gmail',
      description: 'Read emails for context and draft replies',
      icon: Mail,
      authorizeEndpoint: '/integrations/gmail-read/authorize',
    },
  ].filter((c) => !connectedProviders.has(c.provider))

  return (
    <div className="space-y-6">
      {connected.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-muted-foreground">Connected</h3>
          {connected.map((integration) => (
            <IntegrationCard
              key={integration.id}
              integration={integration}
              onDisconnect={() => disconnectMutation.mutate(integration.id)}
              isDisconnecting={disconnectMutation.isPending}
            />
          ))}
        </div>
      )}

      {availableConnections.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-muted-foreground">Available</h3>
          {availableConnections.map((conn) => (
            <ConnectCard key={conn.provider} {...conn} />
          ))}
        </div>
      )}

      {connected.length === 0 && availableConnections.length === 0 && (
        <p className="text-sm text-muted-foreground">All integrations connected.</p>
      )}
    </div>
  )
}
