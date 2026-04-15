import { themeQuartz } from 'ag-grid-community'

export const gridTheme = themeQuartz.withParams({
  backgroundColor: '#FFFFFF',
  foregroundColor: '#121212',
  headerBackgroundColor: '#FAFAFA',
  headerTextColor: '#9CA3AF',
  borderColor: '#F3F4F6',
  accentColor: '#E94D35',
  rowHoverColor: 'rgba(233,77,53,0.03)',
  fontSize: 13,
  rowHeight: 44,
  headerHeight: 36,
  headerFontWeight: 600,
  headerColumnBorder: false,
  columnBorder: false,
  fontFamily: "'Geist Variable', ui-sans-serif, system-ui, sans-serif",
})

/** Three-layer Airbnb shadow for grid wrapper div */
export const GRID_SHADOW = '0 1px 2px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.04)'

/** Standard border radius for grid wrapper */
export const GRID_BORDER_RADIUS = 12
