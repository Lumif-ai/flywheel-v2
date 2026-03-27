import type { LucideIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/cn'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
  className?: string
}

export function EmptyState({ icon: Icon, title, description, actionLabel, onAction, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center py-16 px-8 text-center", className)}>
      <div
        className="flex items-center justify-center size-16 rounded-2xl mb-4"
        style={{ background: 'var(--brand-light)', color: 'var(--brand-coral)' }}
      >
        <Icon className="size-8" />
      </div>
      <h3
        className="text-lg font-semibold mb-1"
        style={{ color: 'var(--heading-text)' }}
      >
        {title}
      </h3>
      <p
        className="text-sm max-w-sm mb-6"
        style={{ color: 'var(--secondary-text)' }}
      >
        {description}
      </p>
      {actionLabel && onAction && (
        <Button onClick={onAction} size="sm">
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
