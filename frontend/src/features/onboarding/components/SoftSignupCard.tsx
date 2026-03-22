/**
 * SoftSignupCard - Non-blocking signup nudge for anonymous users.
 *
 * Appears at the top of the briefing page. Can be dismissed for 24 hours
 * via localStorage. No functionality is gated behind signup.
 */

import { useState } from 'react'
import { CheckCircle, ArrowRight, Loader2 } from 'lucide-react'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/lib/api'

const DISMISS_KEY = 'signup_card_dismissed_at'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function isSignupCardDismissed(): boolean {
  const dismissed = localStorage.getItem(DISMISS_KEY)
  if (!dismissed) return false
  const dismissedAt = new Date(dismissed).getTime()
  const twentyFourHours = 24 * 60 * 60 * 1000
  return Date.now() - dismissedAt < twentyFourHours
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SoftSignupCard() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState(false)

  const handleDismiss = () => {
    localStorage.setItem(DISMISS_KEY, new Date().toISOString())
    setDismissed(true)
  }

  const handleSave = async () => {
    if (!email.trim()) return

    setLoading(true)
    setError(null)

    try {
      // Promote the anonymous session with email via backend
      await api.post('/onboarding/promote', { email })

      // Update local auth state
      const currentUser = useAuthStore.getState().user
      if (currentUser) {
        useAuthStore.getState().setUser({
          ...currentUser,
          email,
          is_anonymous: false,
        })
      }

      setSuccess(true)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save. Please try again.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  if (dismissed) return null

  // Success state
  if (success) {
    return (
      <div className="rounded-xl border-2 border-green-200 bg-green-50 p-6">
        <div className="flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
          <div>
            <p className="font-medium text-green-900">
              Saved! Check your email to verify.
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border-2 border-primary/20 bg-primary/5 p-6 space-y-4">
      {/* Header */}
      <div>
        <h3 className="text-lg font-semibold">Save your workspace</h3>
        <p className="text-sm text-muted-foreground">
          Enter your email to keep your intelligence and get daily briefings
        </p>
      </div>

      {/* Email input + save */}
      <div className="flex items-center gap-3">
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSave()}
          placeholder="you@company.com"
          className="flex-1 rounded-lg border bg-background px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
        />
        <button
          onClick={handleSave}
          disabled={loading || !email.trim()}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            'Save'
          )}
        </button>
      </div>

      {/* Error */}
      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}

      {/* Calendar connect suggestion */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span>Connect your calendar to auto-detect meetings</span>
        <a
          href="/settings"
          className="inline-flex items-center gap-1 text-primary hover:underline"
        >
          Set up
          <ArrowRight className="w-3 h-3" />
        </a>
      </div>

      {/* Dismiss */}
      <div className="text-right">
        <button
          onClick={handleDismiss}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          Maybe later
        </button>
      </div>
    </div>
  )
}
