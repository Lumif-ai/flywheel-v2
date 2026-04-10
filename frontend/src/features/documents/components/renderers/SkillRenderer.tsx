import { MeetingPrepRenderer } from './MeetingPrepRenderer'
import { GenericRenderer } from './GenericRenderer'
import { OnePagerRenderer } from './OnePagerRenderer'
import { isOnePagerData } from '../../types/one-pager'
import { typography } from '@/lib/design-tokens'

interface SkillRendererProps {
  /** Skill name / document_type (e.g. "meeting-prep", "company-intel") */
  skillType: string
  /** Raw text output from the skill run */
  output: string | null
  /** Pre-rendered HTML (meeting-prep produces this directly) */
  renderedHtml: string | null
}

/**
 * Dispatches to the appropriate skill-specific renderer based on skill type.
 *
 * Priority:
 * 1. If skill type has a dedicated renderer AND the required data exists, use it
 * 2. If raw output exists, use GenericRenderer (handles markdown/text)
 * 3. If only rendered_html exists (legacy), fall back to MeetingPrepRenderer
 *    (which handles any pre-rendered HTML via sanitized dangerouslySetInnerHTML)
 */
/**
 * Detect if "HTML" is actually raw markdown that wasn't rendered properly.
 * Checks for markdown table pipes or unrendered headings as telltale signs.
 */
function looksLikeRawMarkdown(html: string): boolean {
  // If it contains markdown table syntax (pipes with dashes) but no <table> tag
  if (/\|[-:]+\|/.test(html) && !/<table/i.test(html)) return true
  // If it contains raw ### headings not wrapped in HTML tags
  if (/^#{1,4}\s+/m.test(html) && !/<h[1-4]/i.test(html)) return true
  return false
}

export function SkillRenderer({ skillType, output, renderedHtml }: SkillRendererProps) {
  // Structured JSON output — detect and dispatch to dedicated renderers
  if (output) {
    try {
      const parsed = JSON.parse(output)
      if (isOnePagerData(parsed)) {
        return <OnePagerRenderer data={parsed} />
      }
      // Future structured types can be detected here
    } catch {
      // Not JSON — fall through to existing renderers
    }
  }

  // Meeting-prep: prefer rendered HTML (it's purpose-built HTML from the LLM)
  if (skillType === 'meeting-prep' || skillType === 'ctx-meeting-prep' || skillType === 'flywheel') {
    // If rendered_html is actually raw markdown (backend rendering failed),
    // fall through to GenericRenderer which uses react-markdown
    if (renderedHtml && !looksLikeRawMarkdown(renderedHtml)) {
      return <MeetingPrepRenderer renderedHtml={renderedHtml} />
    }
    // Use raw output with react-markdown, or the broken rendered_html as markdown
    const markdownContent = output || renderedHtml
    if (markdownContent) {
      return <GenericRenderer output={markdownContent} skillName={skillType} />
    }
  }

  // All other skills: prefer raw output rendered natively
  if (output) {
    return <GenericRenderer output={output} skillName={skillType} />
  }

  // Legacy fallback: render pre-existing HTML if that's all we have
  if (renderedHtml) {
    return <MeetingPrepRenderer renderedHtml={renderedHtml} />
  }

  // Nothing to render
  return (
    <div
      style={{
        textAlign: 'center',
        padding: '80px 0',
        color: 'var(--secondary-text)',
        fontSize: typography.body.size,
      }}
    >
      No content available for this document.
    </div>
  )
}
