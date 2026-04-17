// frontend/src/features/broker/utils/excerptMatch.ts
// Pure helpers for matching contract excerpts against pdfjs text items.
// No React, no DOM, no side effects — framework-agnostic so the tricky
// text-matching logic is trivial to spot-check in isolation.

import type { PDFDocumentProxy } from 'pdfjs-dist'

/**
 * Normalize text for robust cross-language matching.
 * - NFD normalization + diacritic strip handles Spanish/Portuguese accent variation
 *   (PDF text layer may emit composed or decomposed forms; Claude's extraction may differ).
 * - Whitespace collapse handles PDF text items with padded spaces.
 * - Lowercase handles case drift between extraction and source.
 *
 * See mozilla/pdf.js#8101 for the upstream motivation.
 */
export function normalize(s: string): string {
  return s
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

/**
 * Minimal HTML escaper. react-pdf's customTextRenderer returns a string
 * that is spliced into the DOM as HTML, so we MUST escape PDF text content
 * before interpolating it inside <mark>...</mark>. See research §Pitfall 1.
 *
 * Only & < > need escaping here (customTextRenderer output is never used as
 * an attribute value, so we don't need to escape " or ').
 */
export function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/**
 * Walk the PDF headlessly and return the first page (1-indexed) whose
 * concatenated text contains the normalized excerpt. Returns null if no match
 * or if the excerpt is too short (< 4 chars normalized — too fuzzy).
 *
 * Uses pdfjs's getTextContent() which is per-page cached; for a 20-30 page
 * contract expect ~200-500ms total. Callers should show a spinner or disable
 * interaction during the search.
 *
 * Cancellation: callers should treat this as non-cancellable at the pdfjs level
 * — instead, gate the RESULT consumption with an external token (ref or state).
 */
export async function findPageContainingExcerpt(
  pdf: PDFDocumentProxy,
  excerpt: string,
): Promise<number | null> {
  const needle = normalize(excerpt)
  if (needle.length < 4) return null

  for (let n = 1; n <= pdf.numPages; n++) {
    const page = await pdf.getPage(n)
    const content = await page.getTextContent()
    // TextContent.items is TextItem | TextMarkedContent; only TextItem has `str`.
    const pageText = normalize(
      content.items
        .filter((it): it is { str: string } & typeof it => 'str' in it)
        .map((it) => it.str)
        .join(' '),
    )
    if (pageText.includes(needle)) return n
  }
  return null
}

/**
 * Given a single pdfjs text-item string and the full excerpt, decide whether
 * this item should be wrapped in <mark>. Uses bidirectional substring match
 * to mitigate the GH#306 limitation that customTextRenderer can't see phrases
 * that span multiple items:
 *   - itemN is inside excerptN (item is a fragment of a long excerpt) → mark it
 *     (adjacent marks visually merge)
 *   - excerptN is inside itemN (short excerpt contained in a large item) → mark it
 *     (whole-item highlight; sub-item splitting is out of scope)
 *
 * Returns true if this item should be highlighted.
 */
export function shouldHighlightItem(itemStr: string, excerpt: string): boolean {
  const itemN = normalize(itemStr)
  const excerptN = normalize(excerpt)
  if (itemN.length === 0 || excerptN.length === 0) return false
  return excerptN.includes(itemN) || itemN.includes(excerptN)
}
