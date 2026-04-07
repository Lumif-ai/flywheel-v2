import { Mail, Linkedin } from 'lucide-react'
import type { PipelineContact, PipelineActivity } from '../types/pipeline'
import { usePipelineDetail } from '../hooks/usePipelineDetail'

interface ContactDetailRowProps {
  entryId: string
  entryName: string
}

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  drafted: { bg: '#F3F4F6', text: '#6B7280' },
  sent: { bg: '#DBEAFE', text: '#1E40AF' },
  replied: { bg: '#DCFCE7', text: '#166534' },
}

export function ContactDetailRow({ entryId }: ContactDetailRowProps) {
  const { data: detail, isLoading: loading } = usePipelineDetail(entryId)
  const contacts: PipelineContact[] = detail?.contacts || []
  const activities: PipelineActivity[] = detail?.recent_activities || []

  if (loading) {
    return (
      <div style={{ padding: '12px 48px', color: '#9CA3AF', fontSize: '12px' }}>
        Loading contacts...
      </div>
    )
  }
  if (contacts.length === 0) {
    return (
      <div style={{ padding: '12px 48px', color: '#9CA3AF', fontSize: '12px' }}>
        No contacts
      </div>
    )
  }

  // Build a map: contact_id -> latest outreach activity
  const activityByContact: Record<string, PipelineActivity> = {}
  for (const a of activities) {
    if (a.type === 'outreach' && a.contact_id) {
      const existing = activityByContact[a.contact_id]
      if (
        !existing ||
        (a.occurred_at && a.occurred_at > (existing.occurred_at || ''))
      ) {
        activityByContact[a.contact_id] = a
      }
    }
  }

  return (
    <div
      style={{
        padding: '8px 16px 8px 48px',
        background: '#FAFAFA',
        borderBottom: '1px solid #F3F4F6',
        overflowY: 'auto',
        height: '100%',
      }}
    >
      <table
        style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}
      >
        <thead>
          <tr
            style={{
              color: '#9CA3AF',
              fontWeight: 600,
              textTransform: 'uppercase',
              fontSize: '10px',
              letterSpacing: '0.05em',
            }}
          >
            <th style={{ textAlign: 'left', padding: '4px 8px', width: '200px' }}>
              Contact
            </th>
            <th style={{ textAlign: 'left', padding: '4px 8px', width: '180px' }}>
              Title
            </th>
            <th style={{ textAlign: 'left', padding: '4px 8px', width: '200px' }}>
              Email
            </th>
            <th style={{ textAlign: 'left', padding: '4px 8px', width: '80px' }}>
              Links
            </th>
            <th style={{ textAlign: 'left', padding: '4px 8px', width: '120px' }}>
              Outreach
            </th>
            <th style={{ textAlign: 'left', padding: '4px 8px' }}>Subject</th>
          </tr>
        </thead>
        <tbody>
          {contacts.map((c) => {
            const activity = activityByContact[c.id]
            const outreachStatus = activity?.status || null
            const colors = outreachStatus
              ? STATUS_COLORS[outreachStatus] || { bg: 'transparent', text: '#D1D5DB' }
              : null

            return (
              <tr key={c.id} style={{ borderTop: '1px solid #F3F4F6' }}>
                <td
                  style={{
                    padding: '6px 8px',
                    fontWeight: 500,
                    color: '#121212',
                  }}
                >
                  {c.name}
                </td>
                <td style={{ padding: '6px 8px', color: '#6B7280' }}>
                  {c.title || '\u2014'}
                </td>
                <td
                  style={{
                    padding: '6px 8px',
                    color: '#6B7280',
                    fontSize: '11px',
                  }}
                >
                  {c.email || '\u2014'}
                </td>
                <td style={{ padding: '6px 8px' }}>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    {c.email && (
                      <a
                        href={`mailto:${c.email}`}
                        title="Email"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Mail size={13} style={{ color: '#9CA3AF' }} />
                      </a>
                    )}
                    {c.linkedin_url && (
                      <a
                        href={c.linkedin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="LinkedIn"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Linkedin size={13} style={{ color: '#9CA3AF' }} />
                      </a>
                    )}
                  </div>
                </td>
                <td style={{ padding: '6px 8px' }}>
                  {outreachStatus && colors ? (
                    <span
                      style={{
                        display: 'inline-flex',
                        padding: '1px 6px',
                        borderRadius: '9999px',
                        fontSize: '10px',
                        fontWeight: 500,
                        background: colors.bg,
                        color: colors.text,
                      }}
                    >
                      {outreachStatus}
                    </span>
                  ) : (
                    <span style={{ color: '#D1D5DB' }}>{'\u2014'}</span>
                  )}
                </td>
                <td
                  style={{
                    padding: '6px 8px',
                    color: '#6B7280',
                    fontSize: '11px',
                  }}
                >
                  {activity?.subject || '\u2014'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
