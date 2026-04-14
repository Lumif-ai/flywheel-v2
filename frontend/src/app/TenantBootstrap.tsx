import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useTenantStore } from '@/stores/tenant'
import type { Tenant } from '@/types/api'

/**
 * Ensures tenant state is resolved before rendering children.
 *
 * - If Zustand persist already hydrated activeTenant from localStorage,
 *   renders children immediately (no network gate).
 * - Fetches tenants from API via React Query (pure fetch, no side effects in queryFn).
 * - Syncs fetched data to Zustand store via useEffect:
 *   - Always calls setTenants(data) to keep the store list fresh.
 *   - If activeTenant is null: sets data[0] as the active tenant.
 *   - If activeTenant exists: refreshes with server data (features/plan may have changed).
 *     Falls back to data[0] if the active tenant was deleted server-side.
 *
 * Only blocks rendering when BOTH !activeTenant AND isLoading are true —
 * i.e., localStorage had nothing and the network hasn't responded yet.
 */
export function TenantBootstrap({ children }: { children: React.ReactNode }) {
  const activeTenant = useTenantStore((s) => s.activeTenant)
  const setActiveTenant = useTenantStore((s) => s.setActiveTenant)
  const setTenants = useTenantStore((s) => s.setTenants)

  const { data, isLoading } = useQuery({
    queryKey: ['tenants'],
    queryFn: () => api.get<Tenant[]>('/tenants'),
  })

  useEffect(() => {
    if (!data || data.length === 0) return

    setTenants(data)

    if (!activeTenant) {
      // No persisted tenant — bootstrap from first in list
      setActiveTenant(data[0])
    } else {
      // Refresh active tenant with latest server data (features/plan may have changed)
      const fresh = data.find((t) => t.id === activeTenant.id)
      if (fresh) {
        setActiveTenant(fresh)
      } else {
        // Active tenant no longer exists server-side — fall back to first
        setActiveTenant(data[0] ?? null)
      }
    }
    // activeTenant intentionally omitted from deps to avoid infinite loop —
    // this effect only needs to run when fresh server data arrives.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, setActiveTenant, setTenants])

  // Only block rendering if there's nothing from localStorage AND network is in-flight
  if (!activeTenant && isLoading) {
    return (
      <div className="flex h-dvh items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
      </div>
    )
  }

  return <>{children}</>
}
