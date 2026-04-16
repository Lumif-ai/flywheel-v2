export const INSURANCE_CATEGORIES = ['liability', 'property', 'auto', 'workers_comp', 'specialty'] as const
export const SURETY_CATEGORIES = ['surety'] as const
export const ALL_CATEGORIES = [...INSURANCE_CATEGORIES, ...SURETY_CATEGORIES] as const

export type CoverageCategory = typeof ALL_CATEGORIES[number]

export const GAP_STATUS = ['covered', 'missing', 'insufficient', 'unknown'] as const
export type GapStatus = typeof GAP_STATUS[number]

export const STATUS_COLORS: Record<GapStatus, { bg: string; text: string }> = {
  covered: { bg: '#DCFCE7', text: '#15803D' },
  missing: { bg: '#FEE2E2', text: '#B91C1C' },
  insufficient: { bg: '#FEF3C7', text: '#A16207' },
  unknown: { bg: '#F3F4F6', text: '#6B7280' },
}
