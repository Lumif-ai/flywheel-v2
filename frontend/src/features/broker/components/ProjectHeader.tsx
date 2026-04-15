import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { ArrowLeft, MapPin } from 'lucide-react'
import { StatusBadge } from './StatusBadge'
import type { BrokerProjectDetail } from '../types/broker'

interface ProjectHeaderProps {
  project: BrokerProjectDetail
}

export function ProjectHeader({ project }: ProjectHeaderProps) {
  const navigate = useNavigate()

  const formattedValue =
    project.contract_value != null
      ? new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: project.currency || 'USD',
          maximumFractionDigits: 0,
        }).format(project.contract_value)
      : null

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => navigate('/broker/projects')}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-lg font-semibold leading-none">{project.name}</h1>
        <span className="text-sm text-muted-foreground">
          {project.project_type || 'General'}
        </span>
        <StatusBadge status={project.status} />
      </div>
      <div className="flex items-center gap-3">
        {project.location && (
          <span className="flex items-center gap-1 text-sm text-muted-foreground">
            <MapPin className="h-3.5 w-3.5" />
            {project.location}
          </span>
        )}
        {formattedValue && (
          <span className="text-sm font-medium">{formattedValue}</span>
        )}
      </div>
    </div>
  )
}
