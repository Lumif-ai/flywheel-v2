import type { ComparisonCoverage } from '../../types/broker'

export { INSURANCE_CATEGORIES, SURETY_CATEGORIES } from '../../constants/coverage'

export function formatCurrency(value: number | null, currency: string): string {
  if (value === null) return '\u2014'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(value)
}

export function hasMeaningfulDifference(
  coverage: ComparisonCoverage,
  threshold = 0.15
): boolean {
  const quotes = coverage.quotes
  if (quotes.length < 2) return true

  // Check for exclusion difference: any quote has critical exclusion while another doesn't
  const hasExclusion = quotes.some((q) => q.has_critical_exclusion)
  const hasNoExclusion = quotes.some((q) => !q.has_critical_exclusion)
  if (hasExclusion && hasNoExclusion) return true

  // Check for insufficient limit difference: any limit differs from required_limit
  if (coverage.required_limit != null) {
    const hasInsufficient = quotes.some(
      (q) => q.limit_amount != null && q.limit_amount < coverage.required_limit!
    )
    if (hasInsufficient) return true
  }

  // Check premium variance
  const premiums = quotes.map((q) => q.premium).filter((p): p is number => p !== null)
  if (premiums.length < 2) return true

  const min = Math.min(...premiums)
  const max = Math.max(...premiums)
  if (min === 0) return true
  return (max - min) / min > threshold
}

export function getUniqueCarriers(
  coverages: ComparisonCoverage[]
): { name: string; carrier_config_id: string | null }[] {
  const seen = new Map<string, string | null>()
  for (const cov of coverages) {
    for (const q of cov.quotes) {
      if (!seen.has(q.carrier_name)) {
        seen.set(q.carrier_name, q.carrier_config_id)
      }
    }
  }
  return Array.from(seen.entries())
    .map(([name, carrier_config_id]) => ({ name, carrier_config_id }))
    .sort((a, b) => a.name.localeCompare(b.name))
}

export function computeCarrierTotals(
  coverages: ComparisonCoverage[],
  carriers: { name: string }[]
): Map<string, number> {
  const totals = new Map<string, number>()
  for (const carrier of carriers) {
    totals.set(carrier.name, 0)
  }
  for (const cov of coverages) {
    for (const q of cov.quotes) {
      if (q.premium != null && totals.has(q.carrier_name)) {
        totals.set(q.carrier_name, totals.get(q.carrier_name)! + q.premium)
      }
    }
  }
  return totals
}

export function isInsufficientLimit(
  limit: number | null,
  required: number | null
): boolean {
  return limit != null && required != null && limit < required
}
