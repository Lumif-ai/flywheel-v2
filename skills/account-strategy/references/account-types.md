# Account Type Reference

This file defines the three account archetypes and how each type changes the emphasis of the account strategy pipeline. Referenced by SKILL.md Phase 1 (classification) and Phase 8 (recommendations).

---

## Type 1: Customer / Pilot

**Definition:** A prospect evaluating lumif.ai as an end-user. They will deploy the product within their own operations.

**Examples:** RMR Group (property management COI tracking), any enterprise evaluating lumif.ai for their own workflow.

**Qualification signals:**
- They described an internal workflow problem
- They asked about pricing for their own use
- They have an internal champion pushing for a solution
- They mentioned a POC, pilot, or trial

### Phase Emphasis Overrides

| Phase | Emphasis | Why |
|-------|----------|-----|
| 3: Stakeholders | Map the full decision chain: champion -> evaluator -> budget holder -> CIO/CTO sign-off | Enterprise deals die when you miss a decision-maker |
| 4: Competitive | Focus on internal tools first, then external competitors. Internal tools are the #1 competitor. | RMR had an internal COI Validation Agent. This is always the hardest to displace. |
| 5: Pricing | Per-unit economics (per COI, per contract, per user). Pilot pricing vs scale pricing. Cost-of-problem as anchor. | Buyers need to justify ROI to finance. "It costs $X per unit, you currently spend $Y" wins. |
| 6: Demo/POC | Specific script modifications. Use their terminology, their systems, their pain points. Demo data should mirror their world. | RMR needed Yardi not Salesforce, portfolio view not single-property. Generic demos lose. |
| 7: Risk | Integration complexity, IT approval timeline, internal tool overlap, champion departure risk | "Yardi took 6 months" is a real timeline signal |

### Recommendation Template

Recommendations for Customer/Pilot accounts should address:
1. **Pilot design:** Scope (which entities/properties/contracts), duration, success metrics
2. **Integration path:** Which systems to integrate first, technical requirements
3. **Champion enablement:** What materials does the champion need to sell internally?
4. **Pricing structure:** Pilot pricing that de-risks the buyer's decision
5. **Timeline:** Realistic timeline based on their procurement signals

### Success Metrics
- Pilot agreement signed
- Integration requirements documented
- Champion armed with internal pitch materials
- Clear path from pilot to full deployment

---

## Type 2: Channel / White-Label Partner

**Definition:** A partner who will resell or white-label lumif.ai to their own clients. They are not the end user -- they are a distribution channel.

**Examples:** Amphibious Group (TAG) -- insurance consultancy white-labeling lumif.ai for their GC clients.

**Qualification signals:**
- They serve a portfolio of clients who match our ICP
- They asked about white-labeling, reselling, or embedding
- Their business model is advisory/consulting (they add services on top)
- They want to offer "their platform" (powered by lumif.ai)

### Phase Emphasis Overrides

| Phase | Emphasis | Why |
|-------|----------|-----|
| 2: Company | Deep dive into their service portfolio and client base. How many clients? What verticals? What's their revenue model? | Partner value = reach x relevance. Need to quantify both. |
| 3: Stakeholders | Identify the partner's decision-maker AND their clients' typical decision-makers | Two-level stakeholder map: partner contacts + their client archetypes |
| 4: Competitive | What could the partner use instead of lumif.ai? Other platforms they could white-label? Or build internally? | TAG evaluated building their own tool. That's always the alternative. |
| 5: Pricing | Wholesale pricing (our price to partner), partner margin analysis, end-client pricing benchmarks. Must model both sides. | Partner must make margin. If our wholesale price doesn't leave room, they won't partner. |
| 7: Risk | Partner dependency risk (what if they pivot?), exclusivity implications, brand control, support SLA expectations | Channel deals have unique risks: divided loyalty, brand confusion, support overhead |

### Recommendation Template

Recommendations for Channel/White-Label accounts should address:
1. **White-label scope:** What's branded, what's not, customization boundaries
2. **Commercial structure:** Wholesale pricing, minimum commitments, margin analysis
3. **Mutual value exchange:** What does each party bring? (lumif.ai = tech, partner = distribution + domain)
4. **Exclusivity terms:** Vertical exclusivity? Geographic? Time-limited?
5. **Support model:** Who handles L1/L2/L3? Training requirements?
6. **Co-GTM plan:** Joint marketing, case studies, client introductions

### Success Metrics
- Partnership agreement terms defined
- Pricing model agreed (wholesale + partner margin)
- First joint client identified
- Co-branded materials created

---

## Type 3: Strategic Partner

**Definition:** A larger entity where the relationship involves co-development, market access, joint GTM, or investment -- not just buyer/seller.

**Examples:** (Future) Large insurer co-developing features, technology partner embedding lumif.ai in their stack, investor-operator hybrid.

**Qualification signals:**
- They proposed co-development or technology partnership
- They have market access we cannot build ourselves
- The relationship involves equity, investment, or deep integration
- Mutual strategic value beyond a transaction

### Phase Emphasis Overrides

| Phase | Emphasis | Why |
|-------|----------|-----|
| 2: Company | Strategic position in the market. Where are they going? What's their 3-year strategy? | Strategic partnerships must align on direction, not just current state |
| 3: Stakeholders | Map to executive/C-suite level. Strategic deals are top-down. | VP-level champions can't approve strategic partnerships |
| 4: Competitive | Less about "us vs them" -- more about "together vs alternatives." What's the joint competitive position? | Strategic value = what we can do together that neither can do alone |
| 5: Pricing | Revenue sharing, co-investment, licensing models. Not per-unit pricing. | Strategic deals have fundamentally different economics |
| 7: Risk | Strategic alignment drift, IP ownership, exclusivity lock-in, dependency asymmetry | Strategic risks are existential, not operational |

### Recommendation Template

Recommendations for Strategic Partner accounts should address:
1. **Partnership framework:** Structure (JV, licensing, co-development, investment)
2. **Joint value proposition:** What can we offer the market together?
3. **IP and ownership:** Who owns what? Especially for co-developed features
4. **Exclusivity and commitment:** What does each party commit to?
5. **Governance:** Decision-making process, conflict resolution, exit terms
6. **Milestones:** Phase 1 proof of concept -> Phase 2 deeper integration -> Phase 3 market launch

### Success Metrics
- LOI or term sheet signed
- Joint roadmap defined
- First co-developed feature or joint client
- Strategic alignment validated through working together

---

## Type Detection Heuristics

When the user doesn't specify account type, detect from context:

| Signal | Likely Type |
|--------|------------|
| "They want to use our product" | Customer/Pilot |
| "They want to offer it to their clients" | Channel/White-Label |
| "They want to partner / co-develop / invest" | Strategic |
| Context store has `relationship: prospect` | Customer/Pilot (default) |
| Context store has `relationship: partner` | Channel/White-Label |
| Multiple client references in transcripts | Channel/White-Label |
| C-suite only meetings, no operational detail | Strategic |

If ambiguous, ask: "Is {Company} evaluating lumif.ai for their own use (Customer), to resell/white-label to their clients (Channel Partner), or for a strategic partnership (co-development, investment, joint GTM)?"
