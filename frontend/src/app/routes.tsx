import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router'
import { BriefingPage } from '@/features/briefing/components/BriefingPage'
import { BriefingFullViewer } from '@/features/briefing/components/BriefingFullViewer'
import { StreamDetailPage } from '@/features/streams/components/StreamDetailPage'
import { ActPage } from '@/pages/ActPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { OnboardingPage } from '@/pages/OnboardingPage'
import { InviteAcceptPage } from '@/pages/InviteAcceptPage'
import { AuthCallback } from '@/app/AuthCallback'

// Lazy-loaded profile page
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
      {/* Primary routes */}
      <Route path="/" element={<BriefingPage />} />
      <Route path="/streams/:id" element={<StreamDetailPage />} />
      <Route path="/chat" element={<ActPage />} />
      <Route path="/email" element={<Suspense fallback={null}><EmailPage /></Suspense>} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/briefing/:runId" element={<BriefingFullViewer />} />
      <Route path="/onboarding" element={<OnboardingPage />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/invite" element={<InviteAcceptPage />} />
      <Route path="/profile" element={<Suspense fallback={null}><CompanyProfilePage /></Suspense>} />
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
