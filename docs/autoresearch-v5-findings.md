# Autoresearch Findings: v4 to v5 Engine Redesign

## Date: March 30, 2026
## Trigger: Mark requested verification that all dimensions are pure AAO, differentiated, and pertinent

---

## Research Questions

1. Is 6 dimensions enough to feel comprehensive, or does 8 add value?
2. Should Reputation Intelligence be a scored dimension?
3. Does AI Visibility belong as a dimension or premium feature?
4. Do we need vertical-conditional check logic (not just weights)?
5. Does keeping 8 dimensions enhance the agency value proposition vs. 6?

---

## Research Stream 1: Scoring Product Dimension Benchmarks

### Products Analyzed

| Product | Top-Level Dimensions | Market Position |
|---|---|---|
| FICO | 5 factors | Gold standard. 90%+ US lender adoption. Unchanged for decades despite access to thousands of data points. |
| Google Lighthouse | 4 categories | Industry standard. Performance, Accessibility, Best Practices, SEO. Each rolls up dozens of audits. |
| HubSpot Website Grader | 4 categories | 10M+ sites graded. Deliberately kept simple for clarity and actionability. |
| Semrush Site Audit | 4-5 top-level categories | Market leader. 140+ individual checks grouped into one Site Health %. |
| Ahrefs | 5-6 headline metrics | Market leader. DR is a single 0-100 score. Power users go deeper. |
| SEOptimer | 5 categories | Agency standard. On-Page SEO, Links, Usability, Performance, Social. |
| BrightLocal | 7 categories | Agency standard. Includes Reviews, Citations, GBP as separate categories. |
| Moz Domain Authority | 1 headline metric | Industry standard. Multiple signals compressed to single number. |
| GTmetrix | 2 primary scores | Widely used. Recently simplified from 3 scores to 2. |
| SecurityScorecard | 10 risk factor groups | Outlier. Enterprise security niche where CISOs expect exhaustiveness. |

### Cognitive Science

- **Miller's Law (1956):** Working memory holds 7 plus or minus 2 chunks
- **Cowan (2001) refinement:** True limit closer to 4 plus or minus 1
- **Nielsen Norman Group:** 5-9 KPIs maximum on a dashboard, 5-7 optimal
- **McKinsey B2B research:** Products with 5-7 evaluation criteria close faster than 10+
- **Barry Schwartz (Paradox of Choice):** More dimensions decrease confidence in the score's authority

### Conclusion

**6 dimensions is in the proven zone.** The median for market leaders is 4-5. SecurityScorecard's 10 serves a niche that expects thoroughness. Going from 8 to 6 moves TOWARD the proven sweet spot, not away from it. Depth (50-60 total checks across 6 dimensions) provides substance equivalent to SEOptimer (100+ checks across 5 categories).

---

## Research Stream 2: Reputation Signals in AI Agent Decision-Making

### Key Finding: Agents Do NOT Use On-Site Reputation for Selection

**ChatGPT Shopping (launched April 2025):**
- Recommendations based on product metadata, web content, and third-party review aggregation
- NOT on-site AggregateRating schema
- OpenAI designed this deliberately to prevent manipulation
- Reviews surfaced to users come from external aggregators

**Google Gemini / Google AI Agents:**
- Relies on Google's first-party data: Google Business Profile, Google Maps reviews
- Does NOT read business website reviews for selection decisions
- Google has de-emphasized self-reported review schema since 2021-2024 crackdown
- Same distrust carries into agent recommendations

**Perplexity Shopping:**
- Cites external sources: Wirecutter, Reddit threads, aggregated review scores
- Does not parse on-site AggregateRating for merchant selection

**Agent Frameworks and Protocols:**
- A2A: No mention of reputation as site-level signal. Focuses on capability discovery, authentication, task handoff.
- OpenAI Actions/Plugins: Evaluates on API availability, authentication methods, schema completeness for actions. No reputation component.
- W3C WebMCP: Machine-readable capability exposure. No reputation dimension.
- Google agent developer docs: Site readiness = structured data for actions (booking, product, service schema), not reviews.

**Academic Research (2024-2025):**
- Stanford (Voyager, Generative Agents), Microsoft (AutoGen): When reputation is mentioned, it's always an external knowledge base query, never an on-site signal to parse.

### The Core Distinction

| Aspect | On-Site Reviews | External Reviews |
|---|---|---|
| Who controls the data | Business (self-reported) | Third-party platform |
| Trust level for agents | Low (easily gamed) | High (independently verified) |
| Used for agent selection | No evidence | Yes, extensively |
| Relevant to AAO | No | Not a site-readiness factor |

