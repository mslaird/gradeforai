# GradeForAI: AI Agent Optimization Scoring Engine

A Python platform that measures whether **AI agents can navigate, extract data from, and complete transactions on** a business website. Built solo. Scored **505,140 businesses** across **130+ industries and 390+ cities**.

> **What is and is not in this repository.** The scoring engine (`score_engine.py`, 5,661 lines), its dimension weights, per-vertical calibration logic, and the scored dataset are **private** — they are the proprietary core. **Everything around the engine is here**: persistence and schema, the concurrent scorer, the harvesting pipeline, the self-migrating deploy orchestrator, the operator CLI, report generation, the systemd units it ran under, the backup runbook, a production incident postmortem, the adversarial red-team analysis, and the agent-readable surface of the product's own site. Roughly **10,800 lines** across 36 files, published.

**On the shape of this repository.** These files are an extraction from the private working
repository, which holds **216 commits across 49 days** (2026-03-15 to 2026-05-04). What you see here
arrived in a single commit because it was copied out, not developed here. The engine and dataset
stayed behind.

---

## The thesis

AI assistants are becoming the buyer. When someone asks an agent to "find and book a dentist near me," the agent can only act on a business whose site it can read and transact with. Most businesses fail at least one of those steps and never learn why.

I built the engine that scores it, under the framing **AI Agent Optimization (AAO)**. AAO is distinct from SEO (search rankings) and AEO (answer visibility): it measures whether an agent can actually *operate* on a site.

**The finding across half a million businesses: 89% were below agent-ready.**

## Scoring dimensions

The composite 0-100 score spans six dimensions, each calibrated per industry so a law firm and a plumbing company are judged against the appropriate standard:

| Dimension | What it measures |
|---|---|
| **Agent Compatibility** | Can an agent navigate the site? Semantic HTML, form accessibility, anti-bot friction |
| **Transaction Readiness** | Can an agent complete the core transaction, adapted per vertical (booking, consultation, reservation) |
| **Agentic Commerce Readiness** | Connection to emerging agent protocols and platforms |
| **Operational Data Structure** | Is operational data machine-readable? Service schema, hours, pricing, location |
| **Data Accuracy & Currency** | Will extracted data lead to a successful action? NAP consistency, identity consistency |
| **Competitive Position** | Percentile rank against the scored database, with per-dimension breakdown |

*Weights, signal checks, and calibration thresholds are intentionally not published.*

**A caveat on the number six.** The composite above is the v5 model. The v6 reframe shipped a
four-dimension **AI Agent Preference Score** (Agent Accessibility, Transaction Completeness, Data
Reliability, Competitive Position), and both formulas were computed and stored in production — which
is the divergence described under *What I would do differently*. The site and the agent-readable
surface say four because that is what shipped last.

## System architecture

```
Discovery  →  Harvest  →  Score  →  Store  →  Report
   │            │           │         │         │
 Serper     serper_      score_    storage    pdf_report
 search     harvest      engine    (SQLite)   generator
            auto_        parallel_  trend
            harvest      scorer     history
```

Roughly **18,000 lines of Python** across 17 modules. Here is what is in this repository and what is not:

| Module | Lines | Role | |
|---|---:|---|---|
| `score_engine.py` | 5,661 | Scoring logic, dimension weights, per-vertical calibration | **private** |
| [`platform/pdf_report_v2.py`](platform/pdf_report_v2.py) | 2,038 | Client PDF report generation (WeasyPrint, CSS Paged Media) | public |
| [`platform/storage.py`](platform/storage.py) | 1,421 | SQLite schema, in-place migrations, benchmarks, trend history | public |
| [`platform/design_tokens.py`](platform/design_tokens.py) | 519 | Centralized report design system | public |
| [`platform/serper_harvest.py`](platform/serper_harvest.py) | 490 | Business discovery and harvesting | public |
| [`platform/update_industry_scores.py`](platform/update_industry_scores.py) | 384 | DB to published statistics | public |
| [`platform/parallel_scorer.py`](platform/parallel_scorer.py) | 372 | Concurrent scoring, dedup, graceful shutdown | public |
| [`platform/cli.py`](platform/cli.py) | 297 | Operator entry point | public |
| [`platform/post_deploy.py`](platform/post_deploy.py) | 288 | Version-drift detection and self-migrating rescore | public |
| [`platform/rescore.py`](platform/rescore.py) | 250 | Scheduled re-scoring service | public |
| `auto_harvest.py` | 423 | Fallback harvester | private |

