import { useState, useRef } from 'react'
import { useProfileRefresh } from '../hooks/useProfileRefresh'
import {
  Building2,
  Package,
  UserCheck,
  TrendingUp,
  Check,
  Upload,
  FileText,
  Globe,
  Clock,
  AlertCircle,
  RefreshCw,
  Shield,
  Layers,
  ClipboardCheck,
  Activity,
  FileEdit,
  Calculator,
  Lock,
  Target,
  AlertTriangle,
  Swords,
  ChevronDown,
  Users,
  Cpu,
  MapPin,
  Zap,
  ExternalLink,
  Pencil,
} from 'lucide-react'
import { colors, spacing, typography } from '@/lib/design-tokens'
import {
  useCompanyProfile,
  useUpdateCategory,
  useLinkProfileFile,
  type ProfileGroup,
  type ProductTab,
} from '../hooks/useCompanyProfile'
import { useProfileCrawl } from '../hooks/useProfileCrawl'
import { LiveCrawl } from '@/features/onboarding/components/LiveCrawl'
import { api } from '@/lib/api'

// ---------------------------------------------------------------------------
// URL helpers
// ---------------------------------------------------------------------------

function normalizeUrl(input: string): string {
  const trimmed = input.trim()
  if (!trimmed) return ''
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  return `https://${trimmed}`
}

function isValidUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

// ---------------------------------------------------------------------------
// Icon map
// ---------------------------------------------------------------------------

const ICON_MAP: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  Building2, Package, UserCheck, TrendingUp, Shield, Layers,
  ClipboardCheck, Activity, FileEdit, Calculator, Lock, Target,
  AlertTriangle, Swords, Users, Cpu, MapPin,
}

function CategoryIcon({ name, className, style }: { name: string; className?: string; style?: React.CSSProperties }) {
  const Icon = ICON_MAP[name] ?? Building2
  return <Icon className={className} style={style} />
}

// ---------------------------------------------------------------------------
// Content helpers
// ---------------------------------------------------------------------------

const PROSE_CATEGORIES = new Set(['positioning', 'value-mapping'])

function isProductCategory(category: string) {
  return category.startsWith('product:')
}

// ---------------------------------------------------------------------------
// About section — structured grid
// ---------------------------------------------------------------------------

