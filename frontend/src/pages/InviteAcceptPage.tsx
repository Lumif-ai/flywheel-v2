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

export function InviteAcceptPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''

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
  } = useTeamOnboarding(token)

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
