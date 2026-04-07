# Valuation Methods — Detailed Calculation Frameworks

## Method 1: Revenue Multiple Valuation

### When to Use
- Company has revenue but may not be profitable
- Industry has established revenue multiple benchmarks
- Growth-stage companies where future earnings are uncertain

### Step-by-Step Calculation

```
1. Determine Base Revenue
   - Use TTM (trailing twelve months) revenue as primary basis
   - If strong growth trajectory, also calculate using forward (NTM) revenue
   - Decide: Gross Revenue vs Net Revenue
     * Use NET Revenue if there are significant pass-through costs, reseller margins, or COGS that are not value-add
     * Use GROSS Revenue only if gross margin > 60% and industry convention uses gross
     * ALWAYS state which revenue figure is used and why

2. Select Industry Multiple
   - Look up median EV/Revenue from references/industry-multiples.md
   - Note the 25th and 75th percentile for range construction

3. Apply Adjustments
   a) Size/Illiquidity Discount (for private companies):
      - See discount table in industry-multiples.md
      - Cite: Damodaran illiquidity discount + Kroll size premium

   b) Growth Premium/Discount:
      - Calculate company revenue CAGR
      - Compare to industry median growth rate
      - If company CAGR > 2x industry: apply 20-50% premium
      - If company CAGR < 0.5x industry: apply 10-30% discount
      - Formula: Adjusted Multiple = Base Multiple × (1 + Growth Adjustment)

   c) Margin Premium/Discount:
      - If gross margins significantly above industry median: +10-20% premium
      - If below: -10-20% discount

   d) Revenue Quality Adjustment:
      - Recurring/subscription revenue: +15-30% premium
      - One-time / project revenue: -10-20% discount
      - Concentrated customer base (top customer > 25% revenue): -10-25% discount

4. Calculate Enterprise Value
   EV = Adjusted Multiple × Revenue

5. Build Range
   - Low: 25th percentile multiple × TTM Revenue (with all discounts applied)
   - Mid: Median multiple × TTM Revenue (with adjustments)
   - High: 75th percentile multiple × Forward Revenue (with premiums)
```

### Output Format
| Component | Low | Base | High |
|-----------|-----|------|------|
| Revenue Basis | TTM | TTM | NTM (Forward) |
| Industry Median Multiple | X.Xx | X.Xx | X.Xx |
| Size/Illiquidity Discount | -XX% | -XX% | -XX% |
| Growth Adjustment | +/-XX% | +/-XX% | +/-XX% |
| Revenue Quality Adjustment | +/-XX% | +/-XX% | +/-XX% |
| **Applied Multiple** | X.Xx | X.Xx | X.Xx |
| **Enterprise Value** | $X.XM | $X.XM | $X.XM |

---

## Method 2: EBITDA Multiple Valuation

### When to Use
- Company has positive, stable EBITDA
- Industry convention uses EBITDA multiples (common in industrials, services, mature companies)
- More reliable than revenue multiples for profitable companies

### Step-by-Step Calculation

```
1. Determine Normalized EBITDA
   Start with reported EBITDA, then adjust:
   - Add back: one-time/non-recurring expenses (legal settlements, restructuring, etc.)
   - Add back: above-market owner compensation (for private companies, replace with market-rate exec salary)
   - Add back: related-party transactions at non-market rates
   - Remove: one-time revenue windfalls
   - ALWAYS disclose each adjustment and its amount

2. Select Industry Multiple
   - Look up median EV/EBITDA from references/industry-multiples.md
   - Note 25th and 75th percentile

3. Apply Adjustments
   - Same framework as revenue multiples: size discount, growth, quality
   - Additional: margin sustainability discount if EBITDA margin is unusually high due to temporary factors

4. Calculate
   EV = Adjusted Multiple × Normalized EBITDA

5. Cross-Check
   - Calculate implied EV/Revenue from this valuation
   - If implied EV/Revenue is wildly different from industry norm, investigate why
```

---

## Method 3: Discounted Cash Flow (DCF)

### When to Use
- Company has (or will soon have) positive cash flows
- Sufficient data to build reasonable projections
- Complements multiple-based approaches

### Step-by-Step Calculation

