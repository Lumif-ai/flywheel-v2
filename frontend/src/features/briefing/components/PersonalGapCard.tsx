/**
 * PersonalGapCard - Briefing card showing team vs personal context contribution.
 *
 * Highlights streams where the team has context but the current user has
 * contributed little or nothing, encouraging participation.
 */

import { Users } from 'lucide-react'
import { Link } from 'react-router'

interface PersonalGapCardProps {
  title: string
  detail: string
  streamId: string
  teamCount: number
  myCount: number
}

export function PersonalGapCard({
  title,
  detail,
  streamId,
  teamCount,
  myCount,
}: PersonalGapCardProps) {
  const isZeroContribution = myCount === 0

  return (
    <div
      className={`rounded-xl border p-4 space-y-2 ${
        isZeroContribution
          ? 'border-amber-200 bg-amber-50/50'
          : 'border-border bg-card'
      }`}
    >
      <div className="flex items-start gap-3">
        <Users
          className={`mt-0.5 h-5 w-5 shrink-0 ${
            isZeroContribution
              ? 'text-amber-600'
              : 'text-muted-foreground'
          }`}
        />
        <div className="min-w-0 flex-1">
          <h3 className="font-medium leading-tight">{title}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{detail}</p>

          {/* Counts */}
          <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
            <span>{teamCount} team entries</span>
            <span>{myCount} from you</span>
          </div>

          {/* Link to stream */}
          <Link
            to={`/streams/${streamId}`}
            className="mt-2 inline-block text-sm text-primary hover:underline"
          >
            View what the team knows
          </Link>
        </div>
      </div>
    </div>
  )
}
