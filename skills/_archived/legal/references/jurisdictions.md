# Jurisdiction Reference — Startup Contract Review

Quick-reference for jurisdiction-specific contract issues. Designed for AI-assisted review of startup agreements. Not legal advice — flag issues for lawyer review.

---

## United States

### Delaware

- **Key contract law differences:** Most flexible corporate law. Court of Chancery (no jury) handles business disputes — fast, predictable. Freedom of contract is very strong; courts enforce what you sign.
- **Enforceability gotchas:** Fiduciary duty waivers in LLC agreements are permitted (unlike most states). Fee-shifting bylaws are allowed. Limitation of liability clauses are broadly enforced.
- **Data protection regime:** No state-level comprehensive privacy law. Federal sectoral laws apply (HIPAA, COPPA, etc.). If users are in California, CCPA/CPRA still applies regardless of incorporation state.
- **Non-compete / Non-solicit:** Enforceable if reasonable in scope, duration (typically 1-2 years), and geography. Employee non-competes are upheld. Non-solicits are easier to enforce.
- **IP ownership defaults:** Work-for-hire doctrine applies per federal copyright law. For contractors, must have a written work-for-hire agreement or explicit assignment — verbal agreements are insufficient.
- **Red flags for founders:** Delaware governing law ≠ Delaware jurisdiction. If you pick DE law but don't consent to DE courts, disputes may land in your opponent's home state. Forum selection clauses matter.
- **Governing law strategy:** Strong default for B2B SaaS, investment docs, and inter-company agreements. Accept freely. Investors will expect it.

### California

