import { useParams, useNavigate, useLocation } from 'react-router'
import {
  ArrowLeft,
  Globe,
  ExternalLink,
  FileSearch,
  Mail,
  Phone,
  Linkedin,
  Calendar,
  MessageSquare,
  Video,
  FileText,
  CheckSquare,
  Square,
  Clock,
  AlertCircle,
  User,
  Building2,
} from 'lucide-react'
import { format } from 'date-fns'
import { ShimmerSkeleton } from '@/components/ui/skeleton'
import { usePipelineDetail } from '../hooks/usePipelineDetail'
import { usePipelineTimeline } from '../hooks/usePipelineTimeline'
import { usePipelineTasks } from '../hooks/usePipelineTasks'
import { STAGE_COLORS, TIER_COLORS, INSIGHT_TAG_COLORS } from '../constants'
import type {
  PipelineDetail,
  PipelineContact,
  PipelineTaskItem,
  TimelineItem,
  KeyInsight,
  OutreachStep,
} from '../types/pipeline'

/* ------------------------------------------------------------------ */
/* Inline badge components                                             */
/* ------------------------------------------------------------------ */

function StagePill({ stage }: { stage: string }) {
  const key = stage.toLowerCase()
  const c = STAGE_COLORS[key] ?? { bg: '#F3F4F6', text: '#6B7280' }
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '3px 10px',
        borderRadius: '9999px',
        fontSize: '12px',
        fontWeight: 600,
        textTransform: 'capitalize',
        background: c.bg,
        color: c.text,
      }}
    >
      {key}
    </span>
  )
}

function FitTierBadge({ tier }: { tier: string }) {
  const key = tier.toLowerCase()
  const c = TIER_COLORS[key] ?? { bg: '#F3F4F6', text: '#6B7280' }
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '3px 10px',
        borderRadius: '9999px',
        fontSize: '12px',
        fontWeight: 600,
        background: c.bg,
        color: c.text,
      }}
    >
      {tier}
    </span>
  )
}

function TagBadge({ label, bg, text }: { label: string; bg: string; text: string }) {
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: '9999px',
        fontSize: '11px',
        fontWeight: 600,
        background: bg,
        color: text,
      }}
    >
      {label}
    </span>
  )
}

/* ------------------------------------------------------------------ */
/* Card wrapper                                                        */
/* ------------------------------------------------------------------ */

function Card({
  children,
  style,
}: {
  children: React.ReactNode
  style?: React.CSSProperties
}) {
  return (
    <div
      style={{
        background: '#FFFFFF',
        borderRadius: '12px',
        border: '1px solid #E5E7EB',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        padding: '20px',
        ...style,
      }}
    >
      {children}
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3
      style={{
        fontSize: '11px',
        fontWeight: 600,
        color: '#9CA3AF',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        marginBottom: '12px',
        marginTop: 0,
      }}
    >
      {children}
    </h3>
  )
}

/* ------------------------------------------------------------------ */
/* Timeline icon helper                                                */
/* ------------------------------------------------------------------ */

const TIMELINE_ICONS: Record<string, React.ComponentType<{ style?: React.CSSProperties }>> = {
  activity: MessageSquare,
  meeting: Video,
  context: FileText,
}

/* ------------------------------------------------------------------ */
/* Priority colors                                                     */
/* ------------------------------------------------------------------ */

const PRIORITY_COLORS: Record<string, { bg: string; text: string }> = {
  high: { bg: '#FEE2E2', text: '#DC2626' },
  medium: { bg: '#FEF3C7', text: '#D97706' },
  low: { bg: '#F3F4F6', text: '#6B7280' },
}

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  draft: { bg: '#F3F4F6', text: '#6B7280' },
  sent: { bg: '#DBEAFE', text: '#2563EB' },
  replied: { bg: '#D1FAE5', text: '#059669' },
}

/* ------------------------------------------------------------------ */
/* Helper: format date safely                                          */
/* ------------------------------------------------------------------ */

function formatDate(date: string | null, fmt: string = 'MMM d, yyyy'): string {
  if (!date) return '--'
  try {
    return format(new Date(date), fmt)
  } catch {
    return '--'
  }
}

function formatDateTime(date: string | null): string {
  return formatDate(date, 'MMM d, yyyy h:mm a')
}

