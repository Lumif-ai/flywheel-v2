/**
 * AuthCallback -- Handles the OAuth redirect from Supabase.
 *
 * Supabase automatically exchanges the code from the URL hash/params.
 * This component shows a loading spinner while that happens, then:
 * 1. Extracts provider_token + provider_refresh_token from the session
 * 2. Calls POST /onboarding/promote-oauth to create tenant + integrations
 * 3. If provider_token is unavailable, falls back to two-step OAuth
 * 4. Resumes any pending action stored in localStorage
 * 5. Redirects to /
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
        useAuthStore.getState().setToken(session.access_token)
        useAuthStore.getState().setUser({
          id: session.user?.id ?? '',
          email: session.user?.email ?? null,
          is_anonymous: session.user?.is_anonymous ?? false,
        })

        // Determine the OAuth provider
        const provider = session.user?.app_metadata?.provider
        const providerNormalized =
          provider === 'azure' ? 'microsoft' : provider === 'google' ? 'google' : null

        if (providerNormalized && session.provider_token) {
          // Primary path: provider_token available -- single-step promote with integrations
          try {
            await api.post('/onboarding/promote-oauth', {
              provider: providerNormalized,
              provider_token: session.provider_token,
              provider_refresh_token: session.provider_refresh_token ?? null,
              email: session.user?.email ?? '',
            })
          } catch (err) {
            // If promote-oauth fails (e.g., user already promoted), log and continue
            console.warn('promote-oauth failed, user may already be promoted:', err)
          }
        } else if (session.user?.email) {
          // Fallback: Supabase session did not include provider_token.
          // Using two-step OAuth: identity via Supabase, data access via Integration OAuth.
          try {
            await api.post('/onboarding/promote', { email: session.user.email })
          } catch (err) {
            console.warn('promote fallback failed:', err)
          }

          // Redirect to Integration OAuth for the same provider to get data access tokens
          if (providerNormalized === 'google') {
            // Existing Integration OAuth endpoint for Google Calendar
            window.location.href = '/api/v1/integrations/google-calendar/authorize'
            return
          } else if (providerNormalized === 'microsoft') {
            // Existing Integration OAuth endpoint for Microsoft Outlook
            window.location.href = '/api/v1/integrations/microsoft-outlook/authorize'
            return
          }
        }

        // Resume pending action if stored
        const pendingRaw = localStorage.getItem('pendingAction')
        if (pendingRaw) {
          localStorage.removeItem('pendingAction')
          // The pending action will be handled by the page that loads after redirect
          // Store it back briefly for the destination page to pick up
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
