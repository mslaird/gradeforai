#!/usr/bin/env python3
"""
Pipeline Health Check — Runs every 30 minutes via launchd.
Sends a macOS notification if the pipeline is disrupted (no scores in 2+ hours).
Also checks that all services are running.

Usage:
    python health_check.py          # Check and notify if unhealthy
    python health_check.py --test   # Send a test notification
"""

import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.expanduser("~/agent-readiness/data/scores.db")

SERVICES = [
    "com.agentreadiness.harvester",
    "com.agentreadiness.scorer",
    "com.agentreadiness.rescore",
]


def send_notification(title, message, sound=True):
    """Send a macOS notification."""
    sound_flag = 'sound name "Funk"' if sound else ""
    script = f'display notification "{message}" with title "{title}" {sound_flag}'
    subprocess.run(["osascript", "-e", script], capture_output=True)


def check_scoring_health(max_minutes=120):
    """Check if scoring has happened recently."""
    if not os.path.isfile(DB_PATH):
        return False, "No database found"

    conn = sqlite3.connect(DB_PATH)
    last = conn.execute(
        "SELECT timestamp FROM scores ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    total = conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
    conn.close()

    if not last:
        return False, "No scores in database"

    try:
        last_dt = datetime.fromisoformat(last[0].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        mins_ago = (now - last_dt).total_seconds() / 60

        if mins_ago > max_minutes:
            return False, f"No scores in {mins_ago:.0f} minutes. Total: {total:,}"
        return True, f"Last score {mins_ago:.0f}m ago. Total: {total:,}"
    except Exception as e:
        return False, f"Error parsing timestamp: {e}"


def check_services():
    """Check that critical launchd services are running."""
    try:
        result = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=5
        )
        output = result.stdout
    except Exception:
        return False, "Could not check services"

    down = []
    for service in SERVICES:
        found = False
        for line in output.splitlines():
            if service in line:
                parts = line.split()
                pid = parts[0]
                if pid != "-":
                    found = True
                break
        if not found:
            name = service.split(".")[-1]
            down.append(name)

    if down:
        return False, f"Services down: {', '.join(down)}"
    return True, "All services running"


def main():
    parser = argparse.ArgumentParser(description="Pipeline health check")
    parser.add_argument("--test", action="store_true", help="Send test notification")
    args = parser.parse_args()

    if args.test:
        send_notification("Agent Readiness", "Test notification. Pipeline monitoring is active.")
        print("Test notification sent.")
        return

    scoring_ok, scoring_msg = check_scoring_health()
    services_ok, services_msg = check_services()

    timestamp = datetime.now().strftime("%H:%M:%S")

    if not scoring_ok:
        send_notification(
            "Agent Readiness ALERT",
            f"Scoring disrupted: {scoring_msg}"
        )
        print(f"[{timestamp}] ALERT - Scoring: {scoring_msg}")

    if not services_ok:
        send_notification(
            "Agent Readiness ALERT",
            f"Pipeline issue: {services_msg}"
        )
        print(f"[{timestamp}] ALERT - Services: {services_msg}")

    if scoring_ok and services_ok:
        print(f"[{timestamp}] OK - {scoring_msg} | {services_msg}")


if __name__ == "__main__":
    main()
