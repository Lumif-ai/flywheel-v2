import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { ArrowLeft, Share2, Download, ChevronDown } from 'lucide-react'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { fetchDocument, shareDocument } from '../api'
import type { DocumentDetail } from '../api'
import { getTypeLabel, formatDate, relativeTime } from '../utils'
import { SkillRenderer } from './renderers'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DocumentViewer() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [document, setDocument] = useState<DocumentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [shareToast, setShareToast] = useState(false)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError(null)

    fetchDocument(id)
      .then((doc) => setDocument(doc))
      .catch((err) => setError(err.message || 'Failed to load document'))
      .finally(() => setLoading(false))
  }, [id])

  const handleShare = async () => {
    if (!document) return
    try {
      const res = await shareDocument(document.id)
      const url = `${window.location.origin}${res.share_url}`
      await navigator.clipboard.writeText(url)
      setShareToast(true)
      setTimeout(() => setShareToast(false), 3000)
    } catch (err) {
      console.error('Failed to share:', err)
    }
  }

  const handleBack = () => {
    navigate('/documents')
  }

  // Loading state
  if (loading) {
    return (
      <div
        className="mx-auto w-full page-enter"
        style={{ maxWidth: spacing.maxBriefing, padding: `${spacing.section} ${spacing.pageDesktop}` }}
      >
        <div className="h-4 w-32 rounded animate-shimmer bg-[var(--skeleton-bg)] mb-8" />
        <div className="h-8 w-3/4 rounded animate-shimmer bg-[var(--skeleton-bg)] mb-4" />
        <div className="h-4 w-1/4 rounded animate-shimmer bg-[var(--skeleton-bg)] mb-8" />
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="rounded animate-shimmer bg-[var(--skeleton-bg)]"
              style={{
                height: '16px',
                width: `${60 + Math.random() * 35}%`,
                animationDelay: `${i * 80}ms`,
              }}
            />
          ))}
        </div>
      </div>
    )
  }

  // Error state
  if (error || !document) {
    return (
      <div
        className="mx-auto w-full text-center py-16"
        style={{ maxWidth: spacing.maxBriefing, padding: `${spacing.section} ${spacing.pageDesktop}` }}
      >
        <p style={{ fontSize: typography.body.size, color: colors.secondaryText }}>
          {error || 'Document not found'}
        </p>
        <button
          type="button"
          onClick={handleBack}
          className="mt-4 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          style={{ color: colors.brandCoral }}
        >
          Back to Library
        </button>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors block mx-auto"
          style={{ color: colors.brandCoral }}
        >
          Try again
        </button>
      </div>
    )
  }

  const contacts = document.metadata?.contacts ?? []
  const companies = document.metadata?.companies ?? []

  return (
    <div
      className="mx-auto w-full page-enter"
      style={{
        maxWidth: spacing.maxBriefing,
        padding: `${spacing.section} ${spacing.pageDesktop}`,
      }}
    >
      {/* Back button */}
      <button
        type="button"
        onClick={handleBack}
        className="inline-flex items-center gap-1.5 text-sm font-medium mb-6 transition-colors hover:opacity-80"
        style={{ color: colors.secondaryText }}
      >
        <ArrowLeft size={16} />
        Back to Library
      </button>

      {/* Title + badge + time */}
      <h1
        style={{
          fontSize: typography.pageTitle.size,
          fontWeight: typography.pageTitle.weight,
          lineHeight: typography.pageTitle.lineHeight,
          letterSpacing: typography.pageTitle.letterSpacing,
          color: colors.headingText,
          marginBottom: spacing.tight,
        }}
      >
        {document.title}
      </h1>
      <div className="flex items-center gap-3 mb-2" style={{ color: colors.secondaryText }}>
        <span
          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
          style={{
            backgroundColor: colors.brandTint,
            color: colors.brandCoral,
          }}
        >
          {getTypeLabel(document.document_type)}
        </span>
        <span style={{ fontSize: typography.caption.size }}>
          {relativeTime(document.created_at)}
        </span>
      </div>

      {/* Metadata line */}
      {(contacts.length > 0 || companies.length > 0) && (
        <p
          className="mb-6"
          style={{
            fontSize: typography.caption.size,
            color: colors.secondaryText,
          }}
        >
          {companies.length > 0 && companies.join(', ')}
          {companies.length > 0 && contacts.length > 0 && ' \u2014 '}
          {contacts.length > 0 && contacts.join(', ')}
        </p>
      )}

      {/* Action bar */}
      <div
        className="flex items-center gap-3 mb-8 pb-6"
        style={{ borderBottom: `1px solid ${colors.subtleBorder}` }}
      >
        <button
          type="button"
          onClick={handleShare}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 hover:shadow-md"
          style={{
            background: `linear-gradient(135deg, ${colors.brandCoral}, ${colors.brandGradientEnd})`,
            color: 'var(--primary-foreground, #fff)',
          }}
        >
          <Share2 size={14} />
          {shareToast ? 'Copied!' : 'Share'}
        </button>
        <div className="relative group">
          <button
            type="button"
            disabled
            aria-label="Export coming soon"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium opacity-50 cursor-not-allowed"
            style={{
              backgroundColor: colors.brandTint,
              color: colors.secondaryText,
            }}
          >
            <Download size={14} />
            Export
            <ChevronDown size={12} />
          </button>
          <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
            Coming soon
          </div>
        </div>
      </div>

      {/* Native skill output rendering */}
      <SkillRenderer
        skillType={document.document_type}
        output={document.output}
        renderedHtml={document.rendered_html}
      />

      {/* Footer */}
      <p
        className="mt-8 text-center"
        style={{
          fontSize: typography.caption.size,
          color: colors.secondaryText,
        }}
      >
        Created on {formatDate(document.created_at)}
      </p>
    </div>
  )
}
