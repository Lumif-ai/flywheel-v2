import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router'
import { BriefingPage } from '@/features/briefing/components/BriefingPage'
import { StreamDetailPage } from '@/features/streams/components/StreamDetailPage'
import { ActPage } from '@/pages/ActPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { OnboardingPage } from '@/pages/OnboardingPage'
import { InviteAcceptPage } from '@/pages/InviteAcceptPage'

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

// Lazy-loaded public pages (infrequently accessed)
const TermsPage = lazy(() =>
  import('@/pages/TermsPage').then((m) => ({ default: m.TermsPage }))
)
const PrivacyPage = lazy(() =>
  import('@/pages/PrivacyPage').then((m) => ({ default: m.PrivacyPage }))
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
      <Route path="/onboarding" element={<OnboardingPage />} />
      <Route path="/invite" element={<InviteAcceptPage />} />
      <Route path="/profile" element={<Suspense fallback={null}><CompanyProfilePage /></Suspense>} />
      <Route path="/documents" element={<Suspense fallback={null}><DocumentLibrary /></Suspense>} />
      <Route path="/documents/:id" element={<Suspense fallback={null}><DocumentViewer /></Suspense>} />
      <Route path="/terms" element={<Suspense fallback={null}><TermsPage /></Suspense>} />
      <Route path="/privacy" element={<Suspense fallback={null}><PrivacyPage /></Suspense>} />

      {/* Public share page -- no auth required */}
      <Route path="/d/:token" element={<Suspense fallback={null}><SharedDocumentPage /></Suspense>} />

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
