import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, UserPlus, X, Mail } from 'lucide-react'
import { api } from '@/lib/api'
import { useTenantStore } from '@/stores/tenant'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

interface Member {
  id: string
  email: string
  role: 'admin' | 'member'
  joined_at: string
}

interface Invite {
  id: string
  email: string
  status: 'pending' | 'accepted' | 'expired'
  expires_at: string
}

export function TeamManager() {
  const queryClient = useQueryClient()
  const activeTenant = useTenantStore((s) => s.activeTenant)
  const currentUser = useAuthStore((s) => s.user)
  const [inviteEmail, setInviteEmail] = useState('')

  const tenantId = activeTenant?.id

  const { data: members, isLoading: membersLoading } = useQuery({
    queryKey: ['members', tenantId],
    queryFn: () => api.get<Member[]>(`/tenants/${tenantId}/members`),
    enabled: !!tenantId,
  })

  const { data: invites, isLoading: invitesLoading } = useQuery({
    queryKey: ['invites', tenantId],
    queryFn: () => api.get<Invite[]>(`/tenants/${tenantId}/invites`),
    enabled: !!tenantId,
  })

  const inviteMutation = useMutation({
    mutationFn: (email: string) =>
      api.post<Invite>(`/tenants/${tenantId}/invites`, { email }),
    onSuccess: () => {
      setInviteEmail('')
      queryClient.invalidateQueries({ queryKey: ['invites', tenantId] })
    },
  })

  const removeMutation = useMutation({
    mutationFn: (memberId: string) =>
      api.delete<void>(`/tenants/${tenantId}/members/${memberId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members', tenantId] })
    },
  })

  const revokeMutation = useMutation({
    mutationFn: (inviteId: string) =>
      api.delete<void>(`/tenants/${tenantId}/invites/${inviteId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invites', tenantId] })
    },
  })

  const handleInvite = () => {
    if (!inviteEmail.trim()) return
    inviteMutation.mutate(inviteEmail.trim())
  }

  if (!tenantId) {
    return (
      <div className="text-sm text-muted-foreground">
        No workspace selected.
      </div>
    )
  }

  const adminCount = members?.filter((m) => m.role === 'admin').length ?? 0

  return (
    <div className="space-y-8">
      {/* Invite Section */}
      <div className="space-y-3">
        <div>
          <h3 className="text-base font-semibold text-foreground">Invite Members</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Add team members by email address.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            type="email"
            placeholder="colleague@company.com"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleInvite()}
          />
          <Button
            onClick={handleInvite}
            disabled={!inviteEmail.trim() || inviteMutation.isPending}
          >
            {inviteMutation.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <>
                <UserPlus className="size-4" />
                Send Invite
              </>
            )}
          </Button>
        </div>
        {inviteMutation.isError && (
          <p className="text-sm text-destructive">
            Failed to send invite. The user may already be a member.
          </p>
        )}
        {inviteMutation.isSuccess && (
          <p className="text-sm text-green-600">Invite sent successfully.</p>
        )}
      </div>

      {/* Members List */}
      <div className="space-y-3">
        <h3 className="text-base font-semibold text-foreground">
          Members {members ? `(${members.length})` : ''}
        </h3>

        {membersLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full rounded-lg" />
            ))}
          </div>
        ) : members && members.length > 0 ? (
          <div className="divide-y divide-border rounded-lg border border-border">
            {members.map((member) => {
              const isCurrentUser = member.id === currentUser?.id
              const isLastAdmin = member.role === 'admin' && adminCount <= 1
              const canRemove = !isCurrentUser || !isLastAdmin

              return (
                <div
                  key={member.id}
                  className="flex items-center justify-between px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-xs font-medium">
                      {member.email.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        {member.email}
                        {isCurrentUser && (
                          <span className="text-muted-foreground ml-1">(you)</span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Joined {new Date(member.joined_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={member.role === 'admin' ? 'default' : 'secondary'}>
                      {member.role}
                    </Badge>
                    {canRemove && (
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        onClick={() => removeMutation.mutate(member.id)}
                        disabled={removeMutation.isPending}
                      >
                        <X className="size-3" />
                      </Button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No members yet.</p>
        )}
      </div>

      {/* Pending Invites */}
      <div className="space-y-3">
        <h3 className="text-base font-semibold text-foreground">
          Pending Invites {invites?.filter((i) => i.status === 'pending').length ? `(${invites.filter((i) => i.status === 'pending').length})` : ''}
        </h3>

        {invitesLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full rounded-lg" />
          </div>
        ) : invites && invites.filter((i) => i.status === 'pending').length > 0 ? (
          <div className="divide-y divide-border rounded-lg border border-border">
            {invites
              .filter((i) => i.status === 'pending')
              .map((invite) => (
                <div
                  key={invite.id}
                  className="flex items-center justify-between px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <Mail className="size-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm text-foreground">{invite.email}</p>
                      <p className="text-xs text-muted-foreground">
                        Expires {new Date(invite.expires_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={() => revokeMutation.mutate(invite.id)}
                    disabled={revokeMutation.isPending}
                  >
                    Revoke
                  </Button>
                </div>
              ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No pending invites.</p>
        )}
      </div>
    </div>
  )
}
