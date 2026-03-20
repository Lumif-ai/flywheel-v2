import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronsUpDown, Plus, Check } from 'lucide-react'
import { api } from '@/lib/api'
import { useTenantStore } from '@/stores/tenant'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import type { Tenant } from '@/types/api'

export function TenantSwitcher() {
  const queryClient = useQueryClient()
  const activeTenant = useTenantStore((s) => s.activeTenant)
  const setActiveTenant = useTenantStore((s) => s.setActiveTenant)
  const setTenants = useTenantStore((s) => s.setTenants)

  const { data: tenants } = useQuery({
    queryKey: ['tenants'],
    queryFn: async () => {
      const data = await api.get<Tenant[]>('/tenants')
      setTenants(data)
      return data
    },
  })

  const handleSwitch = async (tenant: Tenant) => {
    if (tenant.id === activeTenant?.id) return
    try {
      await api.post('/auth/switch-tenant', { tenant_id: tenant.id })
    } catch {
      // Switch may not require backend call in all setups
    }
    setActiveTenant(tenant)
    queryClient.clear()
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-muted transition-colors outline-none">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground font-bold text-xs shrink-0">
          {activeTenant?.name?.charAt(0)?.toUpperCase() ?? 'F'}
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-semibold text-foreground truncate block">
            {activeTenant?.name ?? 'Flywheel'}
          </span>
        </div>
        <ChevronsUpDown className="size-4 text-muted-foreground shrink-0" />
      </DropdownMenuTrigger>

      <DropdownMenuContent align="start" sideOffset={8} className="w-56">
        <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
        {tenants?.map((tenant) => (
          <DropdownMenuItem
            key={tenant.id}
            onClick={() => handleSwitch(tenant)}
            className="flex items-center gap-2"
          >
            <div className="flex h-6 w-6 items-center justify-center rounded bg-muted text-xs font-medium shrink-0">
              {tenant.name.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-sm truncate block">{tenant.name}</span>
            </div>
            <Badge variant="secondary" className="text-[10px] shrink-0">
              {tenant.plan}
            </Badge>
            {tenant.id === activeTenant?.id && (
              <Check className="size-3.5 text-primary shrink-0" />
            )}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem className="flex items-center gap-2 text-muted-foreground">
          <Plus className="size-4" />
          <span>Create workspace</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