```
1. Build Financial Projections (5-year explicit period)

   For each year, project:
   - Revenue (using historical CAGR, moderated toward industry averages over time)
   - EBITDA Margin (trend toward industry median margins over projection period)
   - Capital Expenditures (as % of revenue, using industry benchmarks)
   - Working Capital Changes (as % of revenue delta)
   - Tax Rate (use statutory rate; for pre-profit companies, taxes kick in when profitable)

   Free Cash Flow = EBITDA - Taxes on EBIT - CapEx - Change in Working Capital

   CRITICAL: Revenue growth should decelerate. A company growing at 200%+ will not sustain that.
   Suggested deceleration: reduce growth rate by 20-40% per year until reaching industry long-term growth.

2. Calculate WACC (Weighted Average Cost of Capital)

   WACC = (E/V) × Re + (D/V) × Rd × (1-T)

   Where:
   - Re = Cost of Equity = Risk-Free Rate + Beta × ERP + Size Premium + Country Risk Premium
   - Rd = Cost of Debt (use company's borrowing rate or industry average)
   - E/V = Equity weight (for early-stage companies with no debt, this is ~100%)
   - T = Tax rate

   For small private companies, typical WACC range: 15-30%
   For mature companies: 8-12%

   ALWAYS state each component and its source:
   - Risk-Free Rate: "[X.X]% — U.S. 10-Year Treasury as of [date], from FRED"
   - ERP: "[X.X]% — Damodaran implied equity risk premium for US, January 2025"
   - Beta: "[X.XX] — Damodaran unlevered beta for [industry], relevered for target capital structure"
   - Size Premium: "[X.X]% — Kroll (Duff & Phelps) size premium for companies under $[X]M market cap"

3. Calculate Terminal Value

   Terminal Value = FCF_Year5 × (1 + g) / (WACC - g)

   Where g = long-term growth rate (GDP growth proxy: 2-3% for developed markets)

   ALWAYS run sensitivity analysis on terminal value:
   - Vary g from 1.5% to 3.5%
   - Vary WACC +/- 2 percentage points
   - Terminal value often represents 60-80% of total DCF value — flag this

   Alternative: Exit Multiple method
   Terminal Value = EBITDA_Year5 × Exit Multiple
   Use industry median EV/EBITDA as the exit multiple

4. Discount to Present Value

   PV = Sum of [FCF_t / (1 + WACC)^t] + [Terminal Value / (1 + WACC)^5]

5. Three Scenarios

   Base Case: Most likely projections
   - Revenue growth based on historical trend with reasonable deceleration
   - Margins trend toward industry median

   Optimistic Case:
   - Revenue growth 20-30% above base
   - Margins reach top-quartile industry levels
   - Lower WACC (reduced risk premium as company matures)

   Conservative Case:
   - Revenue growth 20-30% below base
   - Margins stay below industry median
   - Higher WACC (elevated risk)
```

### DCF Sensitivity Table (include in report)
| | WACC -2% | WACC Base | WACC +2% |
|---|----------|----------|----------|
| Growth +1% | $X.XM | $X.XM | $X.XM |
| Growth Base | $X.XM | $X.XM | $X.XM |
| Growth -1% | $X.XM | $X.XM | $X.XM |

---

## Method 4: Comparable Transaction Analysis

### When to Use
- Recent M&A transactions exist in the same industry
- Provides market-validated multiples that include control premiums
- Especially relevant for acquisition context

### Step-by-Step

```
1. Identify Comparable Transactions
   Search for: "[industry] acquisition [year]", "[sector] M&A deal"
   Sources: SEC EDGAR (proxy statements), PitchBook, press releases

2. For Each Transaction, Note:
   - Target company name and description
   - Acquirer name
   - Transaction date
   - Deal value (Enterprise Value)
   - Target revenue at time of deal
   - Target EBITDA at time of deal
   - Implied EV/Revenue and EV/EBITDA

3. Adjust for Comparability
   - Size: larger targets command higher multiples
   - Growth: faster-growing targets command premiums
   - Timing: recent deals (< 2 years) are more relevant
   - Strategic fit: strategic acquirers pay more than financial buyers

4. Derive Implied Valuation
   - Use median of comparable transaction multiples
   - Apply to subject company's financials
```

---

## Combining Methods: The Football Field

After running all applicable methods, present a "football field" summary:

```
Method              |  Low    |  Base   |  High   |
-------------------------------------------------
Revenue Multiple    |  $X.XM  |  $X.XM  |  $X.XM  |
EBITDA Multiple     |  $X.XM  |  $X.XM  |  $X.XM  |
DCF                 |  $X.XM  |  $X.XM  |  $X.XM  |
Comparable Txns     |  $X.XM  |  $X.XM  |  $X.XM  |
-------------------------------------------------
WEIGHTED RANGE      |  $X.XM  |  $X.XM  |  $X.XM  |
```

Apply weights per the guidance in SKILL.md Step 5 and explicitly state why each method received its weight.

---

## Equity Value Bridge

After calculating Enterprise Value, bridge to Equity Value:

```
Enterprise Value
  + Cash and Cash Equivalents
  - Total Debt (short-term + long-term)
  - Minority Interests
  - Preferred Equity
  +/- Other adjustments (pension obligations, off-balance sheet items)
  = Equity Value
```

For many small private companies with no debt and minimal cash, EV ≈ Equity Value. But ALWAYS state whether this bridge was applied or not, and why.
