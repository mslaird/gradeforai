#!/usr/bin/env python3
"""
Weekly Auto-Export — Dumps all scored data to CSV and JSON.
Designed to run via cron/launchd every Sunday.

Usage:
    python weekly_export.py
    python weekly_export.py --output ~/Desktop  # custom output dir

Output files:
    exports/export-YYYY-MM-DD.csv   — Full score database as CSV
    exports/export-YYYY-MM-DD.json  — Full score database as JSON
    exports/summary-YYYY-MM-DD.txt  — Quick stats summary
"""

import argparse
import csv
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.expanduser("~/agent-readiness/data/scores.db")
DEFAULT_EXPORT_DIR = os.path.expanduser("~/agent-readiness/exports")


def export_all(output_dir=None):
    export_dir = output_dir or DEFAULT_EXPORT_DIR
    os.makedirs(export_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")

    if not os.path.isfile(DB_PATH):
        print(f"No database found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Export scores with business info
    query = """
        SELECT
            b.url, b.domain, b.business_name, b.city, b.state, b.vertical,
            s.timestamp, s.composite_score, s.grade,
            s.discoverability_score, s.service_clarity_score, s.bookability_score,
            s.contactability_score, s.quotability_score, s.verifiability_score, s.payability_score,
            b.first_scored, b.last_scored
        FROM scores s
        JOIN businesses b ON s.business_id = b.id
        ORDER BY s.timestamp DESC
    """

    rows = conn.execute(query).fetchall()
    conn.close()

    if not rows:
        print("No scores in database yet.")
        return

    # CSV export
    csv_path = os.path.join(export_dir, f"export-{date_str}.csv")
    fieldnames = rows[0].keys()
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))

    # JSON export
    json_path = os.path.join(export_dir, f"export-{date_str}.json")
    data = [dict(row) for row in rows]
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

    # Summary
    scores = [row["composite_score"] for row in rows if row["composite_score"]]
    avg_score = sum(scores) / len(scores) if scores else 0
    unique_domains = len(set(row["domain"] for row in rows))

    # Grade distribution
    grades = {}
    for row in rows:
        g = row["grade"] or "?"
        grades[g] = grades.get(g, 0) + 1

    # Vertical breakdown
    verticals = {}
    for row in rows:
        v = row["vertical"] or "unknown"
        if v not in verticals:
            verticals[v] = {"count": 0, "total_score": 0}
        verticals[v]["count"] += 1
        verticals[v]["total_score"] += row["composite_score"] or 0

    summary_path = os.path.join(export_dir, f"summary-{date_str}.txt")
    with open(summary_path, "w") as f:
        f.write(f"Agent Readiness Export Summary - {date_str}\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Total score records:  {len(rows)}\n")
        f.write(f"Unique businesses:    {unique_domains}\n")
        f.write(f"Average score:        {avg_score:.1f}/100\n\n")

        f.write("Grade Distribution:\n")
        for g in ["A", "B", "C", "D", "F"]:
            count = grades.get(g, 0)
            pct = (count / len(rows) * 100) if rows else 0
            bar = "#" * int(pct / 2)
            f.write(f"  {g}: {count:4d} ({pct:5.1f}%) {bar}\n")

        f.write(f"\nVertical Breakdown:\n")
        for v, info in sorted(verticals.items(), key=lambda x: x[1]["count"], reverse=True):
            avg = info["total_score"] / info["count"] if info["count"] else 0
            f.write(f"  {v:20s}  {info['count']:4d} scored  avg {avg:.0f}/100\n")

    print(f"Export complete:")
    print(f"  CSV:     {csv_path}")
    print(f"  JSON:    {json_path}")
    print(f"  Summary: {summary_path}")
    print(f"  Records: {len(rows)} scores, {unique_domains} unique businesses")

    # Clean exports older than 90 days
    import glob
    for pattern in ["export-*.csv", "export-*.json", "summary-*.txt"]:
        for filepath in glob.glob(os.path.join(export_dir, pattern)):
            age_days = (datetime.now().timestamp() - os.path.getmtime(filepath)) / 86400
            if age_days > 90:
                os.remove(filepath)
                print(f"  Cleaned old export: {os.path.basename(filepath)}")


def main():
    parser = argparse.ArgumentParser(description="Export all scored data")
    parser.add_argument("--output", help="Output directory")
    args = parser.parse_args()
    export_all(output_dir=args.output)


if __name__ == "__main__":
    main()
