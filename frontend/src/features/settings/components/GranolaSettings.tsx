import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarDays, CheckCircle2, Eye, EyeOff, Loader2 } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface Integration {
  id: string
  provider: string
  status: string
  last_synced_at: string | null
}

interface IntegrationsResponse {
  items: Integration[]
}

interface SyncResult {
  synced: number
  skipped: number
  already_seen: number
  total_from_provider: number
}

export function GranolaSettings() {
  const queryClient = useQueryClient()
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)

  const { data: integrations } = useQuery({
    queryKey: ['integrations'],
    queryFn: () => api.get<IntegrationsResponse>('/integrations/'),
  })

  // CRITICAL: check BOTH provider AND status — a disconnected row may exist
  const granolaIntegration = integrations?.items?.find(
    (i) => i.provider === 'granola' && i.status === 'connected'
  ) ?? null

  const connectMutation = useMutation({
    mutationFn: (key: string) =>
      api.post<{ status: string }>('/integrations/granola/connect', { api_key: key }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations'] })
      toast.success('Granola connected')
      setApiKey('')
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Failed to connect Granola')
    },
  })

  const disconnectMutation = useMutation({
    mutationFn: (id: string) =>
      api.delete<{ disconnected: boolean }>(`/integrations/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations'] })
      toast.success('Granola disconnected')
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Failed to disconnect Granola')
    },
  })

  const syncMutation = useMutation({
    mutationFn: () => api.post<SyncResult>('/meetings/sync'),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] })
      toast.success(
        `Sync complete — ${data.synced} new, ${data.skipped} skipped, ${data.already_seen} already seen`
      )
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Sync failed')
    },
  })

  const formatLastSynced = (lastSyncedAt: string | null): string => {
    if (!lastSyncedAt) return 'Never'
    try {
      return formatDistanceToNow(new Date(lastSyncedAt), { addSuffix: true })
    } catch {
      return 'Unknown'
    }
  }

  if (granolaIntegration) {
    return (
      <div className="space-y-6">
        <div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="size-5 text-green-500" />
            <h3 className="text-base font-semibold text-foreground">Granola</h3>
          </div>
          <p className="text-sm text-green-600 mt-1 font-medium">Connected</p>
        </div>

        <div className="rounded-lg border border-border bg-muted/50 px-4 py-3 space-y-1">
          <p className="text-sm text-muted-foreground">
            Last synced:{' '}
            <span className="text-foreground font-medium">
              {formatLastSynced(granolaIntegration.last_synced_at)}
            </span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
          >
            {syncMutation.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Syncing...
              </>
            ) : (
              'Sync Now'
            )}
          </Button>

          <Button
            variant="outline"
            onClick={() => disconnectMutation.mutate(granolaIntegration.id)}
            disabled={disconnectMutation.isPending}
            className="text-destructive hover:text-destructive border-destructive/30 hover:border-destructive/60"
          >
            {disconnectMutation.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Disconnecting...
              </>
            ) : (
              'Disconnect'
            )}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <CalendarDays className="size-5 text-muted-foreground" />
          <h3 className="text-base font-semibold text-foreground">Granola</h3>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Connect your Granola account to automatically sync meeting notes and transcripts.
        </p>
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Input
              type={showKey ? 'text' : 'password'}
              placeholder="Paste your Granola API key..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="pr-8"
            />
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </div>

        <Button
          onClick={() => connectMutation.mutate(apiKey.trim())}
          disabled={!apiKey.trim() || connectMutation.isPending}
        >
          {connectMutation.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Connecting...
            </>
          ) : (
            'Connect'
          )}
        </Button>
      </div>
    </div>
  )
}
