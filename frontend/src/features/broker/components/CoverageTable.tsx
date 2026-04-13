import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Edit2, Save, X } from 'lucide-react'
import { useCoverageMutation } from '../hooks/useCoverageMutation'
import type { ProjectCoverage } from '../types/broker'

interface CoverageTableProps {
  coverages: ProjectCoverage[]
  projectId: string
  isAnalyzing: boolean
}

export function CoverageTable({ coverages, projectId, isAnalyzing }: CoverageTableProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValues, setEditValues] = useState<Partial<ProjectCoverage>>({})
  const mutation = useCoverageMutation(projectId)

  function startEdit(coverage: ProjectCoverage) {
    setEditingId(coverage.id)
    setEditValues({
      coverage_type: coverage.coverage_type,
      description: coverage.description,
      required_limit: coverage.required_limit,
    })
  }

  function cancelEdit() {
    setEditingId(null)
    setEditValues({})
  }

  function saveEdit(coverageId: string) {
    mutation.mutate(
      { coverageId, updates: { ...editValues, is_manual_override: true } },
      {
        onSuccess: () => {
          setEditingId(null)
          setEditValues({})
        },
      }
    )
  }

  if (isAnalyzing) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-lg" />
        ))}
        <p className="text-sm text-muted-foreground text-center">Analyzing contract...</p>
      </div>
    )
  }

  if (coverages.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
        No coverages extracted yet. Trigger analysis to extract requirements.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-2 text-left font-medium">Coverage Type</th>
            <th className="px-3 py-2 text-left font-medium">Description</th>
            <th className="px-3 py-2 text-left font-medium">Limit</th>
            <th className="px-3 py-2 text-left font-medium">Category</th>
            <th className="px-3 py-2 text-left font-medium">Confidence</th>
            <th className="px-3 py-2 text-left font-medium">Source</th>
            <th className="px-3 py-2 text-right font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {coverages.map((cov) => (
            <tr key={cov.id} className="border-b last:border-0 hover:bg-muted/30">
              {editingId === cov.id ? (
                <>
                  <td className="px-3 py-2">
                    <Input
                      value={editValues.coverage_type ?? ''}
                      onChange={(e) => setEditValues((v) => ({ ...v, coverage_type: e.target.value }))}
                      className="h-8 text-sm"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <Input
                      value={editValues.description ?? ''}
                      onChange={(e) => setEditValues((v) => ({ ...v, description: e.target.value }))}
                      className="h-8 text-sm"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <Input
                      type="number"
                      value={editValues.required_limit ?? ''}
                      onChange={(e) =>
                        setEditValues((v) => ({
                          ...v,
                          required_limit: e.target.value ? Number(e.target.value) : null,
                        }))
                      }
                      className="h-8 text-sm w-28"
                    />
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{cov.category}</td>
                  <td className="px-3 py-2"><ConfidenceBadge confidence={cov.confidence} /></td>
                  <td className="px-3 py-2"><SourceBadge isManual={cov.is_manual_override} /></td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => saveEdit(cov.id)}
                        disabled={mutation.isPending}
                      >
                        <Save className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={cancelEdit}>
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </td>
                </>
              ) : (
                <>
                  <td className="px-3 py-2 font-medium">{cov.coverage_type}</td>
                  <td className="px-3 py-2 text-muted-foreground max-w-[200px] truncate">
                    {cov.description || '—'}
                  </td>
                  <td className="px-3 py-2">
                    {cov.required_limit != null
                      ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(cov.required_limit)
                      : '—'}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{cov.category}</td>
                  <td className="px-3 py-2"><ConfidenceBadge confidence={cov.confidence} /></td>
                  <td className="px-3 py-2"><SourceBadge isManual={cov.is_manual_override} /></td>
                  <td className="px-3 py-2 text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => startEdit(cov)}
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </Button>
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const colorMap: Record<string, string> = {
    high: 'bg-green-50 text-green-700 border-green-200',
    medium: 'bg-yellow-50 text-yellow-700 border-yellow-200',
    low: 'bg-red-50 text-red-700 border-red-200',
  }
  const className = colorMap[confidence] ?? colorMap.medium
  return (
    <Badge variant="outline" className={className}>
      {confidence}
    </Badge>
  )
}

function SourceBadge({ isManual }: { isManual: boolean }) {
  return (
    <Badge
      variant="outline"
      className={isManual
        ? 'bg-purple-50 text-purple-700 border-purple-200'
        : 'bg-blue-50 text-blue-700 border-blue-200'
      }
    >
      {isManual ? 'Manual Override' : 'AI Extracted'}
    </Badge>
  )
}
