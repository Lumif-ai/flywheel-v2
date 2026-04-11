import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router'
import {
  ArrowLeft,
  Mail,
  Phone,
  MessageSquare,
  CheckCircle,
  SkipForward,
  Pencil,
  Loader2,
  Linkedin,
} from 'lucide-react'
import type { ContactListItem, PipelineActivity } from '../types/pipeline'
import { useContactActivities } from '../hooks/useContactActivities'
import { useContactMutation } from '../hooks/useContactMutation'
import { useActivityMutation } from '../hooks/useActivityMutation'

/* ------------------------------------------------------------------ */
/* Status colors                                                       */
/* ------------------------------------------------------------------ */

const STATUS_PILL: Record<string, { bg: string; text: string }> = {
  drafted: { bg: '#F3F4F6', text: '#6B7280' },
  approved: { bg: '#FEF3C7', text: '#D97706' },
  sent: { bg: '#DBEAFE', text: '#2563EB' },
  replied: { bg: '#D1FAE5', text: '#059669' },
  bounced: { bg: '#FEE2E2', text: '#DC2626' },
  skipped: { bg: '#F3F4F6', text: '#9CA3AF' },
}

/* ------------------------------------------------------------------ */
/* Channel icon helper                                                 */
/* ------------------------------------------------------------------ */

function ChannelIcon({ channel }: { channel: string | null }) {
  const style = { width: '16px', height: '16px', color: '#6B7280' }
  switch (channel) {
    case 'email':
      return <Mail style={style} />
    case 'linkedin':
      return <Linkedin style={style} />
    case 'phone':
      return <Phone style={style} />
    default:
      return <Mail style={style} />
  }
}

/* ------------------------------------------------------------------ */
/* Editable field                                                      */
/* ------------------------------------------------------------------ */

function EditableField({
  label,
  value,
  onSave,
  icon,
}: {
  label: string
  value: string
  onSave: (val: string) => void
  icon?: React.ReactNode
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
    if (trimmed !== value) onSave(trimmed)
  }, [draft, value, onSave])

  if (editing) {
    return (
      <div className="flex items-center gap-3 py-2">
        {icon && <span style={{ color: '#9CA3AF', flexShrink: 0 }}>{icon}</span>}
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '11px', color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '2px' }}>{label}</div>
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={handleSave}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSave()
              if (e.key === 'Escape') { setDraft(value); setEditing(false) }
            }}
            style={{
              width: '100%',
              padding: '4px 8px',
              fontSize: '14px',
              border: '1px solid #E94D35',
              borderRadius: '4px',
              outline: 'none',
              color: '#121212',
            }}
          />
        </div>
      </div>
    )
  }

  return (
    <div
      className="flex items-center gap-3 py-2 group cursor-pointer"
      onClick={() => setEditing(true)}
    >
      {icon && <span style={{ color: '#9CA3AF', flexShrink: 0 }}>{icon}</span>}
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: '11px', color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '2px' }}>{label}</div>
        <div className="flex items-center gap-1">
          <span style={{ fontSize: '14px', color: value ? '#121212' : '#D1D5DB', fontStyle: value ? 'normal' : 'italic' }}>
            {value || `Add ${label.toLowerCase()}`}
          </span>
          <Pencil style={{ width: '11px', height: '11px', color: '#D1D5DB', opacity: 0, transition: 'opacity 150ms' }} className="group-hover:opacity-100" />
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Step body viewer/editor                                             */
/* ------------------------------------------------------------------ */

