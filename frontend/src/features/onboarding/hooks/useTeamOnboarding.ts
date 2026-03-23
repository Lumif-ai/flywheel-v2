/**
 * useTeamOnboarding - State machine hook for team member invite acceptance flow.
 *
 * Phases: accepting -> streams -> meetings -> done
 *
 * Handles invite token acceptance, team stream listing/joining,
 * and meeting notes ingestion before redirecting to briefing.
 */

import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { api } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Phase = 'accepting' | 'streams' | 'meetings' | 'done'

interface TeamStream {
  id: string
  name: string
  entity_count: number
  entry_count: number
  member_count: number
}

interface TeamOnboardingState {
  phase: Phase
  error: string | null
  loading: boolean
  tenantName: string | null
  teamStreams: TeamStream[]
  selectedStreamIds: Set<string>
  newStreamNames: string[]
}

interface AcceptResponse {
  tenant_id: string
  tenant_name: string
}

interface StreamsResponse {
  streams: TeamStream[]
  prompt: string
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useTeamOnboarding(token: string) {
  const navigate = useNavigate()

  const [state, setState] = useState<TeamOnboardingState>({
    phase: 'accepting',
    error: null,
    loading: false,
    tenantName: null,
    teamStreams: [],
    selectedStreamIds: new Set(),
    newStreamNames: [],
  })

  // ------------------------------------------------------------------
  // Phase: accepting -- call invite accept on mount
  // ------------------------------------------------------------------
  useEffect(() => {
    if (state.phase !== 'accepting' || !token) return

    let cancelled = false

    async function acceptInvite() {
      try {
        const res = await api.post<AcceptResponse>('/tenants/invite/accept', { token })
        if (cancelled) return

        setState(prev => ({
          ...prev,
          tenantName: res.tenant_name,
          phase: 'streams',
        }))
      } catch (err: unknown) {
        if (cancelled) return
        const message =
          err instanceof Error && 'code' in err && (err as { code: number }).code === 404
            ? 'Invalid or expired invite link. Please ask your team admin to resend.'
            : 'Failed to accept invite. Please try again.'
        setState(prev => ({ ...prev, error: message }))
      }
    }

    acceptInvite()
    return () => { cancelled = true }
  }, [token, state.phase])

  // ------------------------------------------------------------------
  // Phase: streams -- fetch team streams
  // ------------------------------------------------------------------
  useEffect(() => {
    if (state.phase !== 'streams' || state.teamStreams.length > 0) return

    let cancelled = false

    async function fetchStreams() {
      try {
        setState(prev => ({ ...prev, loading: true }))
        const res = await api.get<StreamsResponse>('/team-onboarding/streams')
        if (cancelled) return

        setState(prev => ({
          ...prev,
          teamStreams: res.streams,
          loading: false,
        }))
      } catch {
        if (cancelled) return
        setState(prev => ({
          ...prev,
          loading: false,
          error: 'Failed to load team streams.',
        }))
      }
    }

    fetchStreams()
    return () => { cancelled = true }
  }, [state.phase, state.teamStreams.length])

  // ------------------------------------------------------------------
  // Phase: done -- redirect to briefing
  // ------------------------------------------------------------------
  useEffect(() => {
    if (state.phase === 'done') {
      navigate('/')
    }
  }, [state.phase, navigate])

  // ------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------

  const toggleStream = useCallback((id: string) => {
    setState(prev => {
      const next = new Set(prev.selectedStreamIds)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return { ...prev, selectedStreamIds: next }
    })
  }, [])

  const addNewStream = useCallback((name: string) => {
    const trimmed = name.trim()
    if (!trimmed) return
    setState(prev => ({
      ...prev,
      newStreamNames: [...prev.newStreamNames, trimmed],
    }))
  }, [])

  const confirmStreams = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true, error: null }))
    try {
      await api.post('/team-onboarding/join-streams', {
        stream_ids: Array.from(state.selectedStreamIds),
        new_stream_names: state.newStreamNames,
      })
      setState(prev => ({ ...prev, loading: false, phase: 'meetings' }))
    } catch {
      setState(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to join streams. Please try again.',
      }))
    }
  }, [state.selectedStreamIds, state.newStreamNames])

  const skipStreams = useCallback(() => {
    setState(prev => ({ ...prev, phase: 'meetings' }))
  }, [])

  const skipMeetings = useCallback(() => {
    setState(prev => ({ ...prev, phase: 'done' }))
  }, [])

  const onMeetingsComplete = useCallback(() => {
    setState(prev => ({ ...prev, phase: 'done' }))
  }, [])

  return {
    phase: state.phase,
    error: state.error,
    loading: state.loading,
    tenantName: state.tenantName,
    teamStreams: state.teamStreams,
    selectedStreamIds: state.selectedStreamIds,
    newStreamNames: state.newStreamNames,
    toggleStream,
    addNewStream,
    confirmStreams,
    skipStreams,
    skipMeetings,
    onMeetingsComplete,
  }
}
