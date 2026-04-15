import type { BrokerProjectStatus, AnalysisStatus } from '../types/broker'

interface StepIndicatorProps {
  projectStatus: BrokerProjectStatus
  analysisStatus: AnalysisStatus
  onStepClick: (tab: string) => void
}

const WORKFLOW_STEPS = [
  { key: 'overview', label: 'Overview', tab: 'overview' },
  { key: 'analysis', label: 'Analysis', tab: 'analysis' },
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

    case 'analysis':
      if (isAtLeast(projectStatus, 'gaps_identified')) return 'green'
      if (projectStatus === 'analyzing' || analysisStatus === 'running') return 'amber'
      return 'grey'

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

/** Checkmark icon for completed steps */
function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
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
    <div className="flex items-start w-full px-2 py-3">
      {steps.map((step, index) => {
        const isCompleted = step.state === 'green'
        const isCurrent = step.state === 'amber'

        return (
          <div key={step.key} className="flex items-start flex-1 last:flex-none">
            {/* Step dot + label */}
            <button
              type="button"
              className="flex flex-col items-center gap-1.5 cursor-pointer group min-w-[60px]"
              onClick={() => onStepClick(step.tab)}
            >
              {/* Circle */}
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center transition-all group-hover:ring-2 group-hover:ring-offset-2 group-hover:ring-gray-300"
                style={{
                  backgroundColor: isCompleted
                    ? '#16a34a'
                    : isCurrent
                      ? '#E94D35'
                      : '#E5E7EB',
                }}
              >
                {isCompleted ? (
                  <CheckIcon />
                ) : isCurrent ? (
                  <div className="w-3 h-3 rounded-full bg-white" />
                ) : (
                  <span className="text-[12px] text-[#9CA3AF] font-medium">
                    {index + 1}
                  </span>
                )}
              </div>

              {/* Label */}
              <span
                className="text-[12px] font-medium transition-colors group-hover:text-[#121212]"
                style={{
                  color: isCompleted
                    ? '#374151'
                    : isCurrent
                      ? '#E94D35'
                      : '#9CA3AF',
                }}
              >
                {step.label}
              </span>

              {/* Status text */}
              <span
                className="text-[10px]"
                style={{
                  color: isCompleted
                    ? '#16a34a'
                    : isCurrent
                      ? '#E94D35'
                      : '#9CA3AF',
                }}
              >
                {isCompleted ? 'Complete' : isCurrent ? 'In progress' : 'Pending'}
              </span>
            </button>

            {/* Connecting line */}
            {index < steps.length - 1 && (
              <div
                className="h-[2px] flex-1 mx-1 mt-4 rounded-full"
                style={{
                  backgroundColor: steps[index + 1].state !== 'grey'
                    ? '#86efac'
                    : '#E5E7EB',
                }}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
