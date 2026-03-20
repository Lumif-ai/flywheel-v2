# Lumif.ai — Full Company Context for Meeting Preparation

## What Lumif.ai Does (One Sentence)
Lumif.ai is an AI-native platform that parses any contract, extracts structured compliance requirements (insurance, regulatory, SLA, indemnification, credentialing), reconciles those requirements against evidence documents (COIs, endorsements, bonds, BAAs, licenses), and surfaces gaps with full traceability.

## The Core Problem
Every vendor-heavy industry has the same structural problem: contracts create obligations, and evidence documents prove those obligations are met. Today, nobody systematically connects the two sides. Contract teams store contracts. Compliance teams track documents. The reconciliation between "what does the contract require?" and "what has the vendor actually provided?" happens manually, if it happens at all.

## How Lumif.ai Works (The Product)
1. **Upload the contract** (MSA, wrap manual, vendor agreement, BAA, SLA). The AI parser extracts every compliance requirement, organized by category, with page-level source references.
2. **Onboard vendors/subcontractors.** Pull from existing systems (Procore, Salesforce, vendor management platforms) or add manually.
3. **Collect evidence documents.** Vendors upload COIs, endorsements, declarations pages, licenses, bonds, financial statements, safety records. The platform auto-classifies each document type.
4. **AI reconciliation.** The compliance matrix compares every contract requirement against every submitted document, line by line. Green = compliant. Red = missing entirely. Amber = coverage exists but limit falls short (with exact shortfall amount).
5. **Dual traceability.** Every row in the compliance matrix has two clickable links: one to the contract page where the requirement is defined, one to the vendor's document page where the value was extracted. Full audit trail.
6. **Auto-generated notifications.** When gaps are detected, the platform drafts deficiency emails tailored to each vendor, detailing exactly what is missing or insufficient.

## The Key Differentiator
**Contract-to-evidence reconciliation.** COI trackers (Jones, myCOI/illumend, TrustLayer, bcs) check coverage documents against manually configured rule sets. CLM tools (Ironclad, Agiloft) store contracts. Pre-qualification platforms (ISNetworld, Avetta) score vendor risk. Nobody starts from the actual contract language, auto-generates the requirement set, and reconciles across to the evidence documents. Lumif.ai does this.

The sharpest technical differentiator is **endorsement-level parsing**. An MSA might require endorsement form CG 20 10 (Additional Insured - Owners, Lessees or Contractors). A vendor's COI shows "Additional Insured" is checked, but the actual endorsement page shows form CG 20 33 (narrower coverage). No competitor parses endorsement pages for specific form numbers. Lumif.ai does.

---

## [SECTION: MODULES]

### Module 1: Insurance Compliance
- Parse MSA, extract insurance requirements per subcontractor trade
- Ingest sub documents (COI, endorsements, dec pages), auto-classify
- Generate compliance matrix with dual traceability
- Auto-send deficiency notices

### Module 2: Wrap Program Management
- Parse OCIP/CCIP wrap manuals
- Identify wrap-provided vs. off-wrap coverages
- Flag excluded trades attempting enrollment
- Monitor for WC state-level gaps, payroll anomalies, coverage drift
- Continuous monitoring during active construction

### Module 3: Vendor Pre-Qualification
- Ingest AIA A305 qualifications package + supporting documents
- Extract financial risk indicators (revenue trends, liquidity, working capital, backlog concentration, project size fit)
- Extract safety risk indicators (EMR with 3-year trend, OSHA TRIR/DART, loss run analysis)
- Validate claims against public sources (FDIC BankFind, OSHA enforcement, Secretary of State)
- Decision-ready dashboard: approve, conditional approval, or escalation

### Planned: Mid-Project Risk Monitoring (P0 priority)
- Continuous monitoring of subcontractor health after pre-qualification
- OSHA enforcement actions, insurance status changes, financial signals, project performance data
- Transforms from point-in-time assessment to ongoing risk intelligence

### Planned: Change Order Compliance (as feature)
- Parse change orders for new/modified compliance requirements
- Auto-check against sub's current coverage
- Nobody else does this

---

## [SECTION: MOAT]

The moat is not any single feature. It is the integrated platform:
1. **Endorsement-level parsing depth** - requires construction-specific training data and domain expertise in insurance policy language
2. **Wrap program interpretation** - unique capability, no competitor addresses this
3. **Pre-qualification integration** - financial/safety risk scoring connected to compliance verification
4. **Dual traceability** - unique UX linking every compliance decision to source documents on both sides
5. **Continuous monitoring** (planned) - extends snapshot to film

Any individual feature can be replicated in 12-18 months. The combination of all five, integrated into a single platform, is the defensible position.

---

## [SECTION: COMPETITORS]