function StepBody({
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

  useEffect(() => {
    setBody(activity.body_preview ?? '')
    setSubject(activity.subject ?? '')
    setEditing(false)
  }, [activity.id, activity.body_preview, activity.subject])

  useEffect(() => {
    if (editing && textareaRef.current) textareaRef.current.focus()
  }, [editing])

  const handleSave = useCallback(() => {
    setEditing(false)
    const updates: Record<string, unknown> = {}
    if (body.trim() !== (activity.body_preview ?? '').trim()) updates.body_preview = body.trim()
    if (subject.trim() !== (activity.subject ?? '').trim()) updates.subject = subject.trim()
    if (Object.keys(updates).length > 0) {
      activityMutation.mutate({ entryId, activityId: activity.id, data: updates })
    }
  }, [body, subject, activity, entryId, activityMutation])

  const isEmail = activity.channel === 'email'

  if (editing) {
    return (
      <div style={{ marginTop: '8px' }}>
        {isEmail && (
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Subject line..."
            style={{ width: '100%', padding: '8px 12px', fontSize: '14px', fontWeight: 500, border: '1px solid #D1D5DB', borderRadius: '6px', outline: 'none', color: '#121212', marginBottom: '8px' }}
          />
        )}
        <textarea
          ref={textareaRef}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Message body..."
          style={{ width: '100%', minHeight: '200px', padding: '12px 14px', fontSize: '14px', lineHeight: 1.7, border: '1px solid #D1D5DB', borderRadius: '6px', outline: 'none', color: '#374151', resize: 'vertical', fontFamily: 'inherit' }}
        />
        <div className="flex items-center gap-2" style={{ marginTop: '8px' }}>
          <button onClick={handleSave} style={{ padding: '6px 16px', fontSize: '13px', fontWeight: 500, borderRadius: '6px', border: 'none', background: '#E94D35', color: '#FFF', cursor: 'pointer' }}>Save</button>
          <button onClick={() => { setBody(activity.body_preview ?? ''); setSubject(activity.subject ?? ''); setEditing(false) }} style={{ padding: '6px 16px', fontSize: '13px', fontWeight: 500, borderRadius: '6px', border: '1px solid #E5E7EB', background: '#FFF', color: '#6B7280', cursor: 'pointer' }}>Cancel</button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ marginTop: '8px' }}>
      {isEmail && activity.subject && (
        <div style={{ fontSize: '14px', fontWeight: 600, color: '#121212', marginBottom: '6px' }}>
          {activity.subject}
        </div>
      )}
      {activity.body_preview ? (
        <div style={{ fontSize: '14px', lineHeight: 1.7, color: '#374151', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {activity.body_preview}
        </div>
      ) : (
        <div style={{ fontSize: '14px', color: '#D1D5DB', fontStyle: 'italic' }}>No message content</div>
      )}
      <button
        onClick={() => setEditing(true)}
        style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', marginTop: '8px', padding: '4px 10px', fontSize: '12px', fontWeight: 500, color: '#9CA3AF', background: 'none', border: '1px solid #E5E7EB', borderRadius: '4px', cursor: 'pointer' }}
      >
        <Pencil style={{ width: '11px', height: '11px' }} />
        Edit
      </button>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Step actions                                                        */
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

  const change = useCallback(
    (s: string) => activityMutation.mutate({ entryId, activityId: activity.id, data: { status: s } }),
    [activityMutation, entryId, activity.id],
  )

  const btn: React.CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: '5px', padding: '6px 14px', borderRadius: '6px',
    border: '1px solid #E5E7EB', fontSize: '12px', fontWeight: 500, cursor: isPending ? 'not-allowed' : 'pointer',
    opacity: isPending ? 0.5 : 1, background: '#FFF', transition: 'background 150ms',
  }

  return (
    <div className="flex items-center gap-2" style={{ marginTop: '10px' }}>
      {status === 'drafted' && (
        <button style={{ ...btn, color: '#059669', borderColor: '#D1FAE5' }} disabled={isPending} onClick={() => change('approved')}>
          <CheckCircle style={{ width: '14px', height: '14px' }} /> Approve
        </button>
      )}
      {(status === 'drafted' || status === 'approved') && (
        <button style={{ ...btn, color: '#6B7280' }} disabled={isPending} onClick={() => change('skipped')}>
          <SkipForward style={{ width: '14px', height: '14px' }} /> Skip
        </button>
      )}
      {status === 'sent' && (
        <button style={{ ...btn, color: '#059669', borderColor: '#D1FAE5' }} disabled={isPending} onClick={() => change('replied')}>
          <MessageSquare style={{ width: '14px', height: '14px' }} /> Mark Replied
        </button>
      )}
    </div>
  )
}

/* ================================================================== */
/* CONTACT DETAIL PAGE                                                 */
/* ================================================================== */

export function ContactDetailPage() {
  const { contactId } = useParams<{ contactId: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  // Contact data passed via navigation state (from grid row click)
  const contact = (location.state as { contact?: ContactListItem })?.contact ?? null

  const { data: activitiesData, isLoading } = useContactActivities(
    contact?.pipeline_entry_id ?? null,
    contactId ?? null,
  )
  const contactMutation = useContactMutation()
  const activityMutation = useActivityMutation()

  const sortedActivities = useMemo(() => {
    if (!activitiesData?.items) return []
    return [...activitiesData.items].sort((a, b) => {
      const stepA = (a.metadata?.step_number as number) ?? Infinity
      const stepB = (b.metadata?.step_number as number) ?? Infinity
      if (stepA !== stepB) return stepA - stepB
      return (a.occurred_at ?? '').localeCompare(b.occurred_at ?? '')
    })
  }, [activitiesData])

  const handleSaveField = useCallback(
    (field: string, value: string) => {
      if (!contact) return
      contactMutation.mutate({ entryId: contact.pipeline_entry_id, contactId: contact.id, data: { [field]: value || null } })
    },
    [contactMutation, contact],
  )

  if (!contact) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <p style={{ color: '#6B7280', fontSize: '14px' }}>Contact not found. Go back to the pipeline.</p>
        <button
          onClick={() => navigate('/pipeline')}
          style={{ marginTop: '12px', padding: '8px 20px', fontSize: '13px', fontWeight: 500, borderRadius: '6px', border: '1px solid #E5E7EB', background: '#FFF', cursor: 'pointer', color: '#374151' }}
        >
          Back to Pipeline
        </button>
      </div>
    )
  }

  const initial = (contact.name?.[0] ?? '?').toUpperCase()

  // Group activities by channel for multi-channel display
  const activitiesByChannel = useMemo(() => {
    const groups: Record<string, PipelineActivity[]> = {}
    for (const act of sortedActivities) {
      const ch = act.channel ?? 'other'
      ;(groups[ch] ??= []).push(act)
    }
    return groups
  }, [sortedActivities])

  const channelLabels: Record<string, string> = { email: 'Email Outreach', linkedin: 'LinkedIn Outreach', phone: 'Phone Outreach' }

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', padding: '24px 32px' }}>
      {/* Back button */}
      <button
        onClick={() => navigate('/pipeline')}
        className="flex items-center gap-1.5"
        style={{ fontSize: '13px', color: '#6B7280', background: 'none', border: 'none', cursor: 'pointer', padding: '4px 0', marginBottom: '20px' }}
      >
        <ArrowLeft style={{ width: '14px', height: '14px' }} />
        Back to Pipeline
      </button>

      {/* Contact header */}
      <div className="flex items-start gap-4" style={{ marginBottom: '28px' }}>
        <div
          style={{
            width: '52px', height: '52px', minWidth: '52px', borderRadius: '50%',
            background: '#F3F4F6', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '20px', fontWeight: 600, color: '#6B7280',
          }}
        >
          {initial}
        </div>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: '24px', fontWeight: 600, color: '#121212', margin: 0, lineHeight: 1.3 }}>
            {contact.name}
          </h1>
          {(contact.title || contact.company_name) && (
            <div style={{ fontSize: '15px', color: '#6B7280', marginTop: '4px' }}>
              {contact.title}{contact.title && contact.company_name ? ' at ' : ''}{contact.company_name}
            </div>
          )}
        </div>
      </div>

      {/* Contact info grid */}
      <div
        style={{
          background: '#FAFAFA', borderRadius: '8px', border: '1px solid #F3F4F6',
          padding: '4px 16px', marginBottom: '32px',
        }}
      >
        <EditableField label="Email" value={contact.email ?? ''} onSave={(v) => handleSaveField('email', v)} icon={<Mail style={{ width: '16px', height: '16px' }} />} />
        <div style={{ borderTop: '1px solid #F3F4F6' }} />
        <EditableField label="Phone" value={contact.phone ?? ''} onSave={(v) => handleSaveField('phone', v)} icon={<Phone style={{ width: '16px', height: '16px' }} />} />
        <div style={{ borderTop: '1px solid #F3F4F6' }} />
        <EditableField label="LinkedIn" value={contact.linkedin_url ?? ''} onSave={(v) => handleSaveField('linkedin_url', v)} icon={<Linkedin style={{ width: '16px', height: '16px' }} />} />
      </div>

      {/* Outreach sequences — grouped by channel */}
      {isLoading ? (
        <div className="flex items-center gap-2" style={{ padding: '12px 0' }}>
          <Loader2 style={{ width: '16px', height: '16px', color: '#D1D5DB', animation: 'spin 1s linear infinite' }} />
          <span style={{ fontSize: '14px', color: '#9CA3AF' }}>Loading outreach...</span>
        </div>
      ) : sortedActivities.length === 0 ? (
        <p style={{ fontSize: '14px', color: '#9CA3AF', fontStyle: 'italic' }}>
          No outreach steps yet. Use Claude Code to generate sequences.
        </p>
      ) : (
        Object.entries(activitiesByChannel).map(([channel, activities]) => (
          <div key={channel} style={{ marginBottom: '32px' }}>
            <h2 style={{ fontSize: '13px', fontWeight: 600, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ChannelIcon channel={channel} />
              {channelLabels[channel] ?? `${channel} Outreach`}
            </h2>

            {activities.map((activity, idx) => {
              const stepNumber = (activity.metadata?.step_number as number) ?? '?'
              const variant = (activity.metadata?.variant as string) ?? null
              const variantTheme = (activity.metadata?.variant_theme as string) ?? null
              const status = activity.status?.toLowerCase() ?? 'drafted'
              const pill = STATUS_PILL[status] ?? STATUS_PILL.drafted

              return (
                <div
                  key={activity.id}
                  style={{
                    background: '#FFFFFF',
                    border: '1px solid #F3F4F6',
                    borderRadius: '8px',
                    padding: '16px 20px',
                    marginBottom: idx < activities.length - 1 ? '12px' : '0',
                  }}
                >
                  {/* Step header */}
                  <div className="flex items-center gap-2" style={{ marginBottom: '4px' }}>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>
                      Step {stepNumber}
                    </span>
                    {variant && (
                      <span style={{ padding: '1px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: 500, background: '#F3F4F6', color: '#6B7280' }}>
                        {variant}
                      </span>
                    )}
                    <span style={{ flex: 1 }} />
                    <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 500, background: pill.bg, color: pill.text, textTransform: 'capitalize' }}>
                      {status}
                    </span>
                  </div>

                  {/* Variant theme */}
                  {variantTheme && (
                    <div style={{ fontSize: '12px', color: '#9CA3AF', fontStyle: 'italic', marginBottom: '6px' }}>
                      {variantTheme}
                    </div>
                  )}

                  {/* Message body */}
                  <StepBody activity={activity} entryId={contact.pipeline_entry_id} activityMutation={activityMutation} />

                  {/* Action buttons */}
                  <StepActions activity={activity} entryId={contact.pipeline_entry_id} activityMutation={activityMutation} />
                </div>
              )
            })}
          </div>
        ))
      )}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
