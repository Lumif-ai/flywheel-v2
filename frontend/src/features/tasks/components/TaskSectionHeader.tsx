import { Badge } from '@/components/ui/badge'

interface TaskSectionHeaderProps {
  title: string
  count: number
  action?: React.ReactNode
}

export function TaskSectionHeader({ title, count, action }: TaskSectionHeaderProps) {
  return (
    <div className="flex items-center justify-between" style={{ marginBottom: '16px' }}>
      <div className="flex items-center gap-2">
        <h2
          style={{
            fontSize: '18px',
            fontWeight: 600,
            lineHeight: '1.4',
            color: 'var(--heading-text)',
            margin: 0,
          }}
        >
          {title}
        </h2>
        <Badge variant="secondary">{count}</Badge>
      </div>
      {action && <div>{action}</div>}
    </div>
  )
}
