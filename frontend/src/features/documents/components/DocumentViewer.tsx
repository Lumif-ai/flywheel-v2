import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router'
import { ArrowLeft, Share2, Download, ChevronDown } from 'lucide-react'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { fetchDocument, shareDocument } from '../api'
import type { DocumentDetail } from '../api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getTypeLabel(docType: string): string {
  switch (docType) {
    case 'meeting-prep':
      return 'Meeting Prep'
    case 'company-intel':
      return 'Company Intel'
    default:
      return docType.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`
  return formatDate(iso)
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DocumentViewer() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const [document, setDocument] = useState<DocumentDetail | null>(null)
  const [htmlContent, setHtmlContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [shareToast, setShareToast] = useState(false)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError(null)

    fetchDocument(id)
      .then(async (doc) => {
        setDocument(doc)
        // Prefer fetching HTML content for srcDoc to avoid signed URL expiry
        try {
          const res = await fetch(doc.content_url)
          if (res.ok) {
            const text = await res.text()
            setHtmlContent(text)
          }
        } catch {
          // Fallback: use content_url directly as iframe src
          console.warn('Could not fetch content via URL, using src fallback')
        }
      })
      .catch((err) => {
        setError(err.message || 'Failed to load document')
      })
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

  // Auto-resize iframe to fit content
  const handleIframeLoad = () => {
    if (iframeRef.current?.contentDocument) {
      const height = iframeRef.current.contentDocument.body.scrollHeight
      iframeRef.current.style.height = `${height + 32}px`
    }
  }

  // Loading state
  if (loading) {
    return (
      <div
        className="mx-auto w-full"
        style={{ maxWidth: spacing.maxReading, padding: `${spacing.section} ${spacing.pageDesktop}` }}
      >
        <div className="h-4 w-32 rounded animate-shimmer bg-gray-200 mb-8" />
        <div className="h-8 w-3/4 rounded animate-shimmer bg-gray-200 mb-4" />
        <div className="h-4 w-1/4 rounded animate-shimmer bg-gray-200 mb-8" />
        <div className="h-96 rounded-xl animate-shimmer bg-gray-200" />
      </div>
    )
  }

  // Error state
  if (error || !document) {
    return (
      <div
        className="mx-auto w-full text-center py-16"
        style={{ maxWidth: spacing.maxReading, padding: `${spacing.section} ${spacing.pageDesktop}` }}
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
          Back to Documents
        </button>
      </div>
    )
  }

  const contacts = document.metadata?.contacts ?? []
  const companies = document.metadata?.companies ?? []

  return (
    <div
      className="mx-auto w-full"
      style={{
        maxWidth: spacing.maxReading,
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
        Back to Documents
      </button>

      {/* Title + badge + time */}
      <h1
        style={{
          fontSize: typography.pageTitle.size,
          fontWeight: typography.pageTitle.weight,
          lineHeight: typography.pageTitle.lineHeight,
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
          {companies.length > 0 && contacts.length > 0 && ' -- '}
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
            color: '#fff',
          }}
        >
          <Share2 size={14} />
          {shareToast ? 'Copied!' : 'Share'}
        </button>
        <div className="relative group">
          <button
            type="button"
            disabled
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

      {/* Content area */}
      <div className="rounded-xl overflow-hidden border border-[var(--subtle-border)] bg-white">
        <iframe
          ref={iframeRef}
          title={document.title}
          srcDoc={htmlContent ?? undefined}
          src={!htmlContent ? document.content_url : undefined}
          onLoad={handleIframeLoad}
          className="w-full border-0"
          style={{ minHeight: '400px' }}
          sandbox="allow-same-origin"
        />
      </div>

      {/* Footer */}
      <p
        className="mt-6 text-center"
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
