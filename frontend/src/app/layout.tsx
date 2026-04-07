import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
// DevTools removed — was showing coconut tree bubble in production
import { BrowserRouter, useLocation } from 'react-router'
import { SidebarProvider, SidebarInset } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Toaster } from '@/components/ui/sonner'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { AppSidebar } from '@/features/navigation/components/AppSidebar'
import { MobileNav } from '@/features/navigation/components/MobileNav'
import { CommandPalette } from '@/features/navigation/components/CommandPalette'
import { AppRoutes } from '@/app/routes'
import { AuthBootstrap } from '@/app/AuthBootstrap'
import { CriticalEmailAlert } from '@/features/email/components/CriticalEmailAlert'
import { useEmailThreads } from '@/features/email/hooks/useEmailThreads'
import { useFeatureFlag } from '@/lib/feature-flags'

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

// ---------------------------------------------------------------------------
// React Query cache persistence — returning users see instant renders
// ---------------------------------------------------------------------------

const CACHE_KEY = 'flywheel:query-cache'
const CACHE_MAX_AGE = 24 * 60 * 60 * 1000 // 24 hours

// Hydrate from localStorage on startup (before first render)
try {
  const persisted = localStorage.getItem(CACHE_KEY)
  if (persisted) {
    const { timestamp, data } = JSON.parse(persisted) as { timestamp: number; data: Array<{ queryKey: unknown; state: unknown }> }
    if (Date.now() - timestamp < CACHE_MAX_AGE) {
      const VOLATILE_PREFIXES = ['email-threads', 'email-digest', 'thread-detail', 'meetings']
      for (const entry of data) {
        const key = (entry.queryKey as string[])?.[0] ?? ''
        if (VOLATILE_PREFIXES.some((p) => key.startsWith?.(p))) continue
        queryClient.setQueryData(entry.queryKey as string[], entry.state)
      }
    } else {
      localStorage.removeItem(CACHE_KEY)
    }
  }
} catch {
  // Corrupted cache — ignore
}

// Persist cache to localStorage on page unload
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    try {
      const cache = queryClient.getQueryCache().getAll()
      // Exclude frequently-changing data (email, meetings) from persistence
      const VOLATILE_PREFIXES = ['email-threads', 'email-digest', 'thread-detail', 'meetings']
      const data = cache
        .filter((q) => q.state.status === 'success' && q.state.data != null)
        .filter((q) => !VOLATILE_PREFIXES.some((p) => (q.queryKey[0] as string)?.startsWith?.(p)))
        .map((q) => ({ queryKey: q.queryKey, state: q.state.data }))
      localStorage.setItem(CACHE_KEY, JSON.stringify({ timestamp: Date.now(), data }))
    } catch {
      // Quota exceeded or serialization error — skip
    }
  })
}

// Routes that render as standalone pages (no sidebar, no tenant-dependent fetches)
const STANDALONE_ROUTES = ['/onboarding', '/invite', '/terms', '/privacy', '/briefing', '/auth']

// Only rendered inside the authenticated shell so useEmailThreads never fires
// on standalone routes (which have no auth context and would return 401).
// React Query deduplicates this call with the same query on EmailPage.
// Two-component pattern: AuthenticatedAlerts gates on FEATURE_EMAIL before
// rendering EmailAlertInner, ensuring useEmailThreads() never fires when
// email is disabled (hooks cannot be called conditionally).
function EmailAlertInner() {
  const { data: emailData } = useEmailThreads()
  return emailData?.threads ? <CriticalEmailAlert threads={emailData.threads} /> : null
}

function AuthenticatedAlerts() {
  const emailEnabled = useFeatureFlag('email')
  if (!emailEnabled) return null
  return <EmailAlertInner />
}

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
        <AuthenticatedAlerts />
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
      <AuthenticatedAlerts />
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
      <Toaster position="top-right" />
    </QueryClientProvider>
  )
}
