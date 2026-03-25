import { useEffect, useState } from 'react'
import { getSupabase } from '@/lib/supabase'
import { useAuthStore } from '@/stores/auth'

/**
 * Ensures an auth session exists before rendering children.
 * For anonymous users, creates a Supabase anonymous session on app startup
 * so sidebar/layout API calls have a valid JWT token.
 *
 * Also listens for auth state changes (e.g., after OAuth callback) to keep
 * the auth store in sync with Supabase.
 */
export function AuthBootstrap({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false)
  const token = useAuthStore((s) => s.token)

  // Listen for Supabase auth state changes (OAuth callback, token refresh, etc.)
  useEffect(() => {
    let subscription: { unsubscribe: () => void } | null = null

    async function setupListener() {
      const supabase = await getSupabase()
      if (!supabase) return

      const { data } = supabase.auth.onAuthStateChange((event, session) => {
        if (event === 'SIGNED_IN' && session) {
          useAuthStore.getState().setToken(session.access_token)
          useAuthStore.getState().setUser({
            id: session.user?.id ?? '',
            email: session.user?.email ?? null,
            is_anonymous: session.user?.is_anonymous ?? false,
            display_name: session.user?.user_metadata?.full_name ?? session.user?.user_metadata?.name ?? null,
            avatar_url: session.user?.user_metadata?.avatar_url ?? null,
          })
        } else if (event === 'TOKEN_REFRESHED' && session) {
          useAuthStore.getState().setToken(session.access_token)
        } else if (event === 'SIGNED_OUT') {
          useAuthStore.getState().logout()
        }
      })

      subscription = data.subscription
    }

    setupListener()

    return () => {
      subscription?.unsubscribe()
    }
  }, [])

  useEffect(() => {
    if (token) {
      setReady(true)
      return
    }

    async function ensureSession() {
      try {
        const supabase = await getSupabase()

        if (supabase) {
          // Check for existing session first
          const { data: { session: existing } } = await supabase.auth.getSession()
          if (existing?.access_token) {
            useAuthStore.getState().setToken(existing.access_token)
            useAuthStore.getState().setUser({
              id: existing.user?.id ?? '',
              email: existing.user?.email ?? null,
              is_anonymous: existing.user?.is_anonymous ?? true,
              display_name: existing.user?.user_metadata?.full_name ?? existing.user?.user_metadata?.name ?? null,
              avatar_url: existing.user?.user_metadata?.avatar_url ?? null,
            })
            setReady(true)
            return
          }

          // No existing session -- create anonymous
          const previousAnonId = sessionStorage.getItem('flywheel-anon-id')
          if (previousAnonId) {
            console.warn('[AuthBootstrap] Previous anonymous session detected but lost. Previous ID:', previousAnonId)
          }

          const { data, error } = await supabase.auth.signInAnonymously()
          if (error) throw error
          if (data.session?.access_token) {
            useAuthStore.getState().setToken(data.session.access_token)
            useAuthStore.getState().setUser({
              id: data.user?.id ?? '',
              email: null,
              is_anonymous: true,
              display_name: null,
              avatar_url: null,
            })
            // Store anonymous user ID for refresh resilience diagnostics
            if (data.user?.id) {
              sessionStorage.setItem('flywheel-anon-id', data.user.id)
            }
          }
        }
      } catch (err) {
        console.warn('Auth bootstrap failed:', err)
      }
      setReady(true)
    }

    ensureSession()
  }, [token])

  if (!ready) {
    return (
      <div className="flex h-dvh items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
      </div>
    )
  }

  return <>{children}</>
}
