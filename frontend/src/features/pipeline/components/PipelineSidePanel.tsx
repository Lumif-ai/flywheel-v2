import { useEffect, useState } from 'react'
import {
  X,
  Globe,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Loader2,
  CheckSquare,
  Square,
  Mail,
  Activity,
  Calendar,
  FileText,
} from 'lucide-react'
import { format, formatDistanceToNow } from 'date-fns'
import { useQueryClient } from '@tanstack/react-query'
import type { PipelineListItem, KeyInsight, OutreachStep, PipelineContact, PipelineTaskItem, TimelineItem } from '../types/pipeline'
import { STAGE_COLORS, TIER_COLORS, INSIGHT_TAG_COLORS } from '../constants'
import { retirePipelineEntry, reactivatePipelineEntry } from '../api'
import { usePipelineDetail } from '../hooks/usePipelineDetail'
import { usePipelineTimeline } from '../hooks/usePipelineTimeline'
import { usePipelineTasks } from '../hooks/usePipelineTasks'

/* ------------------------------------------------------------------ */
/* Inline stage pill + fit tier badge (non-AG Grid versions)           */
/* ------------------------------------------------------------------ */

function StagePillInline({ stage }: { stage: string }) {
  const key = stage.toLowerCase()
  const colors = STAGE_COLORS[key] ?? { bg: '#F3F4F6', text: '#6B7280' }
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: '9999px',
        fontSize: '11px',
        fontWeight: 600,
        textTransform: 'capitalize',
        background: colors.bg,
        color: colors.text,
      }}
    >
      {key}
    </span>
  )
}

function FitTierBadgeInline({ tier }: { tier: string }) {
  const key = tier.toLowerCase()
  const colors = TIER_COLORS[key] ?? { bg: '#F3F4F6', text: '#6B7280' }
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: '9999px',
        fontSize: '11px',
        fontWeight: 600,
        background: colors.bg,
        color: colors.text,
      }}
    >
      {tier}
    </span>
  )
}

/* ------------------------------------------------------------------ */
/* Section header (11px uppercase pattern)                             */
/* ------------------------------------------------------------------ */

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h3
      style={{
        fontSize: '11px',
        fontWeight: 600,
        color: '#9CA3AF',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        marginBottom: '8px',
        marginTop: '0',
      }}
    >
      {children}
    </h3>
  )
}

/* ------------------------------------------------------------------ */
/* Empty state helper                                                  */
/* ------------------------------------------------------------------ */

function EmptyText({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ fontSize: '13px', color: '#9CA3AF', fontStyle: 'italic', margin: 0 }}>
      {children}
    </p>
  )
}

/* ------------------------------------------------------------------ */
/* Loading skeleton for detail sections                                */
/* ------------------------------------------------------------------ */

