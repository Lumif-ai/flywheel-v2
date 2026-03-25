/**
 * Shared OAuth sign-in hook.
 *
 * Centralizes Google / Microsoft OAuth logic that was previously duplicated
 * across SignupGate, BriefingChatPanel, and AppSidebar.
 *
 * - linkIdentity (first attempt): uses prompt:'consent' to get refresh token
 * - signInWithOAuth (fallback): uses prompt:'select_account' so returning
 *   users aren't forced through the consent screen again
 */

import { getSupabase } from '@/lib/supabase'

type Provider = 'google' | 'azure'

const SCOPES: Record<Provider, string> = {
  google:
    'https://www.googleapis.com/auth/calendar.events.readonly https://www.googleapis.com/auth/gmail.readonly',
  azure: 'Calendars.Read Mail.Read Mail.Send',
}

/**
 * Returns a `signInWithProvider` function that handles the linkIdentity-first,
 * signInWithOAuth-fallback flow for the given provider.
 */
export function useOAuthSignIn() {
  async function signInWithProvider(provider: Provider) {
    const supabase = await getSupabase()
    if (!supabase) return

    // Capture anonymous user ID before OAuth redirect (consumed by Plan 03 data claim)
    const {
      data: { user: currentUser },
    } = await supabase.auth.getUser()
    if (currentUser?.is_anonymous) {
      localStorage.setItem('flywheel-prev-anon-id', currentUser.id)
    }

    const redirectTo = `${window.location.origin}/auth/callback`
    const scopes = SCOPES[provider]

    // linkIdentity keeps the anonymous session's data linkage intact.
    // prompt:'consent' is required here to obtain a refresh token from the provider.
    const linkQueryParams: Record<string, string> =
      provider === 'google'
        ? { access_type: 'offline', prompt: 'consent' }
        : { prompt: 'consent' }

    const { error: linkError } = await supabase.auth.linkIdentity({
      provider,
      options: { redirectTo, scopes, queryParams: linkQueryParams },
    })

    if (linkError) {
      // Identity already exists -- fall back to regular OAuth sign-in.
      // prompt:'select_account' lets returning users pick an account without
      // being forced through the full consent flow again.
      const signInQueryParams: Record<string, string> =
        provider === 'google'
          ? { access_type: 'offline', prompt: 'select_account' }
          : { prompt: 'select_account' }

      await supabase.auth.signInWithOAuth({
        provider,
        options: { redirectTo, scopes, queryParams: signInQueryParams },
      })
    }
  }

  return { signInWithProvider }
}
