import { Routes, Route } from 'react-router'
import { HQPage } from '@/pages/HQPage'
import { PrepPage } from '@/pages/PrepPage'
import { ActPage } from '@/pages/ActPage'
import { IntelPage } from '@/pages/IntelPage'
import { HistoryPage } from '@/pages/HistoryPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { OnboardingPage } from '@/pages/OnboardingPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HQPage />} />
      <Route path="/prep" element={<PrepPage />} />
      <Route path="/act" element={<ActPage />} />
      <Route path="/intel" element={<IntelPage />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/onboarding" element={<OnboardingPage />} />
    </Routes>
  )
}