function SectionSkeleton() {
  return (
    <div className="flex items-center gap-2" style={{ padding: '8px 0' }}>
      <Loader2
        style={{ width: '14px', height: '14px', color: '#D1D5DB', animation: 'spin 1s linear infinite' }}
      />
      <span style={{ fontSize: '12px', color: '#D1D5DB' }}>Loading...</span>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Priority badge for tasks                                            */
/* ------------------------------------------------------------------ */

const PRIORITY_COLORS: Record<string, { bg: string; text: string }> = {
  high: { bg: '#FEE2E2', text: '#DC2626' },
  medium: { bg: '#FEF3C7', text: '#D97706' },
  low: { bg: '#F3F4F6', text: '#6B7280' },
}

/* ------------------------------------------------------------------ */
/* Timeline source icon                                                */
/* ------------------------------------------------------------------ */

function TimelineIcon({ sourceType }: { sourceType: string }) {
  const style = { width: '14px', height: '14px', color: '#9CA3AF' }
  switch (sourceType) {
    case 'activity':
      return <Activity style={style} />
    case 'meeting':
      return <Calendar style={style} />
    case 'context':
      return <FileText style={style} />
    default:
      return <Activity style={style} />
  }
}

/* ------------------------------------------------------------------ */
/* Side panel                                                          */
/* ------------------------------------------------------------------ */

export interface PipelineSidePanelProps {
  item: PipelineListItem
  onClose: () => void
  onOpenProfile: (id: string) => void
}

export function PipelineSidePanel({ item, onClose, onOpenProfile }: PipelineSidePanelProps) {
  const queryClient = useQueryClient()
  const { data: detail, isLoading: detailLoading } = usePipelineDetail(item.id)
  const { data: tasks, isLoading: tasksLoading } = usePipelineTasks(item.id)
  const { data: timelineData, isLoading: timelineLoading } = usePipelineTimeline(item.id)

  // Retire/reactivate loading state
  const [retireLoading, setRetireLoading] = useState(false)

  // Outreach sequence expansion state
  const [expandedStep, setExpandedStep] = useState<number | null>(null)

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const isCompany = item.entity_type === 'company'
  const initial = (item.name?.[0] ?? '?').toUpperCase()

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        width: '420px',
        height: '100vh',
        zIndex: 40,
        background: '#FFFFFF',
        borderLeft: '1px solid #E5E7EB',
        boxShadow: '-4px 0 12px rgba(0,0,0,0.05)',
        display: 'flex',
        flexDirection: 'column',
        animation: 'pipelineSidePanelSlideIn 200ms ease-out',
      }}
    >
      {/* ============================================================ */}
      {/* HEADER (PANEL-02) — fixed, not scrollable                    */}
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
            {/* Entity-type-aware avatar */}
            <div
              style={{
                width: '36px',
                height: '36px',
                minWidth: '36px',
                borderRadius: isCompany ? '8px' : '50%',
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
              <h2 style={{ fontSize: '16px', fontWeight: 600, color: '#121212', margin: 0, lineHeight: 1.3 }}>
                {item.name}
              </h2>
              {item.domain && (
                <a
                  href={`https://${item.domain}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1"
                  style={{ fontSize: '12px', color: '#6B7280', textDecoration: 'none', marginTop: '2px' }}
                >
                  <Globe style={{ width: '11px', height: '11px' }} />
                  {item.domain}
                  <ExternalLink style={{ width: '9px', height: '9px' }} />
                </a>
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

        {/* Stage pill + fit tier */}
        <div className="flex items-center gap-2" style={{ marginBottom: '10px' }}>
          <StagePillInline stage={item.stage} />
          {item.fit_tier && <FitTierBadgeInline tier={item.fit_tier} />}
        </div>

        {/* Open Full Profile + Retire/Reactivate buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => onOpenProfile(item.id)}
            style={{
              flex: 1,
              padding: '7px 12px',
              borderRadius: '6px',
              border: '1px solid #E5E7EB',
              background: '#FAFAFA',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 500,
              color: '#121212',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              transition: 'background 150ms ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = '#F3F4F6')}
            onMouseLeave={(e) => (e.currentTarget.style.background = '#FAFAFA')}
          >
            Open Full Profile
            <ExternalLink style={{ width: '12px', height: '12px' }} />
          </button>
          <button
            disabled={retireLoading}
            onClick={async () => {
              setRetireLoading(true)
              try {
                if (item.retired_at) {
                  await reactivatePipelineEntry(item.id)
                } else {
                  await retirePipelineEntry(item.id)
                }
                await queryClient.invalidateQueries({ queryKey: ['pipeline'] })
              } catch {
                // Silently handle — grid will stay as-is
              } finally {
                setRetireLoading(false)
              }
            }}
            style={{
              padding: '7px 12px',
              borderRadius: '6px',
              border: '1px solid #E5E7EB',
              background: '#FAFAFA',
              cursor: retireLoading ? 'not-allowed' : 'pointer',
              fontSize: '12px',
              fontWeight: 500,
              color: item.retired_at ? '#22C55E' : '#6B7280',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px',
              transition: 'background 150ms ease',
              opacity: retireLoading ? 0.6 : 1,
            }}
            onMouseEnter={(e) => { if (!retireLoading) e.currentTarget.style.background = '#F3F4F6' }}
            onMouseLeave={(e) => { if (!retireLoading) e.currentTarget.style.background = '#FAFAFA' }}
          >
            {retireLoading ? (
              <Loader2 style={{ width: '12px', height: '12px', animation: 'spin 1s linear infinite' }} />
            ) : null}
            {item.retired_at ? 'Reactivate' : 'Retire'}
          </button>
        </div>
      </div>

      {/* ============================================================ */}
      {/* SCROLLABLE CONTENT                                           */}
      {/* ============================================================ */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>

        {/* ---------------------------------------------------------- */}
        {/* AI SUMMARY (PANEL-03)                                      */}
        {/* ---------------------------------------------------------- */}
        <div style={{ marginBottom: '20px' }}>
          <SectionHeader>AI Summary</SectionHeader>
          {detailLoading ? (
            <SectionSkeleton />
          ) : detail?.ai_summary ? (
            <p style={{ fontSize: '13px', color: '#374151', lineHeight: 1.5, margin: 0 }}>
              {detail.ai_summary}
            </p>
          ) : (
            <EmptyText>No AI summary yet</EmptyText>
          )}
        </div>

        {/* ---------------------------------------------------------- */}
        {/* KEY INSIGHTS (PANEL-04)                                    */}
        {/* ---------------------------------------------------------- */}
        <div style={{ marginBottom: '20px' }}>
          <SectionHeader>Key Insights</SectionHeader>
          {detailLoading ? (
            <SectionSkeleton />
          ) : detail?.intel?.key_insights && detail.intel.key_insights.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {detail.intel.key_insights.map((insight: KeyInsight, idx: number) => {
                const tagColors = INSIGHT_TAG_COLORS[insight.tag] ?? { bg: '#F3F4F6', text: '#6B7280' }
                return (
                  <div
                    key={idx}
                    style={{
                      padding: '6px 10px',
                      borderRadius: '8px',
                      background: '#FAFAFA',
                      border: '1px solid #F3F4F6',
                      fontSize: '12px',
                      color: '#374151',
                      lineHeight: 1.4,
                    }}
                  >
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '1px 6px',
                        borderRadius: '9999px',
                        fontSize: '10px',
                        fontWeight: 600,
                        background: tagColors.bg,
                        color: tagColors.text,
                        marginRight: '6px',
                      }}
                    >
                      {insight.tag}
                    </span>
                    {insight.text}
                  </div>
                )
              })}
            </div>
          ) : (
            <EmptyText>No insights yet — insights are generated from meetings and emails.</EmptyText>
          )}
        </div>

        {/* ---------------------------------------------------------- */}
        {/* OUTREACH SEQUENCE (PANEL-05)                               */}
        {/* ---------------------------------------------------------- */}
        <div style={{ marginBottom: '20px' }}>
          <SectionHeader>Outreach Sequence</SectionHeader>
          {detailLoading ? (
            <SectionSkeleton />
          ) : detail?.intel?.outreach_sequence && detail.intel.outreach_sequence.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {detail.intel.outreach_sequence.map((step: OutreachStep) => {
                const isExpanded = expandedStep === step.step
                const statusColors: Record<string, { bg: string; text: string }> = {
                  draft: { bg: '#F3F4F6', text: '#6B7280' },
                  sent: { bg: '#DBEAFE', text: '#2563EB' },
                  replied: { bg: '#D1FAE5', text: '#059669' },
                }
                const sc = statusColors[step.status] ?? statusColors.draft
                return (
                  <div
                    key={step.step}
                    style={{
                      border: '1px solid #F3F4F6',
                      borderRadius: '8px',
                      overflow: 'hidden',
                    }}
                  >
                    <button
                      onClick={() => setExpandedStep(isExpanded ? null : step.step)}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        background: isExpanded ? '#FAFAFA' : '#FFFFFF',
                        border: 'none',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        fontSize: '12px',
                        color: '#121212',
                        textAlign: 'left',
                      }}
                    >
                      {isExpanded ? (
                        <ChevronDown style={{ width: '12px', height: '12px', color: '#9CA3AF', flexShrink: 0 }} />
                      ) : (
                        <ChevronRight style={{ width: '12px', height: '12px', color: '#9CA3AF', flexShrink: 0 }} />
                      )}
                      <span style={{ fontWeight: 600, color: '#6B7280', minWidth: '18px' }}>
                        #{step.step}
                      </span>
                      <span style={{ color: '#9CA3AF', fontSize: '11px', textTransform: 'capitalize' }}>
                        {step.channel}
                      </span>
                      <span
                        style={{
                          flex: 1,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {step.subject}
                      </span>
                      <span
                        style={{
                          padding: '1px 6px',
                          borderRadius: '9999px',
                          fontSize: '10px',
                          fontWeight: 600,
                          background: sc.bg,
                          color: sc.text,
                          textTransform: 'capitalize',
                          flexShrink: 0,
                        }}
                      >
                        {step.status}
                      </span>
                    </button>
                    {isExpanded && (
                      <div style={{ padding: '8px 10px 10px 38px', fontSize: '12px', color: '#374151', lineHeight: 1.5, borderTop: '1px solid #F3F4F6' }}>
                        {step.body}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <EmptyText>No outreach sequence yet.</EmptyText>
          )}
        </div>

        {/* ---------------------------------------------------------- */}
        {/* TASKS (PANEL-06)                                           */}
        {/* ---------------------------------------------------------- */}
        <div style={{ marginBottom: '20px' }}>
          <SectionHeader>Tasks</SectionHeader>
          {tasksLoading ? (
            <SectionSkeleton />
          ) : tasks && tasks.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {tasks.map((task: PipelineTaskItem) => {
                const isDone = task.status === 'done' || task.status === 'completed'
                const priorityKey = (task.priority ?? 'low').toLowerCase()
                const pc = PRIORITY_COLORS[priorityKey] ?? PRIORITY_COLORS.low
                return (
                  <div
                    key={task.id}
                    className="flex items-start gap-2"
                    style={{
                      padding: '6px 8px',
                      borderRadius: '6px',
                      background: isDone ? '#FAFAFA' : '#FFFFFF',
                      border: '1px solid #F3F4F6',
                    }}
                  >
                    {isDone ? (
                      <CheckSquare style={{ width: '14px', height: '14px', color: '#059669', marginTop: '1px', flexShrink: 0 }} />
                    ) : (
                      <Square style={{ width: '14px', height: '14px', color: '#D1D5DB', marginTop: '1px', flexShrink: 0 }} />
                    )}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: '12px',
                          fontWeight: 500,
                          color: isDone ? '#9CA3AF' : '#121212',
                          textDecoration: isDone ? 'line-through' : 'none',
                          lineHeight: 1.3,
                        }}
                      >
                        {task.title}
                      </div>
                      <div className="flex items-center gap-2" style={{ marginTop: '3px' }}>
                        {task.due_date && (
                          <span style={{ fontSize: '11px', color: '#9CA3AF' }}>
                            {format(new Date(task.due_date), 'MMM d')}
                          </span>
                        )}
                        <span
                          style={{
                            padding: '0px 5px',
                            borderRadius: '9999px',
                            fontSize: '10px',
                            fontWeight: 600,
                            background: pc.bg,
                            color: pc.text,
                            textTransform: 'capitalize',
                          }}
                        >
                          {task.priority}
                        </span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <EmptyText>No tasks yet.</EmptyText>
          )}
        </div>

        {/* ---------------------------------------------------------- */}
        {/* CONTACTS (PANEL-07)                                        */}
        {/* ---------------------------------------------------------- */}
        <div style={{ marginBottom: '20px' }}>
          <SectionHeader>Contacts</SectionHeader>
          {detailLoading ? (
            <SectionSkeleton />
          ) : detail?.contacts && detail.contacts.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {detail.contacts.map((contact: PipelineContact) => (
                <div
                  key={contact.id}
                  style={{
                    padding: '8px 10px',
                    borderRadius: '6px',
                    border: '1px solid #F3F4F6',
                    background: '#FFFFFF',
                  }}
                >
                  <div className="flex items-center gap-2">
                    <span style={{ fontSize: '13px', fontWeight: 500, color: '#121212' }}>
                      {contact.name}
                    </span>
                    {contact.is_primary && (
                      <span
                        style={{
                          padding: '0px 5px',
                          borderRadius: '9999px',
                          fontSize: '10px',
                          fontWeight: 600,
                          background: 'rgba(233,77,53,0.1)',
                          color: '#E94D35',
                        }}
                      >
                        Primary
                      </span>
                    )}
                    {contact.role && (
                      <span
                        style={{
                          padding: '0px 5px',
                          borderRadius: '9999px',
                          fontSize: '10px',
                          fontWeight: 600,
                          background: '#F3F4F6',
                          color: '#6B7280',
                          textTransform: 'capitalize',
                        }}
                      >
                        {contact.role}
                      </span>
                    )}
                  </div>
                  {contact.title && (
                    <div style={{ fontSize: '12px', color: '#6B7280', marginTop: '2px' }}>
                      {contact.title}
                    </div>
                  )}
                  {contact.email && (
                    <a
                      href={`mailto:${contact.email}`}
                      className="inline-flex items-center gap-1"
                      style={{ fontSize: '12px', color: '#6B7280', textDecoration: 'none', marginTop: '2px' }}
                    >
                      <Mail style={{ width: '11px', height: '11px' }} />
                      {contact.email}
                    </a>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <EmptyText>No contacts yet.</EmptyText>
          )}
        </div>

        {/* ---------------------------------------------------------- */}
        {/* ACTIVITY TIMELINE (PANEL-08)                               */}
        {/* ---------------------------------------------------------- */}
        <div style={{ marginBottom: '8px' }}>
          <SectionHeader>Activity Timeline</SectionHeader>
          {timelineLoading ? (
            <SectionSkeleton />
          ) : timelineData?.items && timelineData.items.length > 0 ? (
            <div style={{ position: 'relative', paddingLeft: '20px' }}>
              {/* Vertical line */}
              <div
                style={{
                  position: 'absolute',
                  left: '6px',
                  top: '4px',
                  bottom: '4px',
                  width: '1px',
                  background: '#E5E7EB',
                }}
              />
              {timelineData.items.map((entry: TimelineItem, idx: number) => (
                <div
                  key={entry.id}
                  style={{
                    position: 'relative',
                    paddingBottom: idx < timelineData.items.length - 1 ? '12px' : '0',
                  }}
                >
                  {/* Dot on the vertical line */}
                  <div
                    style={{
                      position: 'absolute',
                      left: '-17px',
                      top: '3px',
                      width: '10px',
                      height: '10px',
                      borderRadius: '50%',
                      background: '#FFFFFF',
                      border: '2px solid #D1D5DB',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  />
                  <div className="flex items-start gap-2">
                    <TimelineIcon sourceType={entry.source_type} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '12px', fontWeight: 500, color: '#121212', lineHeight: 1.3 }}>
                        {entry.title}
                      </div>
                      <div style={{ fontSize: '11px', color: '#9CA3AF', marginTop: '2px' }}>
                        {formatDistanceToNow(new Date(entry.date), { addSuffix: true })}
                      </div>
                      {entry.summary && (
                        <div
                          style={{
                            fontSize: '12px',
                            color: '#6B7280',
                            marginTop: '3px',
                            lineHeight: 1.4,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                          }}
                        >
                          {entry.summary}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyText>No activity yet.</EmptyText>
          )}
        </div>
      </div>

      {/* Animation keyframes */}
      <style>{`
        @keyframes pipelineSidePanelSlideIn {
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
