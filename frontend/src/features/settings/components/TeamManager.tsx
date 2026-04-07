import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, UserPlus, X, Mail, Link } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

interface MemberItem {
  user_id: string | null
  invite_id: string | null
  email: string | null
  name: string | null
  role: string
  joined_at: string | null
  status: 'active' | 'pending'
  expires_at: string | null
  invite_token: string | null
}

export function TeamManager() {
  const queryClient = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)
  const [inviteEmail, setInviteEmail] = useState('')

  const { data: members, isLoading } = useQuery({
    queryKey: ['tenant-members'],
    queryFn: () => api.get<MemberItem[]>('/tenants/members'),
    enabled: true,
  })

  const inviteMutation = useMutation({
    mutationFn: (email: string) =>
      api.post('/tenants/invite', { email }),
    onSuccess: () => {
      setInviteEmail('')
      queryClient.invalidateQueries({ queryKey: ['tenant-members'] })
      toast.success('Invite sent')
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Failed to send invite')
    },
  })

  const cancelInviteMutation = useMutation({
    mutationFn: (inviteId: string) =>
      api.delete<void>(`/tenants/invite/${inviteId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-members'] })
      toast.success('Invite cancelled')
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Failed to cancel invite')
    },
  })

  const removeMutation = useMutation({
    mutationFn: (userId: string) =>
      api.delete<void>(`/tenants/members/${userId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-members'] })
      toast.success('Member removed')
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Failed to remove member')
    },
  })

  const copyInviteLink = (token: string) => {
    const link = `${window.location.origin}/invite?token=${token}`
    navigator.clipboard.writeText(link)
    toast.success('Invite link copied')
  }

  const handleInvite = () => {
    if (!inviteEmail.trim()) return
    inviteMutation.mutate(inviteEmail.trim())
  }

  const activeMembers = members?.filter((m) => m.status === 'active') ?? []
  const pendingInvites = members?.filter((m) => m.status === 'pending') ?? []
  const adminCount = activeMembers.filter((m) => m.role === 'admin').length

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
      </div>

      {/* Active Members */}
      <div className="space-y-3">
        <h3 className="text-base font-semibold text-foreground">
          Members {activeMembers.length > 0 ? `(${activeMembers.length})` : ''}
        </h3>

        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full rounded-lg" />
            ))}
          </div>
        ) : activeMembers.length > 0 ? (
          <div className="divide-y divide-border rounded-lg border border-border">
            {activeMembers.map((member) => {
              const isCurrentUser = member.user_id === currentUser?.id
              const isLastAdmin = member.role === 'admin' && adminCount <= 1
              const canRemove = !isCurrentUser && !isLastAdmin

              return (
                <div
                  key={member.user_id ?? member.email}
                  className="flex items-center justify-between px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-xs font-medium">
                      {(member.name ?? member.email)?.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        {member.name ?? member.email}
                        {isCurrentUser && (
                          <span className="text-muted-foreground ml-1">(you)</span>
                        )}
                      </p>
                      {member.name && member.email && (
                        <p className="text-xs text-muted-foreground">{member.email}</p>
                      )}
                      {member.joined_at && (
                        <p className="text-xs text-muted-foreground">
                          Joined {new Date(member.joined_at).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={member.role === 'admin' ? 'default' : 'secondary'}>
                      {member.role}
                    </Badge>
                    {canRemove && member.user_id && (
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        onClick={() => removeMutation.mutate(member.user_id!)}
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
          Pending Invites {pendingInvites.length > 0 ? `(${pendingInvites.length})` : ''}
        </h3>

        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full rounded-lg" />
          </div>
        ) : pendingInvites.length > 0 ? (
          <div className="divide-y divide-border rounded-lg border border-border">
            {pendingInvites.map((invite) => (
              <div
                key={invite.invite_id ?? invite.email}
                className="flex items-center justify-between px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <Mail className="size-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-foreground">{invite.email}</p>
                    {invite.expires_at && (
                      <p className="text-xs text-muted-foreground">
                        Expires {new Date(invite.expires_at).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {invite.invite_token && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyInviteLink(invite.invite_token!)}
                    >
                      <Link className="size-3 mr-1" />
                      Copy Link
                    </Button>
                  )}
                  {invite.invite_id && (
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => cancelInviteMutation.mutate(invite.invite_id!)}
                      disabled={cancelInviteMutation.isPending}
                    >
                      <X className="size-3" />
                    </Button>
                  )}
                  <Badge variant="outline">Pending</Badge>
                </div>
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