/* ------------------------------------------------------------------ */
/* Loading skeleton                                                    */
/* ------------------------------------------------------------------ */

function ProfileSkeleton() {
  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
      {/* Back button skeleton */}
      <ShimmerSkeleton style={{ width: '140px', height: '16px', borderRadius: '4px', marginBottom: '24px' }} />

      {/* Header skeleton */}
      <div className="flex items-center gap-4" style={{ marginBottom: '32px' }}>
        <ShimmerSkeleton style={{ width: '56px', height: '56px', borderRadius: '12px' }} />
        <div>
          <ShimmerSkeleton style={{ width: '200px', height: '24px', borderRadius: '4px', marginBottom: '8px' }} />
          <ShimmerSkeleton style={{ width: '120px', height: '14px', borderRadius: '4px' }} />
        </div>
      </div>

      {/* Two columns skeleton */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <ShimmerSkeleton style={{ width: '100%', height: '120px', borderRadius: '12px' }} />
          <ShimmerSkeleton style={{ width: '100%', height: '160px', borderRadius: '12px' }} />
          <ShimmerSkeleton style={{ width: '100%', height: '200px', borderRadius: '12px' }} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <ShimmerSkeleton style={{ width: '100%', height: '180px', borderRadius: '12px' }} />
          <ShimmerSkeleton style={{ width: '100%', height: '140px', borderRadius: '12px' }} />
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Sub-sections                                                        */
/* ------------------------------------------------------------------ */

function AiSummarySection({ summary }: { summary: string | null }) {
  if (!summary) return null
  return (
    <Card style={{ background: 'rgba(233,77,53,0.03)' }}>
      <SectionLabel>AI Summary</SectionLabel>
      <p style={{ fontSize: '14px', lineHeight: '1.65', color: '#374151', margin: 0, whiteSpace: 'pre-line' }}>
        {summary}
      </p>
    </Card>
  )
}

function KeyInsightsSection({ insights }: { insights: KeyInsight[] | undefined }) {
  return (
    <Card>
      <SectionLabel>Key Insights</SectionLabel>
      {!insights || insights.length === 0 ? (
        <p style={{ fontSize: '13px', color: '#9CA3AF', fontStyle: 'italic', margin: 0 }}>
          No insights yet — insights are generated from meetings and emails.
        </p>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '12px',
          }}
        >
          {insights.map((insight, i) => {
            const tagColor = INSIGHT_TAG_COLORS[insight.tag] ?? { bg: '#F3F4F6', text: '#6B7280' }
            return (
              <div
                key={i}
                style={{
                  background: '#FAFAFA',
                  borderRadius: '8px',
                  padding: '12px',
                  border: '1px solid #F3F4F6',
                }}
              >
                <TagBadge label={insight.tag} bg={tagColor.bg} text={tagColor.text} />
                <p style={{ fontSize: '13px', color: '#374151', margin: '8px 0 0', lineHeight: '1.5' }}>
                  {insight.text}
                </p>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

function OutreachSection({ steps }: { steps: OutreachStep[] | undefined }) {
  return (
    <Card>
      <SectionLabel>Outreach Sequence</SectionLabel>
      {!steps || steps.length === 0 ? (
        <p style={{ fontSize: '13px', color: '#9CA3AF', fontStyle: 'italic', margin: 0 }}>
          No outreach sequence yet.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {steps.map((step) => {
            const statusColor = STATUS_COLORS[step.status] ?? { bg: '#F3F4F6', text: '#6B7280' }
            return (
              <div
                key={step.step}
                style={{
                  background: '#FAFAFA',
                  borderRadius: '8px',
                  padding: '16px',
                  border: '1px solid #F3F4F6',
                }}
              >
                <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
                  <div className="flex items-center gap-2">
                    <span
                      style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        background: '#E5E7EB',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '12px',
                        fontWeight: 600,
                        color: '#6B7280',
                      }}
                    >
                      {step.step}
                    </span>
                    <TagBadge label={step.channel} bg="#DBEAFE" text="#2563EB" />
                  </div>
                  <TagBadge label={step.status} bg={statusColor.bg} text={statusColor.text} />
                </div>
                {step.subject && (
                  <div style={{ fontSize: '14px', fontWeight: 600, color: '#121212', marginBottom: '6px' }}>
                    {step.subject}
                  </div>
                )}
                <p style={{ fontSize: '13px', lineHeight: '1.6', color: '#374151', margin: 0, whiteSpace: 'pre-line' }}>
                  {step.body}
                </p>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

function ActivityTimelineSection({ items }: { items: TimelineItem[] | undefined }) {
  return (
    <Card>
      <SectionLabel>Activity Timeline</SectionLabel>
      {!items || items.length === 0 ? (
        <p style={{ fontSize: '13px', color: '#9CA3AF', fontStyle: 'italic', margin: 0 }}>
          No activity yet.
        </p>
      ) : (
        <div style={{ position: 'relative', paddingLeft: '28px' }}>
          {/* Vertical line */}
          <div
            style={{
              position: 'absolute',
              left: '9px',
              top: '4px',
              bottom: '4px',
              width: '2px',
              background: '#E5E7EB',
              borderRadius: '1px',
            }}
          />
          {items.map((item) => {
            const Icon = TIMELINE_ICONS[item.source_type] ?? FileText
            return (
              <div key={item.id} style={{ position: 'relative', marginBottom: '16px' }}>
                {/* Dot */}
                <div
                  style={{
                    position: 'absolute',
                    left: '-28px',
                    top: '2px',
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    background: '#F3F4F6',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Icon style={{ width: '11px', height: '11px', color: '#6B7280' }} />
                </div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: '#121212', marginBottom: '2px' }}>
                  {item.title}
                </div>
                <div style={{ fontSize: '12px', color: '#9CA3AF', marginBottom: '4px' }}>
                  {formatDateTime(item.date)}
                </div>
                {item.summary && (
                  <p style={{ fontSize: '13px', color: '#6B7280', margin: '4px 0 0', lineHeight: '1.5' }}>
                    {item.summary}
                  </p>
                )}
                <div className="flex items-center gap-2" style={{ marginTop: '6px' }}>
                  {item.type && <TagBadge label={item.type} bg="#F3F4F6" text="#6B7280" />}
                  {item.channel && <TagBadge label={item.channel} bg="#DBEAFE" text="#2563EB" />}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

function CompanyResearchSection({ intel }: { intel: PipelineDetail['intel'] }) {
  const fields: { key: keyof typeof intel; label: string }[] = [
    { key: 'industry', label: 'Industry' },
    { key: 'description', label: 'Description' },
    { key: 'what_they_do', label: 'What They Do' },
    { key: 'headquarters', label: 'Headquarters' },
    { key: 'employees', label: 'Employees' },
    { key: 'funding', label: 'Funding' },
    { key: 'tagline', label: 'Tagline' },
  ]

  const populatedFields = fields.filter(
    (f) => intel[f.key] !== undefined && intel[f.key] !== null && intel[f.key] !== '',
  )

  return (
    <Card>
      <SectionLabel>Company Research</SectionLabel>
      {populatedFields.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '16px 0' }}>
          <FileSearch style={{ width: '32px', height: '32px', color: '#D1D5DB', margin: '0 auto 8px' }} />
          <p style={{ fontSize: '13px', color: '#9CA3AF', fontStyle: 'italic', margin: 0 }}>
            No company research yet — run the Company Intel skill to populate this section.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {populatedFields.map((f) => (
            <div key={f.key}>
              <div
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: '#9CA3AF',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  marginBottom: '4px',
                }}
              >
                {f.label}
              </div>
              <div style={{ fontSize: '13px', color: '#374151', lineHeight: '1.5' }}>
                {String(intel[f.key])}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function ContactsSection({ contacts }: { contacts: PipelineContact[] }) {
  return (
    <Card>
      <SectionLabel>Contacts</SectionLabel>
      {contacts.length === 0 ? (
        <p style={{ fontSize: '13px', color: '#9CA3AF', fontStyle: 'italic', margin: 0 }}>
          No contacts yet.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {contacts.map((contact) => (
            <div
              key={contact.id}
              style={{
                background: '#FAFAFA',
                borderRadius: '8px',
                padding: '12px',
                border: '1px solid #F3F4F6',
              }}
            >
              <div className="flex items-center gap-2" style={{ marginBottom: '4px' }}>
                <span style={{ fontSize: '14px', fontWeight: 600, color: '#121212' }}>
                  {contact.name}
                </span>
                {contact.is_primary && (
                  <TagBadge label="Primary" bg="rgba(233,77,53,0.1)" text="#E94D35" />
                )}
                {contact.role && (
                  <TagBadge label={contact.role} bg="#F3F4F6" text="#6B7280" />
                )}
              </div>
              {contact.title && (
                <div style={{ fontSize: '12px', color: '#6B7280', marginBottom: '4px' }}>
                  {contact.title}
                </div>
              )}
              <div className="flex items-center gap-3" style={{ marginTop: '6px' }}>
                {contact.email && (
                  <a
                    href={`mailto:${contact.email}`}
                    className="inline-flex items-center gap-1"
                    style={{ fontSize: '12px', color: '#6B7280', textDecoration: 'none' }}
                  >
                    <Mail style={{ width: '11px', height: '11px' }} />
                    {contact.email}
                  </a>
                )}
                {contact.phone && (
                  <span className="inline-flex items-center gap-1" style={{ fontSize: '12px', color: '#6B7280' }}>
                    <Phone style={{ width: '11px', height: '11px' }} />
                    {contact.phone}
                  </span>
                )}
                {contact.linkedin_url && (
                  <a
                    href={contact.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1"
                    style={{ fontSize: '12px', color: '#2563EB', textDecoration: 'none' }}
                  >
                    <Linkedin style={{ width: '11px', height: '11px' }} />
                    LinkedIn
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function TasksSection({ tasks }: { tasks: PipelineTaskItem[] | undefined }) {
  return (
    <Card>
      <SectionLabel>Tasks</SectionLabel>
      {!tasks || tasks.length === 0 ? (
        <p style={{ fontSize: '13px', color: '#9CA3AF', fontStyle: 'italic', margin: 0 }}>
          No tasks yet.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {tasks.map((task) => {
            const prioColor = PRIORITY_COLORS[task.priority?.toLowerCase()] ?? { bg: '#F3F4F6', text: '#6B7280' }
            const isDone = task.status === 'done' || task.status === 'completed'
            return (
              <div
                key={task.id}
                className="flex items-start gap-2"
                style={{ padding: '8px 0', borderBottom: '1px solid #F9FAFB' }}
              >
                {isDone ? (
                  <CheckSquare style={{ width: '16px', height: '16px', color: '#22C55E', flexShrink: 0, marginTop: '1px' }} />
                ) : (
                  <Square style={{ width: '16px', height: '16px', color: '#D1D5DB', flexShrink: 0, marginTop: '1px' }} />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: '13px',
                      fontWeight: 500,
                      color: isDone ? '#9CA3AF' : '#121212',
                      textDecoration: isDone ? 'line-through' : 'none',
                    }}
                  >
                    {task.title}
                  </div>
                  <div className="flex items-center gap-2" style={{ marginTop: '4px' }}>
                    <TagBadge label={task.priority} bg={prioColor.bg} text={prioColor.text} />
                    <TagBadge label={task.task_type} bg="#F3F4F6" text="#6B7280" />
                    {task.due_date && (
                      <span style={{ fontSize: '11px', color: '#9CA3AF' }}>
                        Due {formatDate(task.due_date)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

/* ------------------------------------------------------------------ */
/* Main profile page                                                   */
/* ------------------------------------------------------------------ */

export function PipelineProfilePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  const { data: detail, isLoading, error } = usePipelineDetail(id ?? null)
  const { data: timelineData } = usePipelineTimeline(id ?? null)
  const { data: tasks } = usePipelineTasks(id ?? null)

  const handleBack = () => {
    const state = location.state as { from?: string; selectedId?: string; page?: number } | null
    if (state?.from === '/pipeline') {
      navigate('/pipeline', {
        state: { restoreSelectedId: state.selectedId, restorePage: state.page },
      })
    } else {
      navigate('/pipeline')
    }
  }

  /* Loading */
  if (isLoading) return <ProfileSkeleton />

  /* Error */
  if (error || !detail) {
    return (
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <AlertCircle style={{ width: '40px', height: '40px', color: '#DC2626', margin: '0 auto 12px' }} />
          <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#121212', marginBottom: '8px' }}>
            Unable to load profile
          </h2>
          <p style={{ fontSize: '14px', color: '#6B7280', marginBottom: '16px' }}>
            {error instanceof Error ? error.message : 'The pipeline entry could not be found.'}
          </p>
          <button
            onClick={() => navigate('/pipeline')}
            style={{
              background: 'none',
              border: '1px solid #E5E7EB',
              borderRadius: '8px',
              padding: '8px 16px',
              fontSize: '13px',
              fontWeight: 500,
              color: '#374151',
              cursor: 'pointer',
            }}
          >
            Back to Pipeline
          </button>
        </div>
      </div>
    )
  }

  const AvatarIcon = detail.entity_type === 'company' ? Building2 : User

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
      {/* Back button */}
      <button
        onClick={handleBack}
        className="inline-flex items-center gap-1"
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: '13px',
          fontWeight: 500,
          color: '#6B7280',
          padding: '4px 0',
          marginBottom: '20px',
        }}
      >
        <ArrowLeft style={{ width: '14px', height: '14px' }} />
        Back to Pipeline
      </button>

      {/* Header section */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '16px',
          marginBottom: '32px',
          flexWrap: 'wrap',
        }}
      >
        {/* Avatar */}
        <div
          style={{
            width: '56px',
            height: '56px',
            borderRadius: detail.entity_type === 'company' ? '12px' : '50%',
            background: 'rgba(233,77,53,0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <AvatarIcon style={{ width: '28px', height: '28px', color: '#E94D35' }} />
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Name + entity badge */}
          <div className="flex items-center gap-3" style={{ marginBottom: '6px' }}>
            <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#121212', margin: 0 }}>
              {detail.name}
            </h1>
            <span
              style={{
                display: 'inline-block',
                padding: '2px 8px',
                borderRadius: '9999px',
                fontSize: '11px',
                fontWeight: 600,
                textTransform: 'capitalize',
                background: '#F3F4F6',
                color: '#6B7280',
              }}
            >
              {detail.entity_type}
            </span>
          </div>

          {/* Domain */}
          {detail.domain && (
            <a
              href={`https://${detail.domain}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1"
              style={{
                fontSize: '14px',
                color: '#6B7280',
                textDecoration: 'none',
                marginBottom: '10px',
                display: 'inline-flex',
              }}
            >
              <Globe style={{ width: '13px', height: '13px' }} />
              {detail.domain}
              <ExternalLink style={{ width: '11px', height: '11px' }} />
            </a>
          )}

          {/* Stage + Fit + Source + Channels */}
          <div className="flex items-center gap-2" style={{ flexWrap: 'wrap', marginTop: '8px' }}>
            <StagePill stage={detail.stage} />
            {detail.fit_tier && <FitTierBadge tier={detail.fit_tier} />}
            <TagBadge label={detail.source} bg="#F3F4F6" text="#6B7280" />
            {detail.channels.map((ch) => (
              <TagBadge key={ch} label={ch} bg="#EDE9FE" text="#7C3AED" />
            ))}
          </div>

          {/* Dates */}
          <div className="flex items-center gap-4" style={{ marginTop: '10px' }}>
            <span className="inline-flex items-center gap-1" style={{ fontSize: '12px', color: '#9CA3AF' }}>
              <Calendar style={{ width: '11px', height: '11px' }} />
              Created {formatDate(detail.created_at)}
            </span>
            {detail.last_activity_at && (
              <span className="inline-flex items-center gap-1" style={{ fontSize: '12px', color: '#9CA3AF' }}>
                <Clock style={{ width: '11px', height: '11px' }} />
                Last activity {formatDate(detail.last_activity_at)}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Two-column layout */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '2fr 1fr',
          gap: '24px',
        }}
      >
        {/* Main column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', minWidth: 0 }}>
          <AiSummarySection summary={detail.ai_summary} />
          <KeyInsightsSection insights={detail.intel?.key_insights} />
          <OutreachSection steps={detail.intel?.outreach_sequence} />
          <ActivityTimelineSection items={timelineData?.items} />
        </div>

        {/* Sidebar column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', minWidth: 0 }}>
          <CompanyResearchSection intel={detail.intel ?? {}} />
          <ContactsSection contacts={detail.contacts ?? []} />
          <TasksSection tasks={tasks} />
        </div>
      </div>

      {/* Responsive override for small screens */}
      <style>{`
        @media (max-width: 768px) {
          div[style*="grid-template-columns: 2fr 1fr"] {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  )
}
