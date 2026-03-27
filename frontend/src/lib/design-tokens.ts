export const spacing = {
  section: '48px',    // between major sections
  card: '24px',       // card internal padding
  element: '16px',    // between elements within card
  tight: '8px',       // label-to-input, badge-to-text
  pageMobile: '24px', // page horizontal padding mobile
  pageDesktop: '48px', // page horizontal padding desktop
  maxReading: '720px', // max content width for reading
  maxGrid: '1120px',  // max content width for grid layouts
  maxBriefing: '960px', // max content width for briefing viewer
} as const;

export const typography = {
  pageTitle: { size: '28px', weight: '700', lineHeight: '1.2', letterSpacing: '-0.02em' },
  sectionTitle: { size: '18px', weight: '600', lineHeight: '1.4' },
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
  cardShadow: 'var(--card-shadow)',
  cardShadowHover: 'var(--card-shadow-hover)',
  brandTintWarm: 'var(--brand-tint-warm)',
  brandTintWarmest: 'var(--brand-tint-warmest)',
} as const;

export const cardBorderColors = {
  action: '#E94D35',    // coral - action needed
  complete: '#22C55E',  // green - done
  warning: '#F59E0B',   // amber - stale/attention
  info: 'transparent',  // no left border
} as const;

export const shadows = {
  card: 'var(--card-shadow)',
  cardHover: 'var(--card-shadow-hover)',
} as const;

export const transitions = {
  fast: 'var(--transition-fast)',
  interactive: '150ms ease',
} as const;

export const registers = {
  pipeline: { background: 'var(--page-bg)' },           // cool white, dense
  relationship: { background: 'var(--brand-tint-warm)' }, // warm tint
  personal: { background: 'var(--brand-tint-warmest)' },  // warmest
} as const;

export const badges = {
  fitTier: {
    excellent: { bg: 'rgba(34, 197, 94, 0.1)', text: '#16a34a' },
    strong:    { bg: 'rgba(34, 197, 94, 0.1)', text: '#16a34a' },
    good:      { bg: 'rgba(59, 130, 246, 0.1)', text: '#2563eb' },
    fair:      { bg: 'rgba(245, 158, 11, 0.1)', text: '#d97706' },
    weak:      { bg: 'rgba(239, 68, 68, 0.1)', text: '#dc2626' },
    poor:      { bg: 'rgba(239, 68, 68, 0.1)', text: '#dc2626' },
  },
} as const;
