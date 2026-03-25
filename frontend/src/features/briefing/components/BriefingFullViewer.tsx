import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, X, Sparkles } from 'lucide-react'
import { api } from '@/lib/api'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { useLifecycleState } from '@/features/navigation/hooks/useLifecycleState'
import { BriefingChatPanel } from './BriefingChatPanel'
import { PostBriefingSection } from './PostBriefingSection'

interface SkillRunDetail {
  id: string
  skill_name: string
  status: string
  input_text: string | null
  rendered_html: string | null
  attribution: Record<string, unknown> | null
  duration_ms: number | null
  created_at: string | null
}

/**
 * Full-screen briefing viewer for /briefing/:runId.
 *
 * Three-layer layout:
 * 1. Two-column: briefing content (left, scrollable) + always-visible chat panel (right, 350px)
 * 2. Sticky bottom bar: stat line (left) + Explore CTA (right)
 * 3. Post-briefing capability showcase (inside scroll area, after briefing content)
 */
export function BriefingFullViewer() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { state: lifecycleState } = useLifecycleState()

  const { data: run, isLoading, error } = useQuery({
    queryKey: ['briefing-run', runId],
    queryFn: () => api.get<SkillRunDetail>(`/skills/runs/${runId}`),
    enabled: !!runId,
    staleTime: 60_000,
  })

  // Determine back button behavior based on navigation context
  const backAction = useMemo(() => {
    const from = (location.state as Record<string, unknown> | null)?.from as string | undefined

    if (lifecycleState === 'S1') {
      return { label: null, icon: 'x' as const, action: () => navigate('/') }
    }
    if (from === '/documents' || from === '/library') {
      return { label: 'Library', icon: 'arrow' as const, action: () => navigate('/documents') }
    }
    return { label: 'Back', icon: 'arrow' as const, action: () => navigate(-1) }
  }, [lifecycleState, location.state, navigate])

  // Compute stat line values
  const sourceCount = useMemo(() => {
    if (!run?.attribution) return 0
    const entries = (run.attribution as Record<string, unknown>).entries
    if (Array.isArray(entries)) return entries.length
    return Object.keys(run.attribution).length
  }, [run])

  const durationSeconds = useMemo(() => {
    if (!run?.duration_ms) return null
    return Math.round(run.duration_ms / 1000)
  }, [run])

  // Scroll to top on mount
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [runId])

  if (error) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100dvh',
          background: colors.pageBg,
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <p style={{ fontSize: typography.body.size, color: colors.secondaryText }}>
            Unable to load this briefing.
          </p>
          <button
            onClick={() => navigate('/')}
            style={{
              marginTop: '16px',
              padding: '8px 20px',
              borderRadius: '999px',
              border: 'none',
              background: colors.brandCoral,
              color: '#fff',
              fontSize: typography.body.size,
              fontWeight: '500',
              cursor: 'pointer',
            }}
          >
            Go to workspace
          </button>
        </div>
      </div>
    )
  }

  return (
    <div
      style={{
        minHeight: '100dvh',
        background: colors.pageBg,
        display: 'flex',
        flexDirection: 'row',
      }}
    >
      {/* ===== Left: Main content area ===== */}
      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          height: '100dvh',
          overflow: 'hidden',
        }}
      >
        {/* --- Top Bar --- */}
        <header
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 50,
            background: 'rgba(255,255,255,0.85)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            borderBottom: `1px solid ${colors.subtleBorder}`,
            flexShrink: 0,
          }}
        >
          <div style={{
            height: '56px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 24px',
            maxWidth: '960px',
            margin: '0 auto',
            width: '100%',
            boxSizing: 'border-box' as const,
          }}>
          {/* Logo / Home link */}
          <a
            href="/"
            onClick={(e) => { e.preventDefault(); navigate('/') }}
            style={{
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <Sparkles style={{ width: 20, height: 20, color: 'var(--brand-coral)' }} />
            <span
              style={{
                fontSize: '16px',
                fontWeight: '600',
                color: colors.headingText,
                letterSpacing: '-0.01em',
              }}
            >
              Flywheel
            </span>
          </a>

          {/* Context-aware back button */}
          <button
            onClick={backAction.action}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: backAction.label ? '6px 14px' : '6px',
              borderRadius: '999px',
              border: `1px solid ${colors.subtleBorder}`,
              background: 'transparent',
              color: colors.bodyText,
              fontSize: typography.caption.size,
              fontWeight: '500',
              cursor: 'pointer',
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(0,0,0,0.04)' }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
          >
            {backAction.icon === 'x' ? (
              <X style={{ width: 18, height: 18 }} />
            ) : (
              <>
                <ArrowLeft style={{ width: 16, height: 16 }} />
                {backAction.label}
              </>
            )}
          </button>
          </div>
        </header>

        {/* --- Scrollable briefing content --- */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: `48px ${spacing.pageDesktop}`,
            paddingBottom: '80px',
          }}
        >
          <div
            style={{
              maxWidth: '960px',
              margin: '0 auto',
              width: '100%',
            }}
          >
            {isLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div
                  style={{
                    height: '32px',
                    width: '60%',
                    borderRadius: '8px',
                    background: 'rgba(0,0,0,0.06)',
                    animation: 'pulse 1.5s ease-in-out infinite',
                  }}
                />
                {Array.from({ length: 8 }).map((_, i) => (
                  <div
                    key={i}
                    style={{
                      height: '16px',
                      width: `${70 + Math.random() * 30}%`,
                      borderRadius: '6px',
                      background: 'rgba(0,0,0,0.04)',
                      animation: 'pulse 1.5s ease-in-out infinite',
                      animationDelay: `${i * 0.1}s`,
                    }}
                  />
                ))}
              </div>
            ) : run?.rendered_html ? (
              <>
                {/* Rendered briefing HTML */}
                <div
                  className="briefing-content"
                  dangerouslySetInnerHTML={{ __html: run.rendered_html }}
                  style={{
                    fontSize: typography.body.size,
                    lineHeight: typography.body.lineHeight,
                    color: colors.bodyText,
                  }}
                />

                {/* Post-briefing capability showcase */}
                <PostBriefingSection onExplore={() => navigate('/')} />
              </>
            ) : (
              <div style={{ textAlign: 'center', padding: '80px 0' }}>
                <p style={{ fontSize: typography.body.size, color: colors.secondaryText }}>
                  {run?.status === 'pending' || run?.status === 'running'
                    ? 'This briefing is still being generated...'
                    : 'No briefing content available.'}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ===== Right: Always-visible Chat Panel ===== */}
      {runId && <BriefingChatPanel runId={runId} />}

      {/* ===== Sticky Bottom Bar ===== */}
      <footer
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: '350px',
          height: '56px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          background: 'rgba(255,255,255,0.9)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          borderTop: `1px solid ${colors.subtleBorder}`,
          zIndex: 50,
        }}
      >
        {/* Left: stat line */}
        <span style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
          {sourceCount > 0 || durationSeconds
            ? `Created from ${sourceCount} source${sourceCount !== 1 ? 's' : ''}${durationSeconds ? ` in ${durationSeconds}s` : ''}`
            : 'Created by Lumif.ai'}
        </span>
        {/* Right: CTA */}
        <button
          onClick={() => navigate('/')}
          style={{
            padding: '8px 20px',
            borderRadius: '999px',
            border: 'none',
            background: 'linear-gradient(135deg, var(--brand-coral), var(--brand-gradient-end))',
            color: '#fff',
            fontSize: typography.caption.size,
            fontWeight: '500',
            cursor: 'pointer',
            transition: 'transform 0.15s, box-shadow 0.15s',
          }}
          onMouseEnter={(e) => {
            const el = e.currentTarget as HTMLElement
            el.style.transform = 'translateY(-1px)'
            el.style.boxShadow = '0 4px 12px rgba(233,77,53,0.3)'
          }}
          onMouseLeave={(e) => {
            const el = e.currentTarget as HTMLElement
            el.style.transform = 'translateY(0)'
            el.style.boxShadow = 'none'
          }}
        >
          Explore your workspace &rarr;
        </button>
      </footer>
    </div>
  )
}
