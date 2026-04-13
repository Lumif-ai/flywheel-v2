import { useState } from 'react'
import { NavLink, useLocation, useSearchParams, Link } from 'react-router'
import { Home, Settings, FileText, Building2, Lock, Mail, TrendingUp, Briefcase, DollarSign, LogOut, CalendarDays, CheckSquare, Bookmark, Shield } from 'lucide-react'
import { useLifecycleState } from '@/features/navigation/hooks/useLifecycleState'
import { useAuthStore } from '@/stores/auth'
import { useOAuthSignIn } from '@/hooks/useOAuthSignIn'
import { useSavedViews, buildViewUrl } from '@/features/pipeline/hooks/useSavedViews'
import { colors, typography } from '@/lib/design-tokens'
import { useFeatureFlag } from '@/lib/feature-flags'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarHeader,
  SidebarFooter,
} from '@/components/ui/sidebar'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { TenantSwitcher } from './TenantSwitcher'
import { StreamSidebar } from '@/features/streams/components/StreamSidebar'
import { BrokerSidebarContent } from './BrokerSidebarContent'

export function AppSidebar() {
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const emailEnabled = useFeatureFlag('email')
  const tasksEnabled = useFeatureFlag('tasks')
  const pipelineEnabled = useFeatureFlag('pipeline')
  const meetingsEnabled = useFeatureFlag('meetings')
  const brokerEnabled = useFeatureFlag('broker')

  const { state, hasApiKey, isAnonymous: isAnonymousServer } = useLifecycleState()
  const user = useAuthStore((s) => s.user)
  // Use local auth store as source of truth for anonymous status — the server
  // lifecycle can lag or return false for anonymous users with leftover tenant data
  const isAnonymous = user?.is_anonymous ?? isAnonymousServer
  const [oauthLoading, setOauthLoading] = useState<'google' | 'microsoft' | null>(null)
  const { signInWithProvider } = useOAuthSignIn()
  const logout = useAuthStore((s) => s.logout)

  const { data: savedViews = [] } = useSavedViews()

  // Derive display name and initials from user metadata
  const initials = user?.display_name
    ? user.display_name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
    : user?.email
      ? user.email[0].toUpperCase()
      : 'U'
  const displayName = user?.display_name ?? user?.email?.split('@')[0] ?? 'User'

  // Show API key banner only for S4 (power threshold) and S5 (power user without key -- impossible but safe)
  const showApiKeyBanner = !hasApiKey && (state === 'S4' || state === 'S5')

  // Active state detection for pipeline section
  const isPipelinePath = location.pathname === '/pipeline' || location.pathname.startsWith('/pipeline/')
  const activeRelType = searchParams.get('relationshipType')

  const handleSignOut = async () => {
    const supabase = await (await import('@/lib/supabase')).getSupabase()
    if (supabase) await supabase.auth.signOut({ scope: 'local' })
    logout()
    // Clear persisted React Query cache so stale lifecycle data doesn't survive
    localStorage.removeItem('flywheel:query-cache')
    localStorage.removeItem('flywheel-auth')
    window.location.href = '/'
  }

  const handleGoogleSignin = async () => {
    setOauthLoading('google')
    try {
      await signInWithProvider('google')
    } catch (err) {
      console.error('Google OAuth error:', err)
      setOauthLoading(null)
    }
  }

  const handleMicrosoftSignin = async () => {
    setOauthLoading('microsoft')
    try {
      await signInWithProvider('azure')
    } catch (err) {
      console.error('Microsoft OAuth error:', err)
      setOauthLoading(null)
    }
  }

  return (
    <Sidebar>
      <SidebarHeader className="p-3">
        <TenantSwitcher />
      </SidebarHeader>

      <SidebarContent>
        {brokerEnabled ? (
          <BrokerSidebarContent />
        ) : (
          <>
            {/* API key banner — GTM only */}
            {showApiKeyBanner && (
              <div className="mx-3 mb-2">
                <Link
                  to="/settings"
                  className="flex items-center gap-1.5 no-underline hover:opacity-80 transition-opacity"
                  style={{
                    fontSize: '12px',
                    color: 'var(--secondary-text)',
                    padding: '6px 8px',
                    borderRadius: '6px',
                  }}
                >
                  <Lock className="size-3 shrink-0" />
                  <span>Add your API key for unlimited research</span>
                </Link>
              </div>
            )}

            {/* General navigation — GTM only */}
            <SidebarGroup>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton
                      isActive={location.pathname === '/'}
                      render={<NavLink to="/" />}
                      tooltip="Briefing"
                    >
                      <Home className="size-4" />
                      <span>Briefing</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton
                      isActive={location.pathname === '/profile'}
                      render={<NavLink to="/profile" />}
                      tooltip="Company Profile"
                    >
                      <Building2 className="size-4" />
                      <span>Company Profile</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton
                      isActive={location.pathname.startsWith('/documents')}
                      render={<NavLink to="/documents" />}
                      tooltip="Library"
                    >
                      <FileText className="size-4" />
                      <span>Library</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  {emailEnabled && (
                  <SidebarMenuItem>
                    <SidebarMenuButton
                      isActive={location.pathname.startsWith('/email')}
                      render={<NavLink to="/email" />}
                      tooltip="Email"
                    >
                      <Mail className="size-4" />
                      <span>Email</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  )}
                  {meetingsEnabled && (
                  <SidebarMenuItem>
                    <SidebarMenuButton
                      isActive={location.pathname.startsWith('/meetings')}
                      render={<NavLink to="/meetings" />}
                      tooltip="Meetings"
                    >
                      <CalendarDays className="size-4" />
                      <span>Meetings</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  )}
                  {tasksEnabled && (
                  <SidebarMenuItem>
                    <SidebarMenuButton
                      isActive={location.pathname.startsWith('/tasks')}
                      render={<NavLink to="/tasks" />}
                      tooltip="Tasks"
                    >
                      <CheckSquare className="size-4" />
                      <span>Tasks</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  )}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>

            {/* Pipeline — GTM only */}
            {pipelineEnabled && (
            <SidebarGroup>
              <SidebarGroupLabel
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  color: 'var(--secondary-text)',
                }}
              >
                Pipeline
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {/* All entries */}
                  <SidebarMenuItem>
                    <SidebarMenuButton
                      isActive={isPipelinePath && !activeRelType}
                      render={<NavLink to="/pipeline" />}
                      tooltip="All"
                    >
                      <TrendingUp className="size-4" />
                      <span>All</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>

                  {/* Built-in relationship filters */}
                  {[
                    { label: 'Customers', type: 'customer', icon: <TrendingUp className="size-4" /> },
                    { label: 'Advisors', type: 'advisor', icon: <Briefcase className="size-4" /> },
                    { label: 'Investors', type: 'investor', icon: <DollarSign className="size-4" /> },
                  ].map(({ label, type, icon }) => (
                    <SidebarMenuItem key={type}>
                      <SidebarMenuButton
                        isActive={isPipelinePath && activeRelType === type}
                        render={<NavLink to={`/pipeline?relationshipType=${type}`} />}
                        tooltip={label}
                      >
                        {icon}
                        <span>{label}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>

                {/* Saved Views */}
                {savedViews.length > 0 && (
                  <>
                    <SidebarGroupLabel
                      style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        color: 'var(--secondary-text)',
                        marginTop: '8px',
                      }}
                    >
                      Saved Views
                    </SidebarGroupLabel>
                    <SidebarMenu>
                      {savedViews.map((view) => (
                        <SidebarMenuItem key={view.id}>
                          <SidebarMenuButton
                            render={<NavLink to={buildViewUrl(view)} />}
                            tooltip={view.name}
                          >
                            <Bookmark className="size-4" />
                            <span>{view.name}</span>
                          </SidebarMenuButton>
                        </SidebarMenuItem>
                      ))}
                    </SidebarMenu>
                  </>
                )}
              </SidebarGroupContent>
            </SidebarGroup>
            )}

            {/* Streams — GTM only */}
            <SidebarGroup>
              <SidebarGroupContent>
                <StreamSidebar />
              </SidebarGroupContent>
            </SidebarGroup>
          </>
        )}
      </SidebarContent>

      <SidebarFooter className="p-4" style={{ borderTop: '1px solid var(--subtle-border)' }}>
        {isAnonymous ? (
          /* Anonymous users: show sign-in options instead of Settings + avatar */
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <p
              style={{
                fontSize: typography.caption.size,
                color: colors.secondaryText,
                margin: '0 0 4px 0',
              }}
            >
              Sign in to save your work
            </p>
            <button
              onClick={handleGoogleSignin}
              disabled={oauthLoading !== null}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                borderRadius: '8px',
                border: `1px solid ${colors.subtleBorder}`,
                background: '#fff',
                cursor: oauthLoading ? 'not-allowed' : 'pointer',
                opacity: oauthLoading && oauthLoading !== 'google' ? 0.5 : 1,
                fontSize: typography.caption.size,
                fontWeight: '500',
                color: colors.headingText,
                transition: 'border-color 0.15s',
                width: '100%',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
              </svg>
              {oauthLoading === 'google' ? 'Connecting...' : 'Continue with Google'}
            </button>
            <button
              onClick={handleMicrosoftSignin}
              disabled={oauthLoading !== null}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                borderRadius: '8px',
                border: `1px solid ${colors.subtleBorder}`,
                background: '#fff',
                cursor: oauthLoading ? 'not-allowed' : 'pointer',
                opacity: oauthLoading && oauthLoading !== 'microsoft' ? 0.5 : 1,
                fontSize: typography.caption.size,
                fontWeight: '500',
                color: colors.headingText,
                transition: 'border-color 0.15s',
                width: '100%',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 21 21">
                <rect x="1" y="1" width="9" height="9" fill="#F25022" />
                <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
                <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
                <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
              </svg>
              {oauthLoading === 'microsoft' ? 'Connecting...' : 'Continue with Microsoft'}
            </button>
          </div>
        ) : (
          /* Authenticated users: show Settings + avatar */
          <>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  isActive={location.pathname === '/settings'}
                  render={<NavLink to="/settings" />}
                  tooltip="Settings"
                >
                  <Settings className="size-4" />
                  <span>Settings</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
            <div className="flex items-center justify-between mt-2">
              <div className="flex items-center gap-2">
                <Avatar className="h-7 w-7">
                  <AvatarFallback className="text-xs" style={{ backgroundColor: 'var(--brand-tint)', color: 'var(--brand-coral)' }}>{initials}</AvatarFallback>
                </Avatar>
                <span className="text-sm text-muted-foreground truncate max-w-[120px]">{displayName}</span>
              </div>
              <button
                onClick={handleSignOut}
                className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                title="Sign out"
              >
                <LogOut className="size-4" />
              </button>
            </div>
          </>
        )}
      </SidebarFooter>
    </Sidebar>
  )
}
