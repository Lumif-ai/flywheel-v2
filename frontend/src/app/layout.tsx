import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { BrowserRouter, useLocation } from 'react-router'
import { SidebarProvider, SidebarInset } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { AppSidebar } from '@/features/navigation/components/AppSidebar'
import { MobileNav } from '@/features/navigation/components/MobileNav'
import { CommandPalette } from '@/features/navigation/components/CommandPalette'
import { AppRoutes } from '@/app/routes'
import { AuthBootstrap } from '@/app/AuthBootstrap'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

// Routes that render as standalone pages (no sidebar, no tenant-dependent fetches)
const STANDALONE_ROUTES = ['/onboarding', '/invite', '/terms', '/privacy']

function AppShell() {
  const isMobile = useMediaQuery('(max-width: 767px)')
  const location = useLocation()

  // Onboarding and other standalone routes render without the app shell.
  // This prevents tenant-dependent API calls (streams, tenants) from firing
  // before the user has been provisioned.
  const isStandalone = STANDALONE_ROUTES.some((r) => location.pathname.startsWith(r))

  if (isStandalone) {
    return (
      <main className="min-h-dvh">
        <AppRoutes />
      </main>
    )
  }

  if (isMobile) {
    return (
      <div className="flex flex-col h-dvh">
        <main className="flex-1 overflow-auto pb-16">
          <AppRoutes />
        </main>
        <MobileNav />
      </div>
    )
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <main className="flex-1 overflow-auto">
          <AppRoutes />
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}

export function AppLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthBootstrap>
          <TooltipProvider>
            <AppShell />
            <CommandPalette />
          </TooltipProvider>
        </AuthBootstrap>
      </BrowserRouter>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
