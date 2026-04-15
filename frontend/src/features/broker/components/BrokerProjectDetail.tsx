import { useParams, useSearchParams } from 'react-router'
import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useBrokerProject } from '../hooks/useBrokerProject'
import { ProjectHeader } from './ProjectHeader'
import { StepIndicator } from './StepIndicator'
import { ProjectSidebar } from './ProjectSidebar'
import { OverviewTab } from './tabs/OverviewTab'
import { AnalysisTab } from './tabs/AnalysisTab'
import { CoverageTab } from './tabs/CoverageTab'
import { CarriersTab } from './tabs/CarriersTab'
import { QuotesTab } from './tabs/QuotesTab'
import { CompareTab } from './tabs/CompareTab'

const TAB_CONFIG = [
  { key: 'overview', label: 'Overview' },
  { key: 'analysis', label: 'Analysis' },
  { key: 'coverage', label: 'Coverage' },
  { key: 'carriers', label: 'Carriers' },
  { key: 'quotes', label: 'Quotes' },
  { key: 'compare', label: 'Compare' },
] as const

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
    <div className="p-6 space-y-6">
      <ProjectHeader project={project} />
      <StepIndicator
        projectStatus={project.status}
        analysisStatus={project.analysis_status}
        onStepClick={handleTabChange}
      />
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList
          variant="line"
          className="w-full justify-start border-b border-border"
        >
          {TAB_CONFIG.map((tab) => (
            <TabsTrigger key={tab.key} value={tab.key}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
        <div className="mt-6">
          {activeTab === 'analysis' ? (
            // Full-width: no sidebar for analysis split-pane
            <TabsContent value="analysis">
              <AnalysisTab project={project} />
            </TabsContent>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <TabsContent value="overview">
                  <OverviewTab project={project} />
                </TabsContent>
                <TabsContent value="coverage">
                  <CoverageTab projectId={project.id} />
                </TabsContent>
                <TabsContent value="carriers">
                  <CarriersTab projectId={project.id} />
                </TabsContent>
                <TabsContent value="quotes">
                  <QuotesTab projectId={project.id} />
                </TabsContent>
                <TabsContent value="compare">
                  <CompareTab projectId={project.id} />
                </TabsContent>
              </div>
              <div>
                <ProjectSidebar project={project} />
              </div>
            </div>
          )}
        </div>
      </Tabs>
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Skeleton className="h-9 w-9 rounded-md" />
        <div className="space-y-2">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-4 w-24" />
        </div>
      </div>
      {/* Step indicator skeleton */}
      <div className="flex items-center gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex flex-col items-center gap-1">
            <Skeleton className="h-3 w-3 rounded-full" />
            <Skeleton className="h-3 w-12" />
          </div>
        ))}
      </div>
      {/* Tab bar skeleton */}
      <div className="flex gap-4 border-b pb-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-5 w-16" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          <Skeleton className="h-5 w-40" />
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded-lg" />
          ))}
        </div>
        <div className="space-y-4">
          <Skeleton className="h-48 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      </div>
    </div>
  )
}
