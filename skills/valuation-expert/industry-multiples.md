# Industry Multiples Reference Data

## Source Attribution

All multiples in this file are derived from **Aswath Damodaran's publicly available datasets**, NYU Stern School of Business. Damodaran compiles these annually from ~45,000 publicly traded companies globally, grouped by industry.

- Primary dataset: "Enterprise Value Multiples by Industry Sector"
- URL: https://pages.stern.nyu.edu/~adamodar/
- Navigate: Home > Data > Current Data > Enterprise Value Multiples
- Last referenced baseline: January 2025 update

**IMPORTANT**: These are PUBLIC COMPANY medians. For PRIVATE companies (especially small ones), apply the following discounts:

### Private Company / Size Discount (Damodaran + Kroll)
| Company Revenue | Typical Discount to Public Multiples |
|----------------|--------------------------------------|
| < $5M revenue  | 40-60% discount (illiquidity + size)  |
| $5M - $25M     | 25-40% discount                      |
| $25M - $100M   | 15-25% discount                      |
| $100M - $500M  | 5-15% discount                       |
| > $500M        | 0-10% discount                       |

Source: Damodaran "Illiquidity Discount" research + Kroll (formerly Duff & Phelps) Cost of Capital Navigator size premium data.

### Growth Adjustment
Companies growing significantly faster or slower than industry median should be adjusted:
- Revenue growth 2x+ industry median: +20-50% premium to multiple
- Revenue growth at industry median: no adjustment
- Revenue growth below industry median: -10-30% discount to multiple

---

## EV/Revenue Multiples by Industry

These represent median multiples for public companies in each sector.

### Technology & Software
| Sub-Sector | EV/Revenue (Median) | EV/Revenue (25th-75th) | Notes |
|-----------|-------------------|----------------------|-------|
| Software (System & Application) | 5.5x - 7.5x | 3.0x - 12.0x | Wide range due to growth/margin differences |
| SaaS / Cloud (high growth >30%) | 8.0x - 15.0x | 5.0x - 25.0x+ | NRR and growth rate are key drivers |
| SaaS / Cloud (moderate growth 15-30%) | 5.0x - 8.0x | 3.5x - 12.0x | Most common range for mid-stage SaaS |
| SaaS / Cloud (low growth <15%) | 3.0x - 5.0x | 2.0x - 7.0x | Mature SaaS, focus shifts to profitability |
| IT Services | 1.5x - 3.0x | 1.0x - 4.5x | Lower multiples due to labor intensity |
| Semiconductor | 4.0x - 7.0x | 2.5x - 10.0x | Cyclical, IP-driven |
| Internet / E-commerce | 2.0x - 4.0x | 1.0x - 8.0x | Highly variable by sub-model |

### Healthcare & Life Sciences
| Sub-Sector | EV/Revenue (Median) | EV/Revenue (25th-75th) | Notes |
|-----------|-------------------|----------------------|-------|
| Biotech (with revenue) | 4.0x - 8.0x | 2.0x - 15.0x | Pipeline value often dominates |
| Pharma (large cap) | 3.0x - 5.0x | 2.0x - 7.0x | Patent cliffs create range |
| Healthcare Services | 1.5x - 3.0x | 1.0x - 5.0x | Reimbursement-dependent |
| Medical Devices | 3.0x - 6.0x | 2.0x - 9.0x | Recurring revenue from consumables drives premium |
| Healthtech / Digital Health | 4.0x - 10.0x | 2.0x - 18.0x | Treated more like tech if SaaS model |

### Financial Services & Fintech
| Sub-Sector | EV/Revenue (Median) | EV/Revenue (25th-75th) | Notes |
|-----------|-------------------|----------------------|-------|
| Fintech (high growth) | 5.0x - 12.0x | 3.0x - 20.0x | Payment and lending platforms |
| Banking (traditional) | 2.0x - 3.5x | 1.5x - 5.0x | Book value often more relevant |
| Insurance | 1.0x - 2.0x | 0.8x - 3.0x | Combined ratio matters more |
| Asset Management | 3.0x - 6.0x | 2.0x - 8.0x | AUM-based valuation often preferred |

