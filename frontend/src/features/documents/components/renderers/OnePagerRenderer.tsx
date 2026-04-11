import type { OnePagerData } from '../../types/one-pager'

interface OnePagerRendererProps {
  data: OnePagerData
}

export function OnePagerRenderer({ data }: OnePagerRendererProps) {
  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-semibold">{data.title}</h1>
      {data.sections.map((section, i) => (
        <div key={i} className="space-y-2">
          <h2 className="text-lg font-medium">{section.heading}</h2>
          <p className="text-sm text-muted-foreground whitespace-pre-wrap">{section.body}</p>
        </div>
      ))}
    </div>
  )
}
