/**
 * Supabase Realtime subscription hook for background completion alerts.
 *
 * Subscribes to postgres_changes on the skill_runs table to detect when
 * a run completes while the user has navigated away from the chat stream.
 * This enables toast notifications for background completions.
 *
 * NOTE: Stubbed for local dev -- actual Supabase client setup depends on
 * environment variables that may not be available. SSE handles the primary
 * streaming path; Realtime is only for the "closed browser tab" scenario.
 */

import { useEffect } from 'react'

// Supabase client placeholder -- will be configured when VITE_SUPABASE_URL
// and VITE_SUPABASE_ANON_KEY are available in the environment.
let supabaseClient: any = null

try {
  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
  const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY

  if (supabaseUrl && supabaseKey) {
    // Dynamic import to avoid bundling supabase-js when not configured
    import('@supabase/supabase-js').then(({ createClient }) => {
      supabaseClient = createClient(supabaseUrl, supabaseKey)
    }).catch(() => {
      console.debug('Supabase Realtime: @supabase/supabase-js not installed')
    })
  }
} catch {
  // Environment variables not available -- Realtime disabled
}

export interface SkillRunUpdate {
  id: string
  status: string
  skill_name: string
  [key: string]: unknown
}

/**
 * Subscribe to skill_runs table changes for a specific user.
 *
 * Calls onComplete when a run transitions to 'completed' or 'failed'.
 * Returns a cleanup function that unsubscribes on unmount.
 *
 * @param userId - The user's UUID (null disables subscription)
 * @param onComplete - Callback fired with the updated run record
 */
export function useSkillRunRealtime(
  userId: string | null,
  onComplete: (run: SkillRunUpdate) => void,
): void {
  useEffect(() => {
    if (!userId || !supabaseClient) {
      if (!supabaseClient && userId) {
        console.debug('Supabase Realtime not configured -- background notifications disabled')
      }
      return
    }

    const channel = supabaseClient
      .channel(`skill-runs-${userId}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'skill_runs',
          filter: `user_id=eq.${userId}`,
        },
        (payload: { new: SkillRunUpdate }) => {
          const newStatus = payload.new.status
          if (newStatus === 'completed' || newStatus === 'failed') {
            onComplete(payload.new)
          }
        },
      )
      .subscribe()

    return () => {
      supabaseClient.removeChannel(channel)
    }
  }, [userId, onComplete])
}
