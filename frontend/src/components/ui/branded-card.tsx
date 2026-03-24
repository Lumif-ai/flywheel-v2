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

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (onClick && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div
      className={cn(
        'bg-[var(--card-bg)] border border-[var(--subtle-border)] rounded-xl p-6',
        variant !== 'info' && 'border-l-4',
        hoverable && animationClasses.cardHover,
        onClick && 'cursor-pointer',
        className,
      )}
      style={{
        boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)',
        ...(variant !== 'info' ? { borderLeftColor: borderColor } : {}),
      }}
      onClick={onClick}
      onKeyDown={onClick ? handleKeyDown : undefined}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {children}
    </div>
  );
}
