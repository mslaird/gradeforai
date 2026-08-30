#!/usr/bin/env python3
"""
Agent Readiness Score — CLI
Main entry point for scoring local service businesses on AI agent readiness.
"""

import argparse
import os
import sys
import time

# Ensure sibling modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from score_engine import score_business
from storage import (
    init_db,
    save_score,
    get_vertical_benchmarks,
    get_business_history,
    export_csv,
    get_score_count,
    get_all_scores,
)
from report import generate_report, save_report, generate_summary_line


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_table(headers, rows):
    """Print a simple formatted ASCII table."""
    if not rows:
        print("  (no data)")
        return
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in col_widths]))
    for row in rows:
        print(fmt.format(*[str(c) for c in row]))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_score(args):
    """Score a single business."""
    print(f"Scoring {args.url} ...")
    result = score_business(args.url)

    # Attach optional metadata
    result["vertical"] = args.vertical
    result["city"] = args.city
    result["state"] = args.state

    save_score(result, vertical=args.vertical, city=args.city, state=args.state)

    report_text = generate_report(result)
    report_path = save_report(report_text, result.get("domain", "unknown"))

    print()
    print(generate_summary_line(result))
    print(f"Full report saved to: {report_path}")


def cmd_bulk(args):
    """Score multiple businesses from a file."""
    if not os.path.isfile(args.file):
        print(f"Error: file not found — {args.file}", file=sys.stderr)
        sys.exit(1)

    with open(args.file, "r") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not urls:
        print("No URLs found in file.")
        return

    total = len(urls)
    results = []

    for idx, url in enumerate(urls, 1):
        print(f"[{idx}/{total}] Scoring {url} ...")
        try:
            result = score_business(url)
            result["vertical"] = args.vertical
            result["city"] = args.city
            result["state"] = args.state
            save_score(result, vertical=args.vertical, city=args.city, state=args.state)
            results.append(result)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append({"url": url, "overall_score": "ERR", "error": str(exc)})

        # Be polite between requests
        if idx < total:
            time.sleep(2)

    # Summary table
    print()
    print(f"Bulk scoring complete — {len(results)}/{total} processed")
    print()
    headers = ["Domain", "Overall", "Findability", "Bookability", "Contactability"]
    rows = []
    for r in results:
        if r.get("overall_score") == "ERR":
            rows.append([r.get("url", "?"), "ERR", "-", "-", "-"])
        else:
            rows.append([
                r.get("domain", r.get("url", "?")),
                r.get("overall_score", "-"),
                r.get("scores", {}).get("findability", "-"),
                r.get("scores", {}).get("bookability", "-"),
                r.get("scores", {}).get("contactability", "-"),
            ])
    _print_table(headers, rows)


def cmd_benchmarks(args):
    """Show benchmarks for a vertical."""
    data = get_vertical_benchmarks(args.vertical, city=args.city)
    if not data:
        print(f"No data for vertical '{args.vertical}'" +
              (f" in {args.city}" if args.city else "") + ".")
        return

    print(f"Benchmarks: {args.vertical}" +
          (f" — {args.city}" if args.city else ""))
    print(f"Sample size: {data.get('count', 0)}")
    print()

    headers = ["Dimension", "Avg Score", "Min", "Max"]
    rows = []
    for dim, vals in data.get("dimensions", {}).items():
        rows.append([
            dim.title(),
            f"{vals.get('avg', 0):.1f}",
            vals.get("min", "-"),
            vals.get("max", "-"),
        ])
    # Overall
    rows.append([
        "OVERALL",
        f"{data.get('avg_overall', 0):.1f}",
        data.get("min_overall", "-"),
        data.get("max_overall", "-"),
    ])
    _print_table(headers, rows)


def cmd_history(args):
    """Show score history for a domain."""
    records = get_business_history(args.domain)
    if not records:
        print(f"No history for {args.domain}.")
        return

    print(f"Score history: {args.domain}")
    print()
    headers = ["Date", "Overall", "Findability", "Service Clarity", "Availability",
               "Bookability", "Contactability", "Quotability", "Verifiability"]
    rows = []
    for rec in records:
        scores = rec.get("scores", {})
        rows.append([
            rec.get("scored_at", "-"),
            rec.get("overall_score", "-"),
            scores.get("findability", "-"),
            scores.get("service_clarity", "-"),
            scores.get("availability", "-"),
            scores.get("bookability", "-"),
            scores.get("contactability", "-"),
            scores.get("quotability", "-"),
            scores.get("verifiability", "-"),
        ])
    _print_table(headers, rows)


def cmd_export(args):
    """Export all scores to CSV."""
    count = export_csv(args.output)
    print(f"Exported {count} records to {args.output}")


def cmd_stats(args):
    """Show aggregate stats."""
    total = get_score_count()
    if total == 0:
        print("No businesses scored yet.")
        return

    all_scores = get_all_scores()

    print(f"Total businesses scored: {total}")
    print()

    # Average overall score
    overall_vals = [s.get("overall_score", 0) for s in all_scores if isinstance(s.get("overall_score"), (int, float))]
    if overall_vals:
        print(f"Average overall score: {sum(overall_vals) / len(overall_vals):.1f} / 100")
    print()

    # Breakdown by vertical
    verticals = {}
    for s in all_scores:
        v = s.get("vertical", "unknown") or "unknown"
        verticals.setdefault(v, []).append(s.get("overall_score", 0))

    if verticals:
        print("By vertical:")
        headers = ["Vertical", "Count", "Avg Score"]
        rows = []
        for v, scores in sorted(verticals.items()):
            numeric = [x for x in scores if isinstance(x, (int, float))]
            avg = sum(numeric) / len(numeric) if numeric else 0
            rows.append([v, len(scores), f"{avg:.1f}"])
        _print_table(headers, rows)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="agent-readiness",
        description="Agent Readiness Score — audit how ready a business is for AI agents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # score
    p_score = sub.add_parser("score", help="Score a single business")
    p_score.add_argument("url", help="Business website URL")
    p_score.add_argument("--vertical", default=None, help="Business vertical (e.g. plumber, hvac)")
    p_score.add_argument("--city", default=None, help="City")
    p_score.add_argument("--state", default=None, help="State abbreviation")

    # bulk
    p_bulk = sub.add_parser("bulk", help="Score businesses from a file (one URL per line)")
    p_bulk.add_argument("file", help="Path to text file with URLs")
    p_bulk.add_argument("--vertical", default=None, help="Business vertical")
    p_bulk.add_argument("--city", default=None, help="City")
    p_bulk.add_argument("--state", default=None, help="State abbreviation")

    # benchmarks
    p_bench = sub.add_parser("benchmarks", help="View benchmarks for a vertical")
    p_bench.add_argument("--vertical", required=True, help="Business vertical")
    p_bench.add_argument("--city", default=None, help="Filter by city")

    # history
    p_hist = sub.add_parser("history", help="View score history for a domain")
    p_hist.add_argument("domain", help="Domain name (e.g. example-plumbing.com)")

    # export
    p_export = sub.add_parser("export", help="Export all scores to CSV")
    p_export.add_argument("output", help="Output CSV file path")

    # stats
    sub.add_parser("stats", help="Show aggregate scoring stats")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    init_db()
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "score": cmd_score,
        "bulk": cmd_bulk,
        "benchmarks": cmd_benchmarks,
        "history": cmd_history,
        "export": cmd_export,
        "stats": cmd_stats,
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
