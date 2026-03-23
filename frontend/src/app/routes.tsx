import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router'
import { BriefingPage } from '@/features/briefing/components/BriefingPage'
import { StreamDetailPage } from '@/features/streams/components/StreamDetailPage'
import { ActPage } from '@/pages/ActPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { OnboardingPage } from '@/pages/OnboardingPage'
import { InviteAcceptPage } from '@/pages/InviteAcceptPage'

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
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/onboarding" element={<OnboardingPage />} />
      <Route path="/invite" element={<InviteAcceptPage />} />
      <Route path="/terms" element={<Suspense fallback={null}><TermsPage /></Suspense>} />
      <Route path="/privacy" element={<Suspense fallback={null}><PrivacyPage /></Suspense>} />

      {/* Redirects from old routes */}
      <Route path="/hq" element={<Navigate to="/" replace />} />
      <Route path="/prep" element={<Navigate to="/" replace />} />
      <Route path="/act" element={<Navigate to="/chat" replace />} />
      <Route path="/intel" element={<Navigate to="/" replace />} />
      <Route path="/history" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