### Industrials & Manufacturing
| Sub-Sector | EV/Revenue (Median) | EV/Revenue (25th-75th) | Notes |
|-----------|-------------------|----------------------|-------|
| Industrial Manufacturing | 1.0x - 2.0x | 0.7x - 3.0x | Margin-driven, EBITDA multiple preferred |
| Aerospace & Defense | 1.5x - 2.5x | 1.0x - 4.0x | Long contract visibility |
| Chemicals | 1.0x - 2.0x | 0.6x - 3.0x | Commodity vs specialty matters |
| Construction / Engineering | 0.5x - 1.5x | 0.3x - 2.5x | Low margins, project-based |

### Consumer & Retail
| Sub-Sector | EV/Revenue (Median) | EV/Revenue (25th-75th) | Notes |
|-----------|-------------------|----------------------|-------|
| Consumer Products (branded) | 1.5x - 3.0x | 1.0x - 5.0x | Brand strength drives premium |
| Retail (brick & mortar) | 0.5x - 1.5x | 0.3x - 2.5x | Low margins |
| D2C / E-commerce | 1.5x - 4.0x | 0.8x - 8.0x | Unit economics matter |
| Food & Beverage | 1.0x - 2.5x | 0.7x - 4.0x | Stable, brand-dependent |
| Restaurant / Hospitality | 1.0x - 2.0x | 0.5x - 3.5x | Location + brand |

### Energy & Utilities
| Sub-Sector | EV/Revenue (Median) | EV/Revenue (25th-75th) | Notes |
|-----------|-------------------|----------------------|-------|
| Oil & Gas (E&P) | 1.5x - 3.0x | 0.8x - 5.0x | Reserve-based valuation preferred |
| Renewable Energy | 2.0x - 5.0x | 1.0x - 10.0x | PPA contract visibility |
| Utilities (regulated) | 1.5x - 3.0x | 1.0x - 4.0x | Rate base valuation preferred |
| Energy Services | 0.8x - 1.5x | 0.4x - 2.5x | Cyclical |

### Professional & Business Services
| Sub-Sector | EV/Revenue (Median) | EV/Revenue (25th-75th) | Notes |
|-----------|-------------------|----------------------|-------|
| Consulting | 1.0x - 2.5x | 0.7x - 4.0x | People-dependent |
| Staffing / HR | 0.5x - 1.5x | 0.3x - 2.5x | Low margins |
| Marketing / Advertising | 1.0x - 2.5x | 0.5x - 5.0x | Recurring vs project |
| Education / EdTech | 2.0x - 5.0x | 1.0x - 10.0x | SaaS models trade higher |

---

## EV/EBITDA Multiples by Industry

| Sector | EV/EBITDA (Median) | EV/EBITDA (25th-75th) |
|--------|-------------------|----------------------|
| Software / SaaS | 15x - 25x | 10x - 40x+ |
| IT Services | 10x - 15x | 7x - 20x |
| Healthcare Services | 10x - 15x | 7x - 20x |
| Medical Devices | 15x - 22x | 10x - 30x |
| Biotech / Pharma | 12x - 18x | 8x - 25x |
| Fintech | 15x - 25x | 10x - 40x |
| Banking | 8x - 12x | 6x - 15x |
| Industrial Manufacturing | 8x - 12x | 6x - 16x |
| Aerospace / Defense | 10x - 14x | 8x - 18x |
| Consumer Products | 10x - 14x | 7x - 18x |
| Retail | 7x - 12x | 5x - 16x |
| Food & Beverage | 10x - 14x | 7x - 18x |
| Oil & Gas | 5x - 8x | 3x - 12x |
| Renewable Energy | 10x - 18x | 7x - 25x |
| Utilities | 8x - 12x | 6x - 15x |
| Professional Services | 8x - 14x | 6x - 18x |
| Education / EdTech | 12x - 20x | 8x - 30x |

---

## Context-Specific Adjustments

Apply these ONLY when the valuation context warrants them. The user's stated purpose determines which adjustments are relevant.

