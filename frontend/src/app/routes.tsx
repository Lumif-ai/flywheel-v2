import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router'
import { AuthCallback } from '@/app/AuthCallback'

// All page components lazy-loaded — keeps main bundle lean
const BriefingPage = lazy(() =>
  import('@/features/briefing/components/BriefingPage').then((m) => ({ default: m.BriefingPage }))
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

// Lazy-loaded document pages
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

// Lazy-loaded accounts pages
const AccountsPage = lazy(() =>
  import('@/features/accounts/components/AccountsPage').then((m) => ({ default: m.AccountsPage }))
)
const AccountDetailPage = lazy(() =>
  import('@/features/accounts/components/AccountDetailPage').then((m) => ({ default: m.AccountDetailPage }))
)

// Lazy-loaded pipeline page
const PipelinePage = lazy(() =>
  import('@/features/pipeline/components/PipelinePage').then((m) => ({ default: m.PipelinePage }))
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

// Lazy-loaded relationship pages
const RelationshipListPage = lazy(() =>
  import('@/features/relationships/components/RelationshipListPage').then((m) => ({ default: m.RelationshipListPage }))
)
const RelationshipDetail = lazy(() =>
  import('@/features/relationships/components/RelationshipDetail').then((m) => ({ default: m.RelationshipDetail }))
)

// Lazy-loaded public pages (infrequently accessed)
const TermsPage = lazy(() =>
  import('@/pages/TermsPage').then((m) => ({ default: m.TermsPage }))
)
const PrivacyPage = lazy(() =>
  import('@/pages/PrivacyPage').then((m) => ({ default: m.PrivacyPage }))
)
const SpinnerPreview = lazy(() =>
  import('@/pages/SpinnerPreview').then((m) => ({ default: m.SpinnerPreview }))
)

export function AppRoutes() {
  return (
    <Routes>
      {/* Primary routes — all lazy-loaded */}
      <Route path="/" element={<Suspense fallback={null}><BriefingPage /></Suspense>} />
      <Route path="/streams/:id" element={<Suspense fallback={null}><StreamDetailPage /></Suspense>} />
      <Route path="/chat" element={<Suspense fallback={null}><ActPage /></Suspense>} />
      <Route path="/email" element={<Suspense fallback={null}><EmailPage /></Suspense>} />
      <Route path="/settings" element={<Suspense fallback={null}><SettingsPage /></Suspense>} />
      <Route path="/briefing/:runId" element={<Suspense fallback={null}><BriefingFullViewer /></Suspense>} />
      <Route path="/onboarding" element={<Suspense fallback={null}><OnboardingPage /></Suspense>} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/invite" element={<Suspense fallback={null}><InviteAcceptPage /></Suspense>} />
      <Route path="/profile" element={<Suspense fallback={null}><CompanyProfilePage /></Suspense>} />
      <Route path="/pipeline" element={<Suspense fallback={null}><PipelinePage /></Suspense>} />
      <Route path="/meetings" element={<Suspense fallback={null}><MeetingsPage /></Suspense>} />
      <Route path="/meetings/:id" element={<Suspense fallback={null}><MeetingDetailPage /></Suspense>} />
      <Route path="/tasks" element={<Suspense fallback={null}><TasksPage /></Suspense>} />
      <Route path="/relationships/prospects" element={<Suspense fallback={null}><RelationshipListPage type="prospect" /></Suspense>} />
      <Route path="/relationships/customers" element={<Suspense fallback={null}><RelationshipListPage type="customer" /></Suspense>} />
      <Route path="/relationships/advisors" element={<Suspense fallback={null}><RelationshipListPage type="advisor" /></Suspense>} />
      <Route path="/relationships/investors" element={<Suspense fallback={null}><RelationshipListPage type="investor" /></Suspense>} />
      <Route path="/relationships/:id" element={<Suspense fallback={null}><RelationshipDetail /></Suspense>} />
      <Route path="/accounts" element={<Suspense fallback={null}><AccountsPage /></Suspense>} />
      <Route path="/accounts/:id" element={<Suspense fallback={null}><AccountDetailPage /></Suspense>} />
      <Route path="/documents" element={<Suspense fallback={null}><DocumentLibrary /></Suspense>} />
      <Route path="/documents/:id" element={<Suspense fallback={null}><DocumentViewer /></Suspense>} />
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
