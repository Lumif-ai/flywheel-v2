import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { RefreshCw, Send, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { formatDistanceToNow } from 'date-fns'
import { useCreateNote } from '../hooks/useCreateNote'
import { useAsk } from '../hooks/useAsk'
import { useSynthesize } from '../hooks/useSynthesize'
import { spacing, typography, colors } from '@/lib/design-tokens'
import type { AskResponse } from '../types/relationships'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PanelMode = 'idle' | 'asking' | 'saving_note' | 'synthesizing'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AskPanelProps {
  accountId: string
  aiSummary: string | null
  aiSummaryUpdatedAt: string | null
}

// ---------------------------------------------------------------------------
// Intent heuristic — ? at end means ask, everything else is a note
// ---------------------------------------------------------------------------

const isQuestion = (text: string) => text.trim().endsWith('?')

// ---------------------------------------------------------------------------
// Source citation card
// ---------------------------------------------------------------------------

function SourceCard({ source, content, date }: { source: string; content: string; date: string }) {
  const snippet = content.length > 100 ? content.slice(0, 100) + '…' : content
  let dateDisplay = date
  try {
    dateDisplay = formatDistanceToNow(new Date(date), { addSuffix: true })
  } catch {
    // fallback to raw date
  }

  return (
    <div
      style={{
        background: 'rgba(0,0,0,0.03)',
        borderLeft: `3px solid ${colors.subtleBorder}`,
        borderRadius: '6px',
        padding: '8px 10px',
        marginTop: '6px',
      }}
    >
      <p style={{ fontSize: typography.caption.size, fontWeight: '600', color: colors.headingText, marginBottom: '2px' }}>
        {source}
      </p>
      <p style={{ fontSize: typography.caption.size, color: colors.bodyText, lineHeight: typography.caption.lineHeight }}>
        {snippet}
      </p>
      <p style={{ fontSize: '12px', color: colors.secondaryText, marginTop: '2px' }}>
        {dateDisplay}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// AskPanel
// ---------------------------------------------------------------------------

export function AskPanel({ accountId, aiSummary, aiSummaryUpdatedAt }: AskPanelProps) {
  const [mode, setMode] = useState<PanelMode>('idle')
  const [inputValue, setInputValue] = useState('')
  const [lastAnswer, setLastAnswer] = useState<AskResponse | null>(null)

  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const noteMutation = useCreateNote()
  const askMutation = useAsk()
  const synthesizeMutation = useSynthesize()

  // Auto-resize textarea up to 6 rows
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const lineHeight = 20
    const maxHeight = lineHeight * 6 + 16 // 6 rows + padding
    el.style.height = Math.min(el.scrollHeight, maxHeight) + 'px'
  }, [inputValue])

  function handleSubmit() {
    const trimmed = inputValue.trim()
    if (!trimmed) return

    setInputValue('')

    if (isQuestion(trimmed)) {
      setMode('asking')
      askMutation.mutate(
        { id: accountId, question: trimmed },
        {
          onSuccess: (data) => {
            setLastAnswer(data)
            setMode('idle')
          },
          onError: () => {
            setMode('idle')
            toast.error('Failed to get answer. Please try again.')
          },
        },
      )
    } else {
      setMode('saving_note')
      setLastAnswer(null)
      noteMutation.mutate(
        { id: accountId, content: trimmed },
        {
          onSuccess: () => {
            setMode('idle')
            toast.success('Note saved')
          },
          onError: () => {
            setMode('idle')
            toast.error('Failed to save note. Please try again.')
          },
        },
      )
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (mode === 'idle') {
        handleSubmit()
      }
    }
  }

  function handleSynthesizeClick() {
    if (synthesizeMutation.isPending) return
    synthesizeMutation.mutate(accountId)
  }

  const isSynthesizing = synthesizeMutation.isPending
  const isSubmitDisabled = mode !== 'idle' || inputValue.trim() === ''

  // Format updated-at time
  let updatedDisplay: string | null = null
  if (aiSummaryUpdatedAt) {
    try {
      updatedDisplay = 'Updated ' + formatDistanceToNow(new Date(aiSummaryUpdatedAt), { addSuffix: true })
    } catch {
      updatedDisplay = null
    }
  }

  return (
    <div
      className="w-full lg:border-l"
      style={{
        borderColor: colors.subtleBorder,
        background: colors.cardBg,
        borderRadius: '12px',
        padding: spacing.card,
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}
    >
      {/* Section header */}
      <div className="flex items-center justify-between mb-4">
        <h2
          style={{
            fontSize: typography.sectionTitle.size,
            fontWeight: typography.sectionTitle.weight,
            color: colors.headingText,
          }}
        >
          AI Context
        </h2>
        <button
          onClick={handleSynthesizeClick}
          disabled={isSynthesizing}
          title="Refresh AI summary"
          style={{
            background: 'none',
            border: 'none',
            cursor: isSynthesizing ? 'default' : 'pointer',
            padding: '4px',
            borderRadius: '6px',
            color: colors.secondaryText,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'color 150ms ease',
          }}
          className="hover:text-foreground"
        >
          <RefreshCw
            className={isSynthesizing ? 'animate-spin' : ''}
            style={{ width: '16px', height: '16px' }}
          />
        </button>
      </div>

      {/* AI Summary section */}
      <div className="mb-4">
        {aiSummary ? (
          <div
            style={{
              background: colors.brandTint,
              borderRadius: '8px',
              padding: '12px',
            }}
          >
            <p
              style={{
                fontSize: typography.body.size,
                lineHeight: typography.body.lineHeight,
                color: colors.bodyText,
              }}
            >
              {aiSummary}
            </p>
            {updatedDisplay && (
              <p
                style={{
                  fontSize: typography.caption.size,
                  color: colors.secondaryText,
                  marginTop: '8px',
                }}
              >
                {updatedDisplay}
              </p>
            )}
          </div>
        ) : (
          <p
            style={{
              fontSize: typography.body.size,
              color: colors.secondaryText,
              fontStyle: 'italic',
              lineHeight: typography.body.lineHeight,
            }}
          >
            No AI summary yet. Click the refresh icon to generate one, or add notes to build context.
          </p>
        )}
      </div>

      {/* Last Q&A answer section */}
      {lastAnswer && (
        <div
          style={{
            border: `1px solid ${colors.subtleBorder}`,
            borderRadius: '8px',
            padding: '12px',
            marginBottom: '16px',
          }}
        >
          {/* Insufficient context warning */}
          {lastAnswer.insufficient_context && (
            <p
              style={{
                fontSize: typography.caption.size,
                color: colors.secondaryText,
                marginBottom: '8px',
                fontStyle: 'italic',
              }}
            >
              Limited context available — answer may be incomplete
            </p>
          )}

          {/* Answer text */}
          <p
            style={{
              fontSize: typography.body.size,
              lineHeight: typography.body.lineHeight,
              color: colors.bodyText,
            }}
          >
            {lastAnswer.answer}
          </p>

          {/* Source citations */}
          {lastAnswer.sources.length > 0 && (
            <div style={{ marginTop: '10px' }}>
              {lastAnswer.sources.map((src, idx) => (
                <SourceCard
                  key={idx}
                  source={src.source}
                  content={src.content}
                  date={src.date}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Input area */}
      <div>
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <textarea
              ref={textareaRef}
              rows={2}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={mode !== 'idle'}
              placeholder="Add a note or ask a question..."
              style={{
                width: '100%',
                resize: 'none',
                overflow: 'hidden',
                fontSize: typography.body.size,
                lineHeight: '1.5',
                color: colors.bodyText,
                background: 'var(--input)',
                border: `1px solid ${colors.subtleBorder}`,
                borderRadius: '8px',
                padding: '8px 10px',
                outline: 'none',
                fontFamily: 'inherit',
                transition: 'border-color 150ms ease',
              }}
              className="focus:border-[var(--brand-coral)] placeholder:text-muted-foreground"
            />
          </div>

          <button
            onClick={handleSubmit}
            disabled={isSubmitDisabled}
            style={{
              flexShrink: 0,
              width: '36px',
              height: '36px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: isSubmitDisabled ? 'var(--muted)' : colors.brandCoral,
              border: 'none',
              borderRadius: '8px',
              cursor: isSubmitDisabled ? 'default' : 'pointer',
              color: isSubmitDisabled ? colors.secondaryText : 'white',
              transition: 'background 150ms ease',
            }}
          >
            {mode === 'asking' ? (
              <Loader2 style={{ width: '16px', height: '16px' }} className="animate-spin" />
            ) : (
              <Send style={{ width: '15px', height: '15px' }} />
            )}
          </button>
        </div>

        {/* Hint + saving state */}
        <div
          className="flex items-center justify-between mt-1"
          style={{ minHeight: '18px' }}
        >
          <p style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
            End with ? to ask AI, otherwise saves as a note
          </p>
          {mode === 'saving_note' && (
            <p style={{ fontSize: typography.caption.size, color: colors.secondaryText }}>
              Saving...
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
