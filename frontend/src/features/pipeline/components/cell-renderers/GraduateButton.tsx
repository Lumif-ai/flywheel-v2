import { ArrowUpRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { ICellRendererParams } from 'ag-grid-community'
import type { PipelineItem } from '../../types/pipeline'

interface GraduateContext {
  onGraduate?: (id: string, name: string) => void
}

export function GraduateButton(
  props: ICellRendererParams<PipelineItem, unknown> & { context: GraduateContext }
) {
  const { data, context } = props
  if (!data) return null
  return (
    <div className="flex items-center h-full">
      <Button
        variant="ghost"
        size="sm"
        className="h-8 text-xs gap-1"
        onClick={() => context.onGraduate?.(data.id, data.name)}
      >
        Graduate
        <ArrowUpRight className="size-3.5" />
      </Button>
    </div>
  )
}
