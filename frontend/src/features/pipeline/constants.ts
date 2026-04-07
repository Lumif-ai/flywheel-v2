export const STAGE_COLORS: Record<string, { bg: string; text: string }> = {
  identified: { bg: '#F3F4F6', text: '#6B7280' },
  contacted: { bg: '#DBEAFE', text: '#2563EB' },
  engaged: { bg: '#FEF3C7', text: '#D97706' },
  qualified: { bg: '#D1FAE5', text: '#059669' },
  committed: { bg: '#EDE9FE', text: '#7C3AED' },
  closed: { bg: 'rgba(233,77,53,0.1)', text: '#E94D35' },
}

export const TIER_COLORS: Record<string, { bg: string; text: string }> = {
  strong: { bg: '#D1FAE5', text: '#059669' },
  medium: { bg: '#FEF3C7', text: '#D97706' },
  weak: { bg: '#FEE2E2', text: '#DC2626' },
}

export const STAGE_ORDER = [
  'identified',
  'contacted',
  'engaged',
  'qualified',
  'committed',
  'closed',
] as const

export const NEXT_STEP_COLORS: Record<string, { bg: string; text: string }> = {
  'Ready to send': { bg: '#DBEAFE', text: '#1E40AF' },
  'Replied - engage': { bg: '#DCFCE7', text: '#166534' },
  'Bounced - fix email': { bg: '#FEE2E2', text: '#DC2626' },
  'Follow up now': { bg: '#FEF3C7', text: '#D97706' },
  // "Follow up in Xd" matched via startsWith in NextStepCell
}

export const ACTIVITY_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  drafted: { bg: '#F3F4F6', text: '#6B7280' },
  approved: { bg: '#DBEAFE', text: '#2563EB' },
  sent: { bg: '#FEF3C7', text: '#D97706' },
  replied: { bg: '#DCFCE7', text: '#166534' },
  bounced: { bg: '#FEE2E2', text: '#DC2626' },
}

export const INSIGHT_TAG_COLORS: Record<string, { bg: string; text: string }> = {
  Signal: { bg: '#DBEAFE', text: '#2563EB' },
  Pain: { bg: '#FEE2E2', text: '#DC2626' },
  Commitment: { bg: '#D1FAE5', text: '#059669' },
  Context: { bg: '#F3F4F6', text: '#6B7280' },
}
