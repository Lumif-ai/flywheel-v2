import { FileText, Building2 } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

const TYPE_ICONS: Record<string, LucideIcon> = {
  'meeting-prep': FileText,
  'company-intel': Building2,
}

export function getTypeIcon(docType: string): LucideIcon {
  return TYPE_ICONS[docType] || FileText
}

export function getTypeLabel(docType: string): string {
  switch (docType) {
    case 'meeting-prep':
      return 'Meeting Prep'
    case 'company-intel':
      return 'Company Intel'
    default:
      return docType.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  }
}

export function formatDate(iso: string, options?: { weekday?: boolean }): string {
  const opts: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }
  if (options?.weekday) opts.weekday = 'long'
  return new Date(iso).toLocaleDateString('en-US', opts)
}

export function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
