/**
 * AuthCallback -- Handles the OAuth redirect from Supabase after linkIdentity().
 *
 * linkIdentity() preserves the anonymous user's ID, so all existing data
 * (briefings, company intel, context entries) stays linked. This callback:
 * 1. Waits for Supabase to exchange the code and refresh the session
 * 2. Updates the auth store with the new (non-anonymous) session
 * 3. Calls POST /onboarding/promote-oauth to set up company/tenant + integrations
 * 4. If provider_token is missing (documented linkIdentity limitation), skips
 *    integration creation -- user can connect calendar/email later
 * 5. Resumes any pending action and redirects to /
 */

import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { getSupabase } from '@/lib/supabase'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/lib/api'

export function AuthCallback() {
  const navigate = useNavigate()
  const processed = useRef(false)

  useEffect(() => {
    if (processed.current) return
    processed.current = true

    async function handleCallback() {
      try {
        const supabase = await getSupabase()
        if (!supabase) {
          navigate('/', { replace: true })
          return
        }

        // Supabase exchanges the code automatically when getSession is called
        // after a redirect with code in the URL params
        const {
          data: { session },
        } = await supabase.auth.getSession()

        if (!session) {
          console.warn('AuthCallback: No session after OAuth redirect')
          navigate('/', { replace: true })
          return
        }

        // Update auth store with the new session
        // After linkIdentity, user.id is the SAME as the anonymous user's id
        useAuthStore.getState().setToken(session.access_token)
        useAuthStore.getState().setUser({
          id: session.user?.id ?? '',
          email: session.user?.email ?? null,
          is_anonymous: session.user?.is_anonymous ?? false,
          display_name: session.user?.user_metadata?.full_name ?? session.user?.user_metadata?.name ?? null,
          avatar_url: session.user?.user_metadata?.avatar_url ?? null,
        })

        // Determine the OAuth provider
        const provider = session.user?.app_metadata?.provider
        const providerNormalized =
          provider === 'azure' ? 'microsoft' : provider === 'google' ? 'google' : null

        if (providerNormalized) {
          // Call promote-oauth to set up company/domain on the existing tenant
          // and create Integration rows if provider_token is available
          try {
            await api.post('/onboarding/promote-oauth', {
              provider: providerNormalized,
              provider_token: session.provider_token ?? '',
              provider_refresh_token: session.provider_refresh_token ?? null,
              email: session.user?.email ?? '',
            })
          } catch (err) {
            // If promote-oauth fails (e.g., user already promoted), log and continue
            console.warn('promote-oauth failed, user may already be promoted:', err)
          }

          // Re-fetch user to get potentially updated metadata
          // (workaround for Supabase linkIdentity metadata gap -- supabase/auth#1708)
          try {
            const { data: { user: freshUser } } = await supabase.auth.getUser()
            if (freshUser) {
              useAuthStore.getState().setUser({
                id: freshUser.id,
                email: freshUser.email ?? null,
                is_anonymous: false,
                display_name: freshUser.user_metadata?.full_name ?? freshUser.user_metadata?.name ?? null,
                avatar_url: freshUser.user_metadata?.avatar_url ?? null,
              })
            }
          } catch {
            // Non-critical: metadata update failed, user still has session data
          }

          // If provider_token was missing (linkIdentity limitation),
          // integrations weren't created. User can connect later from Settings.
          if (!session.provider_token) {
            console.info('AuthCallback: provider_token not available after linkIdentity — integrations skipped')
          }

          // Claim orphaned anonymous data if linkIdentity failed and a new user was created
          const prevAnonId = localStorage.getItem('flywheel-prev-anon-id')
          if (prevAnonId && prevAnonId !== session.user.id) {
            try {
              await api.post('/onboarding/claim-anonymous-data', {
                previous_anonymous_id: prevAnonId,
              })
              console.log('[AuthCallback] Claimed anonymous data from:', prevAnonId)
            } catch (err) {
              // Non-fatal: user just won't have their anonymous data
              console.warn('[AuthCallback] claim-anonymous-data failed:', err)
            } finally {
              localStorage.removeItem('flywheel-prev-anon-id')
            }
          }
        }

        // Resume pending action if stored
        const pendingRaw = localStorage.getItem('pendingAction')
        if (pendingRaw) {
          localStorage.removeItem('pendingAction')
          sessionStorage.setItem('resumeAction', pendingRaw)
        }

        navigate('/', { replace: true })
      } catch (err) {
        console.error('AuthCallback error:', err)
        navigate('/', { replace: true })
      }
    }

    handleCallback()
  }, [navigate])

  return (
    <div className="flex h-dvh items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
        <p className="text-sm text-muted-foreground">Completing sign in...</p>
      </div>
    </div>
  )
}
