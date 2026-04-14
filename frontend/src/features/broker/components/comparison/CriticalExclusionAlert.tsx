import { AlertTriangle } from 'lucide-react'
import type { ComparisonCoverage } from '../../types/broker'

interface CriticalExclusionAlertProps {
  coverages: ComparisonCoverage[]
}

export function CriticalExclusionAlert({ coverages }: CriticalExclusionAlertProps) {
  const exclusionCoverages = coverages.filter((cov) =>
    cov.quotes.some((q) => q.has_critical_exclusion)
  )

  if (exclusionCoverages.length === 0) return null

  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />
        <div>
          <h4 className="text-red-800 font-semibold text-sm">
            Critical Exclusions Detected
          </h4>
          <ul className="mt-2 space-y-1">
            {exclusionCoverages.map((cov) => {
              const excludedQuotes = cov.quotes.filter((q) => q.has_critical_exclusion)
              return (
                <li key={cov.coverage_id} className="text-sm text-red-700">
                  <span className="font-medium">{cov.coverage_type}</span>
                  {excludedQuotes.length > 0 && excludedQuotes[0].critical_exclusion_detail && (
                    <span className="text-red-600"> &mdash; {excludedQuotes[0].critical_exclusion_detail}</span>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      </div>
    </div>
  )
}
