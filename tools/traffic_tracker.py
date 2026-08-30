#!/usr/bin/env python3
"""
Parse nginx access logs and store traffic data in SQLite.
Runs every 5 minutes via cron. Tracks unique IPs, page views,
top pages, and referrers. Filters out bots, internal IPs, and
static asset requests.
"""

import os
import re
import sqlite3
from datetime import datetime, timezone
from hashlib import sha256

DB_PATH = os.environ.get(
    "DB_PATH",
    "/opt/agent-readiness/data/scores.db"
    if os.path.exists("/opt/agent-readiness/data/scores.db")
    else os.path.expanduser("~/agent-readiness/data/scores.db"),
)

LOG_FILES = [
    "/var/log/nginx/access.log",
    "/var/log/nginx/access.log.1",
]

STATE_FILE = "/opt/agent-readiness/data/.traffic_offset"

# Filter out these from unique visitor counts
BOT_PATTERNS = re.compile(
    r"(bot|crawl|spider|slurp|bingpreview|facebookexternalhit|"
    r"googleother|bytespider|yandex|semrush|ahrefs|mj12|dotbot|"
    r"petalbot|gptbot|claudebot|ccbot|uptimerobot|pingdom|"
    r"headlesschrome|playwright|python-requests|curl/|wget/)",
    re.IGNORECASE,
)

# Skip static assets and internal paths
SKIP_PATHS = re.compile(
    r"\.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot|map)(\?|$)|"
    r"^/api/(health|stats|feed)|^/(dashboard|leads)",
    re.IGNORECASE,
)

INTERNAL_IPS = {"127.0.0.1", "::1"}

# nginx combined log format parser
LOG_RE = re.compile(
    r'(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<path>\S+) \S+" (?P<status>\d+) \S+ '
    r'"(?P<referrer>[^"]*)" "(?P<ua>[^"]*)"'
)


def init_traffic_tables():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS traffic_hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_hash TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            path TEXT NOT NULL,
            status INTEGER,
            referrer TEXT,
            is_bot INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS traffic_hourly (
            hour TEXT PRIMARY KEY,
            unique_visitors INTEGER DEFAULT 0,
            page_views INTEGER DEFAULT 0,
            bot_hits INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_traffic_hits_ts ON traffic_hits(timestamp);
        CREATE INDEX IF NOT EXISTS idx_traffic_hourly_hour ON traffic_hourly(hour);
    """)
    conn.commit()
    conn.close()


def get_last_offset():
    """Get the last processed byte offset to avoid re-processing."""
    try:
        with open(STATE_FILE, "r") as f:
            parts = f.read().strip().split("|")
            return parts[0], int(parts[1])
    except Exception:
        return "", 0


def save_offset(filename, offset):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        f.write(f"{filename}|{offset}")


def hash_ip(ip):
    """Hash IP for privacy. Still allows unique counting."""
    return sha256(ip.encode()).hexdigest()[:16]


def parse_timestamp(time_str):
    """Parse nginx timestamp like '18/Mar/2026:14:30:00 +0000'."""
    try:
        dt = datetime.strptime(time_str, "%d/%b/%Y:%H:%M:%S %z")
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def parse_logs():
    """Parse new lines from nginx access logs."""
    last_file, last_offset = get_last_offset()
    hits = []

    for log_file in LOG_FILES:
        if not os.path.exists(log_file):
            continue

        # For the primary log file, use offset tracking
        # For rotated logs, only process if we haven't seen them
        start = 0
        if log_file == last_file:
            start = last_offset
        elif log_file != LOG_FILES[0] and last_file == LOG_FILES[0]:
            # We're already past rotated logs
            continue

        try:
            file_size = os.path.getsize(log_file)
            if file_size < start:
                # Log was rotated, start from beginning
                start = 0

            with open(log_file, "r") as f:
                f.seek(start)
                new_data = f.read()
                new_offset = f.tell()

            for line in new_data.strip().split("\n"):
                if not line.strip():
                    continue
                m = LOG_RE.match(line)
                if not m:
                    continue

                ip = m.group("ip")
                if ip in INTERNAL_IPS:
                    continue

                path = m.group("path")
                status = int(m.group("status"))
                ua = m.group("ua")
                referrer = m.group("referrer")
                time_str = m.group("time")

                dt = parse_timestamp(time_str)
                if not dt:
                    continue

                is_bot = 1 if BOT_PATTERNS.search(ua) else 0

                # Skip static assets for page view counting
                if SKIP_PATHS.search(path):
                    continue

                hits.append({
                    "ip_hash": hash_ip(ip),
                    "timestamp": dt.isoformat(),
                    "hour": dt.strftime("%Y-%m-%d %H:00"),
                    "path": path,
                    "status": status,
                    "referrer": referrer if referrer != "-" else "",
                    "is_bot": is_bot,
                })

            # Save offset for primary log only
            if log_file == LOG_FILES[0]:
                save_offset(log_file, new_offset)

        except Exception as e:
            print(f"[traffic] Error reading {log_file}: {e}")

    return hits


def store_hits(hits):
    """Store individual hits and update hourly aggregates."""
    if not hits:
        return 0

    conn = sqlite3.connect(DB_PATH)

    # Insert individual hits
    conn.executemany(
        """INSERT INTO traffic_hits (ip_hash, timestamp, path, status, referrer, is_bot)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [(h["ip_hash"], h["timestamp"], h["path"], h["status"], h["referrer"], h["is_bot"]) for h in hits],
    )

    # Rebuild hourly aggregates for affected hours
    hours = set(h["hour"] for h in hits)
    for hour in hours:
        # Timestamps are ISO format with T separator: 2026-03-18T14:30:00+00:00
        # hour is like "2026-03-18 14:00"
        hour_start = hour.replace(" ", "T") + ":00"
        hour_end = hour[:11] + hour[11:13] + "T" + hour[11:13] + ":59:59"
        # Simpler: just match on the hour prefix
        hour_prefix = hour.replace(" ", "T")[:13]  # "2026-03-18T14"
        row = conn.execute(
            """SELECT
                COUNT(DISTINCT CASE WHEN is_bot = 0 THEN ip_hash END) as unique_visitors,
                COUNT(CASE WHEN is_bot = 0 THEN 1 END) as page_views,
                COUNT(CASE WHEN is_bot = 1 THEN 1 END) as bot_hits
               FROM traffic_hits
               WHERE timestamp LIKE ?""",
            (hour_prefix + "%",),
        ).fetchone()

        conn.execute(
            """INSERT OR REPLACE INTO traffic_hourly (hour, unique_visitors, page_views, bot_hits)
               VALUES (?, ?, ?, ?)""",
            (hour, row[0] or 0, row[1] or 0, row[2] or 0),
        )

    conn.commit()
    conn.close()
    return len(hits)


