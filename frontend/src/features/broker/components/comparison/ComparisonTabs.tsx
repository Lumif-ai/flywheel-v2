import { useMemo } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import type { ComparisonCoverage } from '../../types/broker'
import {
  INSURANCE_CATEGORIES,
  SURETY_CATEGORIES,
  hasMeaningfulDifference,
} from './comparison-utils'
import { ComparisonGrid } from './ComparisonGrid'

interface ComparisonTabsProps {
  coverages: ComparisonCoverage[]
  currency: string
  selectedCarriers: Set<string>
  onToggleCarrier: (name: string) => void
  showDifferencesOnly: boolean
  highlightBest: boolean
}

export function ComparisonTabs({
  coverages,
  currency,
  selectedCarriers,
  onToggleCarrier,
  showDifferencesOnly,
  highlightBest,
}: ComparisonTabsProps) {
  const insuranceCoverages = useMemo(() => {
    const insurance = coverages.filter((c) =>
      INSURANCE_CATEGORIES.includes(c.category)
    )
    const other = coverages.filter(
      (c) =>
        !INSURANCE_CATEGORIES.includes(c.category) &&
        !SURETY_CATEGORIES.includes(c.category)
    )
    return [...insurance, ...other]
  }, [coverages])

  const suretyCoverages = useMemo(
    () => coverages.filter((c) => SURETY_CATEGORIES.includes(c.category)),
    [coverages]
  )

  const insuranceCount = useMemo(() => {
    if (!showDifferencesOnly) return insuranceCoverages.length
    const filtered = insuranceCoverages.filter((c) => hasMeaningfulDifference(c))
    return filtered.length > 0 ? filtered.length : insuranceCoverages.length
  }, [insuranceCoverages, showDifferencesOnly])

  const suretyCount = useMemo(() => {
    if (!showDifferencesOnly) return suretyCoverages.length
    const filtered = suretyCoverages.filter((c) => hasMeaningfulDifference(c))
    return filtered.length > 0 ? filtered.length : suretyCoverages.length
  }, [suretyCoverages, showDifferencesOnly])

  const hasSurety = suretyCoverages.length > 0

  return (
    <Tabs defaultValue="insurance">
      <TabsList>
        <TabsTrigger value="insurance">
          Insurance ({insuranceCount})
        </TabsTrigger>
        {hasSurety && (
          <TabsTrigger value="surety">
            Surety Bonds ({suretyCount})
          </TabsTrigger>
        )}
      </TabsList>

      <TabsContent value="insurance">
        <ComparisonGrid
          coverages={insuranceCoverages}
          currency={currency}
          selectedCarriers={selectedCarriers}
          onToggleCarrier={onToggleCarrier}
          showDifferencesOnly={showDifferencesOnly}
          highlightBest={highlightBest}
        />
      </TabsContent>

      {hasSurety && (
        <TabsContent value="surety">
          <ComparisonGrid
            coverages={suretyCoverages}
            currency={currency}
            selectedCarriers={selectedCarriers}
            onToggleCarrier={onToggleCarrier}
            showDifferencesOnly={showDifferencesOnly}
            highlightBest={highlightBest}
          />
        </TabsContent>
      )}
    </Tabs>
  )
}
