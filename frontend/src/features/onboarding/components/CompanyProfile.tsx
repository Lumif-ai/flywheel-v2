import { Building2, Globe, Tag } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { CompanyData } from '../hooks/useCrawl'

const AVAILABLE_SKILLS = [
  'Company Intelligence',
  'Competitor Analysis',
  'Meeting Prep',
  'Contact Research',
]

interface CompanyProfileProps {
  company: CompanyData
  onRunSkill: () => void
  isRunning?: boolean
}

export function CompanyProfile({ company, onRunSkill, isRunning }: CompanyProfileProps) {
  const detailEntries = Object.entries(company.details).slice(0, 6)

  return (
    <div className="mx-auto max-w-xl space-y-6">
      {/* Company header */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
            <Building2 className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-foreground">{company.name}</h2>
            {company.industry && (
              <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Tag className="h-3 w-3" />
                {company.industry}
              </div>
            )}
          </div>
        </div>

        {company.url && (
          <a
            href={company.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
          >
            <Globe className="h-3.5 w-3.5" />
            {new URL(company.url).hostname}
          </a>
        )}
      </div>

      {/* Description */}
      {company.description && (
        <p className="text-sm text-foreground/80 leading-relaxed">
          {company.description}
        </p>
      )}

      {/* Detail cards */}
      {detailEntries.length > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {detailEntries.map(([key, value]) => (
            <div key={key} className="rounded-lg border border-border p-3">
              <span className="text-xs text-muted-foreground">{key}</span>
              <p className="text-sm font-medium text-foreground">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Available skills */}
      <div className="space-y-2">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Available skills
        </span>
        <div className="flex flex-wrap gap-1.5">
          {AVAILABLE_SKILLS.map((skill) => (
            <Badge key={skill} variant="secondary">
              {skill}
            </Badge>
          ))}
        </div>
      </div>

      {/* CTA */}
      <Button
        onClick={onRunSkill}
        disabled={isRunning}
        size="lg"
        className="w-full"
      >
        {isRunning ? (
          <span className="animate-pulse">Running skill...</span>
        ) : (
          'Run your first skill'
        )}
      </Button>
    </div>
  )
}
