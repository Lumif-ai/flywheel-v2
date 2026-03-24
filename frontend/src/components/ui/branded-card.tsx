import { cn } from '@/lib/cn';
import { cardBorderColors } from '@/lib/design-tokens';
import { animationClasses } from '@/lib/animations';

type CardVariant = 'action' | 'complete' | 'warning' | 'info';

interface BrandedCardProps {
  variant?: CardVariant;
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  hoverable?: boolean;
}

export function BrandedCard({
  variant = 'info',
  children,
  className,
  onClick,
  hoverable = true,
}: BrandedCardProps) {
  const borderColor = cardBorderColors[variant];
  return (
    <div
      className={cn(
        'bg-white border border-[var(--subtle-border)] rounded-xl shadow-sm p-6',
        variant !== 'info' && 'border-l-4',
        hoverable && animationClasses.cardHover,
        onClick && 'cursor-pointer',
        className,
      )}
      style={variant !== 'info' ? { borderLeftColor: borderColor } : undefined}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {children}
    </div>
  );
}
