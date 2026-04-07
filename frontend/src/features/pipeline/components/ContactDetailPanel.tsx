import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import {
  X,
  Mail,
  Phone,
  MessageSquare,
  CheckCircle,
  SkipForward,
  Pencil,
  Loader2,
  ExternalLink,
} from 'lucide-react'
import type { ContactListItem, PipelineActivity } from '../types/pipeline'
import { useContactActivities } from '../hooks/useContactActivities'
import { useContactMutation } from '../hooks/useContactMutation'
import { useActivityMutation } from '../hooks/useActivityMutation'

/* ------------------------------------------------------------------ */
/* Status pill colors                                                  */
/* ------------------------------------------------------------------ */

const STATUS_PILL: Record<string, { bg: string; text: string }> = {
  drafted: { bg: '#F3F4F6', text: '#6B7280' },
  approved: { bg: '#FEF3C7', text: '#D97706' },
  sent: { bg: '#DBEAFE', text: '#2563EB' },
  replied: { bg: '#D1FAE5', text: '#059669' },
  bounced: { bg: '#FEE2E2', text: '#DC2626' },
  skipped: { bg: '#F3F4F6', text: '#9CA3AF' },
}

const STATUS_DOT: Record<string, string> = {
  drafted: '#9CA3AF',
  approved: '#D97706',
  sent: '#2563EB',
  replied: '#059669',
  bounced: '#DC2626',
  skipped: '#D1D5DB',
}

/* ------------------------------------------------------------------ */
/* Channel icon helper                                                 */
/* ------------------------------------------------------------------ */

function ChannelIcon({ channel }: { channel: string | null }) {
  const style = { width: '14px', height: '14px', color: '#9CA3AF' }
  switch (channel) {
    case 'email':
      return <Mail style={style} />
    case 'linkedin':
      return <MessageSquare style={style} />
    case 'phone':
      return <Phone style={style} />
    default:
      return <Mail style={style} />
  }
}

/* ------------------------------------------------------------------ */
/* Editable text field                                                  */
/* ------------------------------------------------------------------ */

