# GradeForAI: AI Agent Optimization Scoring Engine

A Python platform that measures whether **AI agents can navigate, extract data from, and complete transactions on** a business website. Built solo. Scored **505,140 businesses** across **130+ industries and 390+ cities**.

> **Note on this repository.** This is a technical case study. The scoring engine, dimension weights, per-vertical calibration logic, and the scored dataset remain private, since they are the proprietary core of the product. Everything else about how the system was built and operated is documented below.

---

## The thesis

AI Agents are becoming the buyer. When someone asks an agent to "find and book a dentist near me," the agent can only act on a business whose site it can read and transact with. Most businesses fail at least one of those steps and never learn why.

I coined the category for measuring this, **AI Agent Optimization (AAO)**, and built the engine that scores it. AAO is distinct from SEO (search rankings) and AEO (answer visibility): it measures whether an agent can actually *operate* on a site.

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

## System architecture

```
Discovery  →  Harvest  →  Score  →  Store  →  Report
   │            │           │         │         │
 Serper     serper_      score_    storage    pdf_report
 search     harvest      engine    (SQLite)   generator
            auto_        parallel_  trend
            harvest      scorer     history
```

Roughly **18,000 lines of Python** across 17 modules. Module sizes give a sense of where the complexity sits:

| Module | Lines | Role |
|---|---:|---|
| `score_engine.py` | 5,661 | Scoring logic and per-vertical calibration *(private)* |
| `dashboard.py` | 2,324 | Admin dashboard and aggregate views |
| `pdf_report_v2.py` | 2,038 | Client-facing PDF report generation |
| `storage.py` | 1,421 | SQLite persistence, benchmarks, trend history, CSV export |
| `serper_harvest.py` | 490 | Business discovery and harvesting |
| `auto_harvest.py` | 423 | Scheduled harvest orchestration |
| `parallel_scorer.py` | 372 | Concurrent scoring across large batches |
| `cli.py` | 297 | Operator entry point |

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

I also ran an **autoresearch loop** (research, spec, calibrate, verify) to refine methodology against real-world data instead of intuition.

## Stack

`Python` · `SQLite` · `Serper API` · LLM APIs (Claude, GPT) · `schema.org` and structured-data parsing · agent protocols (`llms.txt`, `agent.json`, UCP, ACP) · `systemd` · VPS deployment · shell automation

## Outcome

Scored 505,140 businesses and built a defensible methodology and dataset. I **paused the venture deliberately** when platform incumbents began surfacing comparable readiness signals for free, rather than continuing to invest in a thinning wedge. The dataset and the AAO framework carried forward into later work.

**What this project demonstrates:** taking an ambiguous thesis, building the data and AI system to test it at scale, iterating rigorously against measurable calibration, operating it in production solo, and knowing when to stop.

---

*Built by [Mark Laird](https://markslaird.com) · [LinkedIn](https://www.linkedin.com/in/markslaird/)*
