import { useParams, useSearchParams } from 'react-router'
import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useBrokerProject } from '../hooks/useBrokerProject'
import { ProjectHeader } from './ProjectHeader'
import { OverviewTab } from './tabs/OverviewTab'
import { AnalysisTab } from './tabs/AnalysisTab'
import { CoverageTab } from './tabs/CoverageTab'
import { CarriersTab } from './tabs/CarriersTab'
import { QuotesTab } from './tabs/QuotesTab'
import { CompareTab } from './tabs/CompareTab'
import { DeliveryTab } from './tabs/DeliveryTab'
import type { BrokerProjectStatus, AnalysisStatus } from '../types/broker'

const TAB_CONFIG = [
  { key: 'overview', label: 'Overview' },
  { key: 'analysis', label: 'Analysis' },
  { key: 'coverage', label: 'Coverage' },
  { key: 'carriers', label: 'Carriers' },
  { key: 'quotes', label: 'Quotes' },
  { key: 'compare', label: 'Compare' },
  { key: 'delivery', label: 'Delivery' },
] as const

/* ── Step-status logic (from removed StepIndicator) ── */

const STATUS_ORDER: BrokerProjectStatus[] = [
  'new_request', 'analyzing', 'analysis_failed', 'gaps_identified',
  'soliciting', 'quotes_partial', 'quotes_complete',
  'recommended', 'delivered', 'bound', 'cancelled',
]

function isAtLeast(status: BrokerProjectStatus, target: BrokerProjectStatus) {
  return STATUS_ORDER.indexOf(status) >= STATUS_ORDER.indexOf(target)
}

type StepState = 'grey' | 'amber' | 'green'

function getStepState(
  stepKey: string,
  projectStatus: BrokerProjectStatus,
  analysisStatus: AnalysisStatus,
): StepState {
  switch (stepKey) {
    case 'overview':
      return 'green'
    case 'analysis':
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
      if (['recommended', 'delivered', 'bound'].includes(projectStatus)) return 'green'
      if (projectStatus === 'quotes_complete') return 'amber'
      return 'grey'
    case 'delivery':
      if (projectStatus === 'delivered' || projectStatus === 'bound') return 'green'
      if (projectStatus === 'recommended') return 'amber'
      return 'grey'
    default:
      return 'grey'
  }
}

const DOT_CLASS: Record<StepState, string> = {
  green: 'bg-green-500',
  amber: 'bg-[#E94D35]',
  grey: 'bg-gray-300',
}

type TabKey = (typeof TAB_CONFIG)[number]['key']

const VALID_TABS = new Set<string>(TAB_CONFIG.map((t) => t.key))

export function BrokerProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: project, isLoading } = useBrokerProject(id!)

  const rawTab = searchParams.get('tab') || 'overview'
  const activeTab: TabKey = VALID_TABS.has(rawTab)
    ? (rawTab as TabKey)
    : 'overview'

  const handleTabChange = (value: string | number | null) => {
    setSearchParams({ tab: String(value) }, { replace: true })
  }

  if (isLoading) return <DetailSkeleton />
  if (!project) {
    return (
      <div className="p-6 text-center">
        <p className="text-muted-foreground">Project not found.</p>
        <Button
          variant="ghost"
          className="mt-4"
          onClick={() => navigate('/broker/projects')}
        >
          Back to Projects
        </Button>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-3">
      <ProjectHeader project={project} />
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList
          variant="line"
          className="w-full justify-start border-b border-border"
        >
          {TAB_CONFIG.map((tab) => {
            const state = getStepState(tab.key, project.status, project.analysis_status)
            return (
              <TabsTrigger key={tab.key} value={tab.key} className="flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full ${DOT_CLASS[state]}`} />
                {tab.label}
              </TabsTrigger>
            )
          })}
        </TabsList>
        <div className="mt-6">
          <TabsContent value="overview">
            <OverviewTab project={project} />
          </TabsContent>
          <TabsContent value="analysis">
            <AnalysisTab project={project} />
          </TabsContent>
          <TabsContent value="coverage">
            <CoverageTab projectId={project.id} />
          </TabsContent>
          <TabsContent value="carriers">
            <CarriersTab projectId={project.id} />
          </TabsContent>
          <TabsContent value="quotes">
            <QuotesTab projectId={project.id} coverages={project.coverages ?? []} />
          </TabsContent>
          <TabsContent value="compare">
            <CompareTab projectId={project.id} />
          </TabsContent>
          <TabsContent value="delivery">
            <DeliveryTab projectId={project.id} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="p-6 space-y-3">
      <div className="flex items-center gap-3">
        <Skeleton className="h-9 w-9 rounded-md" />
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      {/* Tab bar skeleton */}
      <div className="flex gap-4 border-b pb-2">
        {Array.from({ length: 7 }).map((_, i) => (
          <Skeleton key={i} className="h-5 w-16" />
        ))}
      </div>
      <div className="space-y-3">
        <Skeleton className="h-5 w-40" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-lg" />
        ))}
      </div>
    </div>
  )
}
