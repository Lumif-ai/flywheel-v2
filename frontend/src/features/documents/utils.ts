import { FileText, Building2, Globe, Phone, Briefcase } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

// ---------------------------------------------------------------------------
// Type-specific visual identity
// ---------------------------------------------------------------------------

interface TypeStyle {
  icon: LucideIcon
  label: string
  iconColor: string
  iconBg: string
  badgeBg: string
  badgeText: string
}

const TYPE_STYLES: Record<string, TypeStyle> = {
  'meeting-prep': {
    icon: FileText,
    label: 'Meeting Prep',
    iconColor: '#3B82F6',
    iconBg: 'rgba(59,130,246,0.08)',
    badgeBg: 'rgba(59,130,246,0.1)',
    badgeText: '#2563EB',
  },
  'company-intel': {
    icon: Building2,
    label: 'Company Intel',
    iconColor: '#A855F7',
    iconBg: 'rgba(168,85,247,0.08)',
    badgeBg: 'rgba(168,85,247,0.1)',
    badgeText: '#7C3AED',
  },
  'account-research': {
    icon: Globe,
    label: 'Account Research',
    iconColor: '#14B8A6',
    iconBg: 'rgba(20,184,166,0.08)',
    badgeBg: 'rgba(20,184,166,0.1)',
    badgeText: '#0D9488',
  },
  'call-intelligence': {
    icon: Phone,
    label: 'Call Intelligence',
    iconColor: '#F97316',
    iconBg: 'rgba(249,115,22,0.08)',
    badgeBg: 'rgba(249,115,22,0.1)',
    badgeText: '#EA580C',
  },
}

const DEFAULT_STYLE: TypeStyle = {
  icon: Briefcase,
  label: 'Document',
  iconColor: 'var(--brand-coral)',
  iconBg: 'var(--brand-tint)',
  badgeBg: 'var(--brand-tint)',
  badgeText: 'var(--brand-coral)',
}

export function getTypeStyle(docType: string): TypeStyle {
  return TYPE_STYLES[docType] ?? {
    ...DEFAULT_STYLE,
    label: docType.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
  }
}

// Keep backward compat
export function getTypeIcon(docType: string): LucideIcon {
  return getTypeStyle(docType).icon
}

export function getTypeLabel(docType: string): string {
  return getTypeStyle(docType).label
}

// ---------------------------------------------------------------------------
// Smart title display
// ---------------------------------------------------------------------------

/**
 * Clean up raw document titles into human-friendly display names.
 * e.g. "Company Intel: https://lumif.ai/" → "Lumif.ai"
 *      "Company Intel: DOCUMENT_FILE:7cc6f848-..." → "Company Research"
 *      "Meeting Prep: Acme Corp Q2 Review" → "Acme Corp Q2 Review"
 */
export function displayTitle(
  title: string,
  docType: string,
  metadata?: { companies?: string[]; contacts?: string[] },
): string {
  let cleaned = title

  // Strip doc-type prefix if title starts with the type label
  const typeLabel = getTypeStyle(docType).label
  const prefixPatterns = [
    `${typeLabel}: `,
    `${typeLabel} - `,
    `${docType}: `,
    `${docType} - `,
  ]
  for (const prefix of prefixPatterns) {
    if (cleaned.toLowerCase().startsWith(prefix.toLowerCase())) {
      cleaned = cleaned.slice(prefix.length).trim()
      break
    }
  }

  // Replace DOCUMENT_FILE:uuid patterns
  if (/^DOCUMENT_FILE:[a-f0-9-]+/i.test(cleaned)) {
    // Try to use company name from metadata instead
    const company = metadata?.companies?.[0]
    if (company) return company
    return typeLabel
  }

  // Replace bare URLs with domain name
  if (/^https?:\/\//i.test(cleaned)) {
    try {
      const url = new URL(cleaned)
      let domain = url.hostname.replace(/^www\./, '')
      // Capitalize first letter of each segment
      domain = domain.split('.')[0]
      domain = domain.charAt(0).toUpperCase() + domain.slice(1)
      const company = metadata?.companies?.[0]
      return company || domain
    } catch {
      // Fall through to return cleaned
    }
  }

  // If still empty or just whitespace, fall back to metadata or type label
  if (!cleaned.trim()) {
    const company = metadata?.companies?.[0]
    if (company) return `${typeLabel} — ${company}`
    return typeLabel
  }

  return cleaned
}

// ---------------------------------------------------------------------------
// Clean entity names for display
// ---------------------------------------------------------------------------

/**
 * Clean up raw entity strings (companies/contacts) from metadata.
 * URLs → domain name, UUIDs/hashes → filtered out, raw strings → trimmed.
 */
export function cleanEntity(raw: string): string | null {
  const trimmed = raw.trim()
  if (!trimmed) return null

  // Filter out DOCUMENT_FILE:uuid patterns
  if (/^DOCUMENT_FILE:/i.test(trimmed)) return null

  // Filter out bare UUIDs
  if (/^[a-f0-9-]{36}$/i.test(trimmed)) return null

  // Convert URLs to domain names
  if (/^https?:\/\//i.test(trimmed)) {
    try {
      const url = new URL(trimmed)
      let domain = url.hostname.replace(/^www\./, '')
      // Capitalize: "lumif.ai" → "Lumif.ai"
      domain = domain.charAt(0).toUpperCase() + domain.slice(1)
      return domain
    } catch {
      return null
    }
  }

  return trimmed
}

/**
 * Get clean, displayable entity list from document metadata.
 */
export function getDisplayEntities(
  metadata?: { companies?: string[]; contacts?: string[] },
  max = 2,
): string[] {
  const companies = metadata?.companies ?? []
  const contacts = metadata?.contacts ?? []
  const all = [...companies, ...contacts]
  const cleaned: string[] = []
  const seen = new Set<string>()

  for (const raw of all) {
    const clean = cleanEntity(raw)
    if (clean && !seen.has(clean.toLowerCase())) {
      seen.add(clean.toLowerCase())
      cleaned.push(clean)
      if (cleaned.length >= max) break
    }
  }

  return cleaned
}

// ---------------------------------------------------------------------------
// Date formatting
// ---------------------------------------------------------------------------

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