def backfill_existing_logs():
    """One-time backfill from all existing log files."""
    # Reset offset to process everything
    save_offset("", 0)

    # Process rotated log first, then current
    all_hits = []
    for log_file in reversed(LOG_FILES):
        if not os.path.exists(log_file):
            continue
        try:
            with open(log_file, "r") as f:
                data = f.read()

            for line in data.strip().split("\n"):
                if not line.strip():
                    continue
                m = LOG_RE.match(line)
                if not m:
                    continue

                ip = m.group("ip")
                if ip in INTERNAL_IPS:
                    continue

                path = m.group("path")
                status = int(m.group("status"))
                ua = m.group("ua")
                referrer = m.group("referrer")
                time_str = m.group("time")

                dt = parse_timestamp(time_str)
                if not dt:
                    continue

                is_bot = 1 if BOT_PATTERNS.search(ua) else 0

                if SKIP_PATHS.search(path):
                    continue

                all_hits.append({
                    "ip_hash": hash_ip(ip),
                    "timestamp": dt.isoformat(),
                    "hour": dt.strftime("%Y-%m-%d %H:00"),
                    "path": path,
                    "status": status,
                    "referrer": referrer if referrer != "-" else "",
                    "is_bot": is_bot,
                })

            # Set offset to end of current log
            if log_file == LOG_FILES[0]:
                save_offset(log_file, os.path.getsize(log_file))

        except Exception as e:
            print(f"[traffic] Backfill error {log_file}: {e}")

    return all_hits


def run():
    init_traffic_tables()
    hits = parse_logs()
    count = store_hits(hits)
    print(f"[traffic] {datetime.now(timezone.utc).isoformat()} -- {count} new hits processed")


def run_backfill():
    init_traffic_tables()
    hits = backfill_existing_logs()
    count = store_hits(hits)
    print(f"[traffic] Backfill complete: {count} hits from existing logs")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--backfill":
        run_backfill()
    else:
        run()