function AboutSection({ group }: { group: ProfileGroup }) {
  // Parse the raw content to extract structured fields
  const raw = group.raw_content || ''
  const lines = raw.split('\n').filter((l) => l.trim())

  let description = ''
  const differentiators: string[] = []
  let pricingModel = ''
  let tagline = ''

  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('Company:')) continue
    if (trimmed.startsWith('Tagline:')) {
      tagline = trimmed.replace('Tagline:', '').trim()
    } else if (trimmed.startsWith('Description:')) {
      description = trimmed.replace('Description:', '').trim()
    } else if (trimmed.startsWith('Differentiator:')) {
      differentiators.push(trimmed.replace('Differentiator:', '').trim())
    } else if (trimmed.startsWith('Pricing model:') || trimmed.startsWith('Pricing:')) {
      pricingModel = trimmed.replace(/^Pricing( model)?:/, '').trim()
    } else if (!description && trimmed.length > 30) {
      description = trimmed
    }
  }

  // Fallback: if parsing didn't find structured fields, show as prose
  const hasStructure = description || differentiators.length > 0

  return (
    <div className="space-y-6">
      {/* Tagline */}
      {tagline && (
        <p
          className="text-lg font-medium"
          style={{ color: colors.headingText, lineHeight: '1.5' }}
        >
          {tagline}
        </p>
      )}

      {hasStructure ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* What We Do */}
          {description && (
            <div
              className="rounded-xl p-5"
              style={{ backgroundColor: colors.pageBg, border: `1px solid ${colors.subtleBorder}` }}
            >
              <div className="flex items-center gap-2 mb-3">
                <Building2 className="size-3.5" style={{ color: colors.secondaryText }} />
                <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: colors.secondaryText }}>
                  What We Do
                </span>
              </div>
              <p className="text-sm leading-relaxed" style={{ color: colors.bodyText }}>
                {description}
              </p>
            </div>
          )}

          {/* Differentiators */}
          {differentiators.length > 0 && (
            <div
              className="rounded-xl p-5"
              style={{ backgroundColor: colors.pageBg, border: `1px solid ${colors.subtleBorder}` }}
            >
              <div className="flex items-center gap-2 mb-3">
                <Zap className="size-3.5" style={{ color: colors.secondaryText }} />
                <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: colors.secondaryText }}>
                  Differentiators
                </span>
              </div>
              <ul className="space-y-2">
                {differentiators.map((d, i) => (
                  <li key={i} className="flex gap-2 text-sm leading-relaxed" style={{ color: colors.bodyText }}>
                    <span className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: colors.subtleBorder }} />
                    <span>{d}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Pricing */}
          {pricingModel && (
            <div
              className="rounded-xl p-5"
              style={{ backgroundColor: colors.pageBg, border: `1px solid ${colors.subtleBorder}` }}
            >
              <div className="flex items-center gap-2 mb-3">
                <Calculator className="size-3.5" style={{ color: colors.secondaryText }} />
                <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: colors.secondaryText }}>
                  Pricing
                </span>
              </div>
              <p className="text-sm leading-relaxed" style={{ color: colors.bodyText }}>
                {pricingModel}
              </p>
            </div>
          )}
        </div>
      ) : (
        // Fallback prose
        <p className="text-sm leading-relaxed" style={{ color: colors.bodyText }}>
          {raw}
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Product card (expandable)
// ---------------------------------------------------------------------------

function ProductCard({ tab, editMode: _editMode }: { tab: ProductTab; editMode: boolean }) {
  const [expanded, setExpanded] = useState(false)

  // Extract overview description from the first section
  const overviewSection = tab.sections.find((s) => s.label === 'Overview')
  const icpSection = tab.sections.find((s) => s.label === 'Target Customers')
  const painSection = tab.sections.find((s) => s.label === 'Pain Points Solved')
  const compSection = tab.sections.find((s) => s.label === 'Competitors')

  // Parse overview to get description
  let description = ''
  let valueProps: string[] = []
  if (overviewSection) {
    const lines = overviewSection.raw_content.split('\n').filter((l) => l.trim())
    for (const line of lines) {
      const trimmed = line.trim()
      if (trimmed.startsWith('Value Proposition:')) {
        valueProps.push(trimmed.replace('Value Proposition:', '').trim())
      } else if (/^[-•*]\s/.test(trimmed)) {
        const clean = trimmed.replace(/^[-•*]\s*/, '')
        if (clean.startsWith('Value Proposition:')) {
          valueProps.push(clean.replace('Value Proposition:', '').trim())
        } else if (clean.length > 30) {
          if (!description) description = clean
        }
      } else if (trimmed.length > 30 && trimmed !== tab.name) {
        if (!description) description = trimmed
      }
    }
  }

  return (
    <div
      className="rounded-xl border overflow-hidden transition-all duration-200"
      style={{
        backgroundColor: colors.cardBg,
        borderColor: expanded ? 'rgba(233,77,53,0.2)' : colors.subtleBorder,
        boxShadow: expanded ? '0 4px 14px rgba(233,77,53,0.06)' : '0 1px 3px rgba(0,0,0,0.04)',
      }}
    >
      {/* Card header — always visible */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-start gap-4 p-5 text-left transition-colors hover:bg-gray-50/50"
      >
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 mt-0.5"
          style={{ backgroundColor: 'rgba(233,77,53,0.08)' }}
        >
          <Package className="size-5" style={{ color: colors.brandCoral }} />
        </div>
        <div className="flex-1 min-w-0">
          <h3
            className="font-semibold text-base"
            style={{ color: colors.headingText }}
          >
            {tab.name}
          </h3>
          {description && (
            <p
              className="text-sm mt-1 line-clamp-2"
              style={{ color: colors.bodyText, lineHeight: '1.6' }}
            >
              {description}
            </p>
          )}
          {!expanded && icpSection && icpSection.items.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {icpSection.items.slice(0, 3).map((item, i) => (
                <span
                  key={i}
                  className="text-xs px-2.5 py-1 rounded-full"
                  style={{ backgroundColor: colors.brandTint, color: colors.brandCoral }}
                >
                  {item}
                </span>
              ))}
              {icpSection.items.length > 3 && (
                <span className="text-xs px-2.5 py-1 rounded-full" style={{ color: colors.secondaryText }}>
                  +{icpSection.items.length - 3}
                </span>
              )}
            </div>
          )}
        </div>
        <ChevronDown
          className="size-5 shrink-0 mt-1 transition-transform duration-200"
          style={{
            color: colors.secondaryText,
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
          }}
        />
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t px-5 pb-5 pt-4 space-y-5" style={{ borderColor: colors.subtleBorder }}>
          {/* Value proposition highlight */}
          {valueProps.length > 0 && (
            <div
              className="rounded-lg p-4"
              style={{ backgroundColor: colors.pageBg, border: `1px solid ${colors.subtleBorder}` }}
            >
              <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: colors.secondaryText }}>
                Value Proposition
              </span>
              <p className="text-sm mt-1.5 leading-relaxed" style={{ color: colors.bodyText }}>
                {valueProps[0]}
              </p>
            </div>
          )}

          {/* Sub-sections in 2-col grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {icpSection && icpSection.items.length > 0 && (
              <div>
                <h4 className="flex items-center gap-2 text-sm font-semibold mb-2" style={{ color: colors.headingText }}>
                  <UserCheck className="size-3.5" style={{ color: colors.secondaryText }} />
                  Target Customers
                </h4>
                <ul className="space-y-1.5">
                  {icpSection.items.map((item, i) => (
                    <li key={i} className="flex gap-2 text-sm" style={{ color: colors.bodyText }}>
                      <span className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: colors.subtleBorder }} />
                      <span>{item.replace(/^[-•*]\s*/, '')}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {painSection && painSection.items.length > 0 && (
              <div>
                <h4 className="flex items-center gap-2 text-sm font-semibold mb-2" style={{ color: colors.headingText }}>
                  <AlertTriangle className="size-3.5" style={{ color: colors.secondaryText }} />
                  Pain Points Solved
                </h4>
                <ul className="space-y-1.5">
                  {painSection.items.map((item, i) => (
                    <li key={i} className="flex gap-2 text-sm" style={{ color: colors.bodyText }}>
                      <span className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: colors.subtleBorder }} />
                      <span>{item.replace(/^[-•*]\s*/, '')}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {compSection && compSection.items.length > 0 && (
              <div>
                <h4 className="flex items-center gap-2 text-sm font-semibold mb-2" style={{ color: colors.headingText }}>
                  <Swords className="size-3.5" style={{ color: colors.secondaryText }} />
                  Competitors
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {compSection.items.map((item, i) => (
                    <span
                      key={i}
                      className="text-xs px-2.5 py-1 rounded-full"
                      style={{ backgroundColor: colors.pageBg, color: colors.bodyText, border: `1px solid ${colors.subtleBorder}` }}
                    >
                      {item.replace(/^[-•*]\s*/, '')}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Leadership cards
// ---------------------------------------------------------------------------

function LeadershipCards({ items }: { items: string[] }) {
  if (items.length === 0) return null

  // Parse "Name — Title (LinkedIn URL)" format
  const people = items.map((item) => {
    const clean = item.replace(/^[-•*]\s*/, '')
    // Match: Name — Title (URL) or Name - Title (URL)
    const match = clean.match(/^(.+?)\s*[—–-]\s*(.+?)(?:\s*\(?(https?:\/\/[^\s)]+)\)?)?$/)
    if (match) {
      return { name: match[1].trim(), title: match[2].trim(), linkedin: match[3] || null }
    }
    // Fallback: just a name
    return { name: clean, title: '', linkedin: null }
  })

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Users className="size-4" style={{ color: colors.secondaryText }} />
        <h3 className="text-sm font-semibold" style={{ color: colors.headingText }}>
          Leadership
        </h3>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {people.map((person, i) => (
          <div
            key={i}
            className="flex items-center gap-3 p-3 rounded-lg"
            style={{ backgroundColor: colors.pageBg, border: `1px solid ${colors.subtleBorder}` }}
          >
            <div
              className="w-9 h-9 rounded-full flex items-center justify-center shrink-0 text-sm font-semibold"
              style={{ backgroundColor: 'rgba(233,77,53,0.08)', color: colors.brandCoral }}
            >
              {person.name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-medium truncate" style={{ color: colors.headingText }}>
                  {person.name}
                </span>
                {person.linkedin && (
                  <a
                    href={person.linkedin}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 hover:opacity-70 transition-opacity"
                    title="LinkedIn"
                  >
                    <ExternalLink className="size-3" style={{ color: colors.secondaryText }} />
                  </a>
                )}
              </div>
              {person.title && (
                <span className="text-xs truncate block" style={{ color: colors.secondaryText }}>
                  {person.title}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Compact list section (for ICP, Market, Competitive)
// ---------------------------------------------------------------------------

function CompactSection({
  icon,
  iconColor,
  label,
  items,
  style: displayStyle,
}: {
  icon: React.ReactNode
  iconColor: string
  label: string
  items: string[]
  style?: 'pills' | 'list'
}) {
  if (items.length === 0) return null
  const usePills = displayStyle === 'pills'

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="text-sm font-semibold" style={{ color: colors.headingText }}>
          {label}
        </h3>
        <span className="text-xs px-1.5 py-0.5 rounded-full" style={{ backgroundColor: colors.brandTint, color: colors.secondaryText }}>
          {items.length}
        </span>
      </div>
      {usePills ? (
        <div className="flex flex-wrap gap-2">
          {items.map((item, i) => (
            <span
              key={i}
              className="text-sm px-3 py-1.5 rounded-full border"
              style={{ borderColor: colors.subtleBorder, color: colors.bodyText, backgroundColor: colors.cardBg }}
            >
              {item.replace(/^[-•*]\s*/, '')}
            </span>
          ))}
        </div>
      ) : (
        <ul className="space-y-1.5">
          {items.map((item, i) => (
            <li key={i} className="flex gap-2 text-sm" style={{ color: colors.bodyText }}>
              <span className="mt-1.5 w-1 h-1 rounded-full shrink-0" style={{ backgroundColor: iconColor }} />
              <span>{item.replace(/^[-•*]\s*/, '')}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Company details (key-value pairs)
// ---------------------------------------------------------------------------

function CompanyDetailsSection({ group }: { group: ProfileGroup }) {
  const raw = group.raw_content || ''
  const entries: Array<{ key: string; value: string; isLink?: boolean }> = []

  for (const line of raw.split('\n').filter((l) => l.trim())) {
    const trimmed = line.trim().replace(/^[-•*]\s*/, '')
    const colonIdx = trimmed.indexOf(':')
    if (colonIdx > 0 && colonIdx < 40) {
      const key = trimmed.slice(0, colonIdx).trim()
      const value = trimmed.slice(colonIdx + 1).trim()
      const isLink = /^https?:\/\//.test(value)
      entries.push({ key, value, isLink })
    }
  }

  if (entries.length === 0) return null

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3">
      {entries.map((e, i) => (
        <div key={i} className="flex flex-col">
          <span className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>
            {e.key}
          </span>
          {e.isLink ? (
            <a
              href={e.value}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm flex items-center gap-1 hover:underline mt-0.5"
              style={{ color: colors.brandCoral }}
            >
              {e.value.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')}
              <ExternalLink className="size-3" />
            </a>
          ) : (
            <span className="text-sm mt-0.5" style={{ color: colors.headingText }}>
              {e.value}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inline editor overlay
// ---------------------------------------------------------------------------

function InlineEditor({ group, onClose }: { group: ProfileGroup; onClose: () => void }) {
  const [content, setContent] = useState(group.raw_content)
  const [saving, setSaving] = useState(false)
  const updateCategory = useUpdateCategory()

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateCategory.mutateAsync({ entry_id: group.entry_id, content })
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-3 mt-4 pt-4 border-t" style={{ borderColor: colors.subtleBorder }}>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={Math.min(12, Math.max(4, content.split('\n').length + 1))}
        className="w-full rounded-lg border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 resize-y font-mono"
        style={{
          borderColor: colors.subtleBorder,
          color: colors.bodyText,
          backgroundColor: colors.pageBg,
          lineHeight: '1.6',
          // @ts-expect-error CSS variable
          '--tw-ring-color': colors.brandCoral,
        }}
      />
      <div className="flex items-center gap-2">
        <button
          onClick={handleSave}
          disabled={saving || content === group.raw_content}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-white transition-opacity disabled:opacity-50"
          style={{ backgroundColor: colors.brandCoral }}
        >
          {saving ? <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <Check className="size-3.5" />}
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button
          onClick={onClose}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium"
          style={{ color: colors.secondaryText, backgroundColor: colors.brandTint }}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Generic section card (for edit-mode fallback)
// ---------------------------------------------------------------------------

function SectionCard({ group, editMode }: { group: ProfileGroup; editMode: boolean }) {
  const [editing, setEditing] = useState(false)
  const isProse = PROSE_CATEGORIES.has(group.category)

  return (
    <div>
      {!editing ? (
        isProse ? (
          <div className="space-y-2">
            {group.raw_content.split(/\n{2,}/).filter((p) => p.trim()).map((para, i) => (
              <p key={i} className="text-sm leading-relaxed" style={{ color: colors.bodyText }}>
                {para.split('\n').filter((l) => l.trim()).join(' ')}
              </p>
            ))}
          </div>
        ) : (
          <ul className="space-y-1.5">
            {group.items.map((item, i) => (
              <li key={i} className="flex gap-2 text-sm" style={{ color: colors.bodyText }}>
                <span className="mt-1.5 w-1 h-1 rounded-full shrink-0" style={{ backgroundColor: colors.brandCoral }} />
                <span>{item.replace(/^[-•*]\s*/, '')}</span>
              </li>
            ))}
          </ul>
        )
      ) : null}
      {editMode && !editing && (
        <button
          onClick={() => setEditing(true)}
          className="mt-2 text-xs flex items-center gap-1 hover:underline"
          style={{ color: colors.secondaryText }}
        >
          <Pencil className="size-3" /> Edit
        </button>
      )}
      {editing && <InlineEditor group={group} onClose={() => setEditing(false)} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function ProfileSkeleton() {
  return (
    <div className="space-y-8">
      <div className="h-8 w-48 rounded bg-gray-200 animate-pulse" />
      <div className="grid grid-cols-3 gap-5">
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-xl p-5 animate-pulse" style={{ backgroundColor: 'rgba(0,0,0,0.02)' }}>
            <div className="h-4 w-20 rounded bg-gray-200 mb-3" />
            <div className="space-y-2">
              <div className="h-3 w-full rounded bg-gray-100" />
              <div className="h-3 w-4/5 rounded bg-gray-100" />
            </div>
          </div>
        ))}
      </div>
      {[1, 2].map((i) => (
        <div key={i} className="rounded-xl border p-5 animate-pulse" style={{ borderColor: colors.subtleBorder }}>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-gray-200" />
            <div className="h-5 w-48 rounded bg-gray-200" />
          </div>
          <div className="h-3 w-full rounded bg-gray-100 mb-2" />
          <div className="h-3 w-3/4 rounded bg-gray-100" />
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Uploaded files
// ---------------------------------------------------------------------------

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function UploadedFilesSection({
  uploadedFiles,
  onAnalyzeStarted,
}: {
  uploadedFiles: Array<{ id: string; filename: string; mimetype: string; size_bytes: number }>
  onAnalyzeStarted?: (runId: string) => void
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const linkFile = useLinkProfileFile()

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    setUploading(true)
    try {
      const { token } = await import('@/stores/auth').then((m) => ({ token: m.useAuthStore.getState().token }))
      const fileIds: string[] = []
      for (const file of Array.from(files)) {
        const formData = new FormData()
        formData.append('file', file)
        const res = await fetch('/api/v1/files/upload', {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        })
        if (!res.ok) throw new Error(`Upload failed for ${file.name}`)
        const data = await res.json() as { id: string }
        await linkFile.mutateAsync(data.id)
        fileIds.push(data.id)
      }
      if (fileIds.length > 0) {
        const result = await api.post<{ run_id: string }>('/profile/refresh', {})
        onAnalyzeStarted?.(result.run_id)
      }
    } catch (err) {
      console.error('File upload failed:', err)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <FileText className="size-4" style={{ color: colors.secondaryText }} />
          <h3 className="text-sm font-semibold" style={{ color: colors.headingText }}>
            Source Documents
          </h3>
          {uploadedFiles.length > 0 && (
            <span className="text-xs px-1.5 py-0.5 rounded-full" style={{ backgroundColor: colors.brandTint, color: colors.secondaryText }}>
              {uploadedFiles.length}
            </span>
          )}
        </div>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-opacity disabled:opacity-60"
          style={{ backgroundColor: colors.brandTint, color: colors.brandCoral }}
        >
          {uploading ? (
            <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            <Upload className="size-3" />
          )}
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
        <input ref={fileInputRef} type="file" className="hidden" accept=".pdf,.doc,.docx,.txt,.md" multiple onChange={handleFileChange} />
      </div>

      {uploadedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {uploadedFiles.map((file) => (
            <div
              key={file.id}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border"
              style={{ borderColor: colors.subtleBorder, color: colors.bodyText }}
            >
              <FileText className="size-3 shrink-0" style={{ color: colors.secondaryText }} />
              <span className="truncate max-w-[160px]">{file.filename}</span>
              <span style={{ color: colors.secondaryText }}>{formatFileSize(file.size_bytes)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state panels
// ---------------------------------------------------------------------------

function CrawlPanel({ defaultUrl }: { defaultUrl: string }) {
  const crawl = useProfileCrawl()
  const [url, setUrl] = useState(defaultUrl)
  const [urlError, setUrlError] = useState<string | null>(null)

  const handleAnalyze = () => {
    const normalized = normalizeUrl(url)
    if (!normalized) return
    if (!isValidUrl(normalized)) { setUrlError('Please enter a valid URL'); return }
    setUrlError(null)
    crawl.startCrawl(normalized)
  }

  if (crawl.phase === 'crawling' || crawl.phase === 'complete') {
    return (
      <div className="rounded-xl border shadow-sm overflow-hidden p-6" style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}>
        <LiveCrawl crawlItems={crawl.crawlItems} crawlTotal={crawl.crawlTotal} crawlStatus={crawl.crawlStatus} isComplete={crawl.phase === 'complete'} onContinue={() => {}} />
      </div>
    )
  }

  if (crawl.phase === 'error') {
    return (
      <div className="rounded-xl border shadow-sm overflow-hidden p-8 text-center" style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}>
        <AlertCircle className="size-10 mx-auto mb-3" style={{ color: '#EF4444' }} />
        <p className="text-sm mb-4" style={{ color: colors.bodyText }}>{crawl.error?.message ?? 'Something went wrong'}</p>
        {crawl.error?.retryable && (
          <button onClick={crawl.retry} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white" style={{ backgroundColor: colors.brandCoral }}>
            <RefreshCw className="size-3.5" /> Try again
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="rounded-xl border shadow-sm overflow-hidden p-8" style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}>
      <div className="max-w-lg mx-auto text-center">
        <Globe className="size-10 mx-auto mb-4" style={{ color: colors.brandCoral, opacity: 0.8 }} />
        <h2 className="font-semibold mb-2" style={{ fontSize: typography.sectionTitle.size, color: colors.headingText }}>Populate your company profile</h2>
        <p className="text-sm mb-6" style={{ color: colors.secondaryText }}>Enter your company website to automatically discover positioning, products, competitors, and more.</p>
        <div className="flex gap-2">
          <input type="url" value={url} onChange={(e) => { setUrl(e.target.value); setUrlError(null) }} onKeyDown={(e) => { if (e.key === 'Enter') handleAnalyze() }} placeholder="https://yourcompany.com"
            className="flex-1 rounded-lg border px-4 py-2.5 text-sm focus:outline-none focus:ring-2"
            style={{ borderColor: urlError ? '#EF4444' : colors.subtleBorder, color: colors.bodyText, backgroundColor: colors.pageBg, '--tw-ring-color': colors.brandCoral } as React.CSSProperties} />
          <button onClick={handleAnalyze} disabled={!url.trim()} className="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-opacity disabled:opacity-50" style={{ backgroundColor: colors.brandCoral }}>Analyze</button>
        </div>
        {urlError && <p className="text-xs mt-2 text-left" style={{ color: '#EF4444' }}>{urlError}</p>}
      </div>
    </div>
  )
}

function DocumentAnalyzePanel({ onRunStarted }: { onRunStarted?: (runId: string) => void }) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)
  const linkFile = useLinkProfileFile()

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setAnalyzing(true); setAnalyzeError(null)
    try {
      const formData = new FormData(); formData.append('file', file)
      const { token } = await import('@/stores/auth').then((m) => ({ token: m.useAuthStore.getState().token }))
      const uploadRes = await fetch('/api/v1/files/upload', { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: formData })
      if (!uploadRes.ok) throw new Error('Upload failed')
      const uploadData = (await uploadRes.json()) as { id: string }
      await linkFile.mutateAsync(uploadData.id)
      const result = await api.post<{ run_id: string }>('/profile/analyze-document', { file_id: uploadData.id })
      onRunStarted?.(result.run_id)
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : 'Analysis failed')
    } finally {
      setAnalyzing(false); if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className="rounded-xl border shadow-sm overflow-hidden p-8" style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}>
      <div className="max-w-lg mx-auto text-center">
        <FileText className="size-10 mx-auto mb-4" style={{ color: colors.brandCoral, opacity: 0.8 }} />
        <h2 className="font-semibold mb-2" style={{ fontSize: typography.sectionTitle.size, color: colors.headingText }}>Or upload a company document</h2>
        <p className="text-sm mb-6" style={{ color: colors.secondaryText }}>Upload a PDF, Word doc, or text file containing company information.</p>
        <button onClick={() => fileInputRef.current?.click()} disabled={analyzing}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-opacity disabled:opacity-60" style={{ backgroundColor: colors.brandCoral }}>
          {analyzing ? <><span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Analyzing...</> : <><Upload className="size-4" />Upload &amp; Analyze</>}
        </button>
        <input ref={fileInputRef} type="file" className="hidden" accept=".pdf,.doc,.docx,.txt,.md" onChange={handleFileChange} />
        {analyzeError && <p className="text-xs mt-3" style={{ color: '#EF4444' }}>{analyzeError}</p>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function CompanyProfilePage() {
  const [resetConfirm, setResetConfirm] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const { data: profile, isLoading, isError } = useCompanyProfile()
  const refresh = useProfileRefresh()

  if (isLoading) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: colors.pageBg, padding: `${spacing.section} ${spacing.pageDesktop}` }}>
        <div style={{ maxWidth: spacing.maxGrid, margin: '0 auto' }}>
          <ProfileSkeleton />
        </div>
      </div>
    )
  }

  if (isError || !profile) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: colors.pageBg }}>
        <div className="text-center space-y-2">
          <p style={{ color: colors.bodyText }}>Could not load company profile.</p>
          <button onClick={() => window.location.reload()} className="text-sm underline" style={{ color: colors.brandCoral }}>Retry</button>
        </div>
      </div>
    )
  }

  const hasGroups = profile.groups.length > 0 || (profile.product_tabs && profile.product_tabs.length > 0)
  const formattedLastUpdated = profile.last_updated
    ? new Date(profile.last_updated).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : null

  const defaultCrawlUrl = profile.domain ? `https://${profile.domain}` : ''
  const regularGroups = profile.groups.filter((g) => !isProductCategory(g.category))
  const aboutGroup = regularGroups.find((g) => g.category === 'positioning')
  const otherGroups = regularGroups.filter((g) => g.category !== 'positioning')

  // Categorize supporting sections
  const icpGroup = otherGroups.find((g) => g.category === 'icp-profiles')
  const marketGroup = otherGroups.find((g) => g.category === 'market-taxonomy')
  const competitiveGroup = otherGroups.find((g) => g.category === 'competitive-intel')
  const companyDetailsGroup = otherGroups.find((g) => g.category === 'company-details')
  const leadershipGroup = otherGroups.find((g) => g.category === 'leadership')
  const techGroup = otherGroups.find((g) => g.category === 'tech-stack')
  const remainingGroups = otherGroups.filter((g) =>
    !['icp-profiles', 'market-taxonomy', 'competitive-intel', 'company-details', 'leadership', 'tech-stack'].includes(g.category)
  )

  return (
    <div className="min-h-screen" style={{ backgroundColor: colors.pageBg }}>
      <div className="mx-auto" style={{ maxWidth: spacing.maxGrid, padding: `${spacing.section} ${spacing.pageDesktop}` }}>

        {/* ---------------------------------------------------------------- */}
        {/* Page Header                                                      */}
        {/* ---------------------------------------------------------------- */}
        <div className="flex items-start justify-between mb-10">
          <div>
            <h1
              className="font-bold"
              style={{
                fontSize: '30px',
                fontWeight: 700,
                letterSpacing: '-0.02em',
                color: colors.headingText,
                lineHeight: '1.2',
              }}
            >
              {profile.company_name ?? 'Your Company'}
            </h1>
            <div className="flex items-center gap-4 mt-2">
              {profile.domain && (
                <a
                  href={`https://${profile.domain}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-sm hover:underline"
                  style={{ color: colors.secondaryText }}
                >
                  <Globe className="size-3.5" />
                  {profile.domain}
                </a>
              )}
              {formattedLastUpdated && (
                <div className="flex items-center gap-1.5">
                  <Clock className="size-3.5" style={{ color: colors.secondaryText }} />
                  <span className="text-sm" style={{ color: colors.secondaryText }}>
                    Updated {formattedLastUpdated}
                  </span>
                </div>
              )}
            </div>
          </div>

          {hasGroups && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setEditMode((v) => !v)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors"
                style={{
                  backgroundColor: editMode ? 'rgba(233,77,53,0.06)' : colors.cardBg,
                  borderColor: editMode ? 'rgba(233,77,53,0.2)' : colors.subtleBorder,
                  color: editMode ? colors.brandCoral : colors.headingText,
                }}
              >
                <Pencil className={`size-3.5 ${editMode ? '' : ''}`} />
                {editMode ? 'Done Editing' : 'Edit'}
              </button>
              <button
                onClick={() => refresh.startRefresh()}
                disabled={refresh.phase === 'refreshing'}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors"
                style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder, color: colors.headingText }}
              >
                <RefreshCw className={`size-3.5 ${refresh.phase === 'refreshing' ? 'animate-spin' : ''}`} />
                Refresh
              </button>
              <button
                onClick={() => setResetConfirm(true)}
                disabled={refresh.phase === 'refreshing'}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border transition-colors"
                style={{ borderColor: 'rgba(239,68,68,0.2)', color: '#EF4444' }}
              >
                Reset
              </button>
            </div>
          )}
        </div>

        {/* Reset confirmation */}
        {resetConfirm && (
          <div className="flex items-center justify-between px-5 py-3.5 rounded-xl mb-6" style={{ backgroundColor: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)' }}>
            <span className="text-sm" style={{ color: colors.bodyText }}>This will clear your current profile and rebuild from scratch. Continue?</span>
            <div className="flex items-center gap-2">
              <button onClick={() => { setResetConfirm(false); void refresh.startReset() }} className="px-4 py-1.5 rounded-lg text-sm font-medium text-white" style={{ backgroundColor: '#EF4444' }}>Confirm Reset</button>
              <button onClick={() => setResetConfirm(false)} className="px-4 py-1.5 rounded-lg text-sm font-medium" style={{ color: colors.secondaryText, backgroundColor: colors.brandTint }}>Cancel</button>
            </div>
          </div>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* SSE streaming overlay                                            */}
        {/* ---------------------------------------------------------------- */}
        {(refresh.phase === 'refreshing' || refresh.phase === 'complete') ? (
          <div className="rounded-xl border shadow-sm overflow-hidden p-6" style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}>
            <LiveCrawl crawlItems={refresh.crawlItems} crawlTotal={refresh.crawlTotal} crawlStatus={refresh.crawlStatus} isComplete={refresh.phase === 'complete'} onContinue={() => refresh.dismiss()} />
          </div>

        ) : !hasGroups ? (
          /* ---------------------------------------------------------------- */
          /* Empty state                                                      */
          /* ---------------------------------------------------------------- */
          <div className="space-y-4">
            <CrawlPanel defaultUrl={defaultCrawlUrl} />
            <div className="flex items-center gap-4 px-4">
              <div className="flex-1 h-px" style={{ backgroundColor: colors.subtleBorder }} />
              <span className="text-xs font-medium" style={{ color: colors.secondaryText }}>or</span>
              <div className="flex-1 h-px" style={{ backgroundColor: colors.subtleBorder }} />
            </div>
            <DocumentAnalyzePanel onRunStarted={(runId) => refresh.startFromRunId(runId)} />
            <UploadedFilesSection uploadedFiles={profile.uploaded_files} onAnalyzeStarted={(runId) => refresh.startFromRunId(runId)} />
          </div>

        ) : (
          /* ---------------------------------------------------------------- */
          /* Profile body                                                     */
          /* ---------------------------------------------------------------- */
          <div className="space-y-10">

            {/* === ABOUT === */}
            {aboutGroup && (
              <section>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold" style={{ color: colors.headingText }}>
                    About
                  </h2>
                  {editMode && aboutGroup && (
                    <span className="text-xs" style={{ color: colors.secondaryText }}>
                      Edit raw content below
                    </span>
                  )}
                </div>
                {editMode ? (
                  <SectionCard group={aboutGroup} editMode={editMode} />
                ) : (
                  <AboutSection group={aboutGroup} />
                )}
              </section>
            )}

            {/* === PRODUCTS === */}
            {profile.product_tabs && profile.product_tabs.length > 0 && (
              <section>
                <div className="flex items-center gap-3 mb-5">
                  <h2 className="text-lg font-semibold" style={{ color: colors.headingText }}>
                    Products
                  </h2>
                  <span
                    className="text-xs px-2 py-0.5 rounded-full font-medium"
                    style={{ backgroundColor: colors.brandTint, color: colors.brandCoral }}
                  >
                    {profile.product_tabs.length}
                  </span>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {profile.product_tabs.map((tab) => (
                    <ProductCard key={tab.slug} tab={tab} editMode={editMode} />
                  ))}
                </div>
              </section>
            )}

            {/* === MARKET CONTEXT === */}
            {(icpGroup || marketGroup || competitiveGroup) && (
              <section
                className="rounded-xl border p-6"
                style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
              >
                <h2 className="text-lg font-semibold mb-6" style={{ color: colors.headingText }}>
                  Market Context
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                  {icpGroup && (
                    <CompactSection
                      icon={<UserCheck className="size-4" style={{ color: colors.secondaryText }} />}
                      iconColor={colors.subtleBorder}
                      label="Target Customers"
                      items={icpGroup.items}
                      style="list"
                    />
                  )}
                  {marketGroup && (
                    <CompactSection
                      icon={<TrendingUp className="size-4" style={{ color: colors.secondaryText }} />}
                      iconColor={colors.subtleBorder}
                      label="Industries"
                      items={marketGroup.items}
                      style="pills"
                    />
                  )}
                  {competitiveGroup && (
                    <CompactSection
                      icon={<Swords className="size-4" style={{ color: colors.secondaryText }} />}
                      iconColor={colors.subtleBorder}
                      label="Competitors"
                      items={competitiveGroup.items}
                      style="pills"
                    />
                  )}
                </div>
                {editMode && (
                  <div className="mt-4 pt-4 border-t space-y-3" style={{ borderColor: colors.subtleBorder }}>
                    {icpGroup && <SectionCard group={icpGroup} editMode={editMode} />}
                    {marketGroup && <SectionCard group={marketGroup} editMode={editMode} />}
                    {competitiveGroup && <SectionCard group={competitiveGroup} editMode={editMode} />}
                  </div>
                )}
              </section>
            )}

            {/* === COMPANY INFO === */}
            {(companyDetailsGroup || leadershipGroup || techGroup) && (
              <section
                className="rounded-xl border p-6"
                style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
              >
                <h2 className="text-lg font-semibold mb-6" style={{ color: colors.headingText }}>
                  Company Info
                </h2>

                <div className="space-y-6">
                  {companyDetailsGroup && (
                    <div>
                      <CompanyDetailsSection group={companyDetailsGroup} />
                      {editMode && <SectionCard group={companyDetailsGroup} editMode={editMode} />}
                    </div>
                  )}

                  {leadershipGroup && (
                    <div className="pt-4 border-t" style={{ borderColor: colors.subtleBorder }}>
                      <LeadershipCards items={leadershipGroup.items} />
                    </div>
                  )}

                  {techGroup && (
                    <div className="pt-4 border-t" style={{ borderColor: colors.subtleBorder }}>
                      <CompactSection
                        icon={<Cpu className="size-4" style={{ color: colors.secondaryText }} />}
                        iconColor={colors.subtleBorder}
                        label="Tech Stack"
                        items={techGroup.items}
                        style="pills"
                      />
                    </div>
                  )}
                </div>

                {editMode && (leadershipGroup || techGroup) && (
                  <div className="mt-4 pt-4 border-t space-y-3" style={{ borderColor: colors.subtleBorder }}>
                    {leadershipGroup && <SectionCard group={leadershipGroup} editMode={editMode} />}
                    {techGroup && <SectionCard group={techGroup} editMode={editMode} />}
                  </div>
                )}
              </section>
            )}

            {/* === REMAINING SECTIONS === */}
            {remainingGroups.map((group) => (
              <section
                key={group.category}
                className="rounded-xl border p-6"
                style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
              >
                <div className="flex items-center gap-3 mb-4">
                  <CategoryIcon name={group.icon} className="size-4" style={{ color: colors.brandCoral }} />
                  <h2 className="text-lg font-semibold" style={{ color: colors.headingText }}>{group.label}</h2>
                </div>
                <SectionCard group={group} editMode={editMode} />
              </section>
            ))}

            {/* === SOURCE DOCUMENTS === */}
            <section
              className="rounded-xl border p-6"
              style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
            >
              <UploadedFilesSection
                uploadedFiles={profile.uploaded_files}
                onAnalyzeStarted={(runId) => refresh.startFromRunId(runId)}
              />
            </section>
          </div>
        )}
      </div>
    </div>
  )
}
