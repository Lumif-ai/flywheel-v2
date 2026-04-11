import { useState, useEffect, useRef, useCallback } from 'react'
import { getSupabase } from '@/lib/supabase'
import { CompoundingFlywheel } from '@/components/ui/CompoundingFlywheel'
import { DealTapeTheater } from '@/components/ui/DealTapeTheater'

// ---------- icons (inline SVG — aria-hidden by default) ----------

function IconCheck({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M20 6 9 17l-5-5" />
    </svg>
  )
}
function IconArrowRight({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M5 12h14" /><path d="m12 5 7 7-7 7" />
    </svg>
  )
}
function IconCopy({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect width="14" height="14" x="8" y="8" rx="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </svg>
  )
}

// ---------- analytics ----------

function trackSection(section: string) {
  try {
    if (typeof window !== 'undefined' && (window as any).gtag) {
      ;(window as any).gtag('event', 'section_view', { section })
    }
  } catch { /* noop */ }
}

function useScrollAnalytics() {
  const maxDepth = useRef(0)
  useEffect(() => {
    function onScroll() {
      const depth = Math.round(
        (window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100
      )
      if (depth > maxDepth.current) maxDepth.current = depth
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      try {
        if ((window as any).gtag) {
          ;(window as any).gtag('event', 'max_scroll_depth', { value: maxDepth.current })
        }
      } catch { /* noop */ }
    }
  }, [])
}

function useSectionObserver() {
  const observed = useRef(new Set<string>())
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting && !observed.current.has(e.target.id)) {
            observed.current.add(e.target.id)
            trackSection(e.target.id)
          }
        })
      },
      { threshold: 0.3 }
    )
    document.querySelectorAll('[data-track-section]').forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [])
}

// ---------- waitlist form ----------

function WaitlistForm({ variant = 'hero' }: { variant?: 'hero' | 'bottom' }) {
  const [email, setEmail] = useState('')
  const [state, setState] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle')

  const submit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || state === 'submitting') return
    setState('submitting')
    try {
      const sb = await getSupabase()
      if (!sb) throw new Error('no client')
      const { error } = await sb.from('waitlist').insert({ email: email.trim().toLowerCase() })
      if (error && error.code === '23505') {
        setState('success')
        return
      }
      if (error) throw error
      setState('success')
      try {
        if ((window as any).gtag) {
          ;(window as any).gtag('event', 'waitlist_signup', { variant })
        }
      } catch { /* noop */ }
    } catch {
      setState('error')
    }
  }, [email, state, variant])

  if (state === 'success') {
    return (
      <div className="flex items-center gap-2.5 text-[#16A34A] font-medium" role="status">
        <div className="size-6 rounded-full bg-[rgba(34,197,94,0.1)] flex items-center justify-center">
          <IconCheck className="size-3.5" />
        </div>
        <span>You're on the list. We'll be in touch soon.</span>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="flex flex-col sm:flex-row gap-3 w-full max-w-md relative">
      <label htmlFor={`waitlist-email-${variant}`} className="sr-only">Email address</label>
      <input
        id={`waitlist-email-${variant}`}
        type="email"
        required
        placeholder="you@company.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="flex-1 h-12 px-4 rounded-xl border border-[#E5E7EB] bg-white text-base text-[#121212] placeholder:text-[#9CA3AF] outline-none focus-visible:border-[#E94D35] focus-visible:ring-[3px] focus-visible:ring-[rgba(233,77,53,0.1)] transition-all duration-200"
      />
      <button
        type="submit"
        disabled={state === 'submitting'}
        className="h-12 px-6 rounded-xl bg-[#E94D35] text-white font-semibold text-[15px] hover:bg-[#D4412E] hover:shadow-[0_4px_12px_rgba(233,77,53,0.25)] active:translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#E94D35] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shrink-0 cursor-pointer"
      >
        {state === 'submitting' ? (
          <span className="size-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
        ) : (
          <>Join the waitlist <IconArrowRight className="size-4" /></>
        )}
      </button>
      {state === 'error' && (
        <p className="text-sm text-[#EF4444] mt-2 sm:absolute sm:top-full sm:left-0 sm:mt-2" role="alert">
          Something went wrong. Please try again.
        </p>
      )}
    </form>
  )
}

// ---------- deal tape ----------
// (DealTapeTheater imported at top)

// ---------- flywheel diagram ----------

function FlywheelDiagram() {
  return (
    <div className="flex flex-col items-center gap-6">
      <CompoundingFlywheel size={280} />
      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1.5 text-[11px] font-medium text-[#9CA3AF]">
        <span>Emails</span>
        <span>Meetings</span>
        <span>Documents</span>
        <span>Research</span>
        <span>Conversations</span>
        <span>Contacts</span>
        <span>Analytics</span>
        <span>Deals</span>
        <span>Contracts</span>
        <span>LinkedIn</span>
        <span>Tasks</span>
        <span className="text-[#E94D35] font-semibold">all become intelligence</span>
      </div>
    </div>
  )
}

// ---------- copy button ----------

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [text])

  return (
    <button
      onClick={copy}
      aria-label={copied ? 'Copied' : 'Copy install command'}
      className="absolute top-4 right-4 size-9 rounded-lg bg-white/10 flex items-center justify-center hover:bg-white/20 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#E94D35] transition-colors duration-200 cursor-pointer"
    >
      {copied ? <IconCheck className="size-4 text-[#22C55E]" /> : <IconCopy className="size-4 text-gray-400" />}
    </button>
  )
}

