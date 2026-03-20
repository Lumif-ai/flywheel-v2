import { useState, useCallback, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router'
import { Sparkles } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'

export function SignupPrompt() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)

  const handleSignup = useCallback(async () => {
    if (!email.trim() || !email.includes('@')) return
    setStatus('sending')
    setError(null)

    try {
      await api.post('/auth/magic-link', { email: email.trim() })
      setStatus('sent')
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'Failed to send magic link')
    }
  }, [email])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault()
        handleSignup()
      }
    },
    [handleSignup],
  )

  const handleContinueAsGuest = useCallback(() => {
    navigate('/act')
  }, [navigate])

  if (status === 'sent') {
    return (
      <div className="mx-auto max-w-md space-y-4 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
          <Sparkles className="h-7 w-7 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-foreground">Check your email</h2>
        <p className="text-sm text-muted-foreground">
          We sent a magic link to <strong className="text-foreground">{email}</strong>.
          Click it to sign in and save your results.
        </p>
        <Button variant="ghost" onClick={handleContinueAsGuest} className="text-sm">
          Continue as guest for now
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md space-y-6 text-center">
      <div className="space-y-2">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
          <Sparkles className="h-7 w-7 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-foreground">Save your results</h2>
        <p className="text-sm text-muted-foreground">
          Create a free account to keep your research and unlock all skills.
        </p>
      </div>

      <div className="space-y-3">
        <Input
          type="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value)
            setError(null)
          }}
          onKeyDown={handleKeyDown}
          placeholder="you@company.com"
          className="h-12 text-center text-base"
        />
        <Button
          onClick={handleSignup}
          disabled={status === 'sending' || !email.trim()}
          size="lg"
          className="w-full"
        >
          {status === 'sending' ? 'Sending...' : 'Create free account'}
        </Button>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>

      <button
        type="button"
        onClick={handleContinueAsGuest}
        className="text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        Continue as guest
      </button>
    </div>
  )
}
