#!/usr/bin/env python3
"""
Continuous Scorer
Runs perpetually, pulling unscored businesses from target lists and scoring them.
Designed to run as a background process or cron job.

Usage:
    # Run continuously (scores one business every 30 seconds by default)
    python continuous_scorer.py

    # Run with custom interval (seconds between scores)
    python continuous_scorer.py --interval 60

    # Score a specific number then stop
    python continuous_scorer.py --limit 100

    # Run in quiet mode (less output)
    python continuous_scorer.py --quiet

Recommended: Run this in a tmux or screen session, or as a launchd service.
    tmux new -s scorer
    source ~/leadsnare/scripts/venv/bin/activate
    python ~/agent-readiness/continuous_scorer.py
    # Ctrl+B, D to detach
"""

import argparse
import csv
import glob
import json
import os
import sys
import time
import signal
from datetime import datetime, timezone

from score_engine import score_business
from storage import init_db, save_score, get_score_count

TARGETS_DIR = os.path.expanduser("~/agent-readiness/data/targets")
STATE_FILE = os.path.expanduser("~/agent-readiness/data/scorer_state.json")

running = True


def handle_signal(signum, frame):
    global running
    print("\nGraceful shutdown requested. Finishing current score...")
    running = False


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def load_state():
    """Load scorer state (which files/rows have been processed)."""
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"scored_urls": [], "total_scored": 0, "started": datetime.now(timezone.utc).isoformat()}


def save_state(state):
    """Persist scorer state."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_unscored_targets():
    """
    Read all target CSVs and return URLs that haven't been scored yet.
    Returns list of dicts with url, vertical, city, state.
    """
    if not os.path.isdir(TARGETS_DIR):
        return []

    targets = []
    state = load_state()
    scored_set = set(state.get("scored_urls", []))

    csv_files = glob.glob(os.path.join(TARGETS_DIR, "*.csv"))
    for filepath in sorted(csv_files):
        try:
            with open(filepath, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get("url", "").strip()
                    if url and url not in scored_set:
                        targets.append({
                            "url": url,
                            "vertical": row.get("vertical", ""),
                            "city": row.get("city", ""),
                            "state": row.get("state", ""),
                        })
        except Exception as e:
            print(f"  [!] Error reading {filepath}: {e}")

    return targets


def mark_scored(url, state):
    """Mark a URL as scored in the state file."""
    if "scored_urls" not in state:
        state["scored_urls"] = []
    state["scored_urls"].append(url)
    state["total_scored"] = len(state["scored_urls"])
    state["last_scored"] = datetime.now(timezone.utc).isoformat()
    state["last_url"] = url
    save_state(state)


def update_target_csv(url):
    """Mark URL as scored in its target CSV."""
    csv_files = glob.glob(os.path.join(TARGETS_DIR, "*.csv"))
    for filepath in csv_files:
        rows = []
        updated = False
        try:
            with open(filepath, "r") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    if row.get("url", "").strip() == url:
                        row["scored"] = "True"
                        updated = True
                    rows.append(row)

            if updated:
                with open(filepath, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                break
        except Exception:
            pass


def run_continuous(interval=30, limit=None, quiet=False):
    """Main scoring loop."""
    global running

    init_db()
    state = load_state()

    db_count = get_score_count()
    session_count = 0

    print("=" * 60)
    print("  Agent Readiness Continuous Scorer")
    print("=" * 60)
    print(f"  Database records: {db_count}")
    print(f"  Session scored:   {state.get('total_scored', 0)}")
    print(f"  Interval:         {interval}s between scores")
    if limit:
        print(f"  Limit:            {limit} scores then stop")
    print(f"  Started:          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    while running:
        targets = get_unscored_targets()

        if not targets:
            if not quiet:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] No unscored targets. Waiting 5 minutes...")
            time.sleep(300)
            continue

        target = targets[0]
        url = target["url"]
        vertical = target["vertical"]
        city = target["city"]
        st = target["state"]

        if not quiet:
            remaining = len(targets) - 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Scoring: {url} ({vertical}, {city} {st}) | {remaining} remaining")

        try:
            result = score_business(url)
            save_score(result, vertical=vertical, city=city, state=st)
            mark_scored(url, state)
            update_target_csv(url)
            session_count += 1

            score = result.get("composite_score", 0)
            grade = result.get("grade", "?")

            if not quiet:
                domain = result.get("domain", "?")
                print(f"           Score: {score:.0f}/100 ({grade}) | Session: {session_count} | DB total: {db_count + session_count}")

        except Exception as e:
            print(f"           [!] Error: {e}")
            mark_scored(url, state)  # Skip it and move on

        if limit and session_count >= limit:
            print(f"\nLimit reached ({limit} scores). Stopping.")
            break

        if running:
            time.sleep(interval)

    print(f"\nSession complete. Scored {session_count} businesses.")
    print(f"Total in database: {db_count + session_count}")


def main():
    parser = argparse.ArgumentParser(description="Continuously score businesses from target lists")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between scores (default: 30)")
    parser.add_argument("--limit", type=int, help="Stop after scoring this many")
    parser.add_argument("--quiet", action="store_true", help="Less output")
    args = parser.parse_args()

    run_continuous(interval=args.interval, limit=args.limit, quiet=args.quiet)


if __name__ == "__main__":
    main()
