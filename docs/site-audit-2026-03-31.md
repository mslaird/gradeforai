# GradeForAI Full Site Audit -- March 31, 2026

**Audit type:** 30 pages, 5+ iteration passes each, 6 parallel audit teams
**Purpose:** Launch readiness for agency + SMB outreach
**Status:** FIXING IN PROGRESS

---

## TIER 1: CRITICAL -- Fix before sending a single cold email

### C1. Free scan claims "6 dimensions" but only 5 are free
- **Status:** [x] FIXED -- Changed to "5 dimensions" across index.html + services.html (page copy, FAQ, structured data). Removed Competitive Position from free scan claims.

### C2. Score preview mockup shows Competitive Position with visible score (12)
- **Status:** [x] FIXED -- Competitive Position row now locked: dashed border, 50% opacity, "--" score, lock icon, "Available in Full Report" text.

### C3. DFY Implementation ($2,500) positions as implementation agency
- **Status:** [x] FIXED -- Reframed as "Implementation Partner Network" on both index.html and services.html. "We implement" changed to partner referral framing. FAQ updated. Structured data updated. $2,500 pricing removed.

### C4. Certification tier names mismatch
- **Status:** [x] FIXED -- Updated to Verified (50+) / Certified (70+) / Elite (85+). Structured data updated.
- **Files:**
  - `website/src/pages/certification.html` lines 510, 526, 545: Verified (50+) / Ready (70+) / Certified (85+)
  - `website/src/pages/certification.html` lines 464, 471, 478 (structured data): same
- **Problem:** Other docs reference Verified / Certified / Elite. Page uses Verified / Ready / Certified.
- **Fix:** Decide canonical tier names. Update page + structured data + any other references.

### C5. "Named team" comparison row on certification
- **Status:** [x] FIXED -- Row removed from comparison table.

### C6. "Launching April 2026" on certification page
- **Status:** [x] FIXED -- Changed to "Coming Soon."

### C7. About page says "Over 40 verticals" AND "130+ verticals" on same page
- **Status:** [x] FIXED -- Changed to "Over 130 verticals covered."

### C8. AAO page says businesses are "functionally invisible"
- **Status:** [x] FIXED -- Changed to "functionally inoperable for AI agents."

### C9. Blog posts define AAO using "discover" (AEO language)
- **Status:** [x] FIXED -- Changed "discover" to "navigate" in both cuban + plumber blog posts.

### C10. Transaction Readiness average contradicts across blog posts
- **Status:** [x] FIXED -- NVIDIA blog changed from ~3 to ~5 to match Cuban post.

### C11. Benchmark grade distribution sums to 78%, not 100%
- **Status:** [x] FIXED -- Recalculated as % of fully graded businesses (F=86%, D=10%, C=3%, B=1%). Added exclusion note.

### C12. Benchmark case studies leak proprietary weighting methodology
- **Status:** [x] FIXED -- Per-dimension numeric scores removed from all 5 case studies. Replaced with qualitative Strongest/Weakest descriptors.

### C13. All city averages (21-26) fall below national average (27)
- **Status:** [x] FIXED -- Explanatory note added about major metros vs national average including smaller markets.
- **Files:**
  - `website/src/pages/reports/benchmark.html`: national average 27
  - All 6 city pages: Dallas 24, Houston 22, Phoenix 21, Chicago 26, Denver 23, Miami 25
- **Fix:** Add explanatory note on benchmark page (smaller markets/non-metro skew data), or adjust national average to align, or add more cities that score above average.

---

## TIER 2: HIGH -- Fix this week

### H1. FAQ "Can you fix my score?" positions as implementation agency
- **Status:** [x] FIXED (with C3) -- Reframed as partner referral.

### H2. Marquee ticker shows fabricated-looking static scores
- **Status:** [x] FIXED -- Added "Sample scores from 300,000+ businesses" label above marquee.

### H3. "Updated daily" trust bar claim -- scoring may be paused
- **Status:** [x] FIXED -- Changed to "Updated regularly."

### H4. Research logos (NVIDIA, OpenAI, Fortune) imply endorsement
- **Status:** [x] FIXED -- Heading changed to "Building on standards and research from."

### H5. "67% Score F" stat not linked to benchmark methodology
- **Status:** [x] FIXED -- Both instances now link to /reports/benchmark.

### H6. Results page hardcoded fallback "330,000+" vs public "300,000+"
- **Status:** [x] FIXED -- Changed to "300,000+".

### H7. "How AI sees your business" sounds like AEO
- **Status:** [x] FIXED -- Changed to "How AI agents interact with your business."

### H8. "White-label reports" offered but doesn't exist
- **Status:** [x] FIXED -- Now says "in development for qualified partners" with "early access" CTA.

### H9. "Invisible to these agents" conflates visibility/operability
- **Status:** [x] FIXED -- Changed to "unreachable by these agents."

