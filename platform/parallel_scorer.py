#!/usr/bin/env python3
"""
Parallel Scorer
Runs multiple scoring workers simultaneously using ThreadPoolExecutor.
Pulls unscored businesses from target lists and scores them in parallel batches.

Usage:
    # Run with 5 parallel workers (default)
    python parallel_scorer.py

    # Run with 10 workers, 15s between batches
    python parallel_scorer.py --workers 10 --interval 15

    # Score 200 then stop
    python parallel_scorer.py --limit 200

    # Quiet mode
    python parallel_scorer.py --quiet

Recommended: Run in tmux or as a launchd service.
    tmux new -s scorer
    source ~/leadsnare/scripts/venv/bin/activate
    python ~/agent-readiness/parallel_scorer.py --workers 8
    # Ctrl+B, D to detach
"""

import argparse
import csv
import glob
import json
import os
import subprocess
import sys
import time
import signal
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from queue import Queue

from urllib.parse import urlparse

from score_engine import score_business
from storage import init_db, save_score, get_score_count, write_db_stats_file

_opt_targets = "/opt/agent-readiness/data/targets"
TARGETS_DIR = _opt_targets if os.path.isdir(_opt_targets) else os.path.expanduser("~/agent-readiness/data/targets")
_opt_state = "/opt/agent-readiness/data/scorer_state.json"
STATE_FILE = _opt_state if os.path.isfile(_opt_state) else os.path.expanduser("~/agent-readiness/data/scorer_state.json")

running = True
db_lock = threading.Lock()
state_lock = threading.Lock()


def handle_signal(signum, frame):
    global running
    print("\nGraceful shutdown requested. Finishing current batch...")
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


def _extract_domain(url):
    """Extract bare domain from a URL, stripping www. prefix."""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc.lower().strip()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _load_existing_domains():
    """Load all domains already in the businesses table for dedup."""
    import sqlite3
    db_path = os.path.join(
        "/opt/agent-readiness" if os.path.isdir("/opt/agent-readiness/data") else os.path.expanduser("~/agent-readiness"),
        "data", "scores.db"
    )
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT domain FROM businesses").fetchall()
        conn.close()
        return set(r[0].lower() for r in rows if r[0])
    except Exception as e:
        print(f"  [!] Warning: could not load existing domains: {e}")
        return set()