| [`platform/dashboard.py`](platform/dashboard.py) | 2,324 | Admin dashboard, scan API, Stripe webhook (hand-rolled HMAC-SHA256 with a 300s replay window), PDF delivery | public |

Note on `dashboard.py`: it is a hand-rolled `http.server`, not a framework. It served a low-traffic
admin surface and the scan API, with each scan dispatched to a worker thread so requests return
immediately. At real traffic this belongs behind a WSGI server. It is published because the Stripe
signature verification and the TTL-cached aggregate queries are worth reading, and because the
honest shape of a solo build is more useful than a curated one.

Also here:

- [`ops/`](ops/) — shell automation and the seven systemd units the platform ran under
- [`tools/`](tools/) — health checks, a continuous scorer, traffic tracking, weekly export
- [`site/`](site/) — [`build.py`](site/build.py) compiles 17 source pages into 68 output pages so
  every published statistic derives from a single database query, plus
  [`site/.well-known/`](site/.well-known/) and [`site/llms.txt`](site/llms.txt): the product scored
  businesses on whether agents could read them, so its own site implemented the same standards
- [`docs/`](docs/) — see below

### Three things worth opening first

**[`platform/post_deploy.py`](platform/post_deploy.py) — the deploy migrates the corpus by itself.**
It reads `METHODOLOGY_VERSION` out of the deployed engine, compares it against
`SELECT methodology_version, COUNT(*) FROM scores GROUP BY 1`, and if they disagree it rewrites its
own systemd unit to `--max-age 0`, polls progress, triggers a site rebuild every 10,000 new scores,
then resets the unit to `--max-age 7` when the pass completes. A half-million-row migration that
runs itself.

**[`ops/auto_refresh_scores.sh`](ops/auto_refresh_scores.sh) — a regression gate on a statistic.**
The published national average is derived from the database. If a refresh moves that average by more
than 15 points, the script refuses to publish, restores the previous JSON, and emails an alert.
Written after v5.0 shipped inflated scores. Most pipelines guard code; this one guards a number.

**[`platform/serper_harvest.py`](platform/serper_harvest.py) — discovery priced per query.**
Google Maps discovery via Serper with the unit economics written into the module docstring, plus
resumable state so a killed run continues where it stopped. The related cost lesson is in
`score_engine.py`: a Places API field-mask drift silently promoted calls to a higher-priced SKU and
produced a $211 bill, fixed with a two-step call using a pinned Essentials-only mask and a
file-backed daily counter.

**[`docs/red-team-analysis.md`](docs/red-team-analysis.md) — I predicted what killed this.**
A ten-iteration adversarial stress test of the business, written April 2026. Attack Vector 1 opens:
*"A free 'AI Readiness Score' inside Google Business Profile would destroy GradeForAI's core scanning
product overnight."* It happened within months, from Cloudflare rather than Google. The document
names the threat, estimates it, and proposes the pivot. I wound the product down instead of
defending a thinning wedge.

Also in [`docs/`](docs/): the [disk-full production postmortem](docs/incident-2026-04-25-disk-full.md)
(timeline, root cause, offsite verification before any deletion, follow-ups), the
[backup and recovery runbook](docs/backup-and-recovery.md), and a
[65-item site audit](docs/site-audit-2026-03-31.md).

## Operator interface

```bash
# Score a single business
python cli.py score https://example-plumbing.com --vertical plumber --city Dallas --state TX

# Bulk score from a file
python cli.py bulk urls.txt --vertical plumber --city Dallas --state TX

# Per-vertical benchmarks
python cli.py benchmarks --vertical plumber --city Dallas

# Score history for a domain
python cli.py history example-plumbing.com

# Export and aggregate stats
python cli.py export output.csv
python cli.py stats
```

## Running it in production

The platform ran unattended on a VPS as **systemd services and timers**, with harvesting, scoring, and weekly re-scoring on schedule:

```ini
[Unit]
Description=Weekly GradeForAI Score Refresh

[Timer]
OnCalendar=Sun *-*-* 06:00:00
Persistent=true
RandomizedDelaySec=1800

[Install]
WantedBy=timers.target
```

Supporting operational work: parallel scoring to make half a million records tractable, a backup and recovery runbook with offsite snapshots, automated re-scoring to build trend history, and generated PDF reports as the client deliverable.

## How the engine was developed

