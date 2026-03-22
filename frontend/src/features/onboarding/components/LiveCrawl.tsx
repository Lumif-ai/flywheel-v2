import { useEffect, useRef } from 'react'
import {
  Building2,
  Package,
  Users,
  TrendingUp,
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
  isComplete: boolean
  onContinue: () => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LiveCrawl({ crawlItems, crawlTotal, isComplete, onContinue }: LiveCrawlProps) {
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
          <p className="text-3xl font-semibold text-primary tabular-nums">
            {crawlTotal} items found
          </p>
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

      {/* Item list */}
      <div className="max-h-80 overflow-y-auto space-y-2 rounded-lg border border-border p-4">
        {crawlItems.map((item, i) => {
          const IconComponent = CATEGORY_ICONS[item.icon?.toLowerCase() ?? item.category] ?? Building2
          return (
            <div
              key={i}
              className="flex items-start gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300"
              style={{ animationDelay: `${Math.min(i * 50, 500)}ms` }}
            >
              <IconComponent className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <p className="text-sm text-foreground/80">{item.content}</p>
            </div>
          )
        })}
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
