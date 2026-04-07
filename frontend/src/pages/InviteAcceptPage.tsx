/**
 * InviteAcceptPage - Handles /invite?token=... route for team member invitations.
 *
 * Reads token from URL search params, uses useTeamOnboarding hook to manage
 * the acceptance flow: accepting -> streams -> meetings -> briefing redirect.
 */

import { useSearchParams } from 'react-router'
import { Loader2 } from 'lucide-react'
import { useTeamOnboarding } from '@/features/onboarding/hooks/useTeamOnboarding'
import { TeamOnboarding } from '@/features/onboarding/components/TeamOnboarding'
import { useAuthStore } from '@/stores/auth'
import { getSupabase } from '@/lib/supabase'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export function InviteAcceptPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  const user = useAuthStore((s) => s.user)
  const isAnonymous = user?.is_anonymous ?? true
  const [email, setEmail] = useState('')
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)
  const [magicLinkSent, setMagicLinkSent] = useState(false)

  const {
    phase,
    error,
    loading,
    tenantName,
    teamStreams,
    selectedStreamIds,
    newStreamNames,
    toggleStream,
    addNewStream,
    confirmStreams,
    skipStreams,
    skipMeetings,
    onMeetingsComplete,
  } = useTeamOnboarding(isAnonymous ? '' : token) // Don't accept until authenticated

  const handleMagicLink = async () => {
    if (!email.trim()) return
    setAuthLoading(true)
    setAuthError(null)
    try {
      const supabase = await getSupabase()
      if (!supabase) throw new Error('Auth not available')
      const { error } = await supabase.auth.signInWithOtp({
        email: email.trim(),
        options: {
          emailRedirectTo: `${window.location.origin}/invite?token=${token}`,
        },
      })
      if (error) throw error
      setMagicLinkSent(true)
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Failed to send login link')
    }
    setAuthLoading(false)
  }

  // Anonymous user — must sign in first
  if (isAnonymous && token) {
    return (
      <div className="flex min-h-[80vh] flex-col items-center justify-center px-4">
        <div className="max-w-md w-full space-y-6 text-center">
          <div className="space-y-2">
            <h1 className="text-xl font-semibold">You've been invited to Flywheel</h1>
            <p className="text-sm text-muted-foreground">
              Sign in or create an account to accept this invite.
            </p>
          </div>

          {magicLinkSent ? (
            <div className="rounded-lg border border-border p-6 space-y-2">
              <p className="text-sm font-medium">Check your email</p>
              <p className="text-sm text-muted-foreground">
                We sent a sign-in link to <strong>{email}</strong>. Click it to continue.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <Input
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleMagicLink()}
              />
              <Button
                className="w-full"
                onClick={handleMagicLink}
                disabled={!email.trim() || authLoading}
              >
                {authLoading ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  'Continue with Email'
                )}
              </Button>
              {authError && (
                <p className="text-sm text-destructive">{authError}</p>
              )}
            </div>
          )}
        </div>
      </div>
    )
  }

  // No token provided
  if (!token) {
    return (
      <div className="flex min-h-[80vh] flex-col items-center justify-center px-4">
        <div className="max-w-md text-center space-y-3">
          <h1 className="text-xl font-semibold">No invite token found</h1>
          <p className="text-sm text-muted-foreground">
            Please use the invite link sent to your email.
          </p>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex min-h-[80vh] flex-col items-center justify-center px-4">
        <div className="max-w-md text-center space-y-3">
          <h1 className="text-xl font-semibold text-destructive">
            Invite Error
          </h1>
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      </div>
    )
  }

  // Accepting phase -- spinner
  if (phase === 'accepting') {
    return (
      <div className="flex min-h-[80vh] flex-col items-center justify-center px-4">
        <div className="text-center space-y-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
          <p className="text-sm text-muted-foreground">Accepting invite...</p>
        </div>
      </div>
    )
  }

  // Streams or meetings phase -- render TeamOnboarding
  if (phase === 'streams' || phase === 'meetings') {
    return (
      <div className="flex min-h-[80vh] flex-col items-center justify-center px-4 py-12">
        <TeamOnboarding
          phase={phase}
          tenantName={tenantName}
          teamStreams={teamStreams}
          selectedStreamIds={selectedStreamIds}
          newStreamNames={newStreamNames}
          loading={loading}
          toggleStream={toggleStream}
          addNewStream={addNewStream}
          confirmStreams={confirmStreams}
          skipStreams={skipStreams}
          skipMeetings={skipMeetings}
          onMeetingsComplete={onMeetingsComplete}
        />
      </div>
    )
  }

  // Done phase handled by hook redirect -- fallback spinner
  return (
    <div className="flex min-h-[80vh] items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  )
}
