import { getSupabase } from '@/lib/supabase'

export function LoginPage() {
  const handleGoogleLogin = async () => {
    const supabase = await getSupabase()
    if (!supabase) return
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    })
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-6 p-8">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-semibold">Sign in to Flywheel</h1>
          <p className="text-sm text-muted-foreground">Continue with your Google account</p>
        </div>
        <button
          onClick={handleGoogleLogin}
          className="w-full py-3 px-4 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
        >
          Continue with Google
        </button>
      </div>
    </div>
  )
}