### COI Trackers (document verification)
- **Jones** - Construction/CRE focused, 110K vendor network, Procore integration, AI + human review
- **illumend (myCOI rebrand, May 2025)** - 15 years in market, 45M+ docs reviewed, 750K+ partners. Now claims contract parsing via AI ("Lumie" assistant). Procore integration. Multi-industry.
- **TrustLayer** - AI-first, 298K company database, "Pulse" real-time policy monitoring via carrier connections
- **bcs** - Construction/CRE, 78K vendor network, no-login submissions, RiskBot AI
- **Certificial** - "Smart COI" with real-time carrier-connected monitoring. Only platform detecting mid-term cancellations in seconds.
- **SmartCompliance** - OCR-based, less insurance depth

### Pre-Qualification Platforms (vendor risk scoring)
- **ISNetworld (ISN)** - Dominant in oil & gas. Contractor-paid ($700+/month). Extensive questionnaires.
- **Avetta** - 130K+ businesses, 120+ countries. Broadest scope (safety, ESG, DEI, cyber, financial, insurance). Contractor-paid. Worker-level compliance tracking. Sub-tier visibility.
- **Vertikal RMS (PreQual)** - Expert financial analyst review (human, not just AI). Construction-focused.
- **COMPASS SRP** - Q Score for subcontractor execution ability. CSI code ranking. Construction-focused.
- **Highwire** - Pre-qual with claimed $7M annual savings for one client vs. ISNetworld.

### Construction PM / ERP (store but don't parse contracts)
- **Procore** - Center of gravity for construction PM. Everyone integrates with Procore.
- **CMiC** - ERP for larger GCs. Contract and financial management.
- **Sage 300 / Vista** - Accounting/ERP for mid-large GCs.
- **Autodesk Build** - PM platform, growing compliance features.

### Key Competitive Threat: illumend
illumend's contract parsing claim (May 2025) is the most significant competitive development. Their marketing says the AI "reads contracts, extracts insurance requirements, and flags compliance gaps automatically." However:
- Their system still uses human insurance specialists for verification (suggesting AI extraction is not fully autonomous)
- 15 years of heritage is in COI tracking, not contract AI
- No endorsement-level form number parsing demonstrated
- No wrap program interpretation
- No pre-qualification
- Multi-industry focus (10+ industries) means they're not going deep on construction-specific workflows

**The acid test:** Can illumend parse an MSA, extract specific endorsement form numbers (CG 20 10 vs CG 20 37), parse the endorsement page, and flag the wrong form? Can they parse a wrap manual and identify excluded trades? If not, their parsing is shallow.

---

## [SECTION: VERTICALS]

### Currently Active
- **Construction** (initial wedge, three modules built, demo scripts complete)

### Phase 2 Targets (6-12 months)
- **Energy, Oil & Gas** - Closest to construction DNA. High Pain / High Access. Heavy subcontractor use. Master service agreements with insurance/safety/environmental requirements. ISNetworld dominant but hated by contractors. OSHA Process Safety Management creates complex compliance requirements.
- **Data Centers** - Construction-grade build phase + operational compliance. Rapidly growing ($200B+ in planned investment). Every hyperscaler (AWS, Microsoft, Google) and colocation provider (Equinix, Digital Realty) uses GCs and specialty subs with stringent requirements.

### Phase 3 Targets (12-24 months)
- **Retail / Property Management** - Full deep dive completed. Vendor lifecycle (custodial, HVAC, security, landscaping, pest control, IT/POS, construction/remodel). Fidelity bond is #1 missed document. Broker channel is the entry point.
- **CRE / Commercial Real Estate** - Most competitive COI market (Jones, bcs strong here). Building management vendor compliance.

### Phase 4 Targets (24+ months)
- **Healthcare** - #1 ranked opportunity by market size, but hardest GTM. Five compliance layers: insurance, HIPAA/BAA, OIG exclusion screening, vendor credentialing, Stark Law/Anti-Kickback. Full deep dive completed.
- **Financial Services / Banking** - Strong regulatory tailwind (2023 interagency TPRM guidance). Mature ecosystem but contract-to-evidence gap still exists.

---

## [SECTION: GTM]

### Current Sales Motion
- Broker channel connections (construction insurance brokers)
- Cold outreach to alumni and via LinkedIn
- Target: GC risk managers, VPs of Risk, project executives

### The Felt Pain vs. Latent Pain Tension
The most differentiated capabilities (contract parsing, endorsement verification, wrap interpretation) address *latent* pain that buyers don't know they have. The most commonly felt pain (document chaos, expiration tracking) is commoditized.

**Sales sequence:**
1. **Lead with felt pain** - "You spend 15-20 hours/week tracking COIs and chasing subs." (Door opener)
2. **Differentiate on latent pain** - Upload their actual MSA live, show specific endorsement form numbers extracted, demonstrate a gap their current tool misses. (Aha moment)
3. **Close on risk quantification** - "You have 14 subs with the wrong endorsement form. Aggregate exposed subcontract value: $23M." (Dollar conversion)
4. **Retain on lifecycle** - Expand from insurance compliance to wrap management, pre-qual, monitoring, closeout.

### Pricing Approach
- Price per project or per GC (not per sub, to avoid contractor-paid friction)
- Target: $50K-$200K/year depending on project volume and module mix
- Beachhead: mid-size GCs ($100M-$1B revenue) with 10-30 active projects

