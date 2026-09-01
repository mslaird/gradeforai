#!/usr/bin/env python3
"""
Post-Deploy Automation for GradeForAI Scoring Engine

Handles the full lifecycle after a new score_engine.py is deployed:
1. Detects if the deployed engine version differs from what's in the DB
2. Switches rescore service to --max-age 0 (full rescore)
3. Monitors rescore progress, periodically refreshing industry data + website
4. Resets rescore service to --max-age 7 when the full pass completes

Run on VPS:
    python3 post_deploy.py              # Auto-detect and run
    python3 post_deploy.py --force      # Force full rescore even if versions match
    python3 post_deploy.py --status     # Just print current rescore progress
    python3 post_deploy.py --refresh    # Just run industry data refresh + site rebuild

Can also run as a systemd timer (see bottom of file for unit example).
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "data", "scores.db")
STATE_FILE = os.path.join(SCRIPT_DIR, "data", "deploy_state.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "logs", "post_deploy.log")
SERVICE_FILE = "/etc/systemd/system/agent-rescore.service"
REFRESH_SCRIPT = os.path.join(SCRIPT_DIR, "auto_refresh_scores.sh")

NORMAL_MAX_AGE = 7
FULL_RESCORE_MAX_AGE = 0
REFRESH_THRESHOLD = 10000  # refresh industry data every N new scores
POLL_INTERVAL = 300  # check progress every 5 minutes


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)


def get_engine_version():
    """Read METHODOLOGY_VERSION from the deployed score_engine.py."""
    engine_path = os.path.join(SCRIPT_DIR, "score_engine.py")
    with open(engine_path, "r") as f:
        for line in f:
            if line.strip().startswith("METHODOLOGY_VERSION"):
                return line.split("=")[1].strip().strip('"').strip("'")
    return None


def get_db_version_counts():
    """Return {version: count} for all methodology versions in scores table."""
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT methodology_version, COUNT(*) FROM scores GROUP BY methodology_version"
        ).fetchall()
        return {str(r[0]): r[1] for r in rows}
    finally:
        conn.close()


def get_total_businesses():
    """Return total number of businesses in the database."""
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
    finally:
        conn.close()


def get_latest_version_count(version):
    """Count how many businesses have their LATEST score on this version."""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            """SELECT COUNT(*) FROM businesses b
               JOIN scores s ON s.business_id = b.id
               WHERE s.methodology_version = ?
                 AND s.id = (
                     SELECT s2.id FROM scores s2
                     WHERE s2.business_id = b.id
                     ORDER BY s2.timestamp DESC LIMIT 1
                 )""",
            (version,),
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def get_service_max_age():
    """Read current --max-age from the systemd service file."""
    try:
        with open(SERVICE_FILE, "r") as f:
            for line in f:
                if "ExecStart" in line and "--max-age" in line:
                    parts = line.split("--max-age")
                    if len(parts) > 1:
                        return int(parts[1].strip().split()[0])
    except (FileNotFoundError, ValueError):
        pass
    return None


def set_service_max_age(age):
    """Update --max-age in the systemd service file and restart."""
    current = get_service_max_age()
    if current == age:
        log(f"Service already at --max-age {age}, no change needed.")
        return

    with open(SERVICE_FILE, "r") as f:
        content = f.read()

    import re
    content = re.sub(r"--max-age\s+\d+", f"--max-age {age}", content)

    with open(SERVICE_FILE, "w") as f:
        f.write(content)

    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "restart", "agent-rescore"], check=True)
    log(f"Rescore service restarted with --max-age {age}.")


def run_refresh():
    """Run auto_refresh_scores.sh to update industry data and rebuild site.

    Returns True on success, False if the refresh was blocked or failed.
    """
    result = None
    if not os.path.isfile(REFRESH_SCRIPT):
        log(f"Refresh script not found: {REFRESH_SCRIPT}")
        log("Running update_industry_scores.py + build.py directly...")
        subprocess.run(
            [sys.executable, "update_industry_scores.py"],
            cwd=SCRIPT_DIR, check=True,
        )
        subprocess.run(
            [sys.executable, "website/build.py"],
            cwd=SCRIPT_DIR, check=True,
        )
    else:
        # NOTE: deliberately NOT passing --force. --force disables the drift guard
        # in auto_refresh_scores.sh, and this function runs during a methodology
        # migration, which is precisely when a large unexpected shift in the
        # national average means the new engine is miscalibrated. The guard's own
        # alert text says "Do NOT use --force until the scoring engine is
        # recalibrated"; passing it here contradicted that. If the guard blocks,
        # it restores the previous JSON, emails, and exits 1 -- which surfaces
        # below as a refresh failure rather than silently publishing bad scores.
        result = subprocess.run([REFRESH_SCRIPT, "--notify"], cwd=SCRIPT_DIR)
    if result is not None and result.returncode != 0:
        log(f"Refresh script exited {result.returncode}. If this was the drift guard, "
            f"the previous published data was restored and the new scores were NOT published. "
            f"Inspect calibration before re-running.")
        return False
    log("Industry data refreshed and website rebuilt.")
    return True


def load_state():
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def print_status():
    """Print current rescore progress."""
    engine_ver = get_engine_version()
    version_counts = get_db_version_counts()
    total_biz = get_total_businesses()
    current_ver_latest = get_latest_version_count(engine_ver)
    service_age = get_service_max_age()

    print(f"Engine version:     {engine_ver}")
    print(f"Service --max-age:  {service_age}")
    print(f"Total businesses:   {total_biz:,}")
    print(f"v{engine_ver} latest scores: {current_ver_latest:,} / {total_biz:,} ({100*current_ver_latest/max(total_biz,1):.1f}%)")
    print(f"\nAll version counts:")
    for ver, count in sorted(version_counts.items()):
        print(f"  v{ver}: {count:,}")


def run_post_deploy(force=False):
    """Main post-deploy lifecycle."""
    engine_ver = get_engine_version()
    version_counts = get_db_version_counts()
    total_biz = get_total_businesses()
    current_ver_count = version_counts.get(engine_ver, 0)
    state = load_state()

    log(f"Engine version: {engine_ver}")
    log(f"v{engine_ver} scores in DB: {current_ver_count:,}")
    log(f"Total businesses: {total_biz:,}")

    needs_full_rescore = force or current_ver_count < total_biz * 0.9

    if not needs_full_rescore:
        log(f"v{engine_ver} already covers {current_ver_count:,}/{total_biz:,} businesses (>90%). No full rescore needed.")
        run_refresh()
        return

    # Start full rescore
    log(f"Starting full rescore to v{engine_ver}...")
    set_service_max_age(FULL_RESCORE_MAX_AGE)

    state["deploy_version"] = engine_ver
    state["deploy_started"] = datetime.now(timezone.utc).isoformat()
    state["last_refresh_count"] = current_ver_count
    save_state(state)

    # Monitor loop
    last_refresh_at = current_ver_count
    stall_count = 0
    prev_count = 0

    while True:
        time.sleep(POLL_INTERVAL)

        current_latest = get_latest_version_count(engine_ver)
        pct = 100 * current_latest / max(total_biz, 1)
        log(f"Progress: {current_latest:,} / {total_biz:,} ({pct:.1f}%) on v{engine_ver}")

        # Detect stall (no progress for 3 consecutive checks)
        if current_latest == prev_count:
            stall_count += 1
        else:
            stall_count = 0
        prev_count = current_latest

        # Periodic refresh when enough new scores accumulated
        since_refresh = current_latest - last_refresh_at
        if since_refresh >= REFRESH_THRESHOLD:
            log(f"{since_refresh:,} new scores since last refresh. Updating industry data...")
            try:
                # Advance the watermark only if the refresh actually published.
                # If the drift guard blocked it, leaving the watermark alone means
                # the next threshold crossing retries rather than waiting for
                # another REFRESH_THRESHOLD scores to accumulate.
                if run_refresh():
                    last_refresh_at = current_latest
                    state["last_refresh_count"] = current_latest
                    state["last_refresh_time"] = datetime.now(timezone.utc).isoformat()
                    save_state(state)
            except Exception as e:
                log(f"Refresh failed: {e}")

        # Check if done (>95% rescored or stalled for 15+ minutes)
        if pct >= 95 or stall_count >= 3:
            if stall_count >= 3:
                log(f"Rescore appears complete (stalled at {current_latest:,}, {pct:.1f}%).")
            else:
                log(f"Rescore reached {pct:.1f}% coverage.")

            # Final refresh
            log("Running final industry data refresh...")
            try:
                run_refresh()
            except Exception as e:
                log(f"Final refresh failed: {e}")

            # Reset to normal max-age
            log(f"Resetting rescore service to --max-age {NORMAL_MAX_AGE}.")
            set_service_max_age(NORMAL_MAX_AGE)

            state["deploy_completed"] = datetime.now(timezone.utc).isoformat()
            state["final_count"] = current_latest
            state["final_pct"] = round(pct, 1)
            save_state(state)

            log(f"Post-deploy complete. v{engine_ver}: {current_latest:,} businesses rescored ({pct:.1f}%).")
            break


def main():
    parser = argparse.ArgumentParser(description="Post-deploy automation for scoring engine")
    parser.add_argument("--force", action="store_true", help="Force full rescore even if versions match")
    parser.add_argument("--status", action="store_true", help="Print rescore progress and exit")
    parser.add_argument("--refresh", action="store_true", help="Just run industry data refresh + site rebuild")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if args.refresh:
        run_refresh()
        return

    run_post_deploy(force=args.force)


if __name__ == "__main__":
    main()
