import { useState, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
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
  FileText,
  Globe,
  Clock,
  AlertCircle,
  RefreshCw,
} from 'lucide-react'
import { colors, spacing, typography } from '@/lib/design-tokens'
import {
  useCompanyProfile,
  useUpdateCategory,
  useCreateCategory,
  useLinkProfileFile,
  type ProfileGroup,
  type ProfileUploadedFile,
} from '../hooks/useCompanyProfile'
import { useProfileCrawl } from '../hooks/useProfileCrawl'
import { LiveCrawl } from '@/features/onboarding/components/LiveCrawl'
import { api } from '@/lib/api'

// ---------------------------------------------------------------------------
// URL helpers (inlined from UrlInput)
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
// Icon map: file_name -> lucide icon component
// ---------------------------------------------------------------------------

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  Building2,
  Package,
  UserCheck,
  TrendingUp,
}

function CategoryIcon({ name, className }: { name: string; className?: string }) {
  const Icon = ICON_MAP[name] ?? Building2
  return <Icon className={className} />
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function ProfileSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="rounded-xl border p-6 animate-pulse"
          style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="w-9 h-9 rounded-lg bg-gray-200" />
            <div className="h-5 w-32 rounded bg-gray-200" />
          </div>
          <div className="flex flex-wrap gap-2">
            {[1, 2, 3, 4].map((j) => (
              <div key={j} className="h-6 w-24 rounded-full bg-gray-100" />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Category card
// ---------------------------------------------------------------------------

interface CategoryCardProps {
  group: ProfileGroup
  editMode: boolean
}

function CategoryCard({ group, editMode }: CategoryCardProps) {
  const [localContent, setLocalContent] = useState(group.raw_content)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const updateCategory = useUpdateCategory()

  // Reset local content when group changes from outside
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
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setLocalContent(group.raw_content)
  }

  const isDirty = localContent !== group.raw_content

  return (
    <div
      className="rounded-xl border shadow-sm overflow-hidden"
      style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
    >
      {/* Card header */}
      <div
        className="flex items-center justify-between px-5 py-4 border-b"
        style={{ borderColor: colors.subtleBorder }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: 'rgba(233,77,53,0.1)' }}
          >
            <CategoryIcon
              name={group.icon}
              className="size-4"
              style={{ color: colors.brandCoral } as React.CSSProperties}
            />
          </div>
          <span
            className="font-semibold"
            style={{ fontSize: typography.sectionTitle.size, color: colors.headingText }}
          >
            {group.label}
          </span>
        </div>
        <span
          className="text-xs px-2 py-0.5 rounded-full font-medium"
          style={{ backgroundColor: colors.brandTint, color: colors.brandCoral }}
        >
          {group.count}
        </span>
      </div>

      {/* Card body */}
      <div className="p-5">
        {editMode ? (
          <div className="space-y-3">
            <textarea
              value={localContent}
              onChange={(e) => setLocalContent(e.target.value)}
              rows={Math.max(4, group.items.length + 1)}
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 resize-y"
              style={{
                borderColor: colors.subtleBorder,
                color: colors.bodyText,
                backgroundColor: colors.pageBg,
                // @ts-expect-error CSS variable
                '--tw-ring-color': colors.brandCoral,
              }}
              placeholder="One item per line..."
            />
            <p
              className="text-xs"
              style={{ color: colors.secondaryText }}
            >
              One item per line. Changes save when you click Save.
            </p>
            {isDirty && (
              <div className="flex gap-2">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-white transition-opacity disabled:opacity-60"
                  style={{ backgroundColor: colors.brandCoral }}
                >
                  {saving ? (
                    <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : saved ? (
                    <Check className="size-3.5" />
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
            )}
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {group.items.length === 0 ? (
              <p
                className="text-sm italic"
                style={{ color: colors.secondaryText }}
              >
                No items yet. Switch to Edit mode to add.
              </p>
            ) : (
              group.items.map((item, i) => (
                <span
                  key={i}
                  className="inline-block px-3 py-1 rounded-full text-sm"
                  style={{
                    backgroundColor: colors.brandTint,
                    color: colors.headingText,
                    border: `1px solid ${colors.subtleBorder}`,
                  }}
                >
                  {item}
                </span>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Uploaded files section
// ---------------------------------------------------------------------------

interface UploadedFileSectionProps {
  uploadedFiles: Array<{ id: string; filename: string; mimetype: string; size_bytes: number }>
  onLink: (fileId: string) => void
  linking: boolean
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function UploadedFilesSection({ uploadedFiles, onLink, linking }: UploadedFileSectionProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const linkFile = useLinkProfileFile()

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const { token } = await import('@/stores/auth').then((m) => ({ token: m.useAuthStore.getState().token }))
      const res = await fetch('/api/v1/files/upload', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      })
      if (!res.ok) throw new Error('Upload failed')
      const data = await res.json() as { id: string }
      await linkFile.mutateAsync(data.id)
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
          {uploading ? 'Uploading...' : 'Upload file'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf,.doc,.docx,.txt,.md"
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

interface CrawlPanelProps {
  defaultUrl: string
}

function CrawlPanel({ defaultUrl }: CrawlPanelProps) {
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

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleAnalyze()
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
        <AlertCircle
          className="size-10 mx-auto mb-3"
          style={{ color: '#EF4444' }}
        />
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

  // idle
  return (
    <div
      className="rounded-xl border shadow-sm overflow-hidden p-8"
      style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
    >
      <div className="max-w-lg mx-auto text-center">
        <Globe
          className="size-10 mx-auto mb-4"
          style={{ color: colors.brandCoral, opacity: 0.8 }}
        />
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
            onChange={(e) => {
              setUrl(e.target.value)
              setUrlError(null)
            }}
            onKeyDown={handleKeyDown}
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
          <p className="text-xs mt-2 text-left" style={{ color: '#EF4444' }}>
            {urlError}
          </p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state: Document upload + analyze panel
// ---------------------------------------------------------------------------

interface DocumentAnalyzePanelProps {
  onRunStarted?: (runId: string) => void
}

function DocumentAnalyzePanel({ onRunStarted }: DocumentAnalyzePanelProps) {
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
      // 1. Upload file
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

      // 2. Link file to profile
      await linkFile.mutateAsync(fileId)

      // 3. Trigger analysis — returns run_id for SSE streaming
      const result = await api.post<{ run_id: string }>(
        '/profile/analyze-document',
        { file_id: fileId },
      )

      // 4. Hand off to parent for SSE streaming
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
        <FileText
          className="size-10 mx-auto mb-4"
          style={{ color: colors.brandCoral, opacity: 0.8 }}
        />
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
          <p className="text-xs mt-3" style={{ color: '#EF4444' }}>
            {analyzeError}
          </p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function CompanyProfilePage() {
  const [editMode, setEditMode] = useState(false)
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
        <div style={{ maxWidth: spacing.maxGrid, margin: '0 auto' }}>
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

  const hasGroups = profile.groups.length > 0
  const formattedLastUpdated = profile.last_updated
    ? new Date(profile.last_updated).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : null

  const defaultCrawlUrl = profile.domain ? `https://${profile.domain}` : ''

  return (
    <div
      className="min-h-screen"
      style={{ backgroundColor: colors.pageBg }}
    >
      <div
        className="mx-auto"
        style={{
          maxWidth: spacing.maxGrid,
          padding: `${spacing.section} ${spacing.pageDesktop}`,
        }}
      >
        {/* Page header */}
        <div className="flex items-start justify-between mb-8">
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
              <button
                onClick={() => setEditMode((v) => !v)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors"
                style={
                  editMode
                    ? {
                        backgroundColor: colors.brandCoral,
                        borderColor: colors.brandCoral,
                        color: '#fff',
                      }
                    : {
                        backgroundColor: colors.cardBg,
                        borderColor: colors.subtleBorder,
                        color: colors.headingText,
                      }
                }
              >
                {editMode ? (
                  <>
                    <Check className="size-4" />
                    Done editing
                  </>
                ) : (
                  <>
                    <Edit3 className="size-4" />
                    Edit profile
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        {/* Stats bar */}
        {hasGroups && (
          <div
            className="flex items-center gap-6 px-5 py-3 rounded-xl border mb-8"
            style={{ backgroundColor: colors.cardBg, borderColor: colors.subtleBorder }}
          >
            <div>
              <span
                className="text-2xl font-bold"
                style={{ color: colors.headingText }}
              >
                {profile.total_items}
              </span>
              <span className="ml-1.5 text-sm" style={{ color: colors.secondaryText }}>
                intel items
              </span>
            </div>
            <div
              className="w-px h-8"
              style={{ backgroundColor: colors.subtleBorder }}
            />
            <div>
              <span
                className="text-2xl font-bold"
                style={{ color: colors.headingText }}
              >
                {profile.groups.length}
              </span>
              <span className="ml-1.5 text-sm" style={{ color: colors.secondaryText }}>
                categories
              </span>
            </div>
          </div>
        )}

        {/* Inline reset confirmation */}
        {resetConfirm && (
          <div
            className="flex items-center justify-between px-5 py-3.5 rounded-xl mb-4"
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
            {/* URL crawl panel */}
            <CrawlPanel defaultUrl={defaultCrawlUrl} />

            {/* Divider */}
            <div className="flex items-center gap-4 px-4">
              <div className="flex-1 h-px" style={{ backgroundColor: colors.subtleBorder }} />
              <span className="text-xs font-medium" style={{ color: colors.secondaryText }}>
                or
              </span>
              <div className="flex-1 h-px" style={{ backgroundColor: colors.subtleBorder }} />
            </div>

            {/* Document upload + analyze panel */}
            <DocumentAnalyzePanel onRunStarted={(runId) => refresh.startFromRunId(runId)} />

            {/* Show linked files if any exist */}
            {profile.uploaded_files.length > 0 && (
              <UploadedFilesSection
                uploadedFiles={profile.uploaded_files}
                onLink={(fileId) => linkFile.mutate(fileId)}
                linking={linkFile.isPending}
              />
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {profile.groups.map((group) => (
              <CategoryCard key={group.category} group={group} editMode={editMode} />
            ))}

            {/* Uploaded files */}
            <UploadedFilesSection
              uploadedFiles={profile.uploaded_files}
              onLink={(fileId) => linkFile.mutate(fileId)}
              linking={linkFile.isPending}
            />
          </div>
        )}
      </div>
    </div>
  )
}
