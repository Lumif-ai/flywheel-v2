import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { BrowserRouter } from 'react-router'
import { SidebarProvider, SidebarInset } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { AppSidebar } from '@/features/navigation/components/AppSidebar'
import { MobileNav } from '@/features/navigation/components/MobileNav'
import { AppRoutes } from '@/app/routes'

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

function AppShell() {
  const isMobile = useMediaQuery('(max-width: 767px)')

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
        <TooltipProvider>
          <AppShell />
        </TooltipProvider>
      </BrowserRouter>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
