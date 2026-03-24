// All animations: 200ms ease-out
export const transition = 'all 200ms ease-out';

// Content enter: translateY(12px) + opacity(0) -> translateY(0) + opacity(1)
export const fadeSlideUp = {
  initial: { opacity: 0, transform: 'translateY(12px)' },
  animate: { opacity: 1, transform: 'translateY(0)' },
  transition: 'all 200ms ease-out',
};

// Stagger: 50ms between siblings
export const staggerDelay = (index: number) => `${index * 50}ms`;

// CSS class names for use in className strings
export const animationClasses = {
  fadeSlideUp: 'animate-fade-slide-up',
  shimmer: 'animate-shimmer',
  cardHover: 'transition-all duration-200 ease-out hover:shadow-md hover:-translate-y-px active:scale-[0.98] active:shadow-sm',
} as const;