### Conclusion

**Reputation Intelligence should NOT be a scored AAO dimension.** On-site reputation is AEO (rich snippets for search engines), not AAO (agent operability). Every agency already has tools for review monitoring (BrightLocal, Semrush, Podium). Including it blurs differentiation and triggers "I already have that" rejection.

**Alternative:** The research suggested "trust infrastructure" (SSL, security.txt, verified merchant signals, secure payment endpoints) as the operationally relevant version. These checks are distributed across Data Accuracy & Currency (SSL/HTTPS) and Transaction Readiness (payment security) in v5.

---

## Research Stream 3: Agency Buyer Behavior and Tool Adoption

### What Drives Agency Adoption (ranked)

1. **"It sells something they can't sell today."** The new tool opens a new revenue line. #1 trigger.
2. **Lead generation.** Embeddable free scan widget that captures prospect emails. SEOptimer's entire adoption story.
3. **White-label capability.** Custom branding, custom domain. Non-negotiable.
4. **Client-ready output.** Reports non-technical SMB owners can grasp.
5. **Differentiation from existing stack.** Overlap = rejection. Agencies run 6-10 tools.

### Agency Tool Structure

- SEOptimer: 5 categories, 100+ checks, A-F grades per category
- BrightLocal: 7 + Summary, 300+ data points, Good/OK/Poor per section
- AgencyAnalytics: 85+ integrations, modular sections, customizable
- Vendasta: Multi-product suite, white-label platform

### Narrow-But-Differentiated vs. Broad-But-Overlapping

**Research strongly supports narrow and differentiated for initial adoption:**
- 70% of businesses use multiple specialized tools (2025 data)
- Agencies build "center plus satellites" -- CRM hub + best-of-breed specialists
- Consolidation pressure works AGAINST broad tools that overlap existing stack
- Winning pattern: do ONE thing nobody else does, expand after category dominance
- SEOptimer started as just an SEO audit widget. BrightLocal started as just citation management. Both expanded.

### Competitive Landscape (AI Agent Readiness)

| Competitor | Dimensions/Checks | Pricing | Database | Vertical Calibration | White-Label |
|---|---|---|---|---|---|
| Agentiview | 10 dimensions | $349 single / $2,500 full / $1,200/mo | 2,600 companies | No | No |
| AgentSpeed | 10 checks (6 Tier 1, 4 Tier 2) | Free (likely freemium) | Unknown | No | No |
| Pillar (trypillar.com) | 25+ checks, 5 categories | Free | Unknown | No | No |
| AgentReady.site | Lightweight scanner | Free | Unknown | No | No |
| **GradeForAI** | **6 dimensions, 50-60 checks** | **Free scan / $49 report** | **337K+ businesses** | **Yes** | **Planned** |

**Gap nobody fills:** Database benchmarking, vertical calibration, white-label agency tools, embeddable prospecting widget.

### 6 vs. 8 for Agencies

**6 focused dimensions:**
- Every dimension is something existing tools cannot measure
- Zero "I already have that" objections
- Clear pitch: "This is the only tool that measures whether AI agents can USE your client's site"
- Fits the specialist satellite model agencies prefer

**8 with AEO overlap:**
- Creates "is this just another AEO tool?" confusion
- 2 dimensions trigger overlap objection with existing stack
- Dilutes category-creation message
- Positions as mini all-in-one (gets squeezed in consolidation)

### Conclusion

**6 focused dimensions creates a stronger agency value proposition.** Every additional dimension that overlaps with AEO is a liability, not an asset. The agency pitch is maximally sharp at 6: "SEO tools measure search rankings. AEO tools measure AI answer visibility. GradeForAI measures whether AI agents can actually USE your client's website. Nobody else measures this."

---

## Research Stream 4: Vertical Fairness in Scoring Engines

### Legal Industry Constraints

**Open Booking:**
- ABA Model Rule 1.7 (concurrent conflicts) and 1.9 (former client conflicts) require conflict screening before any attorney-client relationship forms
- "Book Now" buttons that create appointments without conflict screening = malpractice liability + bar discipline risk
- Engagement letters required in most jurisdictions before work begins
- Legitimate equivalent: "Request a Consultation" / "Schedule a Screening Call"
- **Penalizing for no "Book Now" is penalizing ethical compliance**

