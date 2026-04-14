import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import { useTenantStore } from '@/stores/tenant'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import type { Tenant } from '@/types/api'

export function TenantSettings() {
  const queryClient = useQueryClient()
  const activeTenant = useTenantStore((s) => s.activeTenant)
  const setActiveTenant = useTenantStore((s) => s.setActiveTenant)

  // Settings page is standalone (no TenantBootstrap wrapper), so Zustand persist
  // hydration is the primary source. This fetch runs only when persist hasn't
  // hydrated yet (e.g., cleared localStorage) to ensure activeTenant is available.
  useQuery({
    queryKey: ['tenants'],
    queryFn: () => api.get<Tenant[]>('/tenants'),
    enabled: !activeTenant,
  })
  const [editName, setEditName] = useState(activeTenant?.name ?? '')
  const [deleteOpen, setDeleteOpen] = useState(false)

  const updateMutation = useMutation({
    mutationFn: (name: string) =>
      api.patch<Tenant>(`/tenants/${activeTenant?.id}`, { name }),
    onSuccess: (data) => {
      setActiveTenant(data)
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.delete<void>(`/tenants/${activeTenant?.id}`),
    onSuccess: () => {
      setDeleteOpen(false)
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      // Redirect handled by parent/router
    },
  })

  if (!activeTenant) {
    return (
      <div className="text-sm text-muted-foreground">
        No workspace selected.
      </div>
    )
  }

  const nameChanged = editName.trim() !== activeTenant.name

  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <div>
          <h3 className="text-base font-semibold text-foreground">Workspace Details</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your workspace settings.
          </p>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium text-foreground">Name</label>
            <div className="flex items-center gap-2 mt-1">
              <Input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                placeholder="Workspace name"
              />
              <Button
                onClick={() => updateMutation.mutate(editName.trim())}
                disabled={!nameChanged || updateMutation.isPending}
                variant={nameChanged ? 'default' : 'outline'}
              >
                {updateMutation.isPending ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  'Save'
                )}
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 rounded-lg border border-border p-4">
            <div>
              <span className="text-xs text-muted-foreground">Slug</span>
              <p className="text-sm font-mono text-foreground">{activeTenant.slug}</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Plan</span>
              <div className="mt-0.5">
                <Badge variant="secondary">{activeTenant.plan}</Badge>
              </div>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Member Limit</span>
              <p className="text-sm text-foreground">{activeTenant.member_limit} members</p>
            </div>
          </div>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="space-y-3 rounded-lg border border-destructive/30 p-4">
        <h4 className="text-sm font-semibold text-destructive">Danger Zone</h4>
        <p className="text-sm text-muted-foreground">
          Permanently delete this workspace and all associated data.
          This action cannot be undone.
        </p>
        <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
          Delete Workspace
        </Button>
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Workspace</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete <strong>{activeTenant.name}</strong>?
              This will permanently remove all data, members, and settings.
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                'Delete Workspace'
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
