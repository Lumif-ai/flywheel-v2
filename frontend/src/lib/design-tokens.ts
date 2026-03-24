export const spacing = {
  section: '48px',    // between major sections
  card: '24px',       // card internal padding
  element: '16px',    // between elements within card
  tight: '8px',       // label-to-input, badge-to-text
  pageMobile: '24px', // page horizontal padding mobile
  pageDesktop: '48px', // page horizontal padding desktop
  maxReading: '720px', // max content width for reading
  maxGrid: '1120px',  // max content width for grid layouts
} as const;

export const typography = {
  pageTitle: { size: '28px', weight: '600', lineHeight: '1.2' },
  sectionTitle: { size: '18px', weight: '500', lineHeight: '1.4' },
  body: { size: '15px', weight: '400', lineHeight: '1.6' },
  caption: { size: '13px', weight: '400', lineHeight: '1.4' },
} as const;

export const colors = {
  pageBg: 'var(--page-bg)',
  cardBg: 'var(--card-bg)',
  headingText: 'var(--heading-text)',
  bodyText: 'var(--body-text)',
  secondaryText: 'var(--secondary-text)',
  subtleBorder: 'var(--subtle-border)',
  brandCoral: 'var(--brand-coral)',
  brandGradientEnd: 'var(--brand-gradient-end)',
  brandTint: 'var(--brand-tint)',
  brandLight: 'var(--brand-light)',
  success: 'var(--success)',
  warning: 'var(--warning)',
  error: 'var(--error)',
} as const;

export const cardBorderColors = {
  action: '#E94D35',    // coral - action needed
  complete: '#22C55E',  // green - done
  warning: '#F59E0B',   // amber - stale/attention
  info: 'transparent',  // no left border
} as const;
