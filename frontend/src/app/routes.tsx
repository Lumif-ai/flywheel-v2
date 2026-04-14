import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate, useParams } from 'react-router'
import { AuthCallback } from '@/app/AuthCallback'
import { useFeatureFlag } from '@/lib/feature-flags'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'

/** Redirect /relationships/:id to /pipeline/:id preserving the param */
function RelationshipRedirect() {
  const { id } = useParams()
  return <Navigate to={`/pipeline/${id}`} replace />
}

// All page components lazy-loaded — keeps main bundle lean
const BriefingPageV2 = lazy(() =>
  import('@/features/briefing/components/BriefingPageV2').then((m) => ({ default: m.BriefingPageV2 }))
)
const BriefingFullViewer = lazy(() =>
  import('@/features/briefing/components/BriefingFullViewer').then((m) => ({ default: m.BriefingFullViewer }))
)
const StreamDetailPage = lazy(() =>
  import('@/features/streams/components/StreamDetailPage').then((m) => ({ default: m.StreamDetailPage }))
)
const ActPage = lazy(() =>
  import('@/pages/ActPage').then((m) => ({ default: m.ActPage }))
)
const SettingsPage = lazy(() =>
  import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage }))
)
const OnboardingPage = lazy(() =>
  import('@/pages/OnboardingPage').then((m) => ({ default: m.OnboardingPage }))
)
const InviteAcceptPage = lazy(() =>
  import('@/pages/InviteAcceptPage').then((m) => ({ default: m.InviteAcceptPage }))
)
const CompanyProfilePage = lazy(() =>
  import('@/features/profile/components/CompanyProfilePage').then((m) => ({ default: m.CompanyProfilePage }))
)

// Lazy-loaded document pages (v12.0 library redesign)
const DocumentLibrary = lazy(() =>
  import('@/features/documents/components/DocumentLibrary').then((m) => ({ default: m.DocumentLibrary }))
)
const DocumentViewer = lazy(() =>
  import('@/features/documents/components/DocumentViewer').then((m) => ({ default: m.DocumentViewer }))
)
const SharedDocumentPage = lazy(() =>
  import('@/features/documents/components/SharedDocumentPage').then((m) => ({ default: m.SharedDocumentPage }))
)

// Lazy-loaded email inbox
const EmailPage = lazy(() =>
  import('@/features/email/components/EmailPage').then((m) => ({ default: m.EmailPage }))
)

// Lazy-loaded pipeline pages
const PipelinePage = lazy(() =>
  import('@/features/pipeline/components/PipelinePage').then((m) => ({ default: m.PipelinePage }))
)
const PipelineProfilePage = lazy(() =>
  import('@/features/pipeline/components/PipelineProfilePage').then(
    (m) => ({ default: m.PipelineProfilePage })
  )
)
const ContactDetailPage = lazy(() =>
  import('@/features/pipeline/components/ContactDetailPage').then(
    (m) => ({ default: m.ContactDetailPage })
  )
)

// Lazy-loaded meetings pages
const MeetingsPage = lazy(() =>
  import('@/features/meetings/components/MeetingsPage').then((m) => ({ default: m.MeetingsPage }))
)
const MeetingDetailPage = lazy(() =>
  import('@/features/meetings/components/MeetingDetailPage').then((m) => ({ default: m.MeetingDetailPage }))
)

// Lazy-loaded tasks page
const TasksPage = lazy(() =>
  import('@/features/tasks/components/TasksPage').then((m) => ({ default: m.TasksPage }))
)

// Broker layout (not lazy — tiny, always needed)
import { BrokerLayout } from '@/features/broker/components/BrokerLayout'

