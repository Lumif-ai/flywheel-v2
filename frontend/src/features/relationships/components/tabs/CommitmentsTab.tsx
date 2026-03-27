import { ArrowUpRight, ArrowDownLeft } from 'lucide-react'

// Commitment shape is unknown for now — backend returns [] (reserved field)
// This component is future-proofed for when commitments data is available
interface Commitment {
  id: string
  title: string
  due_date?: string | null
  source?: string | null
  owner: 'me' | 'them'
}

interface CommitmentsTabProps {
  commitments: unknown[]
}

function isCommitmentArray(arr: unknown[]): arr is Commitment[] {
  return arr.length > 0 && typeof (arr[0] as Record<string, unknown>).id === 'string'
}

function CommitmentRow({ commitment }: { commitment: Commitment }) {
  const isOverdue =
    commitment.due_date ? new Date(commitment.due_date) < new Date() : false

  return (
    <div
      className="py-2 border-b border-[var(--subtle-border)] last:border-b-0"
    >
      <p
        className="text-sm font-medium"
        style={{
          color: isOverdue ? 'var(--error)' : 'var(--heading-text)',
          fontWeight: isOverdue ? 700 : 500,
        }}
      >
        {commitment.title}
      </p>
      {commitment.due_date && (
        <p
          className="text-xs mt-0.5"
          style={{ color: isOverdue ? 'var(--error)' : 'var(--secondary-text)' }}
        >
          Due {new Date(commitment.due_date).toLocaleDateString()}
          {isOverdue && ' — overdue'}
        </p>
      )}
      {commitment.source && (
        <p className="text-xs mt-0.5" style={{ color: 'var(--secondary-text)' }}>
          {commitment.source}
        </p>
      )}
    </div>
  )
}

function ColumnHeader({ label, icon: Icon }: { label: string; icon: React.ElementType }) {
  return (
    <div className="flex items-center gap-1.5 mb-3 pb-2 border-b border-[var(--subtle-border)]">
      <Icon className="size-4" style={{ color: 'var(--secondary-text)' }} />
      <span
        className="text-sm font-semibold"
        style={{ color: 'var(--secondary-text)' }}
      >
        {label}
      </span>
    </div>
  )
}

export function CommitmentsTab({ commitments }: CommitmentsTabProps) {
  const structured = isCommitmentArray(commitments) ? commitments : []
  const mine = structured.filter((c) => c.owner === 'me')
  const theirs = structured.filter((c) => c.owner === 'them')

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* What You Owe */}
      <div>
        <ColumnHeader label="What You Owe" icon={ArrowUpRight} />
        {mine.length === 0 ? (
          <p className="text-sm italic" style={{ color: 'var(--secondary-text)' }}>
            No commitments tracked yet
          </p>
        ) : (
          mine.map((c) => <CommitmentRow key={c.id} commitment={c} />)
        )}
      </div>

      {/* What They Owe */}
      <div>
        <ColumnHeader label="What They Owe" icon={ArrowDownLeft} />
        {theirs.length === 0 ? (
          <p className="text-sm italic" style={{ color: 'var(--secondary-text)' }}>
            No commitments tracked yet
          </p>
        ) : (
          theirs.map((c) => <CommitmentRow key={c.id} commitment={c} />)
        )}
      </div>
    </div>
  )
}
