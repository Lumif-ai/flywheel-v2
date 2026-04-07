import { useState, useRef } from 'react'
import { useProfileRefresh } from '../hooks/useProfileRefresh'
import {
  Building2,
  Package,
  UserCheck,
  TrendingUp,
  Edit3,
  Check,
  X,
  Upload,
  Download,
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
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
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

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  Building2, Package, UserCheck, TrendingUp, Shield, Layers,
  ClipboardCheck, Activity, FileEdit, Calculator, Lock, Target,
  AlertTriangle, Swords,
}

function CategoryIcon({ name, className }: { name: string; className?: string }) {
  const Icon = ICON_MAP[name] ?? Building2
  return <Icon className={className} />
}

// ---------------------------------------------------------------------------
// Content rendering helpers
// ---------------------------------------------------------------------------

/** Categories that should render as flowing prose paragraphs */
const PROSE_CATEGORIES = new Set(['positioning', 'value-mapping'])

/** Categories that are product modules */
function isProductCategory(category: string) {
  return category.startsWith('product:')
}

/**
 * Render raw_content as readable paragraphs.
 * Splits on double-newlines for paragraph breaks.
 * Within a paragraph, lines starting with - or • become bullets.
 */
function ProseContent({ content }: { content: string }) {
  const paragraphs = content.split(/\n{2,}/).filter((p) => p.trim())

  return (
    <div className="space-y-3">
      {paragraphs.map((para, i) => {
        const lines = para.split('\n').filter((l) => l.trim())
        const isBulletBlock = lines.every((l) => /^[-•*]\s/.test(l.trim()))

        if (isBulletBlock) {
          return (
            <ul key={i} className="space-y-1.5 ml-1">
              {lines.map((line, j) => (
                <li
                  key={j}
                  className="flex gap-2 text-sm leading-relaxed"
                  style={{ color: colors.bodyText }}
                >
                  <span
                    className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0"
                    style={{ backgroundColor: colors.brandCoral }}
                  />
                  <span>{line.replace(/^[-•*]\s*/, '')}</span>
                </li>
              ))}
            </ul>
          )
        }

        return (
          <p
            key={i}
            className="text-sm leading-relaxed"
            style={{ color: colors.bodyText }}
          >
            {lines.join(' ')}
          </p>
        )
      })}
    </div>
  )
}

/**
 * Render items as a clean bullet list (for non-prose sections).
 */
function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1.5 ml-1">
      {items.map((item, i) => (
        <li
          key={i}
          className="flex gap-2 text-sm leading-relaxed"
          style={{ color: colors.bodyText }}
        >
          <span
            className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0"
            style={{ backgroundColor: colors.brandCoral }}
          />
          <span>{item.replace(/^[-•*]\s*/, '')}</span>
        </li>
      ))}
    </ul>
  )
}

/**
 * Product card: structured layout with capability bullets.
 */