The scoring engine went through **six major versions**. Each iteration was treated as a measurable calibration problem rather than an opinion: score a sample, compare against manually verified ground truth, diagnose which dimension was miscalibrated, adjust, re-verify. Calibration findings were documented per version.

I also ran an **autoresearch loop** (research, spec, calibrate, verify) to refine methodology against
real-world data instead of intuition — four parallel research agents whose findings were synthesized
and then verified in a second pass. [`docs/autoresearch-v5-findings.md`](docs/autoresearch-v5-findings.md)
is one of those outputs: the v4-to-v5 redesign, benchmarked against how FICO and SecurityScorecard
handle per-vertical scoring, and the argument for why vertical-conditional *check logic* is required
rather than weight adjustment alone.

## Stack

`Python` · `SQLite` · `Serper API` · LLM APIs (Claude, GPT) · `schema.org` and structured-data parsing · agent protocols (`llms.txt`, `agent.json`, UCP, ACP) · `systemd` · VPS deployment · shell automation

## Outcome

Scored 505,140 businesses and built a defensible methodology and dataset. I **paused GradeForAI as a standalone product** when Cloudflare began surfacing comparable readiness signals for free, rather than continuing to invest in a thinning wedge.

The work did not get abandoned, it got redeployed. The **scoring technology and the 505,140-business dataset were folded into CloudAurum**, my AI and workflow consulting practice, where they now surface operational gaps and prospect signals for clients. The AAO framework carried forward with them.

**What this project demonstrates:** taking an ambiguous thesis, building the data and AI system to test it at scale, iterating rigorously against measurable calibration, operating it in production solo, and knowing when to stop.

## Two bugs found reviewing this cold

Publishing meant re-reading code I had not looked at in months. Two things were wrong, and both are
fixed in the tree:

**The deploy orchestrator disarmed its own safety guard.** `post_deploy.py` called
[`ops/auto_refresh_scores.sh`](ops/auto_refresh_scores.sh) with `--force`, which is the flag that
disables the drift guard. The guard exists because v5.0 shipped inflated scores; it blocks a publish
when the national average moves more than 15 points. Its own alert text says *"Do NOT use --force
until the scoring engine is recalibrated"* — and the orchestrator passed it unconditionally during
methodology migrations, the exact case it was built for. Armed on the routine path, disabled on the
risky one. Removed, and the exit code is now checked.

**`init_db()` could not bootstrap a fresh database.** The index on `scores(methodology_version)` was
created in the same script as a `CREATE TABLE scores` that never declared the column — it arrived
later via `ALTER TABLE`. Against clean SQLite: `no such column: methodology_version`. It never bit
because production was migrated incrementally and never rebuilt, which is the real cost of the
migration approach criticized below: the schema was not reproducible from the source.

## What I would do differently

Reading your own code back is the point of publishing it. Four things I would change:

**Testing stopped at the edges.** [`tests/`](tests/) holds two Playwright end-to-end suites against
the live site — the scan flow (homepage, submit, results, email gate, payment link, plus console
errors, broken links, and mobile viewports) and a conversion-path check. What does not exist is a
single unit test over the scoring engine. For an engine recalibrated across six versions, every
calibration was validated by scoring a sample and reading the results by hand. That held at the
scale I ran it and would not survive a second engineer. No CI either. It is the first thing I
would fix.

**`dashboard.py` is a hand-rolled `http.server`.** One thread, an if/elif route table, serving the
scan API, the Stripe webhook, PDF delivery, and the admin surface together. Scans dispatch to a
worker so requests return fast, which hid the limitation at the traffic I had. It belongs behind a
WSGI server with the admin surface split out.

**Migrations are `ALTER TABLE` guarded by `PRAGMA table_info` diffs.** Idempotent and dependency-free,
which is why I did it, but there is no version history and no down-migration. `businesses` accumulated
roughly 35 appended columns as a result, and `scores` still carries dead columns from the v3 model.

**Two scoring formulas coexisted in production.** The v5 six-dimension composite and the v6
four-dimension preference score were both computed and both stored. That divergence produced a real
customer-visible bug: one domain showed 41/100 on the site and 20/100 in the email for the same scan,
because the email path was never updated at the v6 reframe. Shipping a second formula without
retiring the first is the mistake I would most want back.

---

*Built by [Mark Laird](https://markslaird.com) · [LinkedIn](https://www.linkedin.com/in/markslaird/)*
