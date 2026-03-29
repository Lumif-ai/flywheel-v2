import { MeetingPrepRenderer } from './MeetingPrepRenderer'
import { GenericRenderer } from './GenericRenderer'
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
export function SkillRenderer({ skillType, output, renderedHtml }: SkillRendererProps) {
  // Meeting-prep: prefer rendered HTML (it's purpose-built HTML from the LLM)
  if (skillType === 'meeting-prep' || skillType === 'ctx-meeting-prep' || skillType === 'flywheel') {
    if (renderedHtml) {
      return <MeetingPrepRenderer renderedHtml={renderedHtml} />
    }
    // Fallback to generic if HTML is missing for some reason
    if (output) {
      return <GenericRenderer output={output} skillName={skillType} />
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
