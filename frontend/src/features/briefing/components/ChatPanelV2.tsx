import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { Send, Sparkles } from 'lucide-react'
import { useChatStore } from '@/features/chat/store'
import { typography, colors, spacing } from '@/lib/design-tokens'
import type { BriefingV2Response } from '@/features/briefing/types/briefing-v2'

interface ChatPanelV2Props {
  data?: BriefingV2Response
}

/**
 * Derive 2-3 contextual suggested questions from the briefing data.
 * Falls back to sensible defaults when data sections are empty.
 */
function deriveSuggestedQuestions(data?: BriefingV2Response): string[] {
  const questions: string[] = []

  if (data?.today?.meetings?.[0]?.company) {
    questions.push(`Prep me for my meeting with ${data.today.meetings[0].company}`)
  }

  if (data?.attention_items?.replies?.[0]?.contact_name) {
    questions.push(`What should I reply to ${data.attention_items.replies[0].contact_name}?`)
  }

  if (data?.tasks_today && data.tasks_today.length > 0) {
    questions.push('Help me prioritize my tasks for today')
  }

  // Pad with defaults up to 3
  const defaults = [
    'Research a company for me',
    'What can you help me with?',
    'Prep me for my next meeting',
  ]

  for (const d of defaults) {
    if (questions.length >= 3) break
    if (!questions.includes(d)) {
      questions.push(d)
    }
  }

  return questions.slice(0, 3)
}

/**
 * ChatPanelV2 — Persistent right-side chat panel with "Your team" header,
 * contextual suggested question chips, and message input.
 *
 * On submit (Enter key, Send click, or chip click), sends the message
 * via useChatStore and navigates to /chat (CHAT-04).
 */
export function ChatPanelV2({ data }: ChatPanelV2Props) {
  const [value, setValue] = useState('')
  const navigate = useNavigate()
  const sendMessage = useChatStore((s) => s.sendMessage)
  const setStreamId = useChatStore((s) => s.setStreamId)

  // Clear stream context on mount (same pattern as GlobalChatInput)
  useEffect(() => {
    setStreamId(null)
  }, [setStreamId])

  const handleSubmit = async (text: string) => {
    if (!text.trim()) return
    setValue('')
    await sendMessage(text.trim())
    navigate('/chat')
  }

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    handleSubmit(value)
  }

  const suggestedQuestions = deriveSuggestedQuestions(data)

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        padding: spacing.card,
        background: colors.cardBg,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: spacing.tight }}>
        <Sparkles
          size={18}
          style={{ color: colors.brandCoral, flexShrink: 0 }}
        />
        <h2
          style={{
            fontSize: typography.sectionTitle.size,
            fontWeight: typography.sectionTitle.weight,
            lineHeight: typography.sectionTitle.lineHeight,
            color: colors.headingText,
            margin: 0,
          }}
        >
          Your team
        </h2>
      </div>

      {/* Suggested question chips */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.tight,
          marginTop: spacing.element,
        }}
      >
        {suggestedQuestions.map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => handleSubmit(question)}
            style={{
              background: colors.brandTint,
              border: `1px solid ${colors.subtleBorder}`,
              borderRadius: '20px',
              padding: '8px 16px',
              fontSize: typography.caption.size,
              lineHeight: typography.caption.lineHeight,
              color: colors.bodyText,
              cursor: 'pointer',
              textAlign: 'left',
              transition: 'background 150ms ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = colors.brandTintWarm
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = colors.brandTint
            }}
          >
            {question}
          </button>
        ))}
      </div>

      {/* Spacer to push input to bottom */}
      <div style={{ flex: 1 }} />

      {/* Message input */}
      <form
        onSubmit={handleFormSubmit}
        style={{ position: 'relative' }}
      >
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Ask your team anything..."
          style={{
            width: '100%',
            borderRadius: '12px',
            border: `1px solid ${colors.subtleBorder}`,
            padding: '12px 44px 12px 16px',
            fontSize: typography.body.size,
            lineHeight: typography.body.lineHeight,
            color: colors.bodyText,
            background: colors.pageBg,
            outline: 'none',
            boxSizing: 'border-box',
          }}
        />
        <button
          type="submit"
          disabled={!value.trim()}
          style={{
            position: 'absolute',
            right: '8px',
            top: '50%',
            transform: 'translateY(-50%)',
            background: 'none',
            border: 'none',
            cursor: value.trim() ? 'pointer' : 'default',
            opacity: value.trim() ? 1 : 0.4,
            padding: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: colors.brandCoral,
          }}
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  )
}
