import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

interface Tenant {
  id: string
  name: string
  slug: string
  plan: string
  member_limit: number
  features?: Record<string, boolean>
}

interface TenantState {
  activeTenant: Tenant | null
  tenants: Tenant[]
  setActiveTenant: (tenant: Tenant | null) => void
  setTenants: (tenants: Tenant[]) => void
}

export const useTenantStore = create<TenantState>()(
  persist(
    (set) => ({
      activeTenant: null,
      tenants: [],
      setActiveTenant: (activeTenant) => set({ activeTenant }),
      setTenants: (tenants) => set({ tenants }),
    }),
    {
      name: 'flywheel:tenant',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ activeTenant: state.activeTenant }),
    },
  ),
)
