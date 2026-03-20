import { memo } from 'react'
import { sanitizeHTML } from '@/lib/sanitize'

interface SkillOutputProps {
  html: string
}

export const SkillOutput = memo(function SkillOutput({ html }: SkillOutputProps) {
  const clean = sanitizeHTML(html)

  return (
    <div
      className={[
        'mt-2 rounded-lg border bg-card p-4 text-card-foreground',
        '[&_h1]:text-2xl [&_h1]:font-bold [&_h1]:mb-2',
        '[&_h2]:text-xl [&_h2]:font-semibold [&_h2]:mb-2',
        '[&_h3]:text-lg [&_h3]:font-medium [&_h3]:mb-1',
        '[&_p]:my-2',
        '[&_ul]:list-disc [&_ul]:pl-4 [&_ol]:list-decimal [&_ol]:pl-4',
        '[&_li]:my-1',
        '[&_table]:w-full [&_table]:border-collapse',
        '[&_th]:border [&_th]:p-2 [&_th]:bg-muted [&_th]:text-left',
        '[&_td]:border [&_td]:p-2',
        '[&_code]:bg-muted [&_code]:px-1 [&_code]:rounded [&_code]:text-sm',
        '[&_pre]:bg-muted [&_pre]:p-4 [&_pre]:rounded-lg [&_pre]:overflow-x-auto',
        '[&_a]:text-primary [&_a]:underline',
        '[&_blockquote]:border-l-4 [&_blockquote]:border-muted [&_blockquote]:pl-4 [&_blockquote]:italic',
      ].join(' ')}
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  )
})
