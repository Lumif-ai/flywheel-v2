import { useQuery } from '@tanstack/react-query'
import { CalendarDays, ArrowRight } from 'lucide-react'
import { api } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import type { WorkItem, PaginatedResponse } from '@/types/api'

const statusColors: Record<string, 'default' | 'secondary' | 'outline'> = {
  'to_do': 'outline',
  'in_progress': 'default',
  'done': 'secondary',
}

const statusLabels: Record<string, string> = {
  'to_do': 'To Do',
  'in_progress': 'In Progress',
  'done': 'Done',
}

export function PrepPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['work-items'],
    queryFn: () => api.get<PaginatedResponse<WorkItem>>('/work-items'),
  })

  const items = data?.items ?? []

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Prep</h1>
        <p className="text-muted-foreground mt-1">
          Upcoming work and meetings
        </p>
      </div>

      <div className="max-w-3xl space-y-3">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-xl" />
          ))
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <CalendarDays className="size-12 text-muted-foreground/40 mb-4" />
            <h3 className="text-base font-medium text-foreground">No work items yet</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-sm">
              Connect your calendar to get meeting prep suggestions, or create work items manually.
            </p>
          </div>
        ) : (
          items.map((item) => (
            <button
              key={item.id}
              className="w-full text-left rounded-xl border border-border bg-background p-4 hover:bg-muted/50 transition-colors group"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-sm font-medium text-foreground truncate">
                      {item.title}
                    </h3>
                    <Badge variant={statusColors[item.status] ?? 'outline'}>
                      {statusLabels[item.status] ?? item.status}
                    </Badge>
                  </div>
                  {item.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {item.description}
                    </p>
                  )}
                  {item.skill_name && (
                    <div className="mt-2">
                      <Badge variant="secondary" className="text-[10px]">
                        {item.skill_name}
                      </Badge>
                    </div>
                  )}
                </div>
                <ArrowRight className="size-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-1" />
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  )
}
