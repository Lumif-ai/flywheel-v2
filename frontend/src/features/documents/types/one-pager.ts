/**
 * One-pager structured output types.
 */

export interface OnePagerData {
  title: string
  sections: OnePagerSection[]
}

export interface OnePagerSection {
  heading: string
  body: string
}

/** Type guard for detecting one-pager JSON output */
export function isOnePagerData(value: unknown): value is OnePagerData {
  if (!value || typeof value !== 'object') return false
  const obj = value as Record<string, unknown>
  return typeof obj.title === 'string' && Array.isArray(obj.sections)
}