- **Key contract law differences:** Strong consumer and employee protections override contract terms. Contracts of adhesion get heightened scrutiny. Implied covenant of good faith and fair dealing is robust.
- **Enforceability gotchas:** Non-competes are **void** (Business & Professions Code §16600) — even for executives, even with consideration, even governed by another state's law if employee is in CA. Liquidated damages must be reasonable at time of contracting. Unilateral arbitration clauses in employment are heavily scrutinized.
- **Data protection regime:** CCPA/CPRA applies if you meet thresholds ($25M revenue, 100K consumers' data, or 50%+ revenue from selling data). Requires specific DPA provisions: right to delete, right to opt out of sale, data inventory obligations.
- **Non-compete / Non-solicit:** Non-competes: **completely unenforceable** — do not include them for CA-based employees/founders. Non-solicits of employees: also void in CA. Non-solicits of customers: gray area, narrowly enforceable if limited.
- **IP ownership defaults:** California Labor Code §2870 — inventions created on employee's own time, without employer equipment, unrelated to employer's business, belong to the employee. Assignment clauses must carve this out or they're unenforceable.
- **Red flags for founders:** If your team is in CA, CA law applies to employment terms regardless of what governing law the contract states. Including a non-compete for a CA employee signals the contract wasn't reviewed properly.
- **Governing law strategy:** Avoid for B2B vendor contracts if you're the vendor (too protective of the other side). Accept for employment if your team is in CA (you have no choice).

### New York

- **Key contract law differences:** Very literal contract interpretation — courts enforce plain language, rarely look beyond the four corners. No implied good faith duty in contract performance (unlike CA). Merger/integration clauses are strongly enforced.
- **Enforceability gotchas:** Contracts over $250K with NY governing law: if you include a NY forum selection clause, the other party can't challenge jurisdiction. Mandatory pre-dispute arbitration clauses are enforced. No-oral-modification clauses are actually enforced (unlike most states).
- **Data protection regime:** NY SHIELD Act requires reasonable data security safeguards. Breach notification requirements are strict (notify AG, affected individuals). No comprehensive CCPA-equivalent yet.
- **Non-compete / Non-solicit:** Non-competes are enforceable but scrutinized — must protect legitimate business interest, reasonable in time/scope/geography. Typical: 12 months, limited geography. Courts may blue-pencil (narrow) overbroad clauses rather than void them. **Note:** 2025 legislative push to ban them — verify current status.
- **IP ownership defaults:** Standard work-for-hire and assignment rules. No special carve-outs like CA §2870.
- **Red flags for founders:** NY litigation is expensive. Accepting NY jurisdiction means expensive disputes. Ensure arbitration or mediation clauses if you agree to NY law.
- **Governing law strategy:** Common in finance, enterprise SaaS, and VC side letters. Reasonable to accept for commercial contracts. Pair with arbitration to control costs.

### Texas

- **Key contract law differences:** Strong freedom of contract. Courts rarely rewrite deals. Texas Business and Commerce Code governs most B2B. No state income tax makes it attractive for structuring.
- **Enforceability gotchas:** Non-competes require "ancillary to an otherwise enforceable agreement" — must be tied to consideration like confidential information access or specialized training. Overbroad clauses get reformed, not voided.
- **Data protection regime:** Texas Data Privacy and Security Act (TDPSA, effective 2024) — similar to CCPA but with some differences in thresholds and enforcement. Breach notification law requires notice within 60 days.
- **Non-compete / Non-solicit:** Enforceable if ancillary to valid agreement and reasonable. Typical duration: 1-2 years. Courts reform rather than void overbroad clauses — which means even a bad non-compete might survive in narrowed form.
- **IP ownership defaults:** Standard federal rules. No special state-level IP provisions.
- **Red flags for founders:** Texas anti-SLAPP statute is weaker than California's. Arbitration clauses are strongly enforced. Jury trials in Texas can produce large verdicts — consider arbitration.
- **Governing law strategy:** Neutral, business-friendly choice. Acceptable for most B2B contracts.

### Florida

- **Key contract law differences:** Strong enforcement of restrictive covenants by statute (Florida Statutes §542.335). Presumes non-competes are valid — burden shifts to the person challenging them. Courts cannot refuse enforcement based on hardship.
- **Enforceability gotchas:** Non-competes are presumptively valid. Liquidated damages clauses are enforced if not a "penalty." Forum selection clauses strongly enforced.
- **Data protection regime:** Florida Digital Bill of Rights (2023) — applies to companies with $1B+ revenue or significant data operations. Narrower scope than CCPA. Standard breach notification requirements.
- **Non-compete / Non-solicit:** **Most employer-friendly state.** Presumed enforceable. 6 months presumed reasonable; up to 2 years for non-solicits. Courts cannot consider hardship to the restricted party. Very dangerous to sign if you're the employee/founder.
- **IP ownership defaults:** Standard federal rules apply.
- **Red flags for founders:** If someone asks you to sign a non-compete governed by Florida law, push back hard — Florida courts will enforce it. Florida is a poor choice for dispute resolution if you're the smaller party (expensive, slow courts).
- **Governing law strategy:** Favor if you're the party imposing restrictions. Resist if you're the restricted party.

### US Cross-Cutting Issues

- **Statute of limitations:** Varies by state — written contracts: 4 years (CA), 6 years (NY, DE), 4 years (TX). Always check; a stale claim in one state may be live in another.
- **Punitive damages:** Available in most states for fraud/willful misconduct. CA: no cap except medical malpractice. TX: capped at greater of $200K or 2x economic damages. NY: available but courts are conservative.
- **Attorney's fees:** American Rule (each side pays own fees) unless contract says otherwise. Always include a prevailing-party fee-shifting clause — it deters frivolous claims.
- **Arbitration enforceability:** Federal Arbitration Act makes arbitration clauses broadly enforceable. Exceptions: some employment disputes (transportation workers), small claims. JAMS or AAA are standard; ICC for international.
- **Choice of law:** Parties can generally choose, but: (a) consumer contracts may be overridden by local law, (b) employment contracts are often governed by where the employee works, (c) real property governed by situs state.

---

## Singapore

- **Key contract law differences:** Based on English common law. Contract Act (Cap 184) governs. High freedom of contract in commercial deals. Courts enforce bargains with minimal interference. Entire agreement clauses are respected. Oral contracts are enforceable but hard to prove.
- **Enforceability gotchas:** Penalty clauses are unenforceable — liquidated damages must be a genuine pre-estimate of loss. Exclusion clauses subject to Unfair Contract Terms Act (Cap 396, modeled on UK UCTA). Stamp duty required on certain documents (share transfers, leases) — unstamped documents are inadmissible as evidence.
- **Data protection regime:** PDPA (Personal Data Protection Act 2012, amended 2020). Applies to all organizations collecting/using personal data in Singapore. Requires: consent for collection/use/disclosure, purpose limitation, data breach notification within 3 days if significant. DPAs with processors are mandatory. Cross-border transfers require comparable protection standard. Financial penalties up to 10% of annual turnover.
- **Non-compete / Non-solicit:** Enforceable but courts apply strict reasonableness test. Broad non-competes (more than 12 months, unlimited geography) are routinely struck down. Must protect legitimate proprietary interest (trade secrets, client relationships). Non-solicits of clients are more readily enforced than blanket non-competes. Garden leave may be used as alternative.
- **IP ownership defaults:** Copyright Act — employer owns IP created by employees in the course of employment. For contractors, the contractor owns copyright unless there's a written assignment. Patents follow similar rules. Always include explicit IP assignment for contractor agreements.
- **Red flags for founders:** Stamp duty trap — share transfer agreements and certain contract types need stamping within 14 days or face penalties. Employment Act (Cap 91) mandates minimum benefits (14 days leave, sick leave, overtime for non-exempt) that cannot be contracted out of. Directors have fiduciary duties under Companies Act that override contract terms — indemnities for director breach of duty are void.
- **Governing law strategy:** Excellent neutral jurisdiction for Asia-Pacific contracts. Singapore International Arbitration Centre (SIAC) is widely respected. Strong choice for contracts with counterparties in SEA, India, or China. Your home jurisdiction — default to this when possible.

---

## United Kingdom

- **Key contract law differences:** Common law with strong freedom of contract. Parol evidence rule applies — written contracts are hard to contradict with oral evidence. Consideration required (but nominal consideration is fine). Good faith duty is limited — no general duty to negotiate in good faith.
- **Enforceability gotchas:** Unfair Contract Terms Act (UCTA 1977) limits exclusion of liability — cannot exclude liability for death/personal injury from negligence, and exclusion of other negligence liability must be "reasonable." Consumer Rights Act 2015 applies to B2C. Penalty clauses are unenforceable per Cavendish/ParkingEye test — but genuine commercial interest in performance can justify large sums. Entire agreement clauses don't exclude liability for fraudulent misrepresentation.
- **Data protection regime:** UK GDPR (retained EU law post-Brexit) + Data Protection Act 2018. Very similar to EU GDPR. Requires: DPA with processors, lawful basis for processing, DPIA for high-risk processing, breach notification to ICO within 72 hours. International transfers: UK uses own adequacy decisions (not identical to EU's). UK Extension to EU SCCs or UK International Data Transfer Agreement (IDTA) required for transfers to non-adequate countries.
- **Non-compete / Non-solicit:** Enforceable if protecting legitimate business interest and reasonable in scope. Typical: 6-12 months for non-competes, 12 months for non-solicits. Garden leave is common and preferred. Courts will not blue-pencil (rewrite) — if a clause is too broad, the entire clause fails. Draft narrowly.
- **IP ownership defaults:** Copyright, Designs and Patents Act 1988 — employer owns IP created by employees in the course of employment. Contractors retain ownership unless assigned in writing. Moral rights exist and must be explicitly waived if needed. Patents Act 1977 — similar employee/employer rules.
- **Red flags for founders:** Post-Brexit, UK-EU data transfers now require separate legal mechanism (UK adequacy from EU exists until 2025 — verify current status). IR35 rules for contractors — misclassification risk is significant and penalties fall on the hiring company. Notice periods in employment are statutory minimums (1 week per year of service, up to 12 weeks) and cannot be reduced by contract.
- **Governing law strategy:** Respected, neutral jurisdiction for international contracts. London Commercial Court and LCIA arbitration are world-class. Good choice for enterprise contracts with European counterparties. Reasonable to accept for most B2B SaaS deals.

---

## European Union / GDPR Jurisdictions

- **Key contract law differences:** No unified EU contract law — each member state has its own (French Code Civil, German BGB, etc.). However, EU Directives harmonize consumer protection, digital services, and data. Key difference: many civil law jurisdictions imply good faith into all contracts and may override express terms that are deemed unfair.
- **Enforceability gotchas:** Consumer protection Directives restrict unfair terms in B2C — cannot exclude statutory warranty, cannot impose one-sided jurisdiction, limitation of liability in consumer contracts is heavily restricted. B2B is more permissive but some jurisdictions (Germany, France) still apply fairness controls to standard terms. Penalty clauses are generally enforceable in civil law countries (unlike common law) — be careful what you agree to.
- **Data protection regime:** GDPR applies to all processing of EU residents' data, regardless of where you're incorporated. Requires: (a) lawful basis for each processing activity, (b) DPA (Art. 28) with all processors, (c) DPIA for high-risk processing, (d) Data breach notification to supervisory authority within 72 hours, (e) DPO appointment if core activities involve large-scale monitoring. Cross-border transfers to non-adequate countries require Standard Contractual Clauses (SCCs, 2021 version) or Binding Corporate Rules. Right to erasure (Art. 17) impacts data retention clauses. Fines: up to 4% of global annual turnover or EUR 20M.
- **Non-compete / Non-solicit:** Varies wildly by member state. France: enforceable but requires financial compensation during restriction period (typically 30-50% of salary). Germany: enforceable with mandatory compensation (at least 50% of salary). Netherlands: must be in writing and only for definite-term contracts with compelling business interest. Italy: requires compensation and cannot exceed 5 years. General trend: compensation during restriction period is required.
- **IP ownership defaults:** Varies by member state. Generally: employer owns employee-created IP in course of employment. Software has special rules under EU Software Directive — employer owns copyright in software created by employee. Moral rights are strong and often non-waivable (France, Germany).
- **Red flags for founders:** GDPR compliance is non-negotiable — any contract involving EU user data needs proper DPA language. SCCs must be the 2021 version (old 2010 SCCs are invalid). Right to audit processor is mandatory under Art. 28 and cannot be waived. Some EU jurisdictions require contracts to be in the local language to be enforceable against local parties.
- **Governing law strategy:** If contracting with EU companies, expect them to push for their local law. Ireland is a popular neutral EU jurisdiction (English-speaking, common law influenced). Netherlands is also common for international contracts. For data-heavy contracts, ensure GDPR compliance regardless of governing law — it applies extraterritorially.

---

## India

- **Key contract law differences:** Indian Contract Act 1872 governs. Based on English common law but with significant statutory modifications. Contracts must have lawful consideration and lawful object. Courts have broad power to sever unconscionable terms (Section 23 — agreements opposed to public policy). Specific performance is more readily available than in common law jurisdictions.
- **Enforceability gotchas:** **Section 27: Non-competes are void** — any agreement in restraint of trade is void, with the narrow exception of sale-of-goodwill non-competes. This applies to employees, contractors, and even during the term of the agreement (post-termination non-competes are unenforceable). Liquidated damages: courts can reduce if "excessive" (Section 74) even if parties agreed. Stamp duty is mandatory on many agreements — unstamped or under-stamped documents are inadmissible as evidence and attract penalties. Stamp duty rates vary by state.
- **Data protection regime:** Digital Personal Data Protection Act 2023 (DPDPA). Requires: consent for processing, purpose limitation, data principal rights (access, correction, erasure), breach notification to Data Protection Board. Cross-border transfers allowed to all countries unless specifically restricted by government. Penalties up to INR 250 crore (approx. USD 30M). IT Act 2000 and SPDI Rules (2011) still apply in some contexts — reasonable security practices required for sensitive personal data.
- **Non-compete / Non-solicit:** Non-competes: **unenforceable** (Section 27, Indian Contract Act). This is near-absolute — even narrowly drafted post-termination non-competes are void. Non-solicits of clients: gray area, some courts enforce if narrowly drafted as protection of trade secrets/confidential information rather than restraint of trade. Non-solicits of employees: generally unenforceable as restraint of trade. Confidentiality/NDA clauses are enforceable and are the primary protective mechanism.
- **IP ownership defaults:** Copyright Act 1957 — employer owns copyright in works created by employees during course of employment. Contractors retain copyright unless assigned in writing. Patents Act 1970 — inventions by employees using employer resources: employer owns. Assignment of future IP is valid if clearly defined. Moral rights exist under copyright but are narrower than EU.
- **Red flags for founders:** **FEMA (Foreign Exchange Management Act):** Cross-border agreements with Indian entities need FEMA compliance — payment terms, pricing, and certain contract types require RBI approval or compliance with automatic route rules. Share issuance to foreign parties is regulated. Stamp duty trap: varies by state (Maharashtra is highest), and failure to stamp renders the contract inadmissible — critical for enforcement. Indian courts are slow (years for resolution) — always include arbitration (Indian Arbitration Act 1996 is pro-arbitration). Service agreements with Indian contractors may create "permanent establishment" tax risk.
- **Governing law strategy:** Indian courts may refuse to enforce foreign governing law if it conflicts with Indian public policy (Section 27 non-compete, for example). For contracts with Indian employees/contractors: Indian law will apply to employment/engagement terms regardless. For commercial B2B with Indian companies: Singapore law + SIAC arbitration is a very common and effective choice — Singapore awards are enforceable in India. Avoid Indian litigation forum if possible.

---

## Australia

- **Key contract law differences:** Common law, broadly similar to UK but with significant statutory overlays. Australian Consumer Law (ACL, Schedule 2 of Competition and Consumer Act 2010) is the dominant force — it implies warranties and conditions that cannot be excluded. Good faith duty in contract performance is recognized in most states (implied term in many commercial contracts).
- **Enforceability gotchas:** ACL unfair contract terms regime (extended to small business contracts in 2023) — terms that cause significant imbalance, are not reasonably necessary, and would cause detriment can be declared void. Applies to standard form contracts where one party has $10M or fewer employees or $10M or less turnover. Entire agreement clauses do not exclude ACL implied terms. Indemnity clauses that are one-sided may be deemed unfair. Cannot exclude consumer guarantees for goods/services.
- **Data protection regime:** Privacy Act 1988 + Australian Privacy Principles (APPs). Applies to organizations with $3M+ annual turnover (and some smaller organizations). Requires: notice of collection, purpose limitation, data quality, data security, cross-border disclosure protections (must ensure overseas recipient handles data per APPs or consent), breach notification to OAIC within 30 days if likely to result in serious harm. Penalties up to AUD 50M or 30% of turnover. No direct GDPR equivalent but cross-border disclosure rules require contractual protections with overseas processors.
- **Non-compete / Non-solicit:** Enforceable under "restraint of trade" doctrine — presumed void unless the party relying on it proves reasonableness. Courts consider: (a) legitimate protectable interest, (b) reasonable in time, geography, and scope, (c) not contrary to public interest. Cascading/ladder clauses (multiple durations/geographies, court picks the enforceable one) are common and accepted. Typical: 6-12 months. Blue-pencil/reading down is available.
- **IP ownership defaults:** Copyright Act 1968 — employer owns copyright in works created by employees under a contract of service. Contractors (contract for services) retain copyright unless assigned. Important: for commissioned photographs, paintings, and portraits, the commissioner owns copyright. Patents Act 1990 — employer owns employee inventions made in course of employment. Designs Act 2003 — similar employer ownership rules.
- **Red flags for founders:** ACL is the big one — standard US-style limitation of liability and warranty disclaimer clauses will likely be unenforceable for Australian customers if you're providing goods or services. The unfair contract terms regime now carries civil penalties (not just voiding the term). Independent contractor misclassification (sham contracting) carries penalties under Fair Work Act. Modern slavery reporting if revenue exceeds AUD 100M.
- **Governing law strategy:** For contracts with Australian customers/users: Australian law will likely be implied regardless of what you choose (ACL applies). For B2B with Australian companies: accept Australian law if you're providing services to them — resistance looks bad and the law is reasonable. For your own vendor agreements with Australian providers: Singapore or neutral law is fine but ACL consumer guarantees still apply to their services to you if you qualify as a consumer.

---

## Quick Comparison Matrix

| Topic | US (DE) | US (CA) | Singapore | UK | EU (GDPR) | India | Australia |
|---|---|---|---|---|---|---|---|
| Non-compete | Enforceable | **Void** | Strict reasonableness | Enforceable (narrow) | Requires compensation | **Void (S.27)** | Presumed void unless reasonable |
| Privacy law | Sectoral | CCPA/CPRA | PDPA | UK GDPR | GDPR | DPDPA 2023 | Privacy Act/APPs |
| DPA required | If CCPA applies | If CCPA applies | Yes (PDPA) | Yes (UK GDPR) | Yes (Art. 28) | Yes (DPDPA) | Cross-border |
| Penalty clauses | Enforceable if reasonable | Enforceable if reasonable | Unenforceable | Unenforceable | Generally enforceable | Courts can reduce | Unfair terms regime |
| Stamp duty | No | No | Yes (shares, leases) | No (abolished 2003) | Varies by state | **Yes (critical)** | No |
| Arbitration preferred | Yes (FAA) | Yes (with limits) | Yes (SIAC) | Yes (LCIA) | Varies | **Yes (strongly)** | Yes |
| Contractor IP default | Contractor owns | Contractor owns | Contractor owns | Contractor owns | Contractor owns | Contractor owns | Contractor owns |

---

## Decision Framework for Founders

1. **Your employees are in CA or India?** Do not include non-competes. Use NDAs and IP assignment instead.
2. **Handling EU user data?** GDPR DPA with 2021 SCCs is mandatory regardless of governing law.
3. **Singapore Pte. Ltd. contracting with Asian counterparties?** Default to Singapore law + SIAC arbitration — it's your strongest position.
4. **Signing a contract governed by Florida law with non-compete?** Push back hard — Florida courts will enforce it aggressively.
5. **Indian contractor or vendor?** Ensure stamp duty compliance, use SIAC arbitration, budget for FEMA compliance if payments are cross-border.
6. **Australian customers?** Accept that ACL consumer guarantees apply — do not try to disclaim them, it creates legal risk and looks bad.
7. **Cross-border data transfer?** Map data flows first, then layer in SCCs (EU), IDTA (UK), PDPA transfer provisions (SG), or contractual protections (AU) as needed.
