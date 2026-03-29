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
        }
        .meeting-prep-content p {
          margin: 8px 0;
        }
      `}</style>
      <div dangerouslySetInnerHTML={{ __html: clean }} />
    </article>
  )
}
