import { useEffect, useRef } from 'react'
import {
  Building2,
  Package,
  Users,
  TrendingUp,
  Swords,
  Cpu,
  UserCheck,
  DollarSign,
  CheckCircle2,
  type LucideIcon,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { CrawlItem } from '../hooks/useOnboarding'

// ---------------------------------------------------------------------------
// Category icon mapping
// ---------------------------------------------------------------------------

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  company_info: Building2,
  product: Package,
  team: Users,
  market: TrendingUp,
  competitive: Swords,
  technology: Cpu,
  customer: UserCheck,
  financial: DollarSign,
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface LiveCrawlProps {
  crawlItems: CrawlItem[]
  crawlTotal: number
  crawlStatus: string | null
  isComplete: boolean
  onContinue: () => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LiveCrawl({ crawlItems, crawlTotal, crawlStatus, isComplete, onContinue }: LiveCrawlProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [crawlItems.length])

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      {!isComplete ? (
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            Discovering intelligence
            <span className="inline-flex ml-1">
              <span className="animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
              <span className="animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
              <span className="animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
            </span>
          </h2>
          {crawlTotal > 0 ? (
            <p className="text-3xl font-semibold text-primary tabular-nums">
              {crawlTotal} items found
            </p>
          ) : crawlStatus ? (
            <p className="text-sm text-muted-foreground animate-pulse">
              {crawlStatus}
            </p>
          ) : null}
        </div>
      ) : (
        <div className="text-center space-y-3">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
            <CheckCircle2 className="h-6 w-6 text-green-600 dark:text-green-400" />
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            Discovery complete
          </h2>
          <p className="text-lg text-muted-foreground">
            {crawlTotal} entries deposited into your context store
          </p>
        </div>
      )}

      {/* Grouped category cards */}
      <div className="max-h-[28rem] overflow-y-auto space-y-3 rounded-lg border border-border p-4">
        {crawlItems.map((group, i) => {
          const IconComponent = CATEGORY_ICONS[group.category] ?? Building2
          return (
            <div
              key={i}
              className="animate-in fade-in slide-in-from-bottom-2 duration-300 rounded-md border border-border/50 bg-muted/30 p-3"
              style={{ animationDelay: `${Math.min(i * 80, 400)}ms` }}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <IconComponent className="h-4 w-4 shrink-0 text-primary" />
                <span className="text-sm font-medium text-foreground">{group.label}</span>
                <span className="text-xs text-muted-foreground ml-auto">{group.items.length}</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {group.items.map((item, j) => (
                  <span
                    key={j}
                    className="inline-block rounded-full bg-background px-2.5 py-0.5 text-xs text-foreground/80 border border-border/50"
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>
          )
        })}
        {/* Show status while waiting for discoveries */}
        {crawlItems.length === 0 && crawlStatus && (
          <div className="flex items-center justify-center gap-2 py-8 text-muted-foreground">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
            <span className="text-sm">{crawlStatus}</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Continue button on complete */}
      {isComplete && (
        <div className="flex justify-center">
          <Button onClick={onContinue} size="lg" className="gap-2 px-8">
            Continue
          </Button>
        </div>
      )}
    </div>
  )
}