function EditableField({
  label,
  value,
  onSave,
}: {
  label: string
  value: string
  onSave: (val: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setDraft(value)
    setEditing(false)
  }, [value])

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  const handleSave = useCallback(() => {
    setEditing(false)
    const trimmed = draft.trim()
    if (trimmed !== value) {
      onSave(trimmed)
    }
  }, [draft, value, onSave])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') handleSave()
      if (e.key === 'Escape') {
        setDraft(value)
        setEditing(false)
      }
    },
    [handleSave, value],
  )

  if (editing) {
    return (
      <div style={{ marginBottom: '6px' }}>
        <div style={{ fontSize: '10px', color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '2px' }}>
          {label}
        </div>
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={handleSave}
          onKeyDown={handleKeyDown}
          style={{
            width: '100%',
            padding: '4px 8px',
            fontSize: '13px',
            border: '1px solid #E94D35',
            borderRadius: '4px',
            outline: 'none',
            color: '#121212',
            background: '#FFFFFF',
          }}
        />
      </div>
    )
  }

  return (
    <div
      style={{ marginBottom: '6px', cursor: 'pointer' }}
      onClick={() => setEditing(true)}
    >
      <div style={{ fontSize: '10px', color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '2px' }}>
        {label}
      </div>
      <div className="flex items-center gap-1 group" style={{ position: 'relative' }}>
        <span style={{ fontSize: '13px', color: value ? '#121212' : '#D1D5DB', fontStyle: value ? 'normal' : 'italic' }}>
          {value || `Add ${label.toLowerCase()}`}
        </span>
        <Pencil style={{ width: '11px', height: '11px', color: '#D1D5DB', opacity: 0, transition: 'opacity 150ms' }} className="group-hover:opacity-100" />
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Step action buttons                                                 */
/* ------------------------------------------------------------------ */

function StepActions({
  activity,
  entryId,
  activityMutation,
}: {
  activity: PipelineActivity
  entryId: string
  activityMutation: ReturnType<typeof useActivityMutation>
}) {
  const status = activity.status?.toLowerCase() ?? 'drafted'
  const isPending = activityMutation.isPending

  const handleStatusChange = useCallback(
    (newStatus: string) => {
      activityMutation.mutate({
        entryId,
        activityId: activity.id,
        data: { status: newStatus },
      })
    },
    [activityMutation, entryId, activity.id],
  )

  const btnBase: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    padding: '4px 10px',
    borderRadius: '6px',
    border: '1px solid #E5E7EB',
    fontSize: '11px',
    fontWeight: 500,
    cursor: isPending ? 'not-allowed' : 'pointer',
    opacity: isPending ? 0.5 : 1,
    background: '#FFFFFF',
    transition: 'background 150ms',
  }

  return (
    <div className="flex items-center gap-2" style={{ marginTop: '6px' }}>
      {(status === 'drafted') && (
        <button
          style={{ ...btnBase, color: '#059669', borderColor: '#D1FAE5' }}
          disabled={isPending}
          onClick={() => handleStatusChange('approved')}
        >
          <CheckCircle style={{ width: '12px', height: '12px' }} />
          Approve
        </button>
      )}
      {(status === 'drafted' || status === 'approved') && (
        <button
          style={{ ...btnBase, color: '#6B7280' }}
          disabled={isPending}
          onClick={() => handleStatusChange('skipped')}
        >
          <SkipForward style={{ width: '12px', height: '12px' }} />
          Skip
        </button>
      )}
      {status === 'sent' && (
        <button
          style={{ ...btnBase, color: '#059669', borderColor: '#D1FAE5' }}
          disabled={isPending}
          onClick={() => handleStatusChange('replied')}
        >
          <MessageSquare style={{ width: '12px', height: '12px' }} />
          Mark Replied
        </button>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Step body editor                                                    */
/* ------------------------------------------------------------------ */

function StepBodyEditor({
  activity,
  entryId,
  activityMutation,
}: {
  activity: PipelineActivity
  entryId: string
  activityMutation: ReturnType<typeof useActivityMutation>
}) {
  const [editing, setEditing] = useState(false)
  const [body, setBody] = useState(activity.body_preview ?? '')
  const [subject, setSubject] = useState(activity.subject ?? '')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Reset when activity changes
  useEffect(() => {
    setBody(activity.body_preview ?? '')
    setSubject(activity.subject ?? '')
    setEditing(false)
  }, [activity.id, activity.body_preview, activity.subject])

  // Auto-focus textarea when entering edit mode
  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [editing])

  const handleSave = useCallback(() => {
    setEditing(false)
    const trimmedBody = body.trim()
    const trimmedSubject = subject.trim()
    const updates: Record<string, unknown> = {}

    if (trimmedBody !== (activity.body_preview ?? '').trim()) {
      updates.body_preview = trimmedBody
    }
    if (trimmedSubject !== (activity.subject ?? '').trim()) {
      updates.subject = trimmedSubject
    }
    if (Object.keys(updates).length > 0) {
      activityMutation.mutate({ entryId, activityId: activity.id, data: updates })
    }
  }, [body, subject, activity.body_preview, activity.subject, activity.id, entryId, activityMutation])

  const handleCancel = useCallback(() => {
    setBody(activity.body_preview ?? '')
    setSubject(activity.subject ?? '')
    setEditing(false)
  }, [activity.body_preview, activity.subject])

  const isEmail = activity.channel === 'email'
  const hasContent = !!(activity.body_preview || activity.subject)

  // Edit mode
  if (editing) {
    return (
      <div style={{ marginTop: '8px' }}>
        {isEmail && (
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Subject line..."
            style={{
              width: '100%',
              padding: '6px 10px',
              fontSize: '13px',
              fontWeight: 500,
              border: '1px solid #D1D5DB',
              borderRadius: '6px',
              outline: 'none',
              color: '#121212',
              background: '#FFFFFF',
              marginBottom: '6px',
            }}
          />
        )}
        <textarea
          ref={textareaRef}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Message body..."
          style={{
            width: '100%',
            minHeight: '120px',
            padding: '10px 12px',
            fontSize: '13px',
            lineHeight: 1.6,
            border: '1px solid #D1D5DB',
            borderRadius: '6px',
            outline: 'none',
            color: '#374151',
            background: '#FFFFFF',
            resize: 'vertical',
            fontFamily: 'inherit',
          }}
        />
        <div className="flex items-center gap-2" style={{ marginTop: '6px' }}>
          <button
            onClick={handleSave}
            style={{
              padding: '4px 12px',
              fontSize: '12px',
              fontWeight: 500,
              borderRadius: '4px',
              border: 'none',
              background: '#E94D35',
              color: '#FFFFFF',
              cursor: 'pointer',
            }}
          >
            Save
          </button>
          <button
            onClick={handleCancel}
            style={{
              padding: '4px 12px',
              fontSize: '12px',
              fontWeight: 500,
              borderRadius: '4px',
              border: '1px solid #E5E7EB',
              background: '#FFFFFF',
              color: '#6B7280',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  // Read mode — show full message body as readable text
  return (
    <div style={{ marginTop: '8px' }}>
      {isEmail && activity.subject && (
        <div style={{ fontSize: '13px', fontWeight: 500, color: '#121212', marginBottom: '4px' }}>
          {activity.subject}
        </div>
      )}
      {hasContent ? (
        <div
          style={{
            fontSize: '13px',
            lineHeight: 1.6,
            color: '#374151',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            background: '#FAFAFA',
            borderRadius: '6px',
            padding: '10px 12px',
            border: '1px solid #F3F4F6',
          }}
        >
          {activity.body_preview}
        </div>
      ) : (
        <div style={{ fontSize: '13px', color: '#D1D5DB', fontStyle: 'italic' }}>
          No message content
        </div>
      )}
      <button
        onClick={() => setEditing(true)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          marginTop: '6px',
          padding: '2px 8px',
          fontSize: '11px',
          fontWeight: 500,
          color: '#9CA3AF',
          background: 'none',
          border: '1px solid #E5E7EB',
          borderRadius: '4px',
          cursor: 'pointer',
          transition: 'color 150ms',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.color = '#6B7280' }}
        onMouseLeave={(e) => { e.currentTarget.style.color = '#9CA3AF' }}
      >
        <Pencil style={{ width: '10px', height: '10px' }} />
        Edit
      </button>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Timeline step                                                       */
/* ------------------------------------------------------------------ */

function TimelineStep({
  activity,
  entryId,
  isLast,
  activityMutation,
}: {
  activity: PipelineActivity
  entryId: string
  isLast: boolean
  activityMutation: ReturnType<typeof useActivityMutation>
}) {
  const stepNumber = (activity.metadata?.step_number as number) ?? '?'
  const variant = (activity.metadata?.variant as string) ?? null
  const variantTheme = (activity.metadata?.variant_theme as string) ?? null
  const status = activity.status?.toLowerCase() ?? 'drafted'
  const pill = STATUS_PILL[status] ?? STATUS_PILL.drafted
  const dotColor = STATUS_DOT[status] ?? STATUS_DOT.drafted

  return (
    <div style={{ position: 'relative', paddingLeft: '24px', paddingBottom: isLast ? '0' : '20px' }}>
      {/* Vertical line */}
      {!isLast && (
        <div
          style={{
            position: 'absolute',
            left: '4px',
            top: '10px',
            bottom: '0',
            width: '1px',
            background: '#E5E7EB',
          }}
        />
      )}
      {/* Dot marker */}
      <div
        style={{
          position: 'absolute',
          left: '0',
          top: '4px',
          width: '10px',
          height: '10px',
          borderRadius: '50%',
          background: dotColor,
          border: '2px solid #FFFFFF',
          boxShadow: '0 0 0 1px #E5E7EB',
        }}
      />

      {/* Step header row */}
      <div className="flex items-center gap-2" style={{ marginBottom: '4px' }}>
        <span style={{ fontSize: '12px', fontWeight: 600, color: '#374151' }}>
          Step {stepNumber}
        </span>
        <ChannelIcon channel={activity.channel} />
        {variant && (
          <span
            title={variantTheme ? `Variant ${variant}: ${variantTheme}` : `Variant ${variant}`}
            style={{
              padding: '1px 5px',
              borderRadius: '3px',
              fontSize: '10px',
              fontWeight: 500,
              background: '#F3F4F6',
              color: '#6B7280',
              letterSpacing: '0.02em',
            }}
          >
            {variant}
          </span>
        )}
        <span style={{ flex: 1 }} />
        <span
          style={{
            padding: '1px 6px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: 500,
            background: pill.bg,
            color: pill.text,
            textTransform: 'capitalize',
            flexShrink: 0,
            lineHeight: '18px',
          }}
        >
          {status}
        </span>
      </div>
      {/* Variant theme description */}
      {variantTheme && (
        <div style={{ fontSize: '11px', color: '#9CA3AF', fontStyle: 'italic', marginBottom: '4px' }}>
          {variantTheme}
        </div>
      )}

      {/* Editable body + actions */}
      <StepBodyEditor
        activity={activity}
        entryId={entryId}
        activityMutation={activityMutation}
      />
      <StepActions
        activity={activity}
        entryId={entryId}
        activityMutation={activityMutation}
      />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Contact Detail Panel                                                */
/* ------------------------------------------------------------------ */

export interface ContactDetailPanelProps {
  contact: ContactListItem
  onClose: () => void
}

export function ContactDetailPanel({ contact, onClose }: ContactDetailPanelProps) {
  const navigate = useNavigate()
  const { data: activitiesData, isLoading: activitiesLoading } = useContactActivities(
    contact.pipeline_entry_id,
    contact.id,
  )
  const contactMutation = useContactMutation()
  const activityMutation = useActivityMutation()

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  // Sort activities by step_number ascending, fallback to occurred_at
  const sortedActivities = useMemo(() => {
    if (!activitiesData?.items) return []
    return [...activitiesData.items].sort((a, b) => {
      const stepA = (a.metadata?.step_number as number) ?? Infinity
      const stepB = (b.metadata?.step_number as number) ?? Infinity
      if (stepA !== stepB) return stepA - stepB
      // fallback: occurred_at
      const dateA = a.occurred_at ?? a.created_at ?? ''
      const dateB = b.occurred_at ?? b.created_at ?? ''
      return dateA.localeCompare(dateB)
    })
  }, [activitiesData])

  // Save contact field
  const handleSaveField = useCallback(
    (field: string, value: string) => {
      contactMutation.mutate({
        entryId: contact.pipeline_entry_id,
        contactId: contact.id,
        data: { [field]: value || null },
      })
    },
    [contactMutation, contact.pipeline_entry_id, contact.id],
  )

  const initial = (contact.name?.[0] ?? '?').toUpperCase()

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        width: '480px',
        height: '100vh',
        zIndex: 40,
        background: '#FFFFFF',
        borderLeft: '1px solid #E5E7EB',
        boxShadow: '-4px 0 12px rgba(0,0,0,0.05)',
        display: 'flex',
        flexDirection: 'column',
        animation: 'contactDetailPanelSlideIn 200ms ease-out',
      }}
    >
      {/* ============================================================ */}
      {/* HEADER (PANEL-01) -- fixed, not scrollable                   */}
      {/* ============================================================ */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid #F3F4F6',
          flexShrink: 0,
        }}
      >
        <div className="flex items-start justify-between" style={{ marginBottom: '10px' }}>
          <div className="flex items-center gap-3">
            <div
              style={{
                width: '36px',
                height: '36px',
                minWidth: '36px',
                borderRadius: '50%',
                background: '#F3F4F6',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '14px',
                fontWeight: 600,
                color: '#6B7280',
              }}
            >
              {initial}
            </div>
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#121212', margin: 0, lineHeight: 1.3 }}>
                {contact.name}
              </h2>
              {(contact.title || contact.company_name) && (
                <div style={{ fontSize: '13px', color: '#6B7280', marginTop: '2px' }}>
                  {contact.title}{contact.title && contact.company_name ? ' at ' : ''}{contact.company_name}
                </div>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '4px',
              borderRadius: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            aria-label="Close panel"
          >
            <X style={{ width: '16px', height: '16px', color: '#6B7280' }} />
          </button>
        </div>

        {/* View full detail link */}
        <button
          onClick={() => navigate(`/pipeline/contacts/${contact.id}`, { state: { contact } })}
          className="flex items-center gap-1"
          style={{ fontSize: '12px', color: '#E94D35', background: 'none', border: 'none', cursor: 'pointer', padding: '0', marginBottom: '10px' }}
        >
          <ExternalLink style={{ width: '11px', height: '11px' }} />
          View full detail
        </button>

        {/* Editable contact fields */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 12px' }}>
          <EditableField
            label="Email"
            value={contact.email ?? ''}
            onSave={(v) => handleSaveField('email', v)}
          />
          <EditableField
            label="Phone"
            value={contact.phone ?? ''}
            onSave={(v) => handleSaveField('phone', v)}
          />
          <div style={{ gridColumn: '1 / -1' }}>
            <EditableField
              label="LinkedIn"
              value={contact.linkedin_url ?? ''}
              onSave={(v) => handleSaveField('linkedin_url', v)}
            />
          </div>
        </div>
      </div>

      {/* ============================================================ */}
      {/* SCROLLABLE CONTENT                                           */}
      {/* ============================================================ */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
        {/* ---------------------------------------------------------- */}
        {/* OUTREACH SEQUENCE (PANEL-02 through PANEL-05)               */}
        {/* ---------------------------------------------------------- */}
        <h3
          style={{
            fontSize: '11px',
            fontWeight: 600,
            color: '#9CA3AF',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            marginBottom: '12px',
            marginTop: '0',
          }}
        >
          Outreach Sequence
        </h3>

        {activitiesLoading ? (
          <div className="flex items-center gap-2" style={{ padding: '8px 0' }}>
            <Loader2
              style={{ width: '14px', height: '14px', color: '#D1D5DB', animation: 'spin 1s linear infinite' }}
            />
            <span style={{ fontSize: '12px', color: '#D1D5DB' }}>Loading activities...</span>
          </div>
        ) : sortedActivities.length === 0 ? (
          <p style={{ fontSize: '13px', color: '#9CA3AF', fontStyle: 'italic', margin: '0 0 16px 0' }}>
            No outreach steps yet
          </p>
        ) : (
          <div style={{ marginBottom: '16px' }}>
            {sortedActivities.map((activity, idx) => (
              <TimelineStep
                key={activity.id}
                activity={activity}
                entryId={contact.pipeline_entry_id}
                isLast={idx === sortedActivities.length - 1}
                activityMutation={activityMutation}
              />
            ))}
          </div>
        )}

      </div>

      {/* Animation keyframes */}
      <style>{`
        @keyframes contactDetailPanelSlideIn {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