### H10. Unsubstantiated competitor claims in certification comparison table
- **Status:** [x] FIXED (with C4/C5) -- Specific numbers replaced with general language.

### H11. "Most Popular" badge on certification tier -- zero sold
- **Status:** [x] FIXED (with C4) -- Changed to "Recommended."

### H12. Response time contradiction: "few hours" vs "one business day"
- **Status:** [x] FIXED -- services.html changed to "within one business day."

### H13. About page meta uses "Hundreds of thousands" instead of "300,000+"
- **Status:** [x] FIXED (previously with C7) -- All instances changed to "300,000+".

### H14. Exposed Stripe payment link in AAO article body
- **Status:** [x] FIXED -- Changed raw Stripe URL to /services link.

### H15. WordPress 7.0 claim unverifiable
- **Status:** [x] FIXED -- Softened to "WordPress has signaled plans to add native AI client support."

### H16. Claude Code / OpenClaw attributions to Jensen Huang may be fabricated
- **Status:** [x] FIXED -- Removed false attributions. Rewritten as factual statements.

### H17. Plumber blog hardcodes "9/100" average
- **Status:** [x] FIXED -- Added "as of March 2026" qualifier to body copy.

### H18. Blog date mismatch: index says March 18, articles say March 17
- **Status:** [x] FIXED -- Both changed to March 17.

### H19. llms.txt blog uses different CSS class (.article-header vs .article-hero)
- **Status:** [x] FIXED -- Renamed to .article-hero, changed <header> to <div>.

### H20. No agency messaging on any industry page
- **Status:** [x] FIXED -- Agency callout added to all 6 industry pages.

### H21. ~180+ hardcoded dimension scores across industry pages
- **Status:** [x] FIXED -- All 215 template variables now injected from `website/industry_data.json` via `build.py`
- **Files created:**
  - `website/industry_data.json` -- Single source of truth for all scores (national, industry, city, benchmark)
  - `update_industry_scores.py` -- Queries VPS scores.db, regenerates JSON (run after batch rescore)
- **Files modified:**
  - `website/build.py` -- `load_industry_data()` flattens JSON into 215 template variables
  - All 6 industry pages: meta, OG, FAQ schema, hero stat bar, benchmark tables, dim cards, body copy
  - All 6 city pages: meta, OG, hero, stats band, insight cards, vertical tables
  - `reports/benchmark.html`: headline stats, grade distribution, vertical table, dimension chart, key findings
- **Remaining (deferred):**
  - Weekly cron job to auto-run `update_industry_scores.py` (set up after batch rescore completes)
  - After rescore: run `python3 update_industry_scores.py` on VPS, copy JSON locally, rebuild + deploy

### H22. Benchmark dimension averages + case studies enable weight reverse-engineering
- **Status:** [x] FIXED (with C12) -- Per-dimension scores removed from case studies.

### H23. OG images use relative paths on multiple pages
- **Status:** [x] FIXED -- Changed to absolute URLs on demo + 6 city pages + 6 industry pages.

### H24. Benchmark vertical table sums to ~243K with no "showing X of Y" note
- **Status:** [x] FIXED -- Footnote added: "Showing 10 of 130+ verticals."

---

## TIER 3: MEDIUM -- Fix before scaling outreach

### M1. "Limited-time launch price" badge with no deadline
- **Status:** [x] FIXED -- Changed to "Launch pricing through June 2026" on both index + services pages.

### M2. Pervasive inline styles break design system
- **Status:** [ ] DEFERRED -- Systemic refactor. Does not affect visitor experience, only source code maintenance.

### M3. CSS duplication across industry pages (~50 lines x 6) and city pages (~240 lines x 6)
- **Status:** [x] FIXED -- Extracted shared CSS to global style.css. Industry page styles (~50 lines x 6) and city page styles (~240 lines x 6) consolidated. City CTA renamed to .city-cta to avoid global class conflict.

### M4. Missing agency messaging on about, contact, glossary, city pages
- **Status:** [x] FIXED -- Agency callouts added to all 6 city pages. About/contact/glossary were fixed in prior session.

### M5. Dimension name inconsistency: "and" vs "&"
- **Status:** [x] FIXED -- dental.html and legal.html changed to "Data Accuracy & Currency."

### M6. agent.json vs agent-card.json inconsistency
- **Status:** [x] FIXED -- Standardized to "agent-card.json" in blogs, glossary, aao page.

### M7. Glossary missing key terms (UCP, ACP, NAP, A2A)
- **Status:** [x] FIXED -- All 4 terms added with structured data. N and U sections added to alpha-nav.

### M8. Blog posts have no OG images
- **Status:** [ ] DEFERRED -- Requires image assets to be created (Canva or similar).

### M9. No blog content targets agencies
- **Status:** [ ] DEFERRED -- Content strategy gap. Requires writing new blog post(s).

### M10. "Hundreds of Thousands" as JS fallback text
- **Status:** [x] FIXED -- Changed to "300,000+" on about.html and index.html.

