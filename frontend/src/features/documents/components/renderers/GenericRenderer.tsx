import React, { useMemo } from 'react'
import { spacing, typography } from '@/lib/design-tokens'

interface GenericRendererProps {
  output: string
  skillName?: string
}

// ---------------------------------------------------------------------------
// Markdown-ish parser — turns raw skill output into structured sections
// ---------------------------------------------------------------------------

interface Section {
  heading: string | null
  level: number // 1 = #, 2 = ##, 3 = ###
  content: string[]
}

function parseSections(raw: string): Section[] {
  const lines = raw.split('\n')
  const sections: Section[] = []
  let current: Section = { heading: null, level: 0, content: [] }

  for (const line of lines) {
    const headingMatch = line.match(/^(#{1,3})\s+(.+)/)
    if (headingMatch) {
      // Push previous section if it has content
      if (current.heading || current.content.length > 0) {
        sections.push(current)
      }
      current = {
        heading: headingMatch[2].trim(),
        level: headingMatch[1].length,
        content: [],
      }
    } else {
      current.content.push(line)
    }
  }
  // Push final section
  if (current.heading || current.content.length > 0) {
    sections.push(current)
  }

  return sections
}

// ---------------------------------------------------------------------------
// Inline markdown rendering (bold, italic, links, code)
// ---------------------------------------------------------------------------

function renderInline(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code style="background:rgba(0,0,0,0.05);padding:2px 6px;border-radius:4px;font-size:0.9em">$1</code>')
    .replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer" style="color:var(--brand-coral);text-decoration:none">$1</a>',
    )
}

// ---------------------------------------------------------------------------
// Content block renderer — handles lists, paragraphs, bold-label lines
// ---------------------------------------------------------------------------

function renderContentBlocks(lines: string[]) {
  const blocks: React.JSX.Element[] = []
  let listItems: string[] = []
  let orderedItems: string[] = []
  let blockKey = 0

  const flushList = () => {
    if (listItems.length > 0) {
      blocks.push(
        <ul
          key={blockKey++}
          style={{
            margin: '8px 0',
            paddingLeft: '20px',
            listStyleType: 'disc',
            color: 'var(--body-text)',
            fontSize: typography.body.size,
            lineHeight: typography.body.lineHeight,
          }}
        >
          {listItems.map((item, i) => (
            <li
              key={i}
              style={{ marginBottom: '4px' }}
              dangerouslySetInnerHTML={{ __html: renderInline(item) }}
            />
          ))}
        </ul>,
      )
      listItems = []
    }
    if (orderedItems.length > 0) {
      blocks.push(
        <ol
          key={blockKey++}
          style={{
            margin: '8px 0',
            paddingLeft: '20px',
            listStyleType: 'decimal',
            color: 'var(--body-text)',
            fontSize: typography.body.size,
            lineHeight: typography.body.lineHeight,
          }}
        >
          {orderedItems.map((item, i) => (
            <li
              key={i}
              style={{ marginBottom: '4px' }}
              dangerouslySetInnerHTML={{ __html: renderInline(item) }}
            />
          ))}
        </ol>,
      )
      orderedItems = []
    }
  }

  for (const line of lines) {
    const trimmed = line.trim()

    // Skip empty lines (but flush lists first)
    if (!trimmed) {
      flushList()
      continue
    }

    // Horizontal rule
    if (/^[-*_]{3,}$/.test(trimmed)) {
      flushList()
      blocks.push(
        <hr
          key={blockKey++}
          style={{
            border: 'none',
            borderTop: '1px solid var(--subtle-border)',
            margin: '24px 0',
          }}
        />,
      )
      continue
    }

    // Unordered list item
    const ulMatch = trimmed.match(/^[-*+]\s+(.+)/)
    if (ulMatch) {
      if (orderedItems.length > 0) flushList()
      listItems.push(ulMatch[1])
      continue
    }

    // Ordered list item
    const olMatch = trimmed.match(/^\d+[.)]\s+(.+)/)
    if (olMatch) {
      if (listItems.length > 0) flushList()
      orderedItems.push(olMatch[1])
      continue
    }

    // Regular paragraph
    flushList()

    // Bold-label line (e.g. "**Products:** SaaS platform...")
    const boldLabelMatch = trimmed.match(/^\*\*(.+?):\*\*\s*(.*)/)
    if (boldLabelMatch) {
      blocks.push(
        <p
          key={blockKey++}
          style={{
            margin: '6px 0',
            fontSize: typography.body.size,
            lineHeight: typography.body.lineHeight,
            color: 'var(--body-text)',
          }}
        >
          <strong style={{ color: 'var(--heading-text)', fontWeight: 600 }}>
            {boldLabelMatch[1]}:
          </strong>{' '}
          <span dangerouslySetInnerHTML={{ __html: renderInline(boldLabelMatch[2]) }} />
        </p>,
      )
      continue
    }

    // Regular paragraph
    blocks.push(
      <p
        key={blockKey++}
        style={{
          margin: '8px 0',
          fontSize: typography.body.size,
          lineHeight: typography.body.lineHeight,
          color: 'var(--body-text)',
        }}
        dangerouslySetInnerHTML={{ __html: renderInline(trimmed) }}
      />,
    )
  }

  flushList()
  return blocks
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function GenericRenderer({ output }: GenericRendererProps) {
  const sections = useMemo(() => parseSections(output), [output])

  return (
    <article
      style={{
        maxWidth: spacing.maxBriefing,
        margin: '0 auto',
        width: '100%',
      }}
    >
      {sections.map((section, i) => {
        return (
          <section
            key={i}
            style={{
              padding: '32px 0',
              borderBottom:
                i < sections.length - 1
                  ? '1px solid var(--subtle-border)'
                  : undefined,
            }}
          >
            {section.heading && (
              <h2
                style={{
                  fontSize:
                    section.level === 1
                      ? typography.pageTitle.size
                      : typography.sectionTitle.size,
                  fontWeight: section.level === 1 ? '700' : '600',
                  lineHeight: '1.3',
                  letterSpacing: section.level === 1 ? '-0.02em' : '-0.01em',
                  color: 'var(--heading-text)',
                  marginBottom: '16px',
                }}
              >
                {section.heading}
              </h2>
            )}
            {renderContentBlocks(section.content)}
          </section>
        )
      })}
    </article>
  )
}
