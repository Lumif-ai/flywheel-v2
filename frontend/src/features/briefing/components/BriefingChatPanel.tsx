import { useState, useEffect, useRef, useCallback, type KeyboardEvent } from 'react'
import { X, Send, Sparkles } from 'lucide-react'
import { useChatStore } from '@/features/chat/store'
import { ChatMessage } from '@/features/chat/components/ChatMessage'
import { colors, typography } from '@/lib/design-tokens'

const SUGGESTED_QUESTIONS = [
  'Who else from their team should I know?',
  "What's their competitive landscape?",
  'Prep talking points for my meeting',
  'What are the key risks?',
]

interface BriefingChatPanelProps {
  runId: string
  onClose: () => void
}

export function BriefingChatPanel({ runId, onClose }: BriefingChatPanelProps) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

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
  }, [messages])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim()
    if (!trimmed || isBusy) return
    sendMessage(trimmed)
    setInput('')
  }, [input, isBusy, sendMessage])

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
      sendMessage(q)
    },
    [isBusy, sendMessage],
  )

  return (
    <div
      style={{
        width: '350px',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: '#fff',
        borderLeft: `1px solid ${colors.subtleBorder}`,
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 16px',
          borderBottom: `1px solid ${colors.subtleBorder}`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles style={{ width: 16, height: 16, color: 'var(--brand-coral)' }} />
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
        <button
          onClick={onClose}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '28px',
            height: '28px',
            borderRadius: '6px',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            color: colors.secondaryText,
            transition: 'background 0.15s',
          }}
          onMouseEnter={(e) => {
            ;(e.currentTarget as HTMLElement).style.background = 'rgba(0,0,0,0.06)'
          }}
          onMouseLeave={(e) => {
            ;(e.currentTarget as HTMLElement).style.background = 'transparent'
          }}
          aria-label="Close chat panel"
        >
          <X style={{ width: 16, height: 16 }} />
        </button>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        {messages.length === 0 ? (
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
                  background: 'rgba(0,0,0,0.02)',
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
                  el.style.background = 'rgba(0,0,0,0.02)'
                  el.style.borderColor = colors.subtleBorder
                }}
              >
                {q}
              </button>
            ))}
          </div>
        ) : (
          messages.map((msg) => <ChatMessage key={msg.id} message={msg} />)
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
            background: 'transparent',
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
