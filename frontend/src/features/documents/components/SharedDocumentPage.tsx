import { useEffect, useState, useRef } from 'react'
import { useParams } from 'react-router'
import { spacing, typography, colors } from '@/lib/design-tokens'
import { fetchSharedDocument } from '../api'
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
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SharedDocumentPage() {
  const { token } = useParams<{ token: string }>()
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const [document, setDocument] = useState<DocumentDetail | null>(null)
  const [htmlContent, setHtmlContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!token) return
    setLoading(true)
    setError(false)

    fetchSharedDocument(token)
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
          console.warn('Could not fetch content, using src fallback')
        }
      })
      .catch(() => {
        setError(true)
      })
      .finally(() => setLoading(false))
  }, [token])

  // Auto-resize iframe
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
        className="min-h-screen bg-[var(--page-bg)]"
        style={{ padding: `${spacing.section} ${spacing.pageDesktop}` }}
      >
        <div
          className="mx-auto w-full"
          style={{ maxWidth: spacing.maxReading }}
        >
          <div className="h-8 w-3/4 rounded animate-shimmer bg-gray-200 mb-4" />
          <div className="h-4 w-1/3 rounded animate-shimmer bg-gray-200 mb-8" />
          <div className="h-96 rounded-xl animate-shimmer bg-gray-200" />
        </div>
      </div>
    )
  }

  // Error / 404 state
  if (error || !document) {
    return (
      <div
        className="min-h-screen bg-[var(--page-bg)] flex items-center justify-center"
        style={{ padding: `${spacing.section} ${spacing.pageDesktop}` }}
      >
        <div className="text-center">
          <h1
            style={{
              fontSize: typography.pageTitle.size,
              fontWeight: typography.pageTitle.weight,
              color: colors.headingText,
              marginBottom: spacing.element,
            }}
          >
            Document not found
          </h1>
          <p
            style={{
              fontSize: typography.body.size,
              color: colors.secondaryText,
            }}
          >
            This document may have been removed or the link may have expired.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div
      className="min-h-screen bg-[var(--page-bg)]"
      style={{ padding: `${spacing.section} ${spacing.pageDesktop}` }}
    >
      <div
        className="mx-auto w-full"
        style={{ maxWidth: spacing.maxReading }}
      >
        {/* Header */}
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
        <div className="flex items-center gap-3 mb-6">
          <span
            className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
            style={{
              backgroundColor: colors.brandTint,
              color: colors.brandCoral,
            }}
          >
            {getTypeLabel(document.document_type)}
          </span>
          <span
            style={{
              fontSize: typography.caption.size,
              color: colors.secondaryText,
            }}
          >
            Shared via Flywheel
          </span>
        </div>

        {/* Content */}
        <div className="rounded-xl overflow-hidden border border-[var(--subtle-border)] bg-white shadow-sm">
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

        {/* Footer: branding + CTA */}
        <div
          className="mt-10 pt-6 text-center"
          style={{ borderTop: `1px solid ${colors.subtleBorder}` }}
        >
          <p
            style={{
              fontSize: typography.caption.size,
              color: colors.secondaryText,
              marginBottom: spacing.tight,
            }}
          >
            Created on {formatDate(document.created_at)}
          </p>
          <p
            className="mt-4"
            style={{
              fontSize: typography.body.size,
              color: colors.secondaryText,
            }}
          >
            Powered by{' '}
            <span style={{ fontWeight: '600', color: colors.headingText }}>
              Flywheel
            </span>
          </p>
          <p
            className="mt-1"
            style={{
              fontSize: typography.caption.size,
              color: colors.secondaryText,
            }}
          >
            Prepare smarter for every meeting
          </p>
        </div>
      </div>
    </div>
  )
}