def get_unscored_targets():
    """
    Read all target CSVs and return URLs that haven't been scored yet.
    Skips URLs whose domain already exists in the database to avoid
    wasting time scraping/scoring duplicates.
    Returns list of dicts with url, vertical, city, state.
    """
    if not os.path.isdir(TARGETS_DIR):
        return []

    targets = []
    state = load_state()
    scored_set = set(state.get("scored_urls", []))
    existing_domains = _load_existing_domains()
    skipped_dupes = 0

    csv_files = glob.glob(os.path.join(TARGETS_DIR, "*.csv"))
    for filepath in sorted(csv_files):
        try:
            with open(filepath, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get("url", "").strip()
                    if not url or url in scored_set:
                        continue
                    domain = _extract_domain(url)
                    if domain in existing_domains:
                        skipped_dupes += 1
                        continue
                    target = {
                        "url": url,
                        "vertical": row.get("vertical", ""),
                        "city": row.get("city", ""),
                        "state": row.get("state", ""),
                        "business_name": row.get("business_name", ""),
                        "phone": row.get("phone", ""),
                        "address": row.get("address", ""),
                    }
                    # Parse rating/reviews as numeric if present
                    raw_rating = row.get("rating", "")
                    raw_reviews = row.get("reviews", "")
                    try:
                        target["rating"] = float(raw_rating) if raw_rating else None
                    except (ValueError, TypeError):
                        target["rating"] = None
                    try:
                        target["review_count"] = int(raw_reviews) if raw_reviews else None
                    except (ValueError, TypeError):
                        target["review_count"] = None
                    targets.append(target)
                    existing_domains.add(domain)
        except Exception as e:
            print(f"  [!] Error reading {filepath}: {e}")

    if skipped_dupes:
        print(f"  Skipped {skipped_dupes:,} URLs (domain already in DB)")

    return targets


def mark_scored(url, state):
    """Mark a URL as scored in the state file. Must be called under state_lock."""
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


def score_worker(target):
    """
    Score a single business. Returns (target, result, error).
    This runs inside a thread pool worker.
    """
    url = target["url"]
    try:
        result = score_business(url)
        return (target, result, None)
    except Exception as e:
        return (target, None, str(e))


def run_parallel(workers=5, interval=30, limit=None, quiet=False):
    """Main parallel scoring loop."""
    global running

    init_db()
    state = load_state()

    db_count = get_score_count()
    session_count = 0

    print("=" * 60)
    print("  Agent Readiness Parallel Scorer")
    print("=" * 60)
    print(f"  Workers:          {workers}")
    print(f"  Database records: {db_count}")
    print(f"  State scored:     {state.get('total_scored', 0)}")
    print(f"  Interval:         {interval}s between batches")
    if limit:
        print(f"  Limit:            {limit} scores then stop")
    print(f"  Started:          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    while running:
        targets = get_unscored_targets()

        if not targets:
            if not quiet:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] No unscored targets. Checking again in 30s...")
            # Sleep in small increments so we can respond to shutdown signals
            for _ in range(30):
                if not running:
                    break
                time.sleep(1)
            continue

        # Determine batch size
        batch_size = workers
        if limit:
            remaining_limit = limit - session_count
            batch_size = min(batch_size, remaining_limit)

        batch = targets[:batch_size]
        queue_remaining = len(targets) - len(batch)

        if not quiet:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting batch of {len(batch)} (workers={workers}) | Queue: {len(targets)} unscored")

        batch_start = time.time()
        batch_scored = 0
        batch_errors = 0

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(score_worker, t): t for t in batch}

            for future in as_completed(futures):
                if not running:
                    # Cancel remaining futures on shutdown
                    for f in futures:
                        f.cancel()
                    break

                target, result, error = future.result()
                url = target["url"]
                vertical = target["vertical"]
                city = target["city"]
                st = target["state"]

                if error:
                    if not quiet:
                        print(f"  [!] Failed: {url} -- {error}")
                    batch_errors += 1
                    with state_lock:
                        mark_scored(url, state)
                else:
                    with db_lock:
                        save_score(
                            result,
                            vertical=vertical, city=city, state=st,
                            business_name=target.get("business_name"),
                            phone=target.get("phone"),
                            address=target.get("address"),
                            rating=target.get("rating"),
                            review_count=target.get("review_count"),
                        )

                    with state_lock:
                        mark_scored(url, state)
                        update_target_csv(url)

                    batch_scored += 1
                    session_count += 1

                    if not quiet:
                        score = result.get("composite_score", 0)
                        grade = result.get("grade", "?")
                        domain = result.get("domain", "?")
                        print(f"  OK: {domain} -- {score:.0f}/100 ({grade})")

        batch_elapsed = time.time() - batch_start
        current_db_total = db_count + session_count

        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] Batch: scored {batch_scored} businesses in {batch_elapsed:.1f}s"
            f"{f' ({batch_errors} errors)' if batch_errors else ''}"
            f" | DB total: {current_db_total}"
            f" | Queue: {queue_remaining} remaining"
        )

        # Update stats file after each batch so PDF/site counts stay current
        try:
            write_db_stats_file()
        except Exception:
            pass

        if limit and session_count >= limit:
            print(f"\nLimit reached ({limit} scores). Stopping.")
            break

        if running and queue_remaining > 0:
            # Sleep between batches in small increments for signal responsiveness
            for _ in range(interval):
                if not running:
                    break
                time.sleep(1)

    print(f"\nSession complete. Scored {session_count} businesses.")
    print(f"Total in database: {db_count + session_count}")

    # Auto-refresh website scores if we scored anything
    if session_count > 0:
        refresh_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_refresh_scores.sh")
        if os.path.isfile(refresh_script):
            print(f"\nRefreshing website scores...")
            try:
                subprocess.run([refresh_script, "--notify"], timeout=120, check=False)
            except Exception as e:
                print(f"  Warning: score refresh failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Parallel score businesses from target lists")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel scoring threads (default: 5)")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between batches (default: 30)")
    parser.add_argument("--limit", type=int, help="Stop after scoring this many")
    parser.add_argument("--quiet", action="store_true", help="Less output")
    args = parser.parse_args()

    run_parallel(workers=args.workers, interval=args.interval, limit=args.limit, quiet=args.quiet)


if __name__ == "__main__":
    main()
