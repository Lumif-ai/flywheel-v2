import { sanitizeHTML } from '@/lib/sanitize'
import { spacing, typography, colors } from '@/lib/design-tokens'

interface MeetingPrepRendererProps {
  renderedHtml: string
}

/**
 * Renders meeting-prep HTML output.
 *
 * Meeting-prep skills produce fully styled HTML directly from the LLM.
 * We sanitize it and inject it via dangerouslySetInnerHTML, wrapped in
 * a container that applies design-token-based typography overrides.
 *
 * The inline styles from the LLM (Inter font, 720px max-width, brand coral
 * accents) are intentionally preserved — they were generated to match our
 * design system. The wrapper ensures consistency with the rest of the app.
 */
export function MeetingPrepRenderer({ renderedHtml }: MeetingPrepRendererProps) {
  const clean = sanitizeHTML(renderedHtml)

  return (
    <article
      className="meeting-prep-content"
      style={{
        maxWidth: spacing.maxBriefing,
        margin: '0 auto',
        width: '100%',
        fontSize: typography.body.size,
        lineHeight: typography.body.lineHeight,
        color: 'var(--body-text)',
      }}
    >
      <style>{`
        .meeting-prep-content h1,
        .meeting-prep-content h2,
        .meeting-prep-content h3 {
          color: var(--heading-text);
        }
        .meeting-prep-content a {
          color: var(--brand-coral);
        }
        .meeting-prep-content hr {
          border: none;
          border-top: 1px solid var(--subtle-border);
          margin: 24px 0;
        }
        .meeting-prep-content ul,
        .meeting-prep-content ol {
          padding-left: 20px;
          margin: 8px 0;
        }
        .meeting-prep-content li {
          margin-bottom: 4px;
          line-height: 1.6;
        }
        .meeting-prep-content li > ul,
        .meeting-prep-content li > ol {
          margin: 4px 0 4px 0;
        }
        .meeting-prep-content p {
          margin: 8px 0;
        }
        .meeting-prep-content blockquote {
          border-left: 3px solid var(--brand-coral, #E94D35);
          padding: 4px 12px;
          margin: 12px 0;
          color: var(--body-text);
          opacity: 0.85;
        }
        .meeting-prep-content table {
          width: 100%;
          border-collapse: collapse;
          margin: 12px 0;
          font-size: 0.9em;
        }
        .meeting-prep-content th,
        .meeting-prep-content td {
          border: 1px solid var(--subtle-border, #e5e7eb);
          padding: 6px 10px;
          text-align: left;
        }
        .meeting-prep-content th {
          background: var(--surface-secondary, #f9fafb);
          font-weight: 600;
        }
        .meeting-prep-content strong {
          font-weight: 600;
          color: var(--heading-text);
        }
      `}</style>
      <div dangerouslySetInnerHTML={{ __html: clean }} />
    </article>
  )
}