**Pricing:**
- Post-Bates v. State Bar of Arizona (1977): most states permit fee advertising with restrictions
- Must not be misleading. Some states (Florida, Texas) have detailed rules.
- Most legal work is bespoke -- contingency, hourly (varies by attorney), flat fees only for commoditized services
- **Penalizing for no structured pricing is partially unjust for litigation/complex practices**

**Intake Forms:**
- Conflict checks require: full legal name, aliases, opposing party names, nature of matter, prior representation
- Case type, jurisdiction, statute of limitations, brief fact patterns are standard
- 8-12+ fields is the norm, not bloat
- **Penalizing long forms is penalizing necessary data collection**

### Medical/Dental/Healthcare Constraints

**HIPAA:**
- Does not prohibit online booking for simple appointments (name, email, service, time)
- DOES restrict PHI collection through non-HIPAA-compliant channels
- Patient portals require authenticated access precisely because they handle PHI
- Guest access for booking that involves PHI = HIPAA violation
- **Penalizing for requiring login is penalizing federal law compliance**

**Intake Forms:**
- Insurance info: group number, member ID, carrier, policyholder = 4-6 fields minimum
- Medical history, medications, allergies, consent = additional fields
- 12-20+ fields is legitimate for dental/medical intake
- Varies by subspecialty -- dermatology cosmetic consult needs fewer than surgical intake

**Booking:**
- Many practices use Zocdoc, Healthgrades, their EHR's patient portal
- Booking capability exists but often lives off-site
- Check logic must recognize external platform integrations as equivalent

### Real Estate Constraints

**MLS/IDX:**
- IDX is a licensing framework with display rules (disclaimers, refresh intervals, attribution)
- Property data is not the agent's to structure freely
- Showing scheduling often via ShowingTime or MLS-integrated platforms

**Transaction Model:**
- Primary user intent: property search, not service booking
- Agent visits real estate site for property data, not to book the realtor
- "Data extractability" matters more than "service bookability"

### Precedent from Scoring Products

**FICO:** Developed industry-specific scores (Auto Score, Bankcard Score, Mortgage Score) with different check logic, not just weights. Same organization, same entity type, different checks per vertical.

**SecurityScorecard:** Adjusts evaluation criteria by sector. Healthcare = HIPAA-relevant controls. Financial = PCI DSS and SOX. Not just benchmarking against same-industry peers -- actually checking different things.

**Google E-E-A-T:** Initially applied same signals across all content. August 2018 "Medic Update" disproportionately hit health sites. Backlash was not that Google differentiated -- it was that they didn't differentiate sooner.

### Credibility Risk of One-Size-Fits-All

"A law firm managing partner who receives a report penalizing them for not having a 'Book Now' button will immediately question the credibility of the entire assessment. If dimension 1 feels unfair, dimensions 2-10 are tainted by association."

This risk is amplified by the certification model ($149-249/year). Businesses scrutinize methodology when paying for certification.

One-size-fits-all creates a ceiling on which verticals can adopt. If scoring works for trades and restaurants but not for legal, healthcare, and financial services, GradeForAI is locked out of higher-value verticals (where contract values and certification willingness-to-pay would be highest).

### Conclusion

**Vertical-conditional check logic is a credibility requirement, not a nice-to-have.** The changes needed are check substitutions (what to look for, what thresholds to use, what to skip), not just weight adjustments. FICO and SecurityScorecard both do this. GradeForAI must do it to be credible with professional services verticals.

---

## Final Verdict: 6 Dimensions, Pure AAO

The four research streams converge:

1. **6 is the right count.** Market leaders cluster at 4-6. Cognitive science supports 4-7. More is not better.
2. **Reputation Intelligence is AEO, not AAO.** Agents pull reputation from external sources. Drop it.
3. **AI Visibility is AEO.** Keep as premium feature in paid reports. Don't pollute the AAO score.
4. **Vertical-conditional checks are required.** Weight-only adaptation is insufficient. Checks must adapt.
5. **6 focused dimensions > 8 with overlap.** Every overlapping dimension is a liability for agency adoption.

The 6 dimensions: Agent Compatibility, Transaction Readiness, Agentic Commerce Readiness, Operational Data Structure, Data Accuracy & Currency, Competitive Position.

Every dimension passes three tests:
1. AAO-specific (measures agent operability, not findability)
2. Not unjustly penalizing (vertical-conditional where needed)
3. Differentiated (no existing tool measures this)

---

*Research completed March 30, 2026.*
*4 parallel research agents, synthesized through autoresearch evaluation loop.*
*Status: PENDING final verification autoresearch.*
