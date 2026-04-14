import type { BrokerProjectStatus, AnalysisStatus } from '../types/broker'

interface StepIndicatorProps {
  projectStatus: BrokerProjectStatus
  analysisStatus: AnalysisStatus
  onStepClick: (tab: string) => void
}

const WORKFLOW_STEPS = [
  { key: 'overview', label: 'Overview', tab: 'overview' },
  { key: 'coverage', label: 'Coverage', tab: 'coverage' },
  { key: 'carriers', label: 'Carriers', tab: 'carriers' },
  { key: 'quotes', label: 'Quotes', tab: 'quotes' },
  { key: 'compare', label: 'Compare', tab: 'compare' },
] as const

type StepState = 'grey' | 'amber' | 'green'

const STATUS_ORDER: BrokerProjectStatus[] = [
  'new_request',
  'analyzing',
  'analysis_failed',
  'gaps_identified',
  'soliciting',
  'quotes_partial',
  'quotes_complete',
  'recommended',
  'delivered',
  'bound',
  'cancelled',
]

function isAtLeast(status: BrokerProjectStatus, target: BrokerProjectStatus): boolean {
  return STATUS_ORDER.indexOf(status) >= STATUS_ORDER.indexOf(target)
}

function getStepState(
  stepKey: string,
  projectStatus: BrokerProjectStatus,
  analysisStatus: AnalysisStatus,
): StepState {
  switch (stepKey) {
    case 'overview':
      return 'green'

    case 'coverage':
      if (isAtLeast(projectStatus, 'gaps_identified')) return 'green'
      if (projectStatus === 'analyzing' || analysisStatus === 'running') return 'amber'
      return 'grey'

    case 'carriers':
      if (isAtLeast(projectStatus, 'soliciting')) return 'green'
      if (projectStatus === 'gaps_identified') return 'amber'
      return 'grey'

    case 'quotes':
      if (isAtLeast(projectStatus, 'quotes_complete')) return 'green'
      if (projectStatus === 'quotes_partial' || projectStatus === 'soliciting') return 'amber'
      return 'grey'

    case 'compare':
      if (
        projectStatus === 'recommended' ||
        projectStatus === 'delivered' ||
        projectStatus === 'bound'
      )
        return 'green'
      if (projectStatus === 'quotes_complete') return 'amber'
      return 'grey'

    default:
      return 'grey'
  }
}

const DOT_COLORS: Record<StepState, string> = {
  grey: 'bg-gray-300',
  amber: 'bg-amber-400',
  green: 'bg-green-500',
}

export function StepIndicator({
  projectStatus,
  analysisStatus,
  onStepClick,
}: StepIndicatorProps) {
  const steps = WORKFLOW_STEPS.map((step) => ({
    ...step,
    state: getStepState(step.key, projectStatus, analysisStatus),
  }))

  return (
    <div className="flex items-center w-full">
      {steps.map((step, index) => (
        <div key={step.key} className="flex items-center flex-1 last:flex-none">
          {/* Step button */}
          <button
            type="button"
            className="flex flex-col items-center gap-1 cursor-pointer group"
            onClick={() => onStepClick(step.tab)}
          >
            <div
              className={`w-3 h-3 rounded-full transition-colors ${DOT_COLORS[step.state]} group-hover:ring-2 group-hover:ring-offset-2 group-hover:ring-gray-300`}
            />
            <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
              {step.label}
            </span>
          </button>

          {/* Connecting line */}
          {index < steps.length - 1 && (
            <div
              className={`h-0.5 flex-1 mx-2 mt-[-1rem] ${
                steps[index + 1].state !== 'grey' ? 'bg-green-300' : 'bg-gray-200'
              }`}
            />
          )}
        </div>
      ))}
    </div>
  )
}