// Lazy-loaded broker pages
const BrokerDashboard = lazy(() =>
  import('@/features/broker/components/BrokerDashboard').then(
    (m) => ({ default: m.BrokerDashboard })
  )
)
const BrokerProjectDetail = lazy(() =>
  import('@/features/broker/components/BrokerProjectDetail').then(
    (m) => ({ default: m.BrokerProjectDetail })
  )
)
const BrokerProjectsPage = lazy(() =>
  import('@/features/broker/pages/BrokerProjectsPage').then(
    (m) => ({ default: m.BrokerProjectsPage })
  )
)
const BrokerCarriersPage = lazy(() =>
  import('@/features/broker/pages/BrokerCarriersPage').then(
    (m) => ({ default: m.BrokerCarriersPage })
  )
)

// Lazy-loaded public pages (infrequently accessed)
const LoginPage = lazy(() =>
  import('@/pages/LoginPage').then((m) => ({ default: m.LoginPage }))
)
const LandingPage = lazy(() =>
  import('@/pages/LandingPage').then((m) => ({ default: m.LandingPage }))
)
const TermsPage = lazy(() =>
  import('@/pages/TermsPage').then((m) => ({ default: m.TermsPage }))
)
const PrivacyPage = lazy(() =>
  import('@/pages/PrivacyPage').then((m) => ({ default: m.PrivacyPage }))
)
const SpinnerPreview = lazy(() =>
  import('@/pages/SpinnerPreview').then((m) => ({ default: m.SpinnerPreview }))
)

/**
 * Guards broker routes against two distinct states:
 * - Tenant not loaded yet (activeTenant is null) → render nothing, don't redirect.
 *   This prevents a destructive redirect on page refresh before hydration completes.
 * - Tenant loaded but broker feature disabled → redirect to /.
 */
function BrokerGuard({ children }: { children: React.ReactNode }) {
  const activeTenant = useTenantStore((s) => s.activeTenant)
  const brokerEnabled = useFeatureFlag('broker')

  if (!activeTenant) return null
  if (!brokerEnabled) return <Navigate to="/" replace />
  return <>{children}</>
}

/** Root "/" — landing page for anonymous users, briefing dashboard for authenticated */
function HomePage() {
  const user = useAuthStore((s) => s.user)
  const isAnonymous = user?.is_anonymous ?? true
  if (isAnonymous) {
    return <Suspense fallback={null}><LandingPage /></Suspense>
  }
  return <Suspense fallback={null}><BriefingPageV2 /></Suspense>
}