### Control Premium (Acquisition Context Only — Damodaran Research)
When valuing for acquisition, add a control premium to reflect the value of controlling the company:
- Median control premium in US acquisitions: ~25-30% (Damodaran, "Value of Control")
- Range: 15-40% depending on how poorly managed the target is perceived to be
- Higher for companies where operational improvements are possible
- Lower for well-run companies with dispersed ownership
- DO NOT apply for fundraising, strategic planning, or JV valuations

### Synergy Adjustments (Acquisition Context Only)
- Revenue synergies: typically valued at 0.5x-1.5x the estimated annual synergy revenue
- Cost synergies: typically valued at 3x-5x the estimated annual cost savings (higher certainty)
- Source: McKinsey & Co research on M&A synergy realization rates (~60-70% of projected synergies are realized)

### Strategic Premium (Acquisition Context Only)
Beyond financial value, strategic acquisitions may command premiums for:
- Market access (geographic or segment)
- Technology / IP acquisition
- Talent acquisition (acqui-hire)
- Competitive blocking (preventing competitor acquisition)
- Typical range: 10-50% above standalone value

### Fundraising Adjustments
- Use forward (NTM) revenue multiples as primary basis — investors price on growth trajectory
- Apply venture-stage discount rates to DCF: Seed/Series A: 40-60%, Series B/C: 25-35%, Growth: 18-25%
- Reference recent comparable funding rounds in sector
- Pre-money valuation = post-money - investment amount

### Lack of Marketability Discount (DLOM) — Litigation/Tax/Minority Interest Contexts
- Applies when valuing minority interests or for IRS / court purposes
- Typical range: 15-35% discount to freely traded value
- Source: Restricted stock studies (FMV Opinions, Pluris) and pre-IPO studies
- More relevant for litigation/tax valuations; NOT typically applied in fundraising or acquisition

### Lack of Control Discount (DLOC) — Minority Interest Contexts
- Applies when the subject interest lacks control rights
- Typical range: 15-25% (inverse of control premium)
- Relevant for: minority shareholder disputes, gift/estate tax, partner buyouts
- NOT applied when valuing the entire company for acquisition

---

## WACC Components Reference

### Risk-Free Rate
- Use 10-Year U.S. Treasury yield from FRED
- As of early 2025: approximately 4.0-4.5%
- ALWAYS search for current rate when building a DCF

### Equity Risk Premium (ERP)
- Damodaran's implied ERP for US market: ~4.5-5.5% (updated monthly)
- Source: Damodaran "Implied Equity Risk Premium" dataset
- URL: https://pages.stern.nyu.edu/~adamodar/ > Data > Risk Premium

### Country Risk Premium (CRP)
Selected examples from Damodaran:
| Country/Region | CRP |
|---------------|-----|
| United States | 0.00% |
| United Kingdom | 0.58% |
| Germany | 0.00% |
| India | 1.50% - 2.00% |
| China | 0.75% - 1.25% |
| Brazil | 2.50% - 3.50% |
| Southeast Asia (avg) | 1.00% - 2.50% |
| Middle East (avg) | 0.75% - 2.00% |

### Size Premium (Kroll / Duff & Phelps)
| Market Cap | Size Premium |
|-----------|-------------|
| > $25B | 0.0% |
| $10B - $25B | 0.5% - 1.0% |
| $2B - $10B | 1.0% - 1.5% |
| $500M - $2B | 1.5% - 2.5% |
| $200M - $500M | 2.5% - 3.5% |
| < $200M | 3.5% - 6.0%+ |

### Industry Betas (Unlevered, from Damodaran)
| Sector | Unlevered Beta |
|--------|---------------|
| Software | 1.10 - 1.30 |
| Healthcare | 0.90 - 1.15 |
| Fintech | 1.05 - 1.30 |
| Manufacturing | 0.80 - 1.00 |
| Consumer Products | 0.75 - 0.95 |
| Energy | 0.90 - 1.20 |
| Utilities | 0.35 - 0.50 |
| Professional Services | 0.85 - 1.10 |
