import { formatCurrency } from './comparison-utils'
import { cn } from '@/lib/cn'

interface TotalPremiumRowProps {
  carriers: { name: string; carrier_config_id: string | null }[]
  totals: Map<string, number>
  currency: string
  selectedCarriers: Set<string>
}

export function TotalPremiumRow({
  carriers,
  totals,
  currency,
  selectedCarriers,
}: TotalPremiumRowProps) {
  return (
    <tfoot>
      <tr>
        <td
          className="px-4 py-3 text-sm font-bold bg-white border-r"
          style={{
            position: 'sticky',
            bottom: 0,
            left: 0,
            zIndex: 30,
            borderTop: '2px solid rgb(229 231 235)',
          }}
        >
          Total Premium
        </td>
        {carriers.map((carrier) => (
          <td
            key={carrier.name}
            className={cn(
              'px-3 py-3 text-sm font-bold text-center bg-white border-r',
              selectedCarriers.has(carrier.name) && 'bg-blue-50'
            )}
            style={{
              position: 'sticky',
              bottom: 0,
              zIndex: 20,
              borderTop: '2px solid rgb(229 231 235)',
            }}
          >
            {formatCurrency(totals.get(carrier.name) ?? 0, currency)}
          </td>
        ))}
      </tr>
    </tfoot>
  )
}
