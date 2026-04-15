// Carrier logo SVG components — recognizable approximations of real logos
// Used in CarrierBadge, CarrierCell, and other carrier displays

interface LogoProps {
  size?: number
}

/**
 * Mapfre — Red background, white "MAPFRE" text with the distinctive
 * triangular "key" shape above. Simplified to a red rounded square
 * with the triangle + "M" mark.
 */
export function MapfreLogo({ size = 32 }: LogoProps) {
  const s = size
  return (
    <svg width={s} height={s} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="40" height="40" rx="6" fill="#d32f2f" />
      {/* Triangle / key shape */}
      <polygon points="20,6 28,18 12,18" fill="white" opacity="0.95" />
      {/* MAPFRE text */}
      <text x="20" y="30" textAnchor="middle" fill="white" fontSize="7" fontWeight="800" fontFamily="Arial, sans-serif" letterSpacing="0.5">
        MAPFRE
      </text>
    </svg>
  )
}

/**
 * GNP Seguros — Orange sun/asterisk icon with "GNP" text.
 * The real logo has a stylized sun with radiating points.
 */
export function GNPLogo({ size = 32 }: LogoProps) {
  const s = size
  return (
    <svg width={s} height={s} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="40" height="40" rx="6" fill="#F47920" />
      {/* Sun rays — 8 points */}
      {[0, 45, 90, 135, 180, 225, 270, 315].map((angle) => (
        <line
          key={angle}
          x1="20"
          y1="20"
          x2={20 + 9 * Math.cos((angle * Math.PI) / 180)}
          y2={20 + 9 * Math.sin((angle * Math.PI) / 180)}
          stroke="white"
          strokeWidth="2"
          strokeLinecap="round"
          transform={`translate(0, -4)`}
        />
      ))}
      <circle cx="20" cy="16" r="4" fill="white" />
      {/* GNP text */}
      <text x="20" y="33" textAnchor="middle" fill="white" fontSize="8.5" fontWeight="800" fontFamily="Arial, sans-serif" letterSpacing="0.8">
        GNP
      </text>
    </svg>
  )
}

/**
 * Chubb — Clean black square with white "CHUBB" in their distinctive
 * uppercase serif-like style. Simple and corporate.
 */
export function ChubbLogo({ size = 32 }: LogoProps) {
  const s = size
  return (
    <svg width={s} height={s} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="40" height="40" rx="6" fill="#1a1a1a" />
      <text x="20" y="23" textAnchor="middle" fill="white" fontSize="8" fontWeight="700" fontFamily="Georgia, 'Times New Roman', serif" letterSpacing="1.2">
        CHUBB
      </text>
    </svg>
  )
}

/**
 * Zurich — Blue background with white "Z" in a circle,
 * approximating their globe/circle logo mark.
 */
export function ZurichLogo({ size = 32 }: LogoProps) {
  const s = size
  return (
    <svg width={s} height={s} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="40" height="40" rx="6" fill="#0060AE" />
      <circle cx="20" cy="20" r="13" stroke="white" strokeWidth="1.5" fill="none" />
      <text x="20" y="25.5" textAnchor="middle" fill="white" fontSize="16" fontWeight="700" fontFamily="Arial, sans-serif">
        Z
      </text>
    </svg>
  )
}

/**
 * Afianzadora Aserta — Part of Grupo Financiero Banorte.
 * Teal/green with bold "ASERTA" text and a small shield shape.
 */
export function AsertaLogo({ size = 32 }: LogoProps) {
  const s = size
  return (
    <svg width={s} height={s} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="40" height="40" rx="6" fill="#2E7D32" />
      {/* Shield shape */}
      <path d="M20 7 L28 12 L28 20 Q28 27 20 32 Q12 27 12 20 L12 12 Z" fill="white" opacity="0.2" />
      <text x="20" y="22.5" textAnchor="middle" fill="white" fontSize="6.5" fontWeight="800" fontFamily="Arial, sans-serif" letterSpacing="0.3">
        ASERTA
      </text>
    </svg>
  )
}

/**
 * Fianzas Dorama — Dark blue with "DORAMA" text and a subtle
 * wave/ribbon accent.
 */
export function DoramaLogo({ size = 32 }: LogoProps) {
  const s = size
  return (
    <svg width={s} height={s} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="40" height="40" rx="6" fill="#1565C0" />
      {/* Decorative wave */}
      <path d="M6 26 Q13 22 20 26 Q27 30 34 26" stroke="white" strokeWidth="1.2" fill="none" opacity="0.4" />
      <text x="20" y="20" textAnchor="middle" fill="white" fontSize="5.8" fontWeight="800" fontFamily="Arial, sans-serif" letterSpacing="0.5">
        DORAMA
      </text>
    </svg>
  )
}

/**
 * Utility: get logo component by carrier ID
 */
export function CarrierLogo({ carrierId, size = 32 }: { carrierId: string; size?: number }) {
  switch (carrierId) {
    case 'mapfre': return <MapfreLogo size={size} />
    case 'gnp': return <GNPLogo size={size} />
    case 'chubb': return <ChubbLogo size={size} />
    case 'zurich': return <ZurichLogo size={size} />
    case 'aserta': return <AsertaLogo size={size} />
    case 'dorama': return <DoramaLogo size={size} />
    default: return null
  }
}

/**
 * Name-to-ID mapping with case-insensitive fuzzy matching.
 * Handles variations like "Mapfre", "MAPFRE", "Mapfre Mexico", "Mapfre México", etc.
 */
const NAME_MAPPINGS: Array<{ patterns: string[]; id: string }> = [
  { patterns: ['mapfre', 'mapfre mexico', 'mapfre méxico', 'mapfre seguros'], id: 'mapfre' },
  { patterns: ['gnp', 'gnp seguros', 'grupo nacional provincial'], id: 'gnp' },
  { patterns: ['chubb', 'chubb mexico', 'chubb méxico', 'chubb seguros', 'ace seguros'], id: 'chubb' },
  { patterns: ['zurich', 'zurich mexico', 'zurich méxico', 'zurich seguros'], id: 'zurich' },
  { patterns: ['aserta', 'afianzadora aserta', 'fianzas aserta'], id: 'aserta' },
  { patterns: ['dorama', 'fianzas dorama'], id: 'dorama' },
]

/**
 * Resolve a carrier name to a known ID using case-insensitive fuzzy matching.
 * Returns the ID if matched, or null if no match found.
 */
export function resolveCarrierId(name: string): string | null {
  const normalized = name.trim().toLowerCase()

  // Exact match first
  for (const mapping of NAME_MAPPINGS) {
    if (mapping.patterns.includes(normalized)) {
      return mapping.id
    }
  }

  // Fuzzy: check if the normalized name starts with or contains a known pattern
  for (const mapping of NAME_MAPPINGS) {
    for (const pattern of mapping.patterns) {
      if (normalized.startsWith(pattern) || pattern.startsWith(normalized)) {
        return mapping.id
      }
    }
  }

  // Fuzzy: check if any keyword from the carrier ID appears in the name
  for (const mapping of NAME_MAPPINGS) {
    if (normalized.includes(mapping.id)) {
      return mapping.id
    }
  }

  return null
}

/**
 * Utility: get logo by carrier name (for tables that use full names).
 * Uses fuzzy matching to handle name variations.
 * Returns null if no logo match found.
 */
export function CarrierLogoByName({ name, size = 32 }: { name: string; size?: number }) {
  const id = resolveCarrierId(name)
  if (!id) return null
  return <CarrierLogo carrierId={id} size={size} />
}
