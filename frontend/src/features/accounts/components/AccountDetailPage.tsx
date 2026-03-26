import { spacing, typography } from '@/lib/design-tokens'

export function AccountDetailPage() {
  return (
    <div className="mx-auto w-full" style={{ maxWidth: spacing.maxGrid, padding: `${spacing.section} ${spacing.pageDesktop}` }}>
      <h1 style={{ fontSize: typography.pageTitle.size, fontWeight: typography.pageTitle.weight, lineHeight: typography.pageTitle.lineHeight, letterSpacing: typography.pageTitle.letterSpacing }} className="text-foreground">
        Account Detail
      </h1>
      <p className="mt-4 text-muted-foreground">Account detail coming soon...</p>
    </div>
  )
}
