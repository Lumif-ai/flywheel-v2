/**
 * SignupGate -- Inline OAuth signup component that replaces the action area
 * when an anonymous user tries their second action.
 *
 * NOT a modal, NOT a redirect -- renders inline where the action area would be.
 * One OAuth consent handles identity + calendar + email scopes.
 */

import { useState } from 'react'
import { useOAuthSignIn } from '@/hooks/useOAuthSignIn'
import { BrandedCard } from '@/components/ui/branded-card'
import { colors, typography } from '@/lib/design-tokens'

interface SignupGateProps {
  /** The action the user was trying to perform -- stored in localStorage for post-OAuth resume */
  pendingAction?: { type: string; payload?: unknown }
}

export function SignupGate({ pendingAction }: SignupGateProps) {
  const [loading, setLoading] = useState<'google' | 'microsoft' | null>(null)
  const { signInWithProvider } = useOAuthSignIn()

  const handleGoogleSignup = async () => {
    setLoading('google')
    try {
      if (pendingAction) {
        localStorage.setItem('pendingAction', JSON.stringify(pendingAction))
      }
      await signInWithProvider('google')
    } catch (err) {
      console.error('Google OAuth error:', err)
      setLoading(null)
    }
  }

  const handleMicrosoftSignup = async () => {
    setLoading('microsoft')
    try {
      if (pendingAction) {
        localStorage.setItem('pendingAction', JSON.stringify(pendingAction))
      }
      await signInWithProvider('azure')
    } catch (err) {
      console.error('Microsoft OAuth error:', err)
      setLoading(null)
    }
  }

  return (
    <BrandedCard hoverable={false}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          padding: '24px 16px',
          gap: '16px',
        }}
      >
        <h3
          style={{
            fontSize: typography.sectionTitle.size,
            fontWeight: typography.sectionTitle.weight,
            lineHeight: typography.sectionTitle.lineHeight,
            color: colors.headingText,
            margin: 0,
          }}
        >
          Sign in to get briefings for all your meetings
        </h3>
        <p
          style={{
            fontSize: typography.body.size,
            color: colors.secondaryText,
            margin: 0,
            maxWidth: '400px',
          }}
        >
          Your briefing and future research will be saved
        </p>

        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', justifyContent: 'center' }}>
          {/* Google button */}
          <button
            onClick={handleGoogleSignup}
            disabled={loading !== null}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              padding: '10px 24px',
              borderRadius: '10px',
              border: `1px solid ${colors.subtleBorder}`,
              background: '#fff',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading && loading !== 'google' ? 0.5 : 1,
              fontSize: typography.body.size,
              fontWeight: '500',
              color: colors.headingText,
              transition: 'box-shadow 0.15s, border-color 0.15s',
            }}
            onMouseEnter={(e) => {
              if (!loading) e.currentTarget.style.borderColor = colors.brandCoral
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = colors.subtleBorder
            }}
          >
            {/* Google G icon */}
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
            {loading === 'google' ? 'Connecting...' : 'Continue with Google'}
          </button>

          {/* Microsoft button */}
          <button
            onClick={handleMicrosoftSignup}
            disabled={loading !== null}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              padding: '10px 24px',
              borderRadius: '10px',
              border: `1px solid ${colors.subtleBorder}`,
              background: '#fff',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading && loading !== 'microsoft' ? 0.5 : 1,
              fontSize: typography.body.size,
              fontWeight: '500',
              color: colors.headingText,
              transition: 'box-shadow 0.15s, border-color 0.15s',
            }}
            onMouseEnter={(e) => {
              if (!loading) e.currentTarget.style.borderColor = colors.brandCoral
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = colors.subtleBorder
            }}
          >
            {/* Microsoft icon */}
            <svg width="18" height="18" viewBox="0 0 21 21">
              <rect x="1" y="1" width="9" height="9" fill="#F25022" />
              <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
              <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
              <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
            </svg>
            {loading === 'microsoft' ? 'Connecting...' : 'Continue with Microsoft'}
          </button>
        </div>
      </div>
    </BrandedCard>
  )
}
