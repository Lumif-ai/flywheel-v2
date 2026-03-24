/**
 * Shared Supabase client singleton.
 *
 * All code that needs a Supabase client should import `getSupabase()` from here
 * instead of calling `createClient()` directly. This avoids the
 * "Multiple GoTrueClient instances" warning and prevents token-refresh races.
 */

import type { SupabaseClient } from '@supabase/supabase-js'

let client: SupabaseClient | null = null
let initPromise: Promise<SupabaseClient | null> | null = null

/**
 * Returns the shared Supabase client, creating it on first call.
 * Returns null if VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are not set.
 */
export function getSupabase(): Promise<SupabaseClient | null> {
  if (client) return Promise.resolve(client)
  if (initPromise) return initPromise

  initPromise = (async () => {
    try {
      const supabaseUrl = (import.meta as any).env?.VITE_SUPABASE_URL
      const supabaseKey = (import.meta as any).env?.VITE_SUPABASE_ANON_KEY

      if (!supabaseUrl || !supabaseKey) return null

      const { createClient } = await import('@supabase/supabase-js')
      client = createClient(supabaseUrl, supabaseKey)
      return client
    } catch {
      return null
    }
  })()

  return initPromise
}