---

## [SECTION: ANGLES]

### If speaking with a GC Risk Manager / Insurance Coordinator
- They live in the document chaos daily. Lead with time savings.
- Ask: "How do you currently extract insurance requirements from your MSAs?" (If answer is "manually" or "we use a checklist," that's the opening.)
- Ask: "When was the last time you discovered a compliance gap after a claim was filed?" (Horror story trigger)
- Demo hook: Offer to run their actual MSA through the parser live.

### If speaking with a VP of Risk / CRO at a GC
- They care about portfolio-wide visibility and audit defensibility.
- Ask: "Do you have a single dashboard showing compliance status across all your active projects?"
- Ask: "If an owner audited your sub compliance tomorrow, how long would it take to pull the documentation?"
- Value prop: Real-time portfolio risk view, proactive alerts, audit-ready traceability.

### If speaking with a Project Executive / PM
- They care about project delivery risk and sub performance.
- Ask: "How do you evaluate sub risk before signing a subcontract?" (Pre-qual angle)
- Ask: "When you issue a change order that changes scope, does anyone check if it changes the insurance requirements?" (Change order angle - guaranteed they don't do this)

### If speaking with an Owner / Developer
- They care about exposure on their wrap program and GC accountability.
- Ask: "How do you verify that your GC's subcontractors are actually compliant with your program requirements?"
- Ask: "On your OCIP projects, who checks whether excluded trades have been incorrectly enrolled?"
- Value prop: Direct visibility into sub compliance without relying on GC self-certification.

### If speaking with a Construction Insurance Broker
- They are the channel. They advise GCs on programs and manage compliance.
- Ask: "How much of your team's time is spent on manual compliance verification for your construction clients?"
- Ask: "Have you ever had a claim denied because the sub had the wrong endorsement form?"
- Value prop: Lumif.ai makes their service more efficient and more thorough. White-label opportunity.

### If speaking with someone in Energy / Oil & Gas
- ISNetworld fatigue is the entry point. Everyone hates ISN.
- Ask: "How much are your contractors spending on ISNetworld annually?" (Answer: $700+/month per contractor)
- Ask: "Does ISNetworld parse your MSAs to generate compliance requirements, or do you configure those manually?"
- Key insight: Energy MSAs are even more complex than construction (environmental, process safety, shutdown/turnaround requirements). Same contract-to-evidence gap.

### If speaking with someone in Retail / Property Management
- Vendor lifecycle is the frame. They manage 10+ vendor categories.
- Ask: "How do you track insurance compliance for your custodial, HVAC, and security vendors?"
- Ask: "Has a fidelity bond ever come up as a gap?" (Fidelity bond is the #1 missed document in retail - not on ACORD 25, COI trackers can't track it)
- Key insight: Broker channel works the same as construction.

### If speaking with someone in Healthcare
- Compliance layers are the differentiator. Healthcare has 5 layers, not just insurance.
- Ask: "How do you reconcile your vendor BAA requirements against actual BAA execution?"
- Ask: "Who handles OIG exclusion screening for your vendor relationships?"
- Key insight: Healthcare is highest-value but hardest GTM. Use for market intelligence, not immediate sales.

### If speaking with someone in Data Centers
- Construction phase + operational phase creates dual compliance needs.
- Ask: "During your build phase, how do you manage sub insurance compliance across your GCs?"
- Ask: "Once operational, how do you track vendor compliance for maintenance, security, and facility management?"
- Key insight: Data center operators are sophisticated buyers with budget. They use construction GCs for build phase (Lumif.ai's existing wheelhouse) and then need ongoing vendor compliance for operations.

---

## [SECTION: STATS]

### Key Statistics to Reference in Conversations
- U.S. construction spending: $2.2 trillion (2024)
- Construction fatalities: 1,034 (2024), 19% of all U.S. workplace deaths
- OSHA construction penalties: $117.9 million (FY2023)
- COI non-compliance rate on first submission: 60-70%
- Subcontractor default cost: 1.5-3x original contract value (Marsh)
- 43% of subs have insufficient working capital (Billd 2025)
- Sub payment gap: GCs think 30 days, subs wait 56 days average
- illumend/myCOI scale: 45M+ documents, 750K+ partners, 1.2M+ agreements
- Avetta scale: 130K+ businesses, 120+ countries
- Healthcare data breach average cost: $9.48M (IBM 2024)
- HIPAA penalties: up to $2.19M per provision (OCR 2025)

---

## [SECTION: NOT]

### What We Are NOT
- We are not a safety management platform (Procore Safety, Safesite, iAuditor)
- We are not a bid management / estimating tool (ProEst, Buildxact)
- We are not a lien management platform (Levelset / Procore Payments)
- We are not a certified payroll platform (hh2, Foundation Software)
- We are not a general CLM / contract management tool (Ironclad, Agiloft)
- We are not a project management platform (Procore, CMiC)
- We are the reconciliation layer between contracts and evidence. That's the thesis. Every module reinforces it.
