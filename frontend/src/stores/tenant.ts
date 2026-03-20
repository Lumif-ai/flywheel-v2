import { create } from 'zustand'

interface Tenant {
  id: string
  name: string
  slug: string
  plan: string
  member_limit: number
}

interface TenantState {
  activeTenant: Tenant | null
  tenants: Tenant[]
  setActiveTenant: (tenant: Tenant | null) => void
  setTenants: (tenants: Tenant[]) => void
}

export const useTenantStore = create<TenantState>((set) => ({
  activeTenant: null,
  tenants: [],
  setActiveTenant: (activeTenant) => set({ activeTenant }),
  setTenants: (tenants) => set({ tenants }),
}))
