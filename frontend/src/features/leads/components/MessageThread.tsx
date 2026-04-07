import { useState } from 'react'
import { Mail, Linkedin } from 'lucide-react'
import type { LeadMessage } from '../types/lead'

const STATUS_COLORS: Record<string, string> = {
  drafted: '#d97706',
  sent: '#0284c7',
  delivered: '#2563eb',
  replied: '#16a34a',
  bounced: '#dc2626',
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function getFollowUpLabel(msg: LeadMessage): string | null {
  if (msg.status !== 'drafted') return null
  const sendAfter = msg.metadata?.send_after
  if (!sendAfter) return null
  const due = new Date(sendAfter)
  const now = new Date()
  const diffDays = Math.ceil((due.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
  if (diffDays < 0) return `Overdue ${Math.abs(diffDays)}d`
  if (diffDays === 0) return 'Due today'
  if (diffDays === 1) return 'Due tomorrow'
  return `Due in ${diffDays}d`
}

interface MessageThreadProps {
  messages: LeadMessage[]
}

export function MessageThread({ messages }: MessageThreadProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (messages.length === 0) return null

  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  return (
    <div style={{ position: 'relative' }}>
      {messages.map((msg, index) => {
        const isExpanded = expandedId === msg.id
        const color = STATUS_COLORS[msg.status] ?? '#6b7280'
        const isLast = index === messages.length - 1
        const ChannelIcon = msg.channel === 'linkedin' ? Linkedin : Mail
        const followUpLabel = getFollowUpLabel(msg)
        const isOverdue = followUpLabel?.startsWith('Overdue')

        return (
          <div key={msg.id} style={{ display: 'flex', gap: '12px', position: 'relative' }}>
            {/* Timeline node */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  width: '20px',
                  height: '20px',
                  borderRadius: '50%',
                  border: `1px solid ${color}`,
                  background: '#fff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '11px',
                  fontWeight: 600,
                  color,
                  flexShrink: 0,
                }}
              >
                {msg.step_number}
              </div>
              {!isLast && (
                <div
                  style={{
                    width: '1px',
                    flex: 1,
                    background: 'var(--subtle-border)',
                    minHeight: '8px',
                  }}
                />
              )}
            </div>

            {/* Message card */}
            <div style={{ flex: 1, paddingBottom: isLast ? 0 : '8px', minWidth: 0 }}>
              <button
                onClick={() => setExpandedId(isExpanded ? null : msg.id)}
                aria-expanded={isExpanded}
                aria-label={`Message ${msg.step_number}: ${msg.subject ?? 'No subject'}, ${msg.status}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  width: '100%',
                  padding: '4px 8px',
                  background: 'none',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(0,0,0,0.02)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'none'
                }}
              >
                <ChannelIcon
                  aria-hidden
                  style={{ width: '14px', height: '14px', color: 'var(--secondary-text)', flexShrink: 0 }}
                />
                <span
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: color,
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: '13px',
                    fontWeight: 500,
                    color: 'var(--heading-text)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    flex: 1,
                    minWidth: 0,
                  }}
                >
                  {msg.subject ?? 'No subject'}
                </span>
                {followUpLabel && (
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: 600,
                      color: isOverdue ? '#dc2626' : '#0284c7',
                      background: isOverdue ? 'rgba(220,38,38,0.08)' : 'rgba(2,132,199,0.08)',
                      borderRadius: '9999px',
                      padding: '1px 6px',
                      flexShrink: 0,
                    }}
                  >
                    {followUpLabel}
                  </span>
                )}
                <span
                  style={{
                    fontSize: '12px',
                    color: 'var(--secondary-text)',
                    flexShrink: 0,
                    marginLeft: 'auto',
                  }}
                >
                  {formatDate(msg.sent_at ?? msg.drafted_at ?? msg.created_at)}
                </span>
              </button>

              {/* Expandable body */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateRows: isExpanded ? '1fr' : '0fr',
                  transition: prefersReducedMotion ? 'none' : 'grid-template-rows 150ms ease',
                }}
              >
                <div style={{ overflow: 'hidden' }}>
                  <div
                    style={{
                      background: 'rgba(0,0,0,0.02)',
                      borderRadius: '8px',
                      padding: '8px 12px',
                      marginTop: '4px',
                    }}
                  >
                    <div
                      style={{
                        fontSize: '14px',
                        fontWeight: 600,
                        color: 'var(--heading-text)',
                        marginBottom: '4px',
                      }}
                    >
                      {msg.subject ?? 'No subject'}
                    </div>
                    {msg.body && (
                      <div
                        style={{
                          fontSize: '13px',
                          fontWeight: 400,
                          color: 'var(--body-text)',
                          whiteSpace: 'pre-wrap',
                          maxHeight: '200px',
                          overflowY: 'auto',
                          lineHeight: 1.5,
                        }}
                      >
                        {msg.body}
                      </div>
                    )}
                    <div
                      style={{
                        fontSize: '12px',
                        color: 'var(--secondary-text)',
                        marginTop: '6px',
                        display: 'flex',
                        gap: '12px',
                        flexWrap: 'wrap',
                      }}
                    >
                      {msg.drafted_at && <span>Drafted: {formatDate(msg.drafted_at)}</span>}
                      {msg.sent_at && <span>Sent: {formatDate(msg.sent_at)}</span>}
                      {msg.replied_at && <span>Replied: {formatDate(msg.replied_at)}</span>}
                      {msg.metadata?.send_after && msg.status === 'drafted' && (
                        <span style={{ color: isOverdue ? '#dc2626' : '#0284c7', fontWeight: 500 }}>
                          Send after: {formatDate(msg.metadata.send_after)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
