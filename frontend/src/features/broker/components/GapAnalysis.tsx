import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Check, AlertTriangle, X, HelpCircle } from 'lucide-react'
import { useGapAnalysis } from '../hooks/useGapAnalysis'
import type { ProjectCoverage } from '../types/broker'

interface GapAnalysisProps {
  coverages: ProjectCoverage[]
  projectId: string
}

const INSURANCE_CATEGORIES = ['liability', 'property', 'auto', 'workers_comp', 'specialty']
const SURETY_CATEGORIES = ['surety']

const STATUS_CONFIG: Record<string, { bg: string; text: string; icon: React.ElementType }> = {
  covered: { bg: 'bg-green-50', text: 'text-green-700', icon: Check },
  insufficient: { bg: 'bg-yellow-50', text: 'text-yellow-700', icon: AlertTriangle },
  missing: { bg: 'bg-red-50', text: 'text-red-700', icon: X },
  unknown: { bg: 'bg-gray-50', text: 'text-gray-500', icon: HelpCircle },
}

function formatCurrency(value: number | null): string {
  if (value == null) return '\u2014'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

function computeGapAmount(coverage: ProjectCoverage): string {
  if (coverage.gap_status === 'missing') return formatCurrency(coverage.required_limit)
  if (coverage.gap_status === 'insufficient' && coverage.required_limit != null && coverage.current_limit != null) {
    return formatCurrency(coverage.required_limit - coverage.current_limit)
  }
  return '\u2014'
}

function GapStatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.unknown
  const Icon = config.icon
  return (
    <Badge variant="outline" className={`${config.bg} ${config.text} border-0 gap-1`}>
      <Icon className="h-3 w-3" />
      {status}
    </Badge>
  )
}

function CoverageSection({ title, coverages }: { title: string; coverages: ProjectCoverage[] }) {
  if (coverages.length === 0) return null
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-muted-foreground">{title}</h4>
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-3 py-2 text-left font-medium">Coverage Type</th>
              <th className="px-3 py-2 text-left font-medium">Required Limit</th>
              <th className="px-3 py-2 text-left font-medium">Current Limit</th>
              <th className="px-3 py-2 text-left font-medium">Gap Amount</th>
              <th className="px-3 py-2 text-left font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {coverages.map((cov) => (
              <tr key={cov.id} className="border-b last:border-0 hover:bg-muted/30">
                <td className="px-3 py-2 font-medium">{cov.coverage_type}</td>
                <td className="px-3 py-2">{formatCurrency(cov.required_limit)}</td>
                <td className="px-3 py-2">{formatCurrency(cov.current_limit)}</td>
                <td className="px-3 py-2">{computeGapAmount(cov)}</td>
                <td className="px-3 py-2"><GapStatusBadge status={cov.gap_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function GapAnalysis({ coverages, projectId }: GapAnalysisProps) {
  const gapMutation = useGapAnalysis(projectId)

  if (coverages.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
        No coverages found. Run contract analysis first.
      </div>
    )
  }

  const insuranceCoverages = coverages.filter((c) => INSURANCE_CATEGORIES.includes(c.category))
  const suretyCoverages = coverages.filter((c) => SURETY_CATEGORIES.includes(c.category))
  // Any coverages with categories not in either group go to insurance section
  const otherCoverages = coverages.filter(
    (c) => !INSURANCE_CATEGORIES.includes(c.category) && !SURETY_CATEGORIES.includes(c.category)
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Gap Analysis</h3>
        <Button
          variant="outline"
          size="sm"
          onClick={() => gapMutation.mutate()}
          disabled={gapMutation.isPending}
        >
          {gapMutation.isPending ? 'Analyzing...' : 'Run Gap Analysis'}
        </Button>
      </div>

      <CoverageSection title="Insurance Coverages" coverages={[...insuranceCoverages, ...otherCoverages]} />
      <CoverageSection title="Surety Bonds" coverages={suretyCoverages} />
    </div>
  )
}