// ---------- social proof ----------

const TESTIMONIALS = [
  {
    quote: "I stopped thinking about outreach. Flywheel just handles it — and every message sounds like me.",
    name: 'Sarah K.',
    title: 'Founder, Series A SaaS',
  },
  {
    quote: "Our 3-person team runs GTM like a company with a sales org. The shared memory across the team is the magic.",
    name: 'James R.',
    title: 'CTO & Co-founder, B2B Startup',
  },
  {
    quote: "By month two, the meeting prep alone was worth it. By month three, our whole team couldn't imagine going back.",
    name: 'Priya M.',
    title: 'Co-founder, AI Startup',
  },
]

// ---------- main page ----------

export function LandingPage() {
  useScrollAnalytics()
  useSectionObserver()

  return (
    <div className="min-h-dvh bg-white text-[#121212] antialiased">
      {/* Skip nav (a11y) */}
      <a
        href="#main-content"
        className="absolute top-[-100%] left-4 z-[100] px-5 py-3 bg-[#E94D35] text-white rounded-lg text-sm font-semibold no-underline focus:top-4 transition-[top] duration-200"
      >
        Skip to main content
      </a>

      {/* ---------- NAV ---------- */}
      <nav className="fixed top-0 inset-x-0 z-50 bg-white/80 backdrop-blur-xl border-b border-[#E5E7EB]" aria-label="Main navigation">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <img src="/flywheel-logo.svg" alt="" aria-hidden className="size-8" />
            <span className="font-semibold text-lg tracking-tight text-[#121212]">Flywheel</span>
          </div>
          <div className="flex items-center gap-3">
            <a
              href="/login"
              className="h-9 px-4 rounded-lg border border-[#E5E7EB] bg-white text-[#121212] text-sm font-medium inline-flex items-center hover:border-[#D1D5DB] hover:shadow-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#E94D35] transition-all duration-200 no-underline"
            >
              Log in
            </a>
            <a
              href="/login"
              className="h-9 px-4 rounded-lg bg-[#E94D35] text-white text-sm font-medium inline-flex items-center gap-1.5 hover:bg-[#D4412E] hover:shadow-[0_4px_12px_rgba(233,77,53,0.25)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#E94D35] transition-all duration-200 no-underline"
            >
              Sign up
            </a>
          </div>
        </div>
      </nav>

      <main id="main-content" tabIndex={-1}>
        {/* ---------- HERO ---------- */}
        <section
          id="hero"
          data-track-section
          className="relative pt-28 pb-16 md:pt-40 md:pb-24 px-6 overflow-hidden"
        >
          {/* Radial glow */}
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_0%,rgba(233,77,53,0.06)_0%,transparent_65%)] pointer-events-none" />

          <div className="relative max-w-6xl mx-auto">
            <div className="flex flex-col lg:flex-row items-center gap-12 lg:gap-16">
              {/* Left: Text + CTA */}
              <div className="flex-1 text-center lg:text-left">
                <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[rgba(233,77,53,0.08)] text-[#E94D35] text-sm font-medium mb-8">
                  <span className="size-1.5 rounded-full bg-[#E94D35] motion-safe:animate-pulse" />
                  Now accepting early access signups
                </div>

                <h1 className="text-4xl sm:text-5xl md:text-[3.25rem] font-semibold tracking-[-0.02em] leading-[1.08] text-[#121212] mb-6">
                  Your GTM team.{' '}
                  <span className="text-[#E94D35]">Ready on day one.</span>
                </h1>

                <p className="text-lg sm:text-xl text-[#6B7280] leading-relaxed max-w-lg mb-10">
                  A full go-to-market team that shares one memory and gets smarter
                  with every conversation — from prospecting to close and beyond.
                </p>

                <div className="flex justify-center lg:justify-start">
                  <WaitlistForm variant="hero" />
                </div>
                <p className="mt-5 text-sm text-[#6B7280]">Free during early access. No credit card required.</p>
              </div>

              {/* Right: Compact Deal Tape Theater */}
              <div className="flex-shrink-0 hidden md:block">
                <DealTapeTheater compact />
              </div>
            </div>
          </div>
        </section>

        {/* Social proof bar removed — will add back with real logos/customers */}

        {/* ---------- PROBLEM ---------- */}
        <section id="problem" data-track-section className="py-24 md:py-32 px-6 bg-white">
          <div className="max-w-3xl mx-auto text-center">
            <h2 className="text-3xl sm:text-[2.25rem] font-semibold tracking-[-0.01em] leading-tight mb-6 text-[#121212]">
              You know what great GTM looks like.{' '}
              <span className="text-[#9CA3AF]">There just aren't enough of you.</span>
            </h2>
            <p className="text-lg text-[#6B7280] leading-relaxed max-w-2xl mx-auto mb-14">
              Research every prospect. Score fit. Write personalized outreach. Prep for every meeting.
              Follow up within 24 hours. Track every relationship. Your team knows the playbook — you
              just can't run it without dedicated GTM people.
            </p>
            <div className="grid sm:grid-cols-3 gap-5 text-left">
              {[
                { stat: '68%', label: "of a startup team's week goes to ops, not product" },
                { stat: '3x', label: 'more deals close when follow-up happens within 24h' },
                { stat: '11', label: 'tools the average startup juggles for GTM' },
              ].map(({ stat, label }) => (
                <div key={stat} className="p-5 rounded-xl bg-[#FFF8F6] border border-[rgba(233,77,53,0.08)]">
                  <div className="text-2xl font-bold text-[#121212] mb-1 tabular-nums">{stat}</div>
                  <div className="text-sm text-[#6B7280] leading-relaxed">{label}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---------- SHARED BRAIN / FLYWHEEL EFFECT ---------- */}
        <section id="flywheel" data-track-section className="py-24 md:py-32 px-6 bg-white">
          <div className="max-w-5xl mx-auto">
            <div className="grid md:grid-cols-2 gap-16 items-center">
              <div>
                <h2 className="text-3xl sm:text-[2.25rem] font-semibold tracking-[-0.01em] leading-tight mb-6 text-[#121212]">
                  Week 1, it's helpful.{' '}
                  <span className="text-[#E94D35]">Month 3, it's indispensable.</span>
                </h2>
                <p className="text-lg text-[#6B7280] leading-relaxed mb-8">
                  Every meeting, email, and outreach adds to your team's shared memory.
                  The more you work, the smarter they get. No data entry. No setup.
                  Just work — and watch your team compound.
                </p>
                <ul className="space-y-4" role="list">
                  {[
                    'Meeting prep includes context from outreach 6 weeks ago',
                    'Outreach drafter knows pain points from your last call',
                    'Legal reviewer references deal terms from your pipeline',
                    'Your co-founder\'s meeting makes your outreach smarter',
                  ].map((item) => (
                    <li key={item} className="flex items-start gap-3">
                      <div className="mt-1 size-5 rounded-full bg-[rgba(34,197,94,0.08)] flex items-center justify-center shrink-0">
                        <IconCheck className="size-3 text-[#22C55E]" />
                      </div>
                      <span className="text-[#6B7280] leading-relaxed">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <FlywheelDiagram />
            </div>
          </div>
        </section>

        {/* ---------- TESTIMONIALS ---------- */}
        <section id="testimonials" data-track-section className="py-24 md:py-32 px-6 bg-[#FAFAFA] border-y border-[#E5E7EB]">
          <div className="max-w-5xl mx-auto">
            <h2 className="text-3xl sm:text-[2.25rem] font-semibold tracking-[-0.01em] leading-tight mb-14 text-center text-[#121212]">
              Startup teams are already compounding.
            </h2>
            <div className="grid sm:grid-cols-3 gap-5">
              {TESTIMONIALS.map((t) => (
                <blockquote
                  key={t.name}
                  className="bg-white rounded-xl border border-[#E5E7EB] p-6 flex flex-col transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_4px_12px_rgba(0,0,0,0.06)]"
                >
                  <p className="text-[#6B7280] leading-relaxed flex-1 mb-6">"{t.quote}"</p>
                  <footer>
                    <div className="font-semibold text-sm text-[#121212]">{t.name}</div>
                    <div className="text-sm text-[#9CA3AF]">{t.title}</div>
                  </footer>
                </blockquote>
              ))}
            </div>
          </div>
        </section>

        {/* ---------- GET STARTED ---------- */}
        <section id="get-started" data-track-section className="py-24 md:py-32 px-6 bg-white">
          <div className="max-w-3xl mx-auto">
            <div className="text-center mb-14">
              <h2 className="text-3xl sm:text-[2.25rem] font-semibold tracking-[-0.01em] leading-tight mb-4 text-[#121212]">
                One install. Whole team.
              </h2>
              <p className="text-lg text-[#6B7280]">
                Get started in under 2 minutes. No configuration needed.
              </p>
            </div>

            {/* install command */}
            <div className="relative bg-[#0F1117] rounded-xl p-6 mb-10 overflow-x-auto">
              <div className="flex items-center gap-1.5 mb-4">
                <span className="size-3 rounded-full bg-[#EF4444]/60" />
                <span className="size-3 rounded-full bg-[#F59E0B]/60" />
                <span className="size-3 rounded-full bg-[#22C55E]/60" />
              </div>
              <code className="text-sm text-[#22C55E] font-mono block">
                <span className="text-[#6B7280]">$</span> pip install flywheel-ai && flywheel setup
              </code>
              <CopyButton text="pip install flywheel-ai && flywheel setup" />
            </div>

            {/* try these */}
            <h3 className="text-lg font-semibold text-[#121212] mb-5">Try these first</h3>
            <div className="space-y-3">
              {[
                {
                  prompt: '"Prep me for my meeting with Acme Corp tomorrow"',
                  result: 'Full briefing: who they are, what you discussed, what to ask.',
                },
                {
                  prompt: '"Find 20 companies like our best customer and score their fit"',
                  result: 'Prospect list scored against your ICP with decision-maker contacts.',
                },
                {
                  prompt: '"Draft a follow-up to Sarah based on our last conversation"',
                  result: 'Personalized email in your voice, referencing what you actually discussed.',
                },
              ].map(({ prompt, result }) => (
                <div key={prompt} className="rounded-xl border border-[#E5E7EB] p-4 hover:border-[rgba(233,77,53,0.15)] transition-colors duration-200">
                  <div className="font-mono text-sm text-[#121212] mb-1.5">{prompt}</div>
                  <div className="text-sm text-[#6B7280]">{result}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---------- BOTTOM CTA ---------- */}
        <section
          id="waitlist"
          data-track-section
          className="relative py-24 md:py-32 px-6 overflow-hidden"
        >
          {/* Warm gradient */}
          <div className="absolute inset-0 bg-gradient-to-b from-[#FFF8F6] to-white pointer-events-none" />
          <div className="absolute inset-0 border-t border-[#E5E7EB] pointer-events-none" />

          <div className="relative max-w-2xl mx-auto text-center">
            <h2 className="text-3xl sm:text-[2.25rem] font-semibold tracking-[-0.01em] leading-tight mb-4 text-[#121212]">
              Your team is ready. Are you?
            </h2>
            <p className="text-lg text-[#6B7280] mb-10 leading-relaxed">
              Join the waitlist for early access. Be one of the first startup teams to stop running GTM without a dedicated team.
            </p>
            <div className="flex justify-center">
              <WaitlistForm variant="bottom" />
            </div>
          </div>
        </section>
      </main>

      {/* ---------- FOOTER ---------- */}
      <footer className="border-t border-[#E5E7EB] py-10 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <img src="/flywheel-logo.svg" alt="" aria-hidden className="size-6" />
            <span className="text-sm text-[#6B7280]">Flywheel by Lumif.ai</span>
          </div>
          <div className="flex items-center gap-6 text-sm text-[#6B7280]">
            <a href="/terms" className="hover:text-[#E94D35] hover:underline underline-offset-2 transition-colors duration-200">Terms</a>
            <a href="/privacy" className="hover:text-[#E94D35] hover:underline underline-offset-2 transition-colors duration-200">Privacy</a>
          </div>
        </div>
      </footer>

      {/* Reduced motion: disable all animations */}
      <style>{`
        .sr-only {
          position: absolute;
          width: 1px;
          height: 1px;
          padding: 0;
          margin: -1px;
          overflow: hidden;
          clip: rect(0, 0, 0, 0);
          white-space: nowrap;
          border-width: 0;
        }
        .tabular-nums {
          font-variant-numeric: tabular-nums;
        }
      `}</style>
    </div>
  )
}
