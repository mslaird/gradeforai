#!/usr/bin/env python3
"""
Re-Scoring System
Periodically re-scores businesses already in the database to build
time-series trend data. Each re-score adds a new row to the scores table,
preserving the full history for every business.

Usage:
    python rescore.py
    python rescore.py --interval 60 --workers 5 --max-age 14 --limit 50

Recommended: Run in tmux/screen or as a launchd service.
    tmux new -s rescorer
    source ~/leadsnare/scripts/venv/bin/activate
    python ~/agent-readiness/rescore.py
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from score_engine import score_business
from storage import init_db, save_score, get_businesses_needing_rescore

STATE_FILE = os.path.expanduser("~/agent-readiness/data/rescore_state.json")

running = True


def handle_signal(signum, frame):
    global running
    print("\nGraceful shutdown requested. Finishing current scores...")
    running = False


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def load_state():
    """Load rescore state from disk."""
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "total_rescored": 0,
        "started": datetime.now(timezone.utc).isoformat(),
        "runs": [],
    }


def save_state(state):
    """Persist rescore state to disk."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def rescore_one(biz):
    """
    Re-score a single business. Returns a dict with the result summary
    or an error dict on failure.
    """
    url = biz["url"]
    domain = biz["domain"]
    previous_score = biz["last_score"]
    last_scored = biz["last_scored"]

    ts = datetime.now().strftime("%H:%M:%S")
    last_date = last_scored[:10] if last_scored else "unknown"
    prev_display = f"{previous_score:.0f}" if previous_score is not None else "N/A"
    print(f"[{ts}] Re-scoring: {domain} | Last scored: {last_date} | Previous: {prev_display}/100")

    try:
        result = score_business(url)
        save_score(
            result,
            vertical=biz.get("vertical"),
            city=biz.get("city"),
            state=biz.get("state"),
        )

        new_score = result.get("composite_score", 0)
        if previous_score is not None:
            delta = new_score - previous_score
            sign = "+" if delta >= 0 else ""
            print(f"           {domain}: {previous_score:.0f} -> {new_score:.0f} ({sign}{delta:.0f})")
        else:
            print(f"           {domain}: -> {new_score:.0f}/100 (no previous score)")

        return {
            "domain": domain,
            "url": url,
            "previous_score": previous_score,
            "new_score": new_score,
            "success": True,
        }

    except Exception as e:
        print(f"           [!] Error re-scoring {domain}: {e}")
        return {
            "domain": domain,
            "url": url,
            "success": False,
            "error": str(e),
        }


def run_rescore(interval=30, workers=3, max_age=30, limit=None):
    """Main re-scoring loop."""
    global running

    init_db()
    state = load_state()
    session_count = 0

    print("=" * 60)
    print("  Agent Readiness Re-Scorer")
    print("=" * 60)
    print(f"  Workers:          {workers}")
    print(f"  Interval:         {interval}s between batches")
    print(f"  Max age:          {max_age} days")
    if limit:
        print(f"  Limit:            {limit} businesses per run")
    print(f"  State file:       {STATE_FILE}")
    print(f"  Started:          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    while running:
        fetch_limit = limit if limit else 100
        businesses = get_businesses_needing_rescore(
            max_age_days=max_age, limit=fetch_limit
        )

        if not businesses:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No businesses need re-scoring (max age: {max_age} days). Waiting 5 minutes...")
            # Sleep in small increments so we can respond to shutdown signals
            for _ in range(60):
                if not running:
                    break
                time.sleep(5)
            continue

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {len(businesses)} businesses needing re-score")

        # Process in batches using ThreadPoolExecutor
        batch_results = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for biz in businesses:
                if not running:
                    break
                future = executor.submit(rescore_one, biz)
                futures[future] = biz

            for future in as_completed(futures):
                if not running:
                    break
                try:
                    result = future.result()
                    batch_results.append(result)
                    if result["success"]:
                        session_count += 1
                except Exception as e:
                    biz = futures[future]
                    print(f"           [!] Unexpected error for {biz['domain']}: {e}")

        # Update state
        state["total_rescored"] = state.get("total_rescored", 0) + len(
            [r for r in batch_results if r.get("success")]
        )
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        state["last_batch_size"] = len(batch_results)
        state["runs"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rescored": len([r for r in batch_results if r.get("success")]),
            "errors": len([r for r in batch_results if not r.get("success")]),
        })
        # Keep only last 100 run entries
        state["runs"] = state["runs"][-100:]
        save_state(state)

        successful = len([r for r in batch_results if r.get("success")])
        errors = len([r for r in batch_results if not r.get("success")])
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Batch complete: {successful} re-scored, {errors} errors | Session total: {session_count}")

        if limit and session_count >= limit:
            print(f"\nLimit reached ({limit} re-scores). Stopping.")
            break

        if running:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sleeping {interval}s before next batch...")
            # Sleep in small increments for responsive shutdown
            elapsed = 0
            while elapsed < interval and running:
                time.sleep(min(1, interval - elapsed))
                elapsed += 1

    print(f"\nSession complete. Re-scored {session_count} businesses.")

    # Auto-refresh website scores if we rescored anything
    if session_count > 0:
        refresh_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_refresh_scores.sh")
        if os.path.isfile(refresh_script):
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Refreshing website scores...")
            try:
                subprocess.run([refresh_script, "--notify"], timeout=120, check=False)
            except Exception as e:
                print(f"  Warning: score refresh failed: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Re-score businesses to build time-series trend data"
    )
    parser.add_argument(
        "--interval", type=int, default=30,
        help="Seconds between scoring batches (default: 30)"
    )
    parser.add_argument(
        "--workers", type=int, default=3,
        help="Number of parallel scoring workers (default: 3)"
    )
    parser.add_argument(
        "--max-age", type=int, default=30,
        help="Days since last score to trigger re-score (default: 30)"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max businesses to re-score per run"
    )
    args = parser.parse_args()

    run_rescore(
        interval=args.interval,
        workers=args.workers,
        max_age=args.max_age,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
