import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { colors, typography } from '@/lib/design-tokens'
import type { VoiceSnapshot } from '../types/email'

interface VoiceAnnotationProps {
  snapshot: VoiceSnapshot | null | undefined
}

const COLLAPSED_FIELDS: { key: keyof VoiceSnapshot; label: string; format: (v: unknown) => string }[] = [
  { key: 'tone', label: 'Tone', format: (v) => String(v) },
  { key: 'greeting_style', label: 'Greeting', format: (v) => String(v) },
  { key: 'sign_off', label: 'Sign-off', format: (v) => String(v) },
  { key: 'avg_length', label: 'Avg. Length', format: (v) => `~${v} words` },
  { key: 'phrases', label: 'Phrases', format: (v) => {
    const arr = v as string[]
    return arr.slice(0, 2).join(', ')
  }},
]

const ALL_FIELDS: { key: keyof VoiceSnapshot; label: string }[] = [
  { key: 'tone', label: 'Tone' },
  { key: 'formality_level', label: 'Formality' },
  { key: 'greeting_style', label: 'Greeting' },
  { key: 'sign_off', label: 'Sign-off' },
  { key: 'avg_length', label: 'Avg. Length' },
  { key: 'avg_sentences', label: 'Avg. Sentences' },
  { key: 'paragraph_pattern', label: 'Paragraphs' },
  { key: 'question_style', label: 'Questions' },
  { key: 'emoji_usage', label: 'Emoji' },
  { key: 'phrases', label: 'Phrases' },
]

function formatValue(key: keyof VoiceSnapshot, value: unknown): string {
  if (value === null || value === undefined) return 'Not set'
  if (key === 'phrases') {
    const arr = value as string[]
    return arr.length > 0 ? arr.join(', ') : 'Not set'
  }
  if (key === 'avg_length') return `~${value} words`
  if (key === 'avg_sentences') return String(value)
  return String(value)
}

export function VoiceAnnotation({ snapshot }: VoiceAnnotationProps) {
  const [expanded, setExpanded] = useState(false)

  if (!snapshot) return null

  return (
    <div
      className="rounded-lg p-3"
      style={{ backgroundColor: 'rgba(0,0,0,0.02)', border: '1px solid var(--subtle-border)' }}
    >
      {/* Header toggle */}
      <button
        onClick={() => setExpanded((o) => !o)}
        className="flex items-center gap-1.5 w-full text-left transition-opacity hover:opacity-70"
      >
        {expanded ? (
          <ChevronDown className="size-3 shrink-0" style={{ color: colors.secondaryText }} />
        ) : (
          <ChevronRight className="size-3 shrink-0" style={{ color: colors.secondaryText }} />
        )}
        <span
          style={{
            fontSize: typography.caption.size,
            fontWeight: '600',
            color: colors.secondaryText,
            letterSpacing: '0.02em',
          }}
        >
          Voice applied
        </span>
      </button>

      {/* Collapsed: 5 key fields as badges */}
      {!expanded && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {COLLAPSED_FIELDS.map(({ key, label, format }) => {
            const val = snapshot[key]
            if (val === null || val === undefined) return null
            if (key === 'phrases' && (val as string[]).length === 0) return null
            return (
              <span
                key={key}
                className="inline-flex items-center rounded-full px-2 py-0.5 text-xs"
                style={{
                  backgroundColor: 'rgba(233,77,53,0.06)',
                  color: colors.secondaryText,
                }}
                title={label}
              >
                {format(val)}
              </span>
            )
          })}
        </div>
      )}

      {/* Expanded: all 10 fields in 2-column grid */}
      {expanded && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 mt-2.5">
          {ALL_FIELDS.map(({ key, label }) => {
            const val = snapshot[key]
            return (
              <div key={key} className="min-w-0">
                <span
                  className="block text-xs font-medium"
                  style={{ color: colors.secondaryText }}
                >
                  {label}
                </span>
                <span
                  className="block text-xs truncate"
                  style={{
                    color: val === null || val === undefined ? 'rgba(107,114,128,0.6)' : colors.bodyText,
                  }}
                  title={formatValue(key, val)}
                >
                  {formatValue(key, val)}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
