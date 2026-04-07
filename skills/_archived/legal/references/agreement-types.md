# Agreement Type Reference Guide

Use this file to tailor clause checklists and risk focus based on the document type identified in Step 1.

---

## NDA / Confidentiality Agreement

**Expected clauses (flag as missing if absent):**
- Definition of Confidential Information (should include carve-outs for public info, independently developed info)
- Permitted disclosures (legal compulsion carve-out)
- Term / duration of confidentiality obligations
- Return or destruction of materials
- Residuals clause (very dangerous — allows counterparty to retain "learned" knowledge)
- Injunctive relief clause
- No license grant (confirm IP isn't implicitly licensed)

**Red flags specific to NDAs:**
- One-sided (only founder bound, not counterparty)
- No time limit on confidentiality obligations
- Residuals clause — if present, treat as 🔴 High risk
- Overly broad definition covering "all information shared orally"
- Jurisdiction chosen is counterparty's home state with no explanation

**Market standard:** Mutual NDA, 2–3 year term, standard carve-outs, no residuals

---

## SaaS / Software Agreement (MSA, Order Form, ToS)

**Expected clauses:**
- Service Level Agreement (SLA) with uptime guarantees
- Data ownership and portability on termination
- Limitation of liability (typically 12 months fees paid)
- Mutual indemnification
- IP ownership of customer data and integrations
- Acceptable use policy
- Data processing agreement / GDPR addendum if EU data involved
- Termination for convenience with reasonable notice (30–90 days)
- Price change notice period

**Red flags:**
- Uncapped liability for IP indemnification
- Vendor can use customer data for training AI / improving services
- No data export right on termination ("data hostage")
- Unilateral right to change pricing mid-term
- Auto-renewal with short cancellation window (< 30 days)
- Vendor can suspend service for late payment with < 5 days notice

**Market standard:** Liability capped at 12 months fees, mutual indemnity, 30-day termination notice, data portability

---

## SAFE / Convertible Note (Investment)

**Expected clauses:**
- Valuation cap
- Discount rate
- Conversion triggers (qualified financing threshold)
- MFN (Most Favored Nation) clause
- Pro-rata rights
- Information rights
- Maturity date / repayment terms (notes only)

**Red flags:**
- No valuation cap (uncapped SAFE is extremely dilutive)
- High qualified financing threshold (e.g., $5M minimum to trigger conversion — delays investor)
- Post-money SAFE without founder understanding dilution math
- Side letters granting different terms to some investors
- Change-of-control conversion at 1x — founder gets nothing above liquidation preference
- No pro-rata right for follow-on rounds

**Market standard:** YC post-money SAFE with cap and discount is standard; no repayment obligation; conversion on qualified financing ≥ $1M

---

## Term Sheet (VC / Series A+)

**Expected clauses:**
- Pre-money valuation
- Investment amount and resulting ownership %
- Liquidation preference (1x non-participating is standard)
- Anti-dilution (broad-based weighted average is standard; full ratchet is predatory)
- Board composition
- Protective provisions (what decisions require investor approval)
- Option pool (pre or post-money — this matters enormously for dilution)
- Drag-along rights
- Information rights
- Redemption rights (rare, flag if present)

**Red flags:**
- Participating preferred (double-dip liquidation) — 🔴 High
- Full ratchet anti-dilution — ⛔ Critical
- Option pool shuffle (large pool created pre-money, diluting only founders)
- Broad protective provisions (investor can veto hiring, spending, pivots)
- Super-majority board control to investors at Series A
- Redemption rights after 5 years (forces buyback)
- Pay-to-play without explanation

**Market standard:** NVCA model documents; 1x non-participating liquidation preference; broad-based weighted average anti-dilution; 2 investor / 2 founder / 1 independent board

---

## Employment / Contractor Agreement

**Expected clauses:**
- Compensation and equity (vesting schedule, cliff)
- IP assignment (scope — should be limited to work done for the company)
- Invention assignment carve-out for pre-existing IP and personal projects
- Non-compete (check enforceability in employee's state — unenforceable in CA, ND, OK)
- Non-solicit of employees and customers
- At-will employment / termination for cause definition
- Severance terms
- Garden leave / notice period

**Red flags:**
- Overly broad IP assignment covering personal side projects
- Non-compete in a state where it's enforceable (TX, FL, NY) with no geographic limit
- No IP carve-out for founder's prior inventions (founder is assigning their own startup's IP!)
- Clawback of unvested equity on termination for any reason
- Non-disparagement clause that's one-sided
- Arbitration clause waiving right to jury trial

**Market standard:** At-will, 4-year vest / 1-year cliff equity, IP assignment limited to company-relevant work, carve-out for prior inventions, non-solicit only (no non-compete if in CA)

---

## Enterprise Partnership / Reseller Agreement

**Expected clauses:**
- Territory and exclusivity scope
- Revenue share / commission structure and calculation
- Minimum commitments (if any)
- IP licensing (what you're granting them, and limits)
- White-labeling rights and restrictions
- Termination for non-performance
- Audit rights (scope and frequency)
- Change-of-control (what happens if they get acquired)
- Most Favored Partner / pricing protections

**Red flags:**
- Exclusivity without minimum revenue commitments — ⛔ Critical
- Broad IP license that survives termination
- Unilateral right to add sub-resellers
- Change-of-control that auto-terminates agreement (kills your channel)
- Audit rights with no cap on frequency or cost
- Revenue share defined vaguely ("net revenue" without definition)

**Market standard:** Non-exclusive default; revenue share with clear definition; 30-day cure period before termination; change-of-control requires consent

---

## Data Processing Agreement (DPA) / Privacy Addendum

**Expected clauses:**
- Controller vs. Processor designation
- Subprocessor list and approval process
- Data retention and deletion obligations
- Breach notification timeline (72 hours under GDPR)
- Data transfer mechanisms (SCCs if EU data)
- Security requirements
- Audit rights (limited, not unlimited)

**Red flags:**
- Processor claiming controller rights over your customer data
- No breach notification obligation or timeline
- Subprocessors added without notice
- Data used for any purpose beyond providing the service
- No deletion obligation on termination

**Market standard:** GDPR-compliant DPA, 72-hour breach notification, SCCs for EU transfers, annual audit right

---

## HOW TO USE THIS FILE

1. Identify the agreement type from Step 1 intake
2. Pull the relevant section above
3. Add any "expected but missing" clauses to Section 2 of your analysis as 🟡–🔴 risks
4. Use the "market standard" line to calibrate aggressiveness ratings in Section 6
5. If the document is a hybrid (e.g., MSA + DPA + Order Form), cover all relevant sections
