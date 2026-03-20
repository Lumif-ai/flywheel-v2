# Brand Template Specifications

## Template File
Located at: `~/.claude/brand-assets/lumifai-page-template.docx`

## Brand Colours (aligned to ~/.claude/design-guidelines.md)
- **Primary accent**: #E94D35
- **Dark text** (headlines): #121212
- **Body text**: #333333
- **Secondary text**: #6B7280
- **Muted text**: #9CA3AF
- **Light text / attribution**: #999999
- **Footnotes**: #AAAAAA
- **Status quo panel background**: #FFF8F6 (warm tint from design system)
- **Table alt row**: #FAFAFA
- **Table borders**: #E5E7EB (outer), #F3F4F6 (inner)
- **Status quo panel dividers**: #F0D0C8

## Fonts
- **Headings / Brand elements**: Inter (primary), Rubik Medium (fallback)
- **Body text**: Inter (primary), Arial (fallback)
- **Section headings**: Inter/Rubik Medium, accent (#E94D35)

## Page Setup
- **Size**: US Letter (12240 x 15840 DXA)
- **Margins**: 1" sides (1440 DXA), ~1.3" top (1888 DXA), minimal bottom (~539 DXA)
- **Header**: Lumif.ai icon + "Lumif.ai" in accent colour + divider line. NO company address.
- **Footer**: Half-thickness accent bar (sz=36) -- REMOVE for value prop docs to save space

## Font Sizes (half-points)
- **Headline**: 34-38 (17-19pt)
- **Section headings**: 22-24 (11-12pt)
- **Body text**: 20-22 (10-11pt)
- **Bullet text**: 20 (10pt)
- **Competitive gap text**: 21 (10.5pt)
- **Status quo panel numbers**: 24-28 (12-14pt)
- **Status quo panel descriptions**: 17 (8.5pt)
- **Table header**: 19-20 (9.5-10pt)
- **Table body**: 19 (9.5pt)
- **CTA**: 20-21 (10-10.5pt)
- **Footnotes**: 13-14 (6.5-7pt)
- **Italic capability hint**: 19 (9.5pt)

## Tables
- **Header row**: Accent (#E94D35) background, white bold text
- **Body rows**: White or very light grey (#FAFAFA) alternating
- **Borders**: Thin grey, not accent colour
- **Bold first column** in body rows
- **No teal, green, or navy** in table headers or accents

## Callout Boxes (use sparingly)
- Muted warm background (#FFF8F6), used only for status quo panel
- No shaded backgrounds on competitive gap text, promise boxes, or other sections
- Keep visual noise low: one shaded element per page maximum

## Bullet Points
- Use grey (#9CA3AF) bullets, not accent colour
- Grey lets the bold lead-in text do the visual work
- Define in numbering.xml with bullet character &#x2022;

## General Rules
- Avoid em dashes throughout
- Use smart quotes (XML entities: &#x201C; &#x201D; &#x2018; &#x2019;)
- Skip boilerplate "how to use" sections
- No Singapore address in header
- Use "contract-to-coverage review" terminology consistently

## Document Build Process
1. Unpack template: use the docx skill's unpack workflow on `~/.claude/brand-assets/lumifai-page-template.docx`
2. Replace `word/document.xml` with new content
3. Update `word/numbering.xml` for grey bullet lists
4. Optionally remove footer bar from `word/footer1.xml` (delete the pBdr/bottom element)
5. Pack using the docx skill's pack workflow
6. Verify: Convert to PDF, check page count
7. If spillover, tighten copy first (not fonts). Fonts should not go below readability thresholds.

## Logo Assets
- **Full logo**: `~/.claude/brand-assets/lumifai-logo.png`
- **Icon only**: `~/.claude/brand-assets/lumifai-icon.png`
- **Small base64**: `~/.claude/brand-assets/lumifai-logo-sm.b64`