function ProductContent({ group }: { group: ProfileGroup }) {
  const paragraphs = group.raw_content.split(/\n{2,}/).filter((p) => p.trim())
  // First paragraph-like block that isn't a bullet = description
  let description = ''
  const bullets: string[] = []

  for (const para of paragraphs) {
    const lines = para.split('\n').filter((l) => l.trim())
    for (const line of lines) {
      if (/^[-•*]\s/.test(line.trim())) {
        bullets.push(line.replace(/^[-•*]\s*/, '').trim())
      } else if (!description && line.trim().length > 20) {
        description = description ? `${description} ${line.trim()}` : line.trim()
      } else {
        bullets.push(line.trim())
      }
    }
  }

  return (
    <div className="space-y-3">
      {description && (
        <p className="text-sm leading-relaxed" style={{ color: colors.bodyText }}>
          {description}
        </p>
      )}
      {bullets.length > 0 && (
        <ul className="space-y-1.5 ml-1">
          {bullets.map((b, i) => (
            <li
              key={i}
              className="flex gap-2 text-sm leading-relaxed"
              style={{ color: colors.bodyText }}
            >
              <span
                className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0"
                style={{ backgroundColor: colors.brandCoral }}
              />
              <span>{b}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function ProfileSkeleton() {
  return (
    <div className="space-y-6">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="rounded-xl border p-6 animate-pulse"
          style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="w-9 h-9 rounded-lg bg-gray-200" />
            <div className="h-5 w-40 rounded bg-gray-200" />
          </div>
          <div className="space-y-2">
            <div className="h-4 w-full rounded bg-gray-100" />
            <div className="h-4 w-5/6 rounded bg-gray-100" />
            <div className="h-4 w-3/4 rounded bg-gray-100" />
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section card (summary view with inline edit)
// ---------------------------------------------------------------------------

interface SectionCardProps {
  group: ProfileGroup
}

function SectionCard({ group }: SectionCardProps) {
  const [editing, setEditing] = useState(false)
  const [localContent, setLocalContent] = useState(group.raw_content)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const updateCategory = useUpdateCategory()

  const prevRawRef = useRef(group.raw_content)
  if (prevRawRef.current !== group.raw_content) {
    prevRawRef.current = group.raw_content
    setLocalContent(group.raw_content)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateCategory.mutateAsync({ entry_id: group.entry_id, content: localContent })
      setSaved(true)
      setTimeout(() => { setSaved(false); setEditing(false) }, 1200)
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setLocalContent(group.raw_content)
    setEditing(false)
  }

  const isDirty = localContent !== group.raw_content
  const isProse = PROSE_CATEGORIES.has(group.category)
  const isProduct = isProductCategory(group.category)

  return (
    <div
      className="rounded-xl border shadow-sm overflow-hidden"
      style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-4"
        style={{ borderBottom: editing ? `1px solid ${colors.subtleBorder}` : 'none' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: 'rgba(233,77,53,0.08)' }}
          >
            <CategoryIcon
              name={group.icon}
              className="size-4"
              // @ts-expect-error style prop on icon
              style={{ color: colors.brandCoral }}
            />
          </div>
          <h2
            className="font-semibold"
            style={{ fontSize: typography.sectionTitle.size, color: colors.headingText }}
          >
            {group.label}
          </h2>
        </div>
        <button
          onClick={() => setEditing((v) => !v)}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors"
          style={{
            color: editing ? colors.brandCoral : colors.secondaryText,
            backgroundColor: editing ? 'rgba(233,77,53,0.08)' : 'transparent',
          }}
        >
          {editing ? (
            <>
              <ChevronDown className="size-3.5" />
              Editing
            </>
          ) : (
            <>
              <Edit3 className="size-3.5" />
              Edit
            </>
          )}
        </button>
      </div>

      {/* Summary content */}
      {!editing && (
        <div className="px-5 pb-5 pt-1">
          {group.items.length === 0 ? (
            <p className="text-sm italic" style={{ color: colors.secondaryText }}>
              No content yet.
            </p>
          ) : isProse ? (
            <ProseContent content={group.raw_content} />
          ) : isProduct ? (
            <ProductContent group={group} />
          ) : (
            <BulletList items={group.items} />
          )}
          {group.count > group.items.length && (
            <p
              className="text-xs mt-3"
              style={{ color: colors.secondaryText }}
            >
              + {group.count - group.items.length} more
            </p>
          )}
        </div>
      )}

      {/* Inline editor */}
      {editing && (
        <div className="px-5 pb-5 pt-4 space-y-3">
          <textarea
            value={localContent}
            onChange={(e) => setLocalContent(e.target.value)}
            rows={Math.min(16, Math.max(5, localContent.split('\n').length + 2))}
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
              disabled={saving || !isDirty}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-white transition-opacity disabled:opacity-50"
              style={{ backgroundColor: colors.brandCoral }}
            >
              {saving ? (
                <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <Check className="size-3.5" />
              )}
              {saving ? 'Saving...' : saved ? 'Saved' : 'Save'}
            </button>
            <button
              onClick={handleCancel}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
              style={{ color: colors.secondaryText, backgroundColor: colors.brandTint }}
            >
              <X className="size-3.5" />
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Product module grid (2-col layout for product cards)
// ---------------------------------------------------------------------------

function ProductTabs({ tabs }: { tabs: ProductTab[] }) {
  if (tabs.length === 0) return null

  return (
    <div
      className="rounded-xl border shadow-sm overflow-hidden"
      style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
    >
      <div
        className="flex items-center gap-3 px-5 py-4 border-b"
        style={{ borderColor: colors.subtleBorder }}
      >
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: 'rgba(233,77,53,0.08)' }}
        >
          <Package className="size-4" style={{ color: colors.brandCoral }} />
        </div>
        <h2
          className="font-semibold"
          style={{ fontSize: typography.sectionTitle.size, color: colors.headingText }}
        >
          Products
        </h2>
        <span
          className="text-xs px-2 py-0.5 rounded-full font-medium"
          style={{ backgroundColor: colors.brandTint, color: colors.brandCoral }}
        >
          {tabs.length}
        </span>
      </div>
      <div className="px-5 py-4">
        <Tabs defaultValue={tabs[0].slug}>
          <TabsList variant="line" className="overflow-x-auto">
            {tabs.map((tab) => (
              <TabsTrigger key={tab.slug} value={tab.slug}>
                {tab.name}
              </TabsTrigger>
            ))}
          </TabsList>
          {tabs.map((tab) => (
            <TabsContent key={tab.slug} value={tab.slug}>
              <div className="space-y-4 pt-4">
                {tab.sections.map((section) => (
                  <SectionCard key={section.category} group={section} />
                ))}
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Uploaded files section
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
      // Trigger analysis for the last uploaded file
      if (fileIds.length > 0) {
        const result = await api.post<{ run_id: string }>('/profile/analyze-document', {
          file_id: fileIds[fileIds.length - 1],
        })
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
    <div
      className="rounded-xl border shadow-sm overflow-hidden"
      style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
    >
      <div
        className="flex items-center justify-between px-5 py-4 border-b"
        style={{ borderColor: colors.subtleBorder }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: 'rgba(233,77,53,0.1)' }}
          >
            <FileText className="size-4" style={{ color: colors.brandCoral }} />
          </div>
          <span
            className="font-semibold"
            style={{ fontSize: typography.sectionTitle.size, color: colors.headingText }}
          >
            Linked Files
          </span>
        </div>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-white transition-opacity disabled:opacity-60"
          style={{ backgroundColor: colors.brandCoral }}
        >
          {uploading ? (
            <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <Upload className="size-3.5" />
          )}
          {uploading ? 'Uploading...' : 'Upload files'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf,.doc,.docx,.txt,.md"
          multiple
          onChange={handleFileChange}
        />
      </div>

      <div className="p-5">
        {uploadedFiles.length === 0 ? (
          <p className="text-sm italic" style={{ color: colors.secondaryText }}>
            No files linked yet. Upload a document to associate it with your company profile.
          </p>
        ) : (
          <div className="space-y-2">
            {uploadedFiles.map((file) => (
              <div
                key={file.id}
                className="flex items-center gap-3 px-3 py-2 rounded-lg border"
                style={{ borderColor: colors.subtleBorder, backgroundColor: colors.pageBg }}
              >
                <FileText className="size-4 shrink-0" style={{ color: colors.secondaryText }} />
                <span className="flex-1 text-sm truncate" style={{ color: colors.bodyText }}>
                  {file.filename}
                </span>
                <span className="text-xs shrink-0" style={{ color: colors.secondaryText }}>
                  {formatFileSize(file.size_bytes)}
                </span>
                <button
                  onClick={async () => {
                    try {
                      const { token } = await import('@/stores/auth').then((m) => ({
                        token: m.useAuthStore.getState().token,
                      }))
                      const res = await fetch(`/api/v1/files/${file.id}/download`, {
                        headers: token ? { Authorization: `Bearer ${token}` } : {},
                      })
                      if (!res.ok) return
                      const data = (await res.json()) as { download_url: string }
                      window.open(data.download_url, '_blank')
                    } catch {
                      // File not available for download
                    }
                  }}
                  className="shrink-0 p-1 rounded hover:bg-gray-100 transition-colors"
                  title="Download"
                >
                  <Download className="size-4" style={{ color: colors.secondaryText }} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state: URL crawl panel
// ---------------------------------------------------------------------------

function CrawlPanel({ defaultUrl }: { defaultUrl: string }) {
  const crawl = useProfileCrawl()
  const [url, setUrl] = useState(defaultUrl)
  const [urlError, setUrlError] = useState<string | null>(null)

  const handleAnalyze = () => {
    const normalized = normalizeUrl(url)
    if (!normalized) return
    if (!isValidUrl(normalized)) {
      setUrlError('Please enter a valid URL')
      return
    }
    setUrlError(null)
    crawl.startCrawl(normalized)
  }

  if (crawl.phase === 'crawling' || crawl.phase === 'complete') {
    return (
      <div
        className="rounded-xl border shadow-sm overflow-hidden p-6"
        style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
      >
        <LiveCrawl
          crawlItems={crawl.crawlItems}
          crawlTotal={crawl.crawlTotal}
          crawlStatus={crawl.crawlStatus}
          isComplete={crawl.phase === 'complete'}
          onContinue={() => {}}
        />
      </div>
    )
  }

  if (crawl.phase === 'error') {
    return (
      <div
        className="rounded-xl border shadow-sm overflow-hidden p-8 text-center"
        style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
      >
        <AlertCircle className="size-10 mx-auto mb-3" style={{ color: '#EF4444' }} />
        <p className="text-sm mb-4" style={{ color: colors.bodyText }}>
          {crawl.error?.message ?? 'Something went wrong'}
        </p>
        {crawl.error?.retryable && (
          <button
            onClick={crawl.retry}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white"
            style={{ backgroundColor: colors.brandCoral }}
          >
            <RefreshCw className="size-3.5" />
            Try again
          </button>
        )}
      </div>
    )
  }

  return (
    <div
      className="rounded-xl border shadow-sm overflow-hidden p-8"
      style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
    >
      <div className="max-w-lg mx-auto text-center">
        <Globe className="size-10 mx-auto mb-4" style={{ color: colors.brandCoral, opacity: 0.8 }} />
        <h2
          className="font-semibold mb-2"
          style={{ fontSize: typography.sectionTitle.size, color: colors.headingText }}
        >
          Populate your company profile
        </h2>
        <p className="text-sm mb-6" style={{ color: colors.secondaryText }}>
          Enter your company website to automatically discover positioning, products, competitors, and more.
        </p>
        <div className="flex gap-2">
          <input
            type="url"
            value={url}
            onChange={(e) => { setUrl(e.target.value); setUrlError(null) }}
            onKeyDown={(e) => { if (e.key === 'Enter') handleAnalyze() }}
            placeholder="https://yourcompany.com"
            className="flex-1 rounded-lg border px-4 py-2.5 text-sm focus:outline-none focus:ring-2"
            style={{
              borderColor: urlError ? '#EF4444' : colors.subtleBorder,
              color: colors.bodyText,
              backgroundColor: colors.pageBg,
              // @ts-expect-error CSS variable
              '--tw-ring-color': colors.brandCoral,
            }}
          />
          <button
            onClick={handleAnalyze}
            disabled={!url.trim()}
            className="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-opacity disabled:opacity-50"
            style={{ backgroundColor: colors.brandCoral }}
          >
            Analyze
          </button>
        </div>
        {urlError && (
          <p className="text-xs mt-2 text-left" style={{ color: '#EF4444' }}>{urlError}</p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state: Document upload + analyze panel
// ---------------------------------------------------------------------------

function DocumentAnalyzePanel({ onRunStarted }: { onRunStarted?: (runId: string) => void }) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)
  const linkFile = useLinkProfileFile()

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setAnalyzing(true)
    setAnalyzeError(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const { token } = await import('@/stores/auth').then((m) => ({
        token: m.useAuthStore.getState().token,
      }))
      const uploadRes = await fetch('/api/v1/files/upload', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      })
      if (!uploadRes.ok) throw new Error('Upload failed')
      const uploadData = (await uploadRes.json()) as { id: string }
      const fileId = uploadData.id
      await linkFile.mutateAsync(fileId)
      const result = await api.post<{ run_id: string }>('/profile/analyze-document', { file_id: fileId })
      onRunStarted?.(result.run_id)
    } catch (err) {
      console.error('Document analyze failed:', err)
      setAnalyzeError(err instanceof Error ? err.message : 'Analysis failed')
    } finally {
      setAnalyzing(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div
      className="rounded-xl border shadow-sm overflow-hidden p-8"
      style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
    >
      <div className="max-w-lg mx-auto text-center">
        <FileText className="size-10 mx-auto mb-4" style={{ color: colors.brandCoral, opacity: 0.8 }} />
        <h2
          className="font-semibold mb-2"
          style={{ fontSize: typography.sectionTitle.size, color: colors.headingText }}
        >
          Or upload a company document
        </h2>
        <p className="text-sm mb-6" style={{ color: colors.secondaryText }}>
          Upload a PDF, Word doc, or text file containing company information.
        </p>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={analyzing}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-opacity disabled:opacity-60"
          style={{ backgroundColor: colors.brandCoral }}
        >
          {analyzing ? (
            <>
              <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Analyzing document...
            </>
          ) : (
            <>
              <Upload className="size-4" />
              Upload &amp; Analyze
            </>
          )}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf,.doc,.docx,.txt,.md"
          onChange={handleFileChange}
        />
        {analyzeError && (
          <p className="text-xs mt-3" style={{ color: '#EF4444' }}>{analyzeError}</p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function CompanyProfilePage() {
  const [resetConfirm, setResetConfirm] = useState(false)
  const { data: profile, isLoading, isError } = useCompanyProfile()
  const linkFile = useLinkProfileFile()
  const refresh = useProfileRefresh()

  if (isLoading) {
    return (
      <div
        className="min-h-screen"
        style={{ backgroundColor: colors.pageBg, padding: `${spacing.section} ${spacing.pageDesktop}` }}
      >
        <div style={{ maxWidth: spacing.maxReading, margin: '0 auto' }}>
          <div className="mb-8">
            <div className="h-8 w-48 rounded bg-gray-200 animate-pulse mb-2" />
            <div className="h-4 w-32 rounded bg-gray-100 animate-pulse" />
          </div>
          <ProfileSkeleton />
        </div>
      </div>
    )
  }

  if (isError || !profile) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ backgroundColor: colors.pageBg }}
      >
        <div className="text-center space-y-2">
          <p style={{ color: colors.bodyText }}>Could not load company profile.</p>
          <button
            onClick={() => window.location.reload()}
            className="text-sm underline"
            style={{ color: colors.brandCoral }}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  const hasGroups = profile.groups.length > 0 || (profile.product_tabs && profile.product_tabs.length > 0)
  const formattedLastUpdated = profile.last_updated
    ? new Date(profile.last_updated).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
      })
    : null

  const defaultCrawlUrl = profile.domain ? `https://${profile.domain}` : ''

  // Products now come from product_tabs; regular groups exclude any legacy product entries
  const regularGroups = profile.groups.filter((g) => !isProductCategory(g.category))

  // Split regular groups into before-products and after-products
  // Products should come after "About" (positioning) and before everything else
  const aboutGroup = regularGroups.find((g) => g.category === 'positioning')
  const otherGroups = regularGroups.filter((g) => g.category !== 'positioning')

  return (
    <div className="min-h-screen" style={{ backgroundColor: colors.pageBg }}>
      <div
        className="mx-auto"
        style={{
          maxWidth: spacing.maxGrid,
          padding: `${spacing.section} ${spacing.pageDesktop}`,
        }}
      >
        {/* Page header */}
        <div className="flex items-start justify-between mb-10">
          <div>
            <h1
              className="font-bold"
              style={{
                fontSize: typography.pageTitle.size,
                fontWeight: typography.pageTitle.weight,
                letterSpacing: typography.pageTitle.letterSpacing,
                color: colors.headingText,
                lineHeight: typography.pageTitle.lineHeight,
              }}
            >
              {profile.company_name ?? 'Your Company'}
            </h1>
            <div className="flex items-center gap-3 mt-1.5">
              {profile.domain && (
                <div className="flex items-center gap-1.5">
                  <Globe className="size-3.5" style={{ color: colors.secondaryText }} />
                  <span className="text-sm" style={{ color: colors.secondaryText }}>
                    {profile.domain}
                  </span>
                </div>
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
                onClick={() => refresh.startRefresh()}
                disabled={refresh.phase === 'refreshing'}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors"
                style={{
                  backgroundColor: colors.cardBg,
                  borderColor: colors.subtleBorder,
                  color: colors.headingText,
                }}
              >
                <RefreshCw className={`size-4 ${refresh.phase === 'refreshing' ? 'animate-spin' : ''}`} />
                Refresh
              </button>
              <button
                onClick={() => setResetConfirm(true)}
                disabled={refresh.phase === 'refreshing'}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors"
                style={{
                  backgroundColor: colors.cardBg,
                  borderColor: 'rgba(239,68,68,0.3)',
                  color: '#EF4444',
                }}
              >
                Reset
              </button>
            </div>
          )}
        </div>

        {/* Inline reset confirmation */}
        {resetConfirm && (
          <div
            className="flex items-center justify-between px-5 py-3.5 rounded-xl mb-6"
            style={{
              backgroundColor: 'rgba(239,68,68,0.06)',
              border: '1px solid rgba(239,68,68,0.2)',
            }}
          >
            <span className="text-sm" style={{ color: colors.bodyText }}>
              This will clear your current profile and rebuild from scratch. Continue?
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setResetConfirm(false)
                  void refresh.startReset()
                }}
                className="px-4 py-1.5 rounded-lg text-sm font-medium text-white"
                style={{ backgroundColor: '#EF4444' }}
              >
                Confirm Reset
              </button>
              <button
                onClick={() => setResetConfirm(false)}
                className="px-4 py-1.5 rounded-lg text-sm font-medium"
                style={{ color: colors.secondaryText, backgroundColor: colors.brandTint }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* SSE streaming overlay or profile body */}
        {(refresh.phase === 'refreshing' || refresh.phase === 'complete') ? (
          <div
            className="rounded-xl border shadow-sm overflow-hidden p-6"
            style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
          >
            <LiveCrawl
              crawlItems={refresh.crawlItems}
              crawlTotal={refresh.crawlTotal}
              crawlStatus={refresh.crawlStatus}
              isComplete={refresh.phase === 'complete'}
              onContinue={() => refresh.dismiss()}
            />
          </div>
        ) : !hasGroups ? (
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
          <div className="space-y-6">
            {/* About section (positioning) — always first */}
            {aboutGroup && <SectionCard group={aboutGroup} />}

            {/* Product modules — 2-col grid */}
            {profile.product_tabs && profile.product_tabs.length > 0 && (
              <ProductTabs tabs={profile.product_tabs} />
            )}

            {/* Remaining sections */}
            {otherGroups.map((group) => (
              <SectionCard key={group.category} group={group} />
            ))}

            {/* Uploaded files — always show so users can upload more */}
            <UploadedFilesSection uploadedFiles={profile.uploaded_files} onAnalyzeStarted={(runId) => refresh.startFromRunId(runId)} />
          </div>
        )}
      </div>
    </div>
  )
}
