import { Zap } from 'lucide-react'

interface TaskSkillChipProps {
  skillName: string
}

export function TaskSkillChip({ skillName }: TaskSkillChipProps) {
  return (
    <span
      className="inline-flex items-center gap-1 dark:bg-[rgba(233,77,53,0.15)]"
      style={{
        background: 'rgba(233,77,53,0.08)',
        color: 'var(--brand-coral)',
        fontSize: '12px',
        fontWeight: 500,
        padding: '4px 10px',
        borderRadius: '9999px',
      }}
    >
      <Zap className="size-3" />
      {skillName}
    </span>
  )
}
