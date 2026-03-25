import { useState, useEffect, useRef, useCallback, type KeyboardEvent } from 'react'
import { Send, Lock } from 'lucide-react'
import { useChatStore } from '@/features/chat/store'
import { ChatMessage } from '@/features/chat/components/ChatMessage'
import { useLifecycleState } from '@/features/navigation/hooks/useLifecycleState'
import { getSupabase } from '@/lib/supabase'
import { colors, typography } from '@/lib/design-tokens'

const SUGGESTED_QUESTIONS = [
  'Who else from their team should I know?',
  "What's their competitive landscape?",
  'Prep talking points for my meeting',
]

/** Heuristic: does this message likely need a web search to answer? */
function needsWebSearch(text: string): boolean {
  const searchPatterns =
    /\b(who else|competitor|find|search|research|look up|what about|more about|latest|news|funding|revenue|headcount|linkedin|website)\b/i
  return searchPatterns.test(text)
}

interface BriefingChatPanelProps {
  runId: string
}

export function BriefingChatPanel({ runId }: BriefingChatPanelProps) {
  const [input, setInput] = useState('')
  const [gateMessage, setGateMessage] = useState<string | null>(null)
  const [oauthLoading, setOauthLoading] = useState<'google' | 'microsoft' | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const { state: lifecycleState } = useLifecycleState()

  const messages = useChatStore((s) => s.messages)
  const streamStatus = useChatStore((s) => s.streamState.status)
  const sendMessage = useChatStore((s) => s.sendMessage)
  const setBriefingId = useChatStore((s) => s.setBriefingId)

  const isBusy =
    streamStatus === 'thinking' ||
    streamStatus === 'streaming' ||
    streamStatus === 'running'

  // Set briefingId on mount, clear on unmount
  useEffect(() => {
    setBriefingId(runId)
    return () => {
      setBriefingId(null)
    }
  }, [runId, setBriefingId])

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, gateMessage])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleGoogleSignup = useCallback(async () => {
    setOauthLoading('google')
    try {
      localStorage.setItem('pendingAction', JSON.stringify({ type: 'chat', payload: { runId } }))
      const supabase = await getSupabase()
      if (!supabase) return
      await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
          scopes:
            'https://www.googleapis.com/auth/calendar.events.readonly https://www.googleapis.com/auth/gmail.readonly',
          queryParams: { access_type: 'offline', prompt: 'consent' },
        },
      })
    } catch (err) {
      console.error('Google OAuth error:', err)
      setOauthLoading(null)
    }
  }, [runId])

  const handleMicrosoftSignup = useCallback(async () => {
    setOauthLoading('microsoft')
    try {
      localStorage.setItem('pendingAction', JSON.stringify({ type: 'chat', payload: { runId } }))
      const supabase = await getSupabase()
      if (!supabase) return
      await supabase.auth.signInWithOAuth({
        provider: 'azure',
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
          scopes: 'Calendars.Read Mail.Read Mail.Send',
          queryParams: { prompt: 'consent' },
        },
      })
    } catch (err) {
      console.error('Microsoft OAuth error:', err)
      setOauthLoading(null)
    }
  }, [runId])

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim()
    if (!trimmed || isBusy) return

    // Smart gating: anonymous users asking web-search questions get a signup prompt
    if (lifecycleState === 'S1' && needsWebSearch(trimmed)) {
      setGateMessage(trimmed)
      setInput('')
      return
    }

    sendMessage(trimmed)
    setInput('')
    setGateMessage(null)
  }, [input, isBusy, lifecycleState, sendMessage])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  const handleSuggestion = useCallback(
    (q: string) => {
      if (isBusy) return

      // Smart gating for suggestions too
      if (lifecycleState === 'S1' && needsWebSearch(q)) {
        setGateMessage(q)
        return
      }

      sendMessage(q)
      setGateMessage(null)
    },
    [isBusy, lifecycleState, sendMessage],
  )

  return (
    <div
      style={{
        width: '350px',
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        background: 'rgba(248,248,248,1)',
        borderLeft: `1px solid ${colors.subtleBorder}`,
        height: 'calc(100dvh - 56px)',
        position: 'sticky',
        top: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '16px',
          borderBottom: `1px solid ${colors.subtleBorder}`,
          height: '56px',
          flexShrink: 0,
        }}
      >
        <img src="/flywheel-icon.svg" alt="" style={{ width: 16, height: 16 }} />
        <span
          style={{
            fontSize: typography.body.size,
            fontWeight: '600',
            color: colors.headingText,
          }}
        >
          Ask about this briefing
        </span>
      </div>

      {/* Messages area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          paddingBottom: '72px',
        }}
      >
        {messages.length === 0 && !gateMessage ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              marginTop: 'auto',
            }}
          >
            <p
              style={{
                fontSize: typography.caption.size,
                color: colors.secondaryText,
                margin: '0 0 8px 0',
              }}
            >
              Suggested questions
            </p>
            {SUGGESTED_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => handleSuggestion(q)}
                disabled={isBusy}
                style={{
                  textAlign: 'left',
                  padding: '10px 14px',
                  borderRadius: '10px',
                  border: `1px solid ${colors.subtleBorder}`,
                  background: '#fff',
                  color: colors.bodyText,
                  fontSize: typography.caption.size,
                  cursor: isBusy ? 'not-allowed' : 'pointer',
                  transition: 'background 0.15s, border-color 0.15s',
                  opacity: isBusy ? 0.5 : 1,
                }}
                onMouseEnter={(e) => {
                  if (!isBusy) {
                    const el = e.currentTarget as HTMLElement
                    el.style.background = 'rgba(233,77,53,0.05)'
                    el.style.borderColor = 'rgba(233,77,53,0.2)'
                  }
                }}
                onMouseLeave={(e) => {
                  const el = e.currentTarget as HTMLElement
                  el.style.background = '#fff'
                  el.style.borderColor = colors.subtleBorder
                }}
              >
                {q}
              </button>
            ))}
          </div>
        ) : (
          <>
            {messages.map((msg) => <ChatMessage key={msg.id} message={msg} />)}

            {/* Inline signup gate for web-search questions */}
            {gateMessage && (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                }}
              >
                {/* Show the user's attempted question */}
                <div
                  style={{
                    alignSelf: 'flex-end',
                    padding: '10px 14px',
                    borderRadius: '12px 12px 4px 12px',
                    background: 'rgba(233,77,53,0.08)',
                    color: colors.bodyText,
                    fontSize: typography.caption.size,
                    maxWidth: '85%',
                  }}
                >
                  {gateMessage}
                </div>

                {/* Bot gate response */}
                <div
                  style={{
                    alignSelf: 'flex-start',
                    padding: '14px 16px',
                    borderRadius: '12px 12px 12px 4px',
                    background: '#fff',
                    border: `1px solid ${colors.subtleBorder}`,
                    maxWidth: '95%',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Lock style={{ width: 14, height: 14, color: colors.secondaryText }} />
                    <span
                      style={{
                        fontSize: typography.caption.size,
                        color: colors.bodyText,
                        lineHeight: '1.4',
                      }}
                    >
                      I'd need to search the web to answer that. Sign in to unlock research.
                    </span>
                  </div>

                  {/* OAuth buttons */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <button
                      onClick={handleGoogleSignup}
                      disabled={oauthLoading !== null}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        padding: '8px 16px',
                        borderRadius: '8px',
                        border: `1px solid ${colors.subtleBorder}`,
                        background: '#fff',
                        cursor: oauthLoading ? 'not-allowed' : 'pointer',
                        opacity: oauthLoading && oauthLoading !== 'google' ? 0.5 : 1,
                        fontSize: typography.caption.size,
                        fontWeight: '500',
                        color: colors.headingText,
                        transition: 'border-color 0.15s',
                      }}
                      onMouseEnter={(e) => {
                        if (!oauthLoading) e.currentTarget.style.borderColor = colors.brandCoral
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = colors.subtleBorder
                      }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                      </svg>
                      {oauthLoading === 'google' ? 'Connecting...' : 'Continue with Google'}
                    </button>

                    <button
                      onClick={handleMicrosoftSignup}
                      disabled={oauthLoading !== null}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        padding: '8px 16px',
                        borderRadius: '8px',
                        border: `1px solid ${colors.subtleBorder}`,
                        background: '#fff',
                        cursor: oauthLoading ? 'not-allowed' : 'pointer',
                        opacity: oauthLoading && oauthLoading !== 'microsoft' ? 0.5 : 1,
                        fontSize: typography.caption.size,
                        fontWeight: '500',
                        color: colors.headingText,
                        transition: 'border-color 0.15s',
                      }}
                      onMouseEnter={(e) => {
                        if (!oauthLoading) e.currentTarget.style.borderColor = colors.brandCoral
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = colors.subtleBorder
                      }}
                    >
                      <svg width="14" height="14" viewBox="0 0 21 21">
                        <rect x="1" y="1" width="9" height="9" fill="#F25022" />
                        <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
                        <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
                        <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
                      </svg>
                      {oauthLoading === 'microsoft' ? 'Connecting...' : 'Continue with Microsoft'}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div
        style={{
          padding: '12px 16px',
          borderTop: `1px solid ${colors.subtleBorder}`,
          display: 'flex',
          alignItems: 'flex-end',
          gap: '8px',
          background: 'rgba(248,248,248,1)',
          flexShrink: 0,
        }}
      >
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question..."
          disabled={isBusy}
          rows={1}
          style={{
            flex: 1,
            resize: 'none',
            border: `1px solid ${colors.subtleBorder}`,
            borderRadius: '10px',
            padding: '10px 14px',
            fontSize: typography.caption.size,
            lineHeight: '1.4',
            color: colors.bodyText,
            background: '#fff',
            outline: 'none',
            fontFamily: 'inherit',
            minHeight: '40px',
            maxHeight: '120px',
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={isBusy || !input.trim()}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '36px',
            height: '36px',
            borderRadius: '10px',
            border: 'none',
            background:
              isBusy || !input.trim()
                ? 'rgba(0,0,0,0.06)'
                : 'linear-gradient(135deg, var(--brand-coral), var(--brand-gradient-end))',
            color: isBusy || !input.trim() ? colors.secondaryText : '#fff',
            cursor: isBusy || !input.trim() ? 'not-allowed' : 'pointer',
            flexShrink: 0,
            transition: 'background 0.15s',
          }}
          aria-label="Send message"
        >
          <Send style={{ width: 16, height: 16 }} />
        </button>
      </div>
    </div>
  )
}
