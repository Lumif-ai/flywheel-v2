/**
 * Format an ISO timestamp as a relative time string (e.g., "2 hours ago").
 * Falls back to the raw string if parsing fails.
 */
export function formatRelativeTime(iso: string): string {
  try {
    const date = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffSec = Math.floor(diffMs / 1000)

    if (diffSec < 60) return 'just now'
    const diffMin = Math.floor(diffSec / 60)
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    const diffDay = Math.floor(diffHr / 24)
    if (diffDay < 30) return `${diffDay}d ago`
    const diffMonth = Math.floor(diffDay / 30)
    if (diffMonth < 12) return `${diffMonth}mo ago`
    return `${Math.floor(diffMonth / 12)}y ago`
  } catch {
    return iso
  }
}

/**
 * Format a duration in milliseconds to a human-readable string.
 */
export function formatDuration(startIso: string, endIso: string | null): string {
  if (!endIso) return 'In progress'
  try {
    const start = new Date(startIso)
    const end = new Date(endIso)
    const diffMs = end.getTime() - start.getTime()
    const seconds = Math.floor(diffMs / 1000)
    if (seconds < 60) return `${seconds}s`
    const minutes = Math.floor(seconds / 60)
    const remainingSec = seconds % 60
    return `${minutes}m ${remainingSec}s`
  } catch {
    return 'Unknown'
  }
}
