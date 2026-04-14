import { useCallback, useMemo } from 'react'
import { AgGridReact } from 'ag-grid-react'
import type { ColDef, ICellRendererParams, CellValueChangedEvent } from 'ag-grid-community'
import { AlertTriangle, CheckCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { gridTheme } from '@/shared/grid/theme'
import { StatusBadge } from '@/shared/grid/cell-renderers'
import { useBrokerProject } from '../../hooks/useBrokerProject'
import { useCoverageMutation } from '../../hooks/useCoverageMutation'
import { useApproveProject } from '../../hooks/useApproveProject'
import type { ProjectCoverage } from '../../types/broker'

const INSURANCE_CATEGORIES = ['liability', 'property', 'auto', 'workers_comp', 'specialty']
const SURETY_CATEGORIES = ['surety']

interface CoverageTabProps {
  projectId: string
}

function ConfidenceDot(props: ICellRendererParams) {
  const value = props.value as string | undefined
  const colorMap: Record<string, string> = {
    high: '#22C55E',
    medium: '#F59E0B',
    low: '#EF4444',
  }
  const color = colorMap[value ?? ''] ?? '#D1D5DB'
  return (
    <div className="flex items-center h-full" title={`Confidence: ${value ?? 'unknown'}`}>
      <span
        style={{
          display: 'inline-block',
          width: 8,
          height: 8,
          borderRadius: '50%',
          backgroundColor: color,
        }}
      />
    </div>
  )
}

export function CoverageTab({ projectId }: CoverageTabProps) {
  const { data: project, isLoading } = useBrokerProject(projectId)
  const mutation = useCoverageMutation(projectId)
  const approve = useApproveProject(projectId)

  const coverages = project?.coverages ?? []

  const missingCoverages = useMemo(
    () => coverages.filter((c) => c.gap_status === 'missing'),
    [coverages],
  )

  const insuranceCoverages = useMemo(() => {
    const insurance = coverages.filter((c) => INSURANCE_CATEGORIES.includes(c.category))
    const other = coverages.filter(
      (c) => !INSURANCE_CATEGORIES.includes(c.category) && !SURETY_CATEGORIES.includes(c.category),
    )
    return [...insurance, ...other]
  }, [coverages])

  const suretyCoverages = useMemo(
    () => coverages.filter((c) => SURETY_CATEGORIES.includes(c.category)),
    [coverages],
  )

  const onCellValueChanged = useCallback(
    (event: CellValueChangedEvent<ProjectCoverage>) => {
      if (event.newValue === event.oldValue) return
      const field = event.colDef.field
      if (!field || !event.data) return
      mutation.mutate({
        coverageId: event.data.id,
        updates: { [field]: event.newValue, is_manual_override: true },
      })
    },
    [mutation],
  )

  const columnDefs: ColDef<ProjectCoverage>[] = useMemo(
    () => [
      {
        field: 'coverage_type',
        headerName: 'Coverage Type',
        flex: 2,
        minWidth: 180,
        editable: true,
      },
      {
        field: 'description',
        headerName: 'Description',
        flex: 2,
        minWidth: 200,
      },
      {
        field: 'required_limit',
        headerName: 'Required Limit',
        flex: 1,
        minWidth: 130,
        editable: true,
        valueFormatter: (params) => {
          if (params.value == null) return '\u2014'
          return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            maximumFractionDigits: 0,
          }).format(params.value)
        },
      },
      {
        field: 'confidence',
        headerName: 'Confidence',
        width: 110,
        cellRenderer: ConfidenceDot,
      },
      {
        field: 'gap_status',
        headerName: 'Gap Status',
        width: 130,
        cellRenderer: StatusBadge,
        cellRendererParams: {
          colorMap: {
            covered: { bg: '#DCFCE7', text: '#15803D' },
            insufficient: { bg: '#FEF3C7', text: '#A16207' },
            missing: { bg: '#FEE2E2', text: '#B91C1C' },
            unknown: { bg: '#F3F4F6', text: '#6B7280' },
          },
        },
      },
      {
        field: 'is_manual_override',
        headerName: 'Source',
        width: 130,
        valueGetter: (params) =>
          params.data?.is_manual_override ? 'Manual Override' : 'AI Extracted',
        cellRenderer: StatusBadge,
        cellRendererParams: {
          colorMap: {
            'manual override': { bg: '#F3E8FF', text: '#7E22CE' },
            'ai extracted': { bg: '#DBEAFE', text: '#1D4ED8' },
          },
        },
      },
    ],
    [],
  )

  if (isLoading) {
    return (
      <div className="space-y-4 py-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-11 w-full rounded" />
        ))}
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
    <div className="space-y-6">
      {/* Critical Findings Alert */}
      {missingCoverages.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-red-800">
                {missingCoverages.length} critical gap{missingCoverages.length > 1 ? 's' : ''} found
              </p>
              <ul className="mt-1 text-sm text-red-700 list-disc list-inside">
                {missingCoverages.map((c) => (
                  <li key={c.id}>{c.coverage_type}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Insurance Coverages Section */}
      {insuranceCoverages.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Insurance Coverages</h3>
          <AgGridReact<ProjectCoverage>
            theme={gridTheme}
            domLayout="autoHeight"
            rowData={insuranceCoverages}
            columnDefs={columnDefs}
            onCellValueChanged={onCellValueChanged}
            suppressMovableColumns
            headerHeight={36}
            rowHeight={44}
          />
        </div>
      )}

      {/* Surety Bonds Section */}
      {suretyCoverages.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Surety Bonds</h3>
          <AgGridReact<ProjectCoverage>
            theme={gridTheme}
            domLayout="autoHeight"
            rowData={suretyCoverages}
            columnDefs={columnDefs}
            onCellValueChanged={onCellValueChanged}
            suppressMovableColumns
            headerHeight={36}
            rowHeight={44}
          />
        </div>
      )}

      {/* Approve Project Button */}
      <div className="pt-2">
        {project?.approval_status === 'approved' ? (
          <div className="flex items-center gap-2 text-green-700">
            <CheckCircle className="h-4 w-4" />
            <span className="text-sm font-medium">Project Approved</span>
          </div>
        ) : (
          <Button onClick={() => approve.mutate()} disabled={approve.isPending}>
            {approve.isPending ? 'Approving...' : 'Approve Project'}
          </Button>
        )}
      </div>
    </div>
  )
}