export function AppRoutes() {
  const emailEnabled = useFeatureFlag('email')
  const tasksEnabled = useFeatureFlag('tasks')
  const pipelineEnabled = useFeatureFlag('pipeline')
  const meetingsEnabled = useFeatureFlag('meetings')

  return (
    <Routes>
      {/* Primary routes — all lazy-loaded */}
      <Route path="/" element={<HomePage />} />
      <Route path="/streams/:id" element={<Suspense fallback={null}><StreamDetailPage /></Suspense>} />
      <Route path="/chat" element={<Suspense fallback={null}><ActPage /></Suspense>} />
      {emailEnabled && <Route path="/email" element={<Suspense fallback={null}><EmailPage /></Suspense>} />}
      {!emailEnabled && <Route path="/email" element={<Navigate to="/" replace />} />}
      <Route path="/settings/*" element={<Suspense fallback={null}><SettingsPage /></Suspense>} />
      <Route path="/briefing/:runId" element={<Suspense fallback={null}><BriefingFullViewer /></Suspense>} />
      <Route path="/onboarding" element={<Suspense fallback={null}><OnboardingPage /></Suspense>} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/invite" element={<Suspense fallback={null}><InviteAcceptPage /></Suspense>} />
      <Route path="/profile" element={<Suspense fallback={null}><CompanyProfilePage /></Suspense>} />
      {pipelineEnabled && <Route path="/pipeline" element={<Suspense fallback={null}><PipelinePage /></Suspense>} />}
      {pipelineEnabled && <Route path="/pipeline/contacts/:contactId" element={<Suspense fallback={null}><ContactDetailPage /></Suspense>} />}
      {pipelineEnabled && <Route path="/pipeline/:id" element={<Suspense fallback={null}><PipelineProfilePage /></Suspense>} />}
      {!pipelineEnabled && <Route path="/pipeline" element={<Navigate to="/" replace />} />}
      {/* Legacy leads route -> pipeline */}
      <Route path="/leads" element={<Navigate to="/pipeline" replace />} />
      {meetingsEnabled && <Route path="/meetings" element={<Suspense fallback={null}><MeetingsPage /></Suspense>} />}
      {!meetingsEnabled && <Route path="/meetings" element={<Navigate to="/" replace />} />}
      {meetingsEnabled && <Route path="/meetings/:id" element={<Suspense fallback={null}><MeetingDetailPage /></Suspense>} />}
      {tasksEnabled && <Route path="/tasks" element={<Suspense fallback={null}><TasksPage /></Suspense>} />}
      {!tasksEnabled && <Route path="/tasks" element={<Navigate to="/" replace />} />}
      <Route path="/broker" element={<BrokerGuard><BrokerLayout /></BrokerGuard>}>
        <Route index element={<Suspense fallback={null}><BrokerDashboard /></Suspense>} />
        <Route path="projects/:id" element={<Suspense fallback={null}><BrokerProjectDetail /></Suspense>} />
        <Route path="projects" element={<Suspense fallback={null}><BrokerProjectsPage /></Suspense>} />
        <Route path="carriers" element={<Suspense fallback={null}><BrokerCarriersPage /></Suspense>} />
        {/* Redirects for removed routes */}
        <Route path="settings/carriers" element={<Navigate to="/broker/carriers" replace />} />
        <Route path="email" element={<Navigate to="/email" replace />} />
        <Route path="clients" element={<Navigate to="/broker/projects" replace />} />
      </Route>
      {/* Legacy relationship routes -> pipeline with filter */}
      <Route path="/relationships/prospects" element={<Navigate to="/pipeline?relationshipType=prospect" replace />} />
      <Route path="/relationships/customers" element={<Navigate to="/pipeline?relationshipType=customer" replace />} />
      <Route path="/relationships/advisors" element={<Navigate to="/pipeline?relationshipType=advisor" replace />} />
      <Route path="/relationships/investors" element={<Navigate to="/pipeline?relationshipType=investor" replace />} />
      <Route path="/relationships/:id" element={<RelationshipRedirect />} />
      {/* Legacy accounts routes -> pipeline */}
      <Route path="/accounts" element={<Navigate to="/pipeline" replace />} />
      <Route path="/accounts/:id" element={<Navigate to="/pipeline" replace />} />
      <Route path="/documents" element={<Suspense fallback={null}><DocumentLibrary /></Suspense>} />
      <Route path="/documents/:id" element={<Suspense fallback={null}><DocumentViewer /></Suspense>} />
      <Route path="/login" element={<Suspense fallback={null}><LoginPage /></Suspense>} />
      <Route path="/landing" element={<Suspense fallback={null}><LandingPage /></Suspense>} />
      <Route path="/terms" element={<Suspense fallback={null}><TermsPage /></Suspense>} />
      <Route path="/privacy" element={<Suspense fallback={null}><PrivacyPage /></Suspense>} />

      {/* Public share page -- no auth required */}
      <Route path="/d/:token" element={<Suspense fallback={null}><SharedDocumentPage /></Suspense>} />

      {/* Dev preview */}
      <Route path="/dev/spinners" element={<Suspense fallback={null}><SpinnerPreview /></Suspense>} />

      {/* Library alias */}
      <Route path="/library" element={<Navigate to="/documents" replace />} />

      {/* Redirects from old routes */}
      <Route path="/hq" element={<Navigate to="/" replace />} />
      <Route path="/prep" element={<Navigate to="/" replace />} />
      <Route path="/act" element={<Navigate to="/chat" replace />} />
      <Route path="/intel" element={<Navigate to="/" replace />} />
      <Route path="/history" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