### M11. City pages claim "thousands" scored -- may not be accurate
- **Status:** [x] FIXED -- Changed to "hundreds" on all 6 city pages (meta + hero copy).

### M12. Glossary says "hundreds of thousands" instead of "300,000+"
- **Status:** [x] FIXED -- Changed to "300,000+".

### M13. llms.txt blog font size 17px vs 16.5px on other posts
- **Status:** [x] FIXED -- Changed to 16.5px.

### M14. llms.txt blog CTA box uses gradient (other posts use bordered box)
- **Status:** [x] FIXED -- Changed to bg-soft + accent border to match other posts.

### M15. Chicago city page has different paragraph spacing
- **Status:** [x] FIXED -- margin-bottom changed to 40px, removed compensating margin-top.

### M16. About page bio "built and sold e-commerce brands" may overstate if no exit
- **Status:** [x] FIXED -- Changed "built and sold" to "built." Jolly Wagz was paused, not sold.

### M17. About page bio "designed AI-powered lead generation systems" unsubstantiated
- **Status:** [x] FIXED -- Removed "AI-powered" qualifier. LeadSnare not trademarked, no value in naming it publicly.

### M18. Benchmark page has no visible "last updated" date
- **Status:** [x] FIXED -- Added "Data as of March 2026" to report-meta section.

### M19. Contact form select dropdown uses heavy inline styles
- **Status:** [x] FIXED -- Styles moved to .contact-form select CSS rule.

### M20. "In 60 seconds" scan time claim -- verify accuracy
- **Status:** [x] SKIPPED -- Approximately accurate. No change needed.

### M21. Certification page missing breadcrumb
- **Status:** [x] FIXED -- Breadcrumb + BreadcrumbList structured data added.

### M22. Certification email signup has no privacy note
- **Status:** [x] FIXED -- Privacy note added below form.

### M23. Certification FAQ uses onclick instead of addEventListener
- **Status:** [x] FIXED -- Replaced with addEventListener. Added chevron SVGs.

### M24. Auto-repair hero stat label truncated ("Agentic Commerce" vs full name)
- **Status:** [x] FIXED -- Changed to "Avg Agentic Commerce Readiness."

### M25. Plumbing FAQ claims "top 10%" without data backing
- **Status:** [x] FIXED -- Changed to "well ahead of most competitors" in FAQ + schema.

### M26. "Six major service verticals" language in auto-repair and roofing
- **Status:** [x] FIXED -- Removed specific count. Now says "major service verticals."

### M27. Cookie consent banner may not exist (referenced in privacy.html)
- **Status:** [x] VERIFIED -- Banner exists in footer.html partial. No fix needed.

### M28. Terms page lacks agency/subscription terms
- **Status:** [ ] DEFERRED -- Add when subscription products launch.

---

## PROGRESS TRACKER

| Tier | Total | Fixed | Remaining |
|------|-------|-------|-----------|
| Critical (Tier 1) | 13 | 13 | 0 |
| High (Tier 2) | 24 | 24 | 0 |
| Medium (Tier 3) | 28 | 22 | 6 (4 deferred) |
| **Total** | **65** | **59** | **6** |

---

## NOTES

- Line numbers reference SOURCE files in `website/src/pages/`, not built output.
- Line numbers are approximate -- they may shift by a few lines after edits.
- After all fixes: rebuild with `python3 website/build.py`, deploy to VPS, commit + push.

## RESUME POINT (saved March 31, 2026)

**All critical and high-priority audit items are COMPLETE (37/37).**

Remaining 4 items are all Medium tier (deferred, non-blocking):
- M2 (inline styles) -- DEFERRED, maintenance only
- M3 (CSS duplication) -- DEFERRED, maintenance only
- M8 (blog OG images) -- DEFERRED, needs image assets
- M9 (agency blog content) -- DEFERRED, needs new blog post
- M28 (agency/subscription terms) -- DEFERRED, add when subscription products launch

**What was accomplished in the March 31 session:**
1. H21 COMPLETED: Built full template variable injection system (215 variables from `website/industry_data.json`)
2. Created `update_industry_scores.py` to auto-regenerate from VPS database
3. Created `auto_refresh_scores.sh` with change detection and email notification
4. Hooked auto-refresh into `rescore.py` and `parallel_scorer.py`
5. Set up `agent-score-refresh.timer` systemd timer (weekly Sunday 6 AM)
6. All files deployed to VPS, site rebuilt and live
7. DISCOVERED: v5.0 scoring engine calibration issue -- scores dramatically inflated
8. See `SCORING-ENGINE-V5.1-CALIBRATION.md` for full diagnosis and fix plan

**IMPORTANT: Do NOT let auto_refresh_scores.sh overwrite published data until v5.1 calibration is complete.** The current JSON uses correct seeded values. The safety guard prevents auto-publish of inflated v5.0 scores.
