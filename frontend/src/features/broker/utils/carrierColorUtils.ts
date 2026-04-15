export const PALETTE = ['#E94D35', '#3B82F6', '#22C55E', '#F97316', '#A855F7', '#14B8A6', '#6366F1']

export function hashCode(str: string): number {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash)
  }
  return Math.abs(hash)
}

export function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}

export function getCarrierColor(name: string): string {
  return PALETTE[hashCode(name) % PALETTE.length]
}
