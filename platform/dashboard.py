#!/usr/bin/env python3
"""
Agent Readiness Pipeline Dashboard
Local web dashboard for monitoring data accumulation and pipeline health.

Usage:
    python dashboard.py
    python dashboard.py --port 8080

Then open http://localhost:8050 in your browser.
"""

import argparse
import json
import os
import sqlite3
import subprocess
import time
import uuid
import threading
import traceback
from urllib.parse import urlparse, parse_qs, unquote
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- TTL cache for expensive DB queries ---
_stats_cache = {"data": None, "expires": 0}
_snapshot_cache = {"data": None, "expires": 0}
_layer_cache = {"data": None, "expires": 0}
_CACHE_TTL = 60  # seconds

# Add project to path for imports
import sys
sys.path.insert(0, "/opt/agent-readiness")
from score_engine import score_business
from email_templates import scorecard_email_html, report_purchased_email_html
from pdf_report_v2 import generate_pdf_report
from storage import get_vertical_benchmarks, get_local_competitors, get_percentile_rank, add_subscriber, remove_subscriber, save_contact_message
import base64
import hashlib
import hmac

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
STRIPE_WEBHOOK_SECRET = "whsec_PURGED_FROM_HISTORY_ROTATED_IN_STRIPE"
FROM_EMAIL = "Mark at GradeForAI <mark@gradeforai.com>"


def send_email(to, subject, html):
    """Send email via Resend API."""
    import urllib.request
    try:
        payload = json.dumps({
            "from": FROM_EMAIL,
            "to": [to],
            "subject": subject,
            "html": html,
        }).encode()
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "GradeForAI/1.0",
            },
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except Exception as e:
        print(f"[!] Email send failed: {e}")
        return None


def _verify_stripe_signature(payload, sig_header, secret, tolerance=300):
    """Verify Stripe webhook signature (v1). Returns True if valid."""
    try:
        parts = dict(pair.split("=", 1) for pair in sig_header.split(","))
        timestamp = parts.get("t", "")
        signature = parts.get("v1", "")
        if not timestamp or not signature:
            return False
        # Check timestamp tolerance (default 5 minutes)
        if abs(time.time() - int(timestamp)) > tolerance:
            return False
        # Compute expected signature
        signed_payload = f"{timestamp}.".encode() + payload
        expected = hmac.new(
            secret.encode(), signed_payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def send_scorecard_email(email, scan_id, scan_data):
    """Send free scorecard email after email capture.

    Score, grade, and dimensions are derived using the same helpers as the
    website (`_band_from_ai_preference_score`, `_derive_ai_preference_dims`)
    so the email always matches the on-page display.
    """
    try:
        score_data = scan_data.get("score_data", {})
        raw = json.loads(score_data.get("raw_json", "{}"))

        domain = score_data.get("domain", "")
        composite_score = scan_data.get("composite_score", 0)

        ai_pref = raw.get("ai_preference_score")
        if ai_pref is None:
            ai_pref = composite_score
        score = int(round(ai_pref or 0))
        grade = _band_from_ai_preference_score(score)

        dims_dict = _derive_ai_preference_dims(raw)
        dim_labels = [
            ("agent_accessibility", "Agent Accessibility"),
            ("transaction_completeness", "Transaction Completeness"),
            ("data_reliability", "Data Reliability"),
            ("competitive_position", "Competitive Position"),
        ]
        dimensions = []
        for key, name in dim_labels:
            val = dims_dict.get(key)
            if val is None:
                dimensions.append({"name": name, "score": None})
            else:
                dimensions.append({"name": name, "score": int(round(val))})

        html = scorecard_email_html(domain, score, grade, dimensions)
        html = html.replace("{{scan_id}}", scan_id)

        send_email(
            email,
            f"Your AI Agent Preference Score: {score}/100 ({grade}) - {domain}",
            html,
        )
        print(f"[email] Scorecard sent to {email} for {domain}")
    except Exception as e:
        print(f"[!] Scorecard email error: {e}")


def deliver_full_report(scan_id, email):
    """Generate PDF report and email it to the customer."""
    try:
        scan_data = get_scan_with_scores(scan_id)
        if not scan_data or scan_data.get("status") != "complete":
            print(f"[!] Cannot deliver report for scan {scan_id}: not complete")
            return

        score_data = scan_data.get("score_data", {})
        raw = json.loads(score_data.get("raw_json", "{}"))

        # Build score_result for PDF generator
        score_result = {
            "domain": score_data.get("domain", ""),
            "url": scan_data.get("url", ""),
            "business_name": score_data.get("business_name", ""),
            "composite_score": float(scan_data.get("composite_score", 0)),
            "grade": scan_data.get("grade", "F"),
            "dimension_scores": raw.get("dimension_scores", {}),
            "ai_preference_dimensions": raw.get("ai_preference_dimensions"),
            "vertical_category": raw.get("_internal", {}).get("vertical_category", "general"),
            "vertical_category_label": raw.get("_internal", {}).get("vertical_category_label", "General"),
        }

        # Try to get benchmarks, competitors, and percentile
        benchmarks = None
        competitors = None
        percentile = None
        try:
            vertical = score_data.get("vertical", "")
            if vertical:
                benchmarks = get_vertical_benchmarks(vertical)
                # Get city from business record for local competitor lookup
                from storage import _get_conn
                conn = _get_conn()
                try:
                    biz = conn.execute(
                        "SELECT city FROM businesses WHERE domain = ?",
                        (score_data.get("domain", ""),)
                    ).fetchone()
                    city = biz["city"] if biz and biz["city"] else None
                finally:
                    conn.close()
                if city:
                    competitors = get_local_competitors(
                        vertical, city,
                        exclude_domain=score_data.get("domain"),
                        limit=3
                    )
                composite = float(scan_data.get("composite_score", 0))
                percentile, _ = get_percentile_rank(vertical, composite)
        except Exception:
            pass

        # Generate PDF
        pdf_path = generate_pdf_report(score_result, benchmarks, competitors, percentile)
        print(f"[report] PDF generated: {pdf_path}")

        # Read PDF for attachment
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        pdf_b64 = base64.b64encode(pdf_bytes).decode()

        domain = score_data.get("domain", "")
        score = int(scan_data.get("composite_score", 0))
        grade = scan_data.get("grade", "F")

        # Send email with PDF attachment via Resend
        html = report_purchased_email_html(domain, score, grade)

        payload = json.dumps({
            "from": FROM_EMAIL,
            "to": [email],
            "subject": f"Your AI Agent Preference Score Report - {domain}",
            "html": html,
            "attachments": [{
                "filename": os.path.basename(pdf_path),
                "content": pdf_b64,
                "type": "application/pdf",
            }],
        })

        result = subprocess.run(
            ["curl", "-s", "-X", "POST", "https://api.resend.com/emails",
             "-H", f"Authorization: Bearer {RESEND_API_KEY}",
             "-H", "Content-Type: application/json",
             "-d", payload],
            capture_output=True, text=True, timeout=30,
        )
        print(f"[report] Email sent to {email}: {result.stdout[:200]}")

    except Exception as e:
        print(f"[!] Report delivery error: {e}")
        traceback.print_exc()


def log_purchase_event(scan_id, email):
    """Log purchase_complete event to database for analytics."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                scan_id TEXT,
                email TEXT,
                metadata TEXT,
                timestamp TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute(
            "INSERT INTO events (event_type, scan_id, email) VALUES (?, ?, ?)",
            ("purchase_complete", scan_id, email),
        )
        conn.commit()
        conn.close()
        print(f"[analytics] purchase_complete logged for {scan_id}")
    except Exception as e:
        print(f"[analytics] Error logging event: {e}")
from storage import (
    init_db, save_score, create_scan, update_scan,
    get_scan, get_scan_with_scores, get_scan_stats, update_scan_email
)

DB_PATH = os.path.expanduser("/opt/agent-readiness/data/scores.db")


# ---------------------------------------------------------------------------
# v6 gated results payload
# ---------------------------------------------------------------------------

def _derive_ai_preference_dims(raw):
    """Extract or derive the 4-dimension preference breakdown from raw_json."""
    dims = raw.get("ai_preference_dimensions") or {}
    if dims:
        # Competitive Position is None when the business has no valid
        # same-vertical + same-metro cohort; preserve None end-to-end so the
        # UI can render "Insufficient data" instead of a fabricated number.
        cp_raw = dims.get("competitive_position")
        cp_out = None if cp_raw is None else int(round(cp_raw))
        return {
            "agent_accessibility": int(round(dims.get("agent_accessibility") or 0)),
            "transaction_completeness": int(round(dims.get("transaction_completeness") or 0)),
            "data_reliability": int(round(dims.get("data_reliability") or 0)),
            "competitive_position": cp_out,
        }
    # Fallback for pre-v6 scores: approximate from legacy 6-dim data
    legacy = raw.get("dimension_scores") or {}

    def _ls(key):
        d = legacy.get(key) or {}
        s = d.get("score", 0) if isinstance(d, dict) else (d or 0)
        return int(round(s or 0))

    aa = _ls("agent_compatibility")
    tc = int(round((_ls("transaction_readiness") + _ls("agentic_commerce")) / 2))
    dr = int(round((_ls("operational_data_structure") + _ls("data_accuracy")) / 2))
    # For legacy rows, if competitive_position is absent/zero we treat it as
    # unavailable (None) rather than defaulting to 50 -- matches v6.1 semantics.
    cp_raw = _ls("competitive_position")
    cp = cp_raw if cp_raw > 0 else None
    return {
        "agent_accessibility": aa,
        "transaction_completeness": tc,
        "data_reliability": dr,
        "competitive_position": cp,
    }


def _derive_tier2_context(raw, dims):
    """Produce one brief context string per dimension. No fixes, no action plan."""
    ctx = {}

    # Transaction Completeness
    tc_bits = []
    booking = raw.get("booking_platform")
    has_booking = raw.get("has_online_booking", False)
    if booking and has_booking:
        tc_bits.append(f"Booking platform detected: {booking}")
    else:
        tc_bits.append("No online booking platform detected")
    missing = raw.get("transaction_stages_missing") or []
    if missing:
        stages = ", ".join(missing[:3])
        tc_bits.append(f"{len(missing)} of 5 transaction stages incomplete ({stages})")
    ctx["transaction_completeness"] = ". ".join(tc_bits) + "."

    # Data Reliability
    ec = raw.get("entity_coherence_score")
    if ec is not None:
        ec_int = int(round(ec))
        if ec_int >= 85:
            ctx["data_reliability"] = f"Identity verified against Google Places (coherence {ec_int}/100)."
        elif ec_int >= 60:
            ctx["data_reliability"] = f"Minor NAP mismatches with Google Places (coherence {ec_int}/100)."
        else:
            ctx["data_reliability"] = f"Significant NAP mismatches with Google Places (coherence {ec_int}/100)."
    else:
        dr = dims.get("data_reliability", 0)
        if dr >= 70:
            ctx["data_reliability"] = "Operational data is structured and consistent across the site."
        elif dr >= 45:
            ctx["data_reliability"] = "Partial structured data. Some inconsistencies detected across pages."
        else:
            ctx["data_reliability"] = "Operational data is largely unstructured or inconsistent across pages."

    # Agent Accessibility
    aa = dims.get("agent_accessibility", 0)
    if aa >= 70:
        ctx["agent_accessibility"] = "Agents can reach and parse the site without significant barriers."
    elif aa >= 45:
        ctx["agent_accessibility"] = "Agent access has friction that reduces extraction quality."
    else:
        ctx["agent_accessibility"] = "Agents face significant barriers: bot blocking, aggressive CAPTCHA, or missing semantic structure."

    # Competitive Position (tier2 shows position without naming competitors -- that is tier3)
    cp = dims.get("competitive_position", 0)
    if cp >= 70:
        ctx["competitive_position"] = "Ranked above most competitors in your vertical and metro area."
    elif cp >= 50:
        ctx["competitive_position"] = "Mid-pack against competitors in your vertical and metro area."
    else:
        ctx["competitive_position"] = "Below-average against competitors in your vertical and metro area."

    return ctx


def _band_from_ai_preference_score(score):
    """Map a 0-100 AI Agent Preference Score to its capability band (v6).

    Must match score_engine.py:score_to_band boundaries exactly. Duplicated here
    so the gated payload is self-contained and can't drift from the display score.
    """
    s = int(round(score or 0))
    if s >= 90:
        return "Agent Preferred"
    if s >= 70:
        return "Agent Optimized"
    if s >= 50:
        return "Agent Ready"
    if s >= 30:
        return "Agent Functional"
    if s >= 10:
        return "Agent Detected"
    return "Agent Incompatible"


def build_gated_score_payload(raw, composite_score, grade, email_unlocked=False):
    """Tier 1: headline score + 4 dim numbers + grade. Tier 2 adds brief per-dim context.

    The `grade` parameter from the DB was computed against composite_score (legacy 6-dim).
    The gated payload must display a band label that matches ai_preference_score, so we
    recompute it here from ai_pref — ignoring the passed-in grade to prevent mismatch.
    """
    dims = _derive_ai_preference_dims(raw)
    ai_pref = raw.get("ai_preference_score")
    if ai_pref is None:
        # Fallback composite: use legacy composite_score so the page still shows a number
        ai_pref = composite_score
    ai_pref_int = int(round(ai_pref or 0))
    payload = {
        "ai_preference_score": ai_pref_int,
        "composite_score": int(round(composite_score or 0)),
        "grade": _band_from_ai_preference_score(ai_pref_int),
        "dimensions": dims,
        "email_unlocked": bool(email_unlocked),
    }
    if email_unlocked:
        payload["context"] = _derive_tier2_context(raw, dims)
    return payload

HARVEST_STATE = os.path.expanduser("/opt/agent-readiness/data/harvest_state.json")
SCORER_STATE = os.path.expanduser("/opt/agent-readiness/data/scorer_state.json")
RESCORE_STATE = os.path.expanduser("/opt/agent-readiness/data/rescore_state.json")
LOG_DIR = os.path.expanduser("/opt/agent-readiness/logs")

SERVICES = [
    ("agent-harvester", "Harvester"),
    ("agent-scorer", "Scorer"),
    ("agent-rescore", "Re-Scorer"),
    ("agent-export.timer", "Weekly Export"),
    ("agent-backup.timer", "Daily Backup"),
]


def get_service_status():
    """Check which systemd services are running."""
    statuses = {}
    for label, name in SERVICES:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", label], capture_output=True, text=True, timeout=5
            )
            active = result.stdout.strip() == "active"
            pid = None
            if active:
                pid_result = subprocess.run(
                    ["systemctl", "show", label, "--property=MainPID", "--value"],
                    capture_output=True, text=True, timeout=5
                )
                pid = pid_result.stdout.strip()
            statuses[name] = {
                "running": active,
                "pid": pid if active else None,
                "exit_code": "active" if active else result.stdout.strip(),
            }
        except Exception:
            statuses[name] = {"running": False, "pid": None, "exit_code": "error"}
    return statuses


def get_db_stats():
    """Get scoring statistics from the database (cached for 60s)."""
    now_ts = time.time()
    if _stats_cache["data"] is not None and now_ts < _stats_cache["expires"]:
        return _stats_cache["data"]

    if not os.path.isfile(DB_PATH):
        return {}

    conn = sqlite3.connect(DB_PATH)
    now = datetime.now(timezone.utc)

    stats = {}

    # Total scores and businesses
    stats["total_scores"] = conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
    stats["total_businesses"] = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
    stats["avg_score"] = conn.execute("SELECT AVG(composite_score) FROM scores").fetchone()[0] or 0

    # Time-based counts
    for label, days in [("today", 1), ("week", 7), ("month", 30), ("year", 365)]:
        cutoff = (now - timedelta(days=days)).isoformat()
        count = conn.execute(
            "SELECT COUNT(*) FROM scores WHERE timestamp > ?", (cutoff,)
        ).fetchone()[0]
        stats[f"scores_{label}"] = count

    # Scores per hour (last 24h)
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    count_24h = conn.execute(
        "SELECT COUNT(*) FROM scores WHERE timestamp > ?", (cutoff_24h,)
    ).fetchone()[0]
    stats["scores_per_hour"] = round(count_24h / 24, 1) if count_24h else 0

    # Most recent score timestamp
    last = conn.execute(
        "SELECT timestamp FROM scores ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    if last:
        stats["last_score_time"] = last[0]
        try:
            last_dt = datetime.fromisoformat(last[0].replace("Z", "+00:00"))
            mins_ago = (now - last_dt).total_seconds() / 60
            stats["mins_since_last"] = round(mins_ago, 1)
            stats["pipeline_healthy"] = mins_ago < 120  # Alert if no score in 2 hours
        except Exception:
            stats["mins_since_last"] = "?"
            stats["pipeline_healthy"] = False
    else:
        stats["last_score_time"] = "never"
        stats["mins_since_last"] = "N/A"
        stats["pipeline_healthy"] = False

    # Grade distribution
    grades = {}
    for row in conn.execute("SELECT grade, COUNT(*) FROM scores GROUP BY grade"):
        grades[row[0] or "?"] = row[1]
    stats["grades"] = grades

    # City coverage
    stats["cities"] = conn.execute("SELECT COUNT(DISTINCT city) FROM businesses").fetchone()[0]
    stats["verticals"] = conn.execute("SELECT COUNT(DISTINCT vertical) FROM businesses").fetchone()[0]

    # Top 10 cities by score count
    top_cities = conn.execute(
        "SELECT city, state, COUNT(*) as cnt FROM businesses GROUP BY city, state ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    stats["top_cities"] = [{"city": r[0], "state": r[1], "count": r[2]} for r in top_cities]

    # Scoring trend (last 7 days, by day) -- single query instead of 7 loops
    cutoff_7d = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0).isoformat()
    trend_rows = conn.execute(
        "SELECT date(timestamp) as d, COUNT(*) FROM scores WHERE timestamp > ? GROUP BY d ORDER BY d",
        (cutoff_7d,)
    ).fetchall()
    trend_map = {r[0]: r[1] for r in trend_rows}
    trend = []
    for i in range(6, -1, -1):
        day_date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        day_label = (now - timedelta(days=i)).strftime("%m/%d")
        trend.append({"day": day_label, "count": trend_map.get(day_date, 0)})
    stats["trend_7d"] = trend

    conn.close()
    _stats_cache["data"] = stats
    _stats_cache["expires"] = time.time() + _CACHE_TTL
    return stats



def get_recent_scores(limit=15):
    """Get the most recent scores for live feed."""
    if not os.path.isfile(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT b.domain, b.city, b.state, b.vertical, s.composite_score, s.grade, s.timestamp
           FROM scores s JOIN businesses b ON s.business_id = b.id
           ORDER BY s.timestamp DESC LIMIT ?""", (limit,)
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        try:
            dt = datetime.fromisoformat(r[6].replace("Z", "+00:00"))
            ago = (datetime.now(timezone.utc) - dt).total_seconds()
            if ago < 60:
                time_str = f"{int(ago)}s ago"
            elif ago < 3600:
                time_str = f"{int(ago/60)}m ago"
            else:
                time_str = f"{int(ago/3600)}h ago"
        except Exception:
            time_str = ""
        results.append({
            "domain": r[0], "city": r[1], "state": r[2], "vertical": r[3],
            "score": r[4], "grade": r[5], "time_ago": time_str
        })
    return results


def get_snapshot_stats():
    """Get re-score snapshot statistics (cached for 60s)."""
    now_ts = time.time()
    if _snapshot_cache["data"] is not None and now_ts < _snapshot_cache["expires"]:
        return _snapshot_cache["data"]

    if not os.path.isfile(DB_PATH):
        return {"total_snapshots": 0, "businesses_with_history": 0, "max_snapshots": 0}
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
    unique = conn.execute("SELECT COUNT(DISTINCT business_id) FROM scores").fetchone()[0]
    multi = conn.execute(
        "SELECT COUNT(*) FROM (SELECT business_id, COUNT(*) as cnt FROM scores GROUP BY business_id HAVING cnt > 1)"
    ).fetchone()[0]
    max_snaps = conn.execute(
        "SELECT MAX(cnt) FROM (SELECT COUNT(*) as cnt FROM scores GROUP BY business_id)"
    ).fetchone()[0] or 0
    conn.close()
    result = {
        "total_snapshots": total,
        "unique_businesses": unique,
        "businesses_with_history": multi,
        "max_snapshots": max_snaps,
    }
    _snapshot_cache["data"] = result
    _snapshot_cache["expires"] = time.time() + _CACHE_TTL
    return result


def get_layer_stats():
    """Get v6.2 data layer statistics (cached for 60s)."""
    now_ts = time.time()
    if _layer_cache["data"] is not None and now_ts < _layer_cache["expires"]:
        return _layer_cache["data"]

    if not os.path.isfile(DB_PATH):
        return {}

    conn = sqlite3.connect(DB_PATH)
    result = {}

    # v6.2 rescore progress
    result["v62_scores"] = conn.execute(
        "SELECT COUNT(*) FROM scores WHERE methodology_version = ?", ("6.2",)
    ).fetchone()[0]
    result["total_businesses"] = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]

    # Methodology version mix (top versions)
    versions = conn.execute(
        "SELECT methodology_version, COUNT(*) FROM scores GROUP BY methodology_version ORDER BY COUNT(*) DESC LIMIT 5"
    ).fetchall()
    result["version_mix"] = [{"version": r[0] or "?", "count": r[1]} for r in versions]

    # Price tier distribution
    tiers = conn.execute(
        "SELECT price_tier, COUNT(*) FROM businesses WHERE price_tier IS NOT NULL GROUP BY price_tier ORDER BY COUNT(*) DESC"
    ).fetchall()
    result["price_tiers"] = {r[0]: r[1] for r in tiers}

    # Observation table counts
    for table in ["scan_observations", "google_observations", "technology_change_events"]:
        try:
            result[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except Exception:
            result[table] = 0

    # Response time stats
    try:
        rt = conn.execute(
            "SELECT AVG(response_time_ms), MIN(response_time_ms), MAX(response_time_ms) "
            "FROM scan_observations WHERE response_time_ms > 0"
        ).fetchone()
        result["rt_avg"] = round(rt[0]) if rt[0] else 0
        result["rt_min"] = rt[1] or 0
        result["rt_max"] = rt[2] or 0
    except Exception:
        result["rt_avg"] = result["rt_min"] = result["rt_max"] = 0

    # Top CMS platforms
    try:
        cms = conn.execute(
            "SELECT cms_detected, COUNT(*) FROM scan_observations "
            "WHERE length(cms_detected) > 0 GROUP BY cms_detected ORDER BY COUNT(*) DESC LIMIT 8"
        ).fetchall()
        result["top_cms"] = [{"name": r[0], "count": r[1]} for r in cms]
    except Exception:
        result["top_cms"] = []

    # HTTP status distribution
    try:
        statuses = conn.execute(
            "SELECT http_status_code, COUNT(*) FROM scan_observations "
            "WHERE http_status_code IS NOT NULL GROUP BY http_status_code ORDER BY COUNT(*) DESC LIMIT 6"
        ).fetchall()
        result["http_statuses"] = [{"code": r[0], "count": r[1]} for r in statuses]
    except Exception:
        result["http_statuses"] = []

    conn.close()
    _layer_cache["data"] = result
    _layer_cache["expires"] = time.time() + _CACHE_TTL
    return result


def get_state_files():
    """Read pipeline state files."""
    states = {}
    for path, name in [
        (HARVEST_STATE, "harvester"),
        (SCORER_STATE, "scorer"),
        (RESCORE_STATE, "rescorer"),
    ]:
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    states[name] = json.load(f)
            except Exception:
                states[name] = {"error": "could not read"}
        else:
            states[name] = {"status": "no state file"}
    return states


def get_log_tail(service, lines=5):
    """Get the last N lines of a service log."""
    log_path = os.path.join(LOG_DIR, f"{service}.log")
    if not os.path.isfile(log_path):
        return "No log file"
    try:
        with open(log_path, "r") as f:
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])
    except Exception:
        return "Could not read log"


def get_db_size():
    """Get database file size."""
    if os.path.isfile(DB_PATH):
        size_bytes = os.path.getsize(DB_PATH)
        if size_bytes > 1_000_000_000:
            return f"{size_bytes / 1_000_000_000:.1f} GB"
        elif size_bytes > 1_000_000:
            return f"{size_bytes / 1_000_000:.1f} MB"
        else:
            return f"{size_bytes / 1_000:.0f} KB"
    return "N/A"



LIVE_FEED_HTML = """
<div class="section" style="margin-top:16px;">
  <div class="section-title">Live Activity Feed <span id="feed-pulse" style="display:inline-block;width:8px;height:8px;background:#22c55e;border-radius:50%;margin-left:8px;animation:pulse 2s infinite;"></span></div>
  <div id="live-feed" class="card" style="max-height:400px;overflow-y:auto;padding:0;">
    <table style="width:100%">
      <thead><tr><th>Business</th><th>Location</th><th>Score</th><th>Grade</th><th>When</th></tr></thead>
      <tbody id="feed-body"></tbody>
    </table>
  </div>
</div>

<style>
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.3; } }
  .grade-badge { padding:2px 8px;border-radius:4px;font-weight:700;font-size:11px;white-space:nowrap; }
  .band-preferred { background:#ca8a0433;color:#ca8a04; }
  .band-optimized { background:#16a34a33;color:#16a34a; }
  .band-ready { background:#22c55e33;color:#22c55e; }
  .band-functional { background:#eab30833;color:#eab308; }
  .band-detected { background:#f9731633;color:#f97316; }
  .band-incompatible { background:#ef444433;color:#ef4444; }
  #live-feed tr { transition: background 0.3s; }
  #live-feed tr.new-row { background: #3b82f622; }
</style>

<script>
let lastFeedDomain = "";
function updateFeed() {
  fetch("/api/feed")
    .then(r => r.json())
    .then(data => {
      const tbody = document.getElementById("feed-body");
      let html = "";
      data.feed.forEach((r, i) => {
        const isNew = i === 0 && r.domain !== lastFeedDomain;
        var bandClass = r.score >= 90 ? 'band-preferred' : r.score >= 70 ? 'band-optimized' : r.score >= 50 ? 'band-ready' : r.score >= 30 ? 'band-functional' : r.score >= 10 ? 'band-detected' : 'band-incompatible';
        html += '<tr class="' + (isNew ? 'new-row' : '') + '">' +
          '<td>' + r.domain + '</td>' +
          '<td>' + r.city + ', ' + r.state + '</td>' +
          '<td>' + Math.round(r.score) + '</td>' +
          '<td><span class=\"grade-badge ' + bandClass + '\">' + r.grade + '</span></td>' +
          '<td>' + r.time_ago + '</td></tr>';
      });
      if (data.feed.length > 0) lastFeedDomain = data.feed[0].domain;
      tbody.innerHTML = html;
      const pulse = document.getElementById("feed-pulse");
      if (data.feed.length > 0 && data.feed[0].time_ago.includes("s ago")) {
        pulse.style.background = "#22c55e";
      } else if (data.feed.length > 0 && data.feed[0].time_ago.includes("m ago")) {
        pulse.style.background = "#eab308";
      } else {
        pulse.style.background = "#ef4444";
      }
    })
    .catch(() => {});
}
updateFeed();
setInterval(updateFeed, 5000);
</script>
"""



def get_traffic_data():
    """Get traffic stats for various time ranges."""
    if not os.path.isfile(DB_PATH):
        return {}

    conn = sqlite3.connect(DB_PATH)
    now = datetime.now(timezone.utc)

    # Check if traffic tables exist
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if "traffic_hourly" not in tables:
        conn.close()
        return {"ranges": {}, "chart_data": [], "top_pages": [], "top_referrers": []}

    # Time ranges to compute
    ranges = {
        "1h": 1,
        "12h": 12,
        "24h": 24,
        "7d": 24 * 7,
        "30d": 24 * 30,
        "3mo": 24 * 90,
        "6mo": 24 * 180,
        "1y": 24 * 365,
        "all": 24 * 3650,
    }

    range_stats = {}
    for label, hours in ranges.items():
        cutoff = (now - timedelta(hours=hours)).strftime("%Y-%m-%d %H:00")
        row = conn.execute(
            """SELECT COALESCE(SUM(unique_visitors), 0), COALESCE(SUM(page_views), 0), COALESCE(SUM(bot_hits), 0)
               FROM traffic_hourly WHERE hour >= ?""",
            (cutoff,),
        ).fetchone()
        range_stats[label] = {
            "visitors": row[0],
            "views": row[1],
            "bots": row[2],
        }

    # Chart data: hourly for last 24h, daily for longer ranges
    chart_24h = []
    for i in range(23, -1, -1):
        h = (now - timedelta(hours=i)).strftime("%Y-%m-%d %H:00")
        row = conn.execute(
            "SELECT unique_visitors, page_views FROM traffic_hourly WHERE hour = ?", (h,)
        ).fetchone()
        chart_24h.append({
            "label": (now - timedelta(hours=i)).strftime("%H:%M"),
            "visitors": row[0] if row else 0,
            "views": row[1] if row else 0,
        })

    # Daily chart for last 7 days
    chart_7d = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        row = conn.execute(
            """SELECT COALESCE(SUM(unique_visitors), 0), COALESCE(SUM(page_views), 0)
               FROM traffic_hourly WHERE hour LIKE ?""",
            (day + "%",),
        ).fetchone()
        chart_7d.append({
            "label": (now - timedelta(days=i)).strftime("%m/%d"),
            "visitors": row[0],
            "views": row[1],
        })

    # Daily chart for last 30 days
    chart_30d = []
    for i in range(29, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        row = conn.execute(
            """SELECT COALESCE(SUM(unique_visitors), 0), COALESCE(SUM(page_views), 0)
               FROM traffic_hourly WHERE hour LIKE ?""",
            (day + "%",),
        ).fetchone()
        chart_30d.append({
            "label": (now - timedelta(days=i)).strftime("%m/%d"),
            "visitors": row[0],
            "views": row[1],
        })

    # Top pages (all time, non-bot)
    top_pages = conn.execute(
        """SELECT path, COUNT(*) as hits, COUNT(DISTINCT ip_hash) as uniques
           FROM traffic_hits WHERE is_bot = 0
           GROUP BY path ORDER BY uniques DESC LIMIT 10"""
    ).fetchall()

    # Top referrers
    top_referrers = conn.execute(
        """SELECT referrer, COUNT(*) as hits, COUNT(DISTINCT ip_hash) as uniques
           FROM traffic_hits WHERE is_bot = 0 AND referrer != '' AND referrer NOT LIKE '%gradeforai%'
           GROUP BY referrer ORDER BY uniques DESC LIMIT 10"""
    ).fetchall()

    conn.close()

    return {
        "ranges": range_stats,
        "chart_24h": chart_24h,
        "chart_7d": chart_7d,
        "chart_30d": chart_30d,
        "top_pages": [{"path": r[0], "hits": r[1], "uniques": r[2]} for r in top_pages],
        "top_referrers": [{"referrer": r[0], "hits": r[1], "uniques": r[2]} for r in top_referrers],
    }


# Internal/test emails to exclude from real lead metrics
INTERNAL_EMAILS = {
    "test@gradeforai.com",
    "mark@gradeforai.com",
    "mark@gradeforai.co",
    "mark@leadsnare.co",
    "mark@layeredmedia.co",
}


def get_lead_data():
    """Get all leads with nurture status, purchase status, and scan details."""
    if not os.path.isfile(DB_PATH):
        return {"leads": [], "stats": {}}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get all scans with emails
    leads_raw = conn.execute("""
        SELECT id, url, email, status, composite_score, grade, created_at, completed_at, score_id
        FROM scans
        WHERE email IS NOT NULL AND email != ''
        ORDER BY created_at DESC
    """).fetchall()

    # Get nurture log
    nurture_map = {}
    for row in conn.execute("SELECT scan_id, email_number, sent_at FROM nurture_log ORDER BY email_number").fetchall():
        nurture_map.setdefault(row[0], []).append({"num": row[1], "sent": row[2]})

    # Get purchases
    purchasers = set()
    try:
        for row in conn.execute("SELECT DISTINCT email FROM events WHERE event_type = 'purchase_complete'").fetchall():
            purchasers.add(row[0].lower())
    except Exception:
        pass

    # Get total scans (including those without email)
    total_scans = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]

    now = datetime.now(timezone.utc)
    leads = []
    for row in leads_raw:
        scan_id = row["id"]
        email = row["email"]
        nurtures = nurture_map.get(scan_id, [])
        nurture_nums = [n["num"] for n in nurtures]
        purchased = email.lower() in purchasers

        # Calculate time since capture
        try:
            created = datetime.fromisoformat(row["created_at"])
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            hours_ago = (now - created).total_seconds() / 3600
            if hours_ago < 1:
                time_str = f"{int(hours_ago * 60)}m ago"
            elif hours_ago < 24:
                time_str = f"{int(hours_ago)}h ago"
            else:
                time_str = f"{int(hours_ago / 24)}d ago"
            date_str = created.strftime("%b %d, %H:%M")
        except Exception:
            time_str = "?"
            date_str = row["created_at"][:16] if row["created_at"] else "?"
            hours_ago = 0

        # Determine stage
        if purchased:
            stage = "Purchased"
            stage_color = "#22c55e"
        elif 5 in nurture_nums:
            stage = "Nurture Complete"
            stage_color = "#6366f1"
        elif nurture_nums:
            stage = f"Nurture {max(nurture_nums)}/5"
            stage_color = "#3b82f6"
        else:
            stage = "New Lead"
            stage_color = "#eab308"

        domain = row["url"].replace("https://", "").replace("http://", "").rstrip("/") if row["url"] else "?"

        is_internal = email.lower() in INTERNAL_EMAILS

        leads.append({
            "scan_id": scan_id,
            "email": email,
            "domain": domain,
            "url": row["url"],
            "score": row["composite_score"],
            "grade": row["grade"],
            "status": row["status"],
            "created_at": date_str,
            "time_ago": time_str,
            "hours_ago": hours_ago,
            "nurture_sent": nurture_nums,
            "purchased": purchased,
            "stage": stage,
            "stage_color": stage_color,
            "internal": is_internal,
        })

    # Stats (exclude internal/test emails)
    real_leads = [l for l in leads if not l["internal"]]
    total_leads = len(real_leads)
    total_purchased = sum(1 for l in real_leads if l["purchased"])
    total_in_nurture = sum(1 for l in real_leads if l["nurture_sent"] and not l["purchased"])
    total_new = sum(1 for l in real_leads if not l["nurture_sent"] and not l["purchased"])

    conn.close()

    return {
        "leads": leads,
        "stats": {
            "total_scans": total_scans,
            "total_leads": total_leads,
            "total_purchased": total_purchased,
            "total_in_nurture": total_in_nurture,
            "total_new": total_new,
            "capture_rate": round(total_leads / max(total_scans, 1) * 100, 1),
            "purchase_rate": round(total_purchased / max(total_leads, 1) * 100, 1),
            "internal_count": sum(1 for l in leads if l["internal"]),
        }
    }


def render_leads_dashboard():
    """Render the leads CRM dashboard HTML."""
    data = get_lead_data()
    traffic = get_traffic_data()
    t_ranges = traffic.get("ranges", {})
    _empty = {"visitors": 0, "views": 0, "bots": 0}
    tv_24h = t_ranges.get("24h", _empty)
    tv_init_visitors = tv_24h.get("visitors", 0)
    tv_init_views = tv_24h.get("views", 0)
    tv_init_bots = tv_24h.get("bots", 0)
    # Pre-serialize JS data
    import json as _json
    js_range_data = _json.dumps(t_ranges)
    js_chart_data = _json.dumps({
        "24h": traffic.get("chart_24h", []),
        "7d": traffic.get("chart_7d", []),
        "30d": traffic.get("chart_30d", []),
    }, default=str)
    leads = data["leads"]
    stats = data["stats"]

    band_colors = {
        "Agent Preferred": "#ca8a04", "Agent Optimized": "#16a34a", "Agent Ready": "#22c55e",
        "Agent Functional": "#eab308", "Agent Detected": "#f97316", "Agent Incompatible": "#ef4444",
    }

    # Lead rows
    lead_rows = ""
    for lead in leads:
        gc = band_colors.get(lead["grade"], "#666")
        score_display = f'{lead["score"]:.0f}' if lead["score"] else "-"
        grade_display = lead["grade"] or "-"

        # Nurture dots (1-5)
        nurture_dots = ""
        for i in range(1, 6):
            if i == 1:
                # Email 1 is always sent (scorecard)
                dot_color = "#22c55e"
                dot_title = "Scorecard (sent)"
            elif i in lead["nurture_sent"]:
                dot_color = "#22c55e"
                dot_title = f"Email {i} (sent)"
            else:
                dot_color = "#333"
                dot_title = f"Email {i} (pending)"
            nurture_dots += f'<span title="{dot_title}" style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{dot_color};margin-right:3px;"></span>'

        purchased_badge = '<span style="background:#22c55e22;color:#22c55e;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;margin-left:8px;">PAID</span>' if lead["purchased"] else ""

        internal_badge = '<span style="background:#ffffff11;color:#666;padding:2px 6px;border-radius:4px;font-size:10px;margin-left:6px;">TEST</span>' if lead["internal"] else ""

        lead_rows += f"""<tr style="opacity:{'0.45' if lead['internal'] else '1'};">
            <td><strong>{lead["email"]}</strong>{purchased_badge}{internal_badge}</td>
            <td><a href="https://{lead["domain"]}" target="_blank" style="color:#60a5fa;text-decoration:none;">{lead["domain"]}</a></td>
            <td><span style="color:{gc};font-weight:700;">{score_display}</span> <span style="color:#666;font-size:11px;">{grade_display}</span></td>
            <td>{nurture_dots}</td>
            <td><span style="color:{lead["stage_color"]};font-weight:600;font-size:12px;">{lead["stage"]}</span></td>
            <td style="color:#888;font-size:12px;" title="{lead["created_at"]}">{lead["time_ago"]}</td>
        </tr>"""

    if not lead_rows:
        lead_rows = '<tr><td colspan="6" style="text-align:center;color:#666;padding:40px;">No leads yet. Leads appear when visitors enter their email on the results page.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="300">
<title>GradeForAI Leads Dashboard</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0a0a0a; color: #e5e5e5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 24px; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; color: #fff; }}
  .subtitle {{ color: #888; font-size: 13px; margin-bottom: 24px; }}
  .nav {{ display: flex; gap: 8px; margin-bottom: 24px; }}
  .nav a {{ padding: 8px 16px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 600; }}
  .nav a.active {{ background: #4353ff; color: #fff; }}
  .nav a:not(.active) {{ background: #161616; color: #888; border: 1px solid #262626; }}
  .nav a:not(.active):hover {{ color: #fff; border-color: #444; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: #161616; border: 1px solid #262626; border-radius: 10px; padding: 20px; }}
  .card-label {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
  .card-value {{ font-size: 28px; font-weight: 700; color: #fff; }}
  .card-sub {{ font-size: 12px; color: #666; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; background: #161616; border: 1px solid #262626; border-radius: 10px; overflow: hidden; }}
  th {{ text-align: left; padding: 12px 16px; font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; background: #1a1a1a; border-bottom: 1px solid #262626; }}
  td {{ padding: 12px 16px; border-bottom: 1px solid #1e1e1e; font-size: 13px; }}
  tr:hover {{ background: #1a1a1a; }}
  a {{ color: #60a5fa; }}
  .funnel {{ display: flex; gap: 4px; align-items: flex-end; height: 60px; margin-top: 12px; }}
  .funnel-step {{ flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }}
  .funnel-bar {{ width: 100%; border-radius: 4px 4px 0 0; min-height: 4px; }}
  .funnel-label {{ font-size: 10px; color: #666; text-align: center; }}
  .funnel-count {{ font-size: 12px; color: #aaa; font-weight: 600; }}
</style>
</head>
<body>

<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
  <h1>Lead Dashboard</h1>
</div>
<div class="nav">
  <a href="/dashboard">Pipeline</a>
  <a href="/leads" class="active">Leads</a>
</div>

<div class="grid">
  <div class="card">
    <div class="card-label">Total Scans</div>
    <div class="card-value">{stats["total_scans"]}</div>
  </div>
  <div class="card">
    <div class="card-label">Email Captures</div>
    <div class="card-value">{stats["total_leads"]}</div>
    <div class="card-sub">{stats["capture_rate"]}% capture rate</div>
    <div class="card-sub" style="color:#555;">+{stats["internal_count"]} internal/test</div>
  </div>
  <div class="card">
    <div class="card-label">In Nurture</div>
    <div class="card-value">{stats["total_in_nurture"]}</div>
  </div>
  <div class="card">
    <div class="card-label">Purchased</div>
    <div class="card-value">{stats["total_purchased"]}</div>
    <div class="card-sub">{stats["purchase_rate"]}% conversion</div>
  </div>
  <div class="card">
    <div class="card-label">New Leads</div>
    <div class="card-value">{stats["total_new"]}</div>
  </div>
  <div class="card">
    <div class="card-label">Revenue</div>
    <div class="card-value">${stats["total_purchased"] * 49}</div>
    <div class="card-sub">@ $49/report</div>
  </div>
</div>

<div class="card" style="margin-bottom:24px;">
  <div style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;font-weight:600;">Funnel</div>
  <div class="funnel">
    <div class="funnel-step">
      <div class="funnel-count">{stats["total_scans"]}</div>
      <div class="funnel-bar" style="background:#3b82f6;height:{min(60, max(4, 60))}px;"></div>
      <div class="funnel-label">Scans</div>
    </div>
    <div class="funnel-step">
      <div class="funnel-count">{stats["total_leads"]}</div>
      <div class="funnel-bar" style="background:#8b5cf6;height:{min(60, max(4, int(stats['total_leads'] / max(stats['total_scans'], 1) * 60)))}px;"></div>
      <div class="funnel-label">Emails</div>
    </div>
    <div class="funnel-step">
      <div class="funnel-count">{stats["total_in_nurture"]}</div>
      <div class="funnel-bar" style="background:#eab308;height:{min(60, max(4, int(stats['total_in_nurture'] / max(stats['total_scans'], 1) * 60)))}px;"></div>
      <div class="funnel-label">Nurturing</div>
    </div>
    <div class="funnel-step">
      <div class="funnel-count">{stats["total_purchased"]}</div>
      <div class="funnel-bar" style="background:#22c55e;height:{min(60, max(4, int(stats['total_purchased'] / max(stats['total_scans'], 1) * 60)))}px;"></div>
      <div class="funnel-label">Paid</div>
    </div>
  </div>
</div>


<div class="card" style="margin-bottom:24px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
    <div style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;">Site Traffic</div>
    <div style="display:flex;gap:4px;" id="range-tabs">
      <button onclick="showRange('1h')" class="range-btn" data-range="1h">1H</button>
      <button onclick="showRange('12h')" class="range-btn" data-range="12h">12H</button>
      <button onclick="showRange('24h')" class="range-btn active" data-range="24h">24H</button>
      <button onclick="showRange('7d')" class="range-btn" data-range="7d">7D</button>
      <button onclick="showRange('30d')" class="range-btn" data-range="30d">30D</button>
      <button onclick="showRange('3mo')" class="range-btn" data-range="3mo">3M</button>
      <button onclick="showRange('6mo')" class="range-btn" data-range="6mo">6M</button>
      <button onclick="showRange('1y')" class="range-btn" data-range="1y">1Y</button>
      <button onclick="showRange('all')" class="range-btn" data-range="all">ALL</button>
    </div>
  </div>

  <div class="grid" style="grid-template-columns:repeat(3, 1fr);margin-bottom:16px;">
    <div>
      <div style="font-size:11px;color:#666;">Unique Visitors</div>
      <div id="tv-visitors" style="font-size:24px;font-weight:700;color:#fff;">{tv_init_visitors}</div>
    </div>
    <div>
      <div style="font-size:11px;color:#666;">Page Views</div>
      <div id="tv-views" style="font-size:24px;font-weight:700;color:#fff;">{tv_init_views}</div>
    </div>
    <div>
      <div style="font-size:11px;color:#666;">Bot Hits</div>
      <div id="tv-bots" style="font-size:11px;color:#666;">{tv_init_bots}</div>
    </div>
  </div>

  <div id="traffic-chart" style="display:flex;align-items:flex-end;gap:2px;height:120px;padding:8px 0;border-top:1px solid #262626;"></div>
</div>

<div class="two-col" style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px;">
  <div class="card" style="padding:0;">
    <div style="padding:12px 16px;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid #262626;">Top Pages</div>
    <table style="border:none;border-radius:0;">
      {"".join(f'<tr><td style="font-size:12px;">{p["path"]}</td><td style="font-size:12px;color:#888;text-align:right;">{p["uniques"]} visitors</td></tr>' for p in traffic.get("top_pages", [])[:8]) or '<tr><td colspan="2" style="color:#666;text-align:center;padding:20px;">No data yet</td></tr>'}
    </table>
  </div>
  <div class="card" style="padding:0;">
    <div style="padding:12px 16px;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid #262626;">Top Referrers</div>
    <table style="border:none;border-radius:0;">
      {"".join(f'<tr><td style="font-size:12px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{r["referrer"][:60]}</td><td style="font-size:12px;color:#888;text-align:right;">{r["uniques"]} visitors</td></tr>' for r in traffic.get("top_referrers", [])[:8]) or '<tr><td colspan="2" style="color:#666;text-align:center;padding:20px;">No referrers yet</td></tr>'}
    </table>
  </div>
</div>

<div style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;font-weight:600;">Leads</div>

<table>
  <thead>
    <tr>
      <th>Email</th>
      <th>Website</th>
      <th>Score</th>
      <th>Nurture (1-5)</th>
      <th>Stage</th>
      <th>Captured</th>
    </tr>
  </thead>
  <tbody>
    {lead_rows}
  </tbody>
</table>

<script>
const rangeData = JSON.parse('{js_range_data}');
const chartSets = JSON.parse('{js_chart_data}');
const rangeToChart = {{"1h":"24h","12h":"24h","24h":"24h","7d":"7d","30d":"30d","3mo":"30d","6mo":"30d","1y":"30d","all":"30d"}};

function showRange(range) {{
  const d = rangeData[range] || {{visitors:0,views:0,bots:0}};
  document.getElementById("tv-visitors").textContent = d.visitors;
  document.getElementById("tv-views").textContent = d.views;
  document.getElementById("tv-bots").textContent = d.bots;
  document.querySelectorAll(".range-btn").forEach(b => b.classList.remove("active"));
  document.querySelector('[data-range="'+range+'"]').classList.add("active");
  renderChart(chartSets[rangeToChart[range]] || []);
}}

function renderChart(data) {{
  const container = document.getElementById("traffic-chart");
  if (!data.length) {{ container.innerHTML = '<div style="color:#666;padding:20px;text-align:center;width:100%;">No data for this range</div>'; return; }}
  const maxVal = Math.max(...data.map(d => d.visitors), 1);
  let html = "";
  for (const point of data) {{
    const h = Math.max(2, (point.visitors / maxVal) * 100);
    const showLabel = data.length <= 24;
    html += '<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;">';
    html += '<div style="font-size:10px;color:#aaa;">' + (point.visitors > 0 ? point.visitors : '') + '</div>';
    html += '<div style="width:100%;height:' + h + 'px;background:linear-gradient(to top,#4353ff,#6373ff);border-radius:3px 3px 0 0;min-height:2px;"></div>';
    if (showLabel) html += '<div style="font-size:9px;color:#555;white-space:nowrap;">' + point.label + '</div>';
    html += '</div>';
  }}
  container.innerHTML = html;
}}

renderChart(chartSets["24h"] || []);
</script>

<div style="margin-top:24px;text-align:center;color:#444;font-size:12px;">
  Auto-refreshes every 30 seconds | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</div>

</body>
</html>"""


def render_dashboard():
    """Render the full dashboard HTML."""
    services = get_service_status()
    recent = get_recent_scores(15)
    snapshots = get_snapshot_stats()
    stats = get_db_stats()
    layers = get_layer_stats()
    states = get_state_files()
    db_size = get_db_size()

    healthy = stats.get("pipeline_healthy", False)
    health_color = "#22c55e" if healthy else "#ef4444"
    health_text = "HEALTHY" if healthy else "DISRUPTED"
    health_icon = "&#9679;" if healthy else "&#9888;"

    # Band distribution bar
    grades = stats.get("grades", {})
    total_graded = sum(grades.values()) or 1
    grade_bars = ""
    band_map = [
        ("Agent Preferred", "#ca8a04"), ("Agent Optimized", "#16a34a"), ("Agent Ready", "#22c55e"),
        ("Agent Functional", "#eab308"), ("Agent Detected", "#f97316"), ("Agent Incompatible", "#ef4444"),
    ]
    for band_name, color in band_map:
        count = grades.get(band_name, 0)
        pct = count / total_graded * 100
        short = band_name.split()[-1]
        grade_bars += f'<div style="flex:{pct};background:{color};text-align:center;color:#fff;font-weight:700;font-size:10px;padding:4px 0;min-width:{20 if pct > 2 else 0}px">{short}: {count}</div>'

    # Services HTML
    svc_html = ""
    for name, info in services.items():
        color = "#22c55e" if info["running"] else "#ef4444"
        status = f"PID {info['pid']}" if info["running"] else f"Stopped ({info['exit_code']})"
        svc_html += f'<div class="svc"><span class="dot" style="background:{color}"></span><strong>{name}</strong><span class="status">{status}</span></div>'

    # Trend chart (simple CSS bar chart)
    trend = stats.get("trend_7d", [])
    max_count = max((t["count"] for t in trend), default=1) or 1
    trend_bars = ""
    for t in trend:
        height = max(4, t["count"] / max_count * 120)
        trend_bars += f'<div class="bar-col"><div class="bar" style="height:{height}px"></div><div class="bar-label">{t["day"]}</div><div class="bar-count">{t["count"]}</div></div>'

    # Top cities
    cities_html = ""
    for c in stats.get("top_cities", []):
        cities_html += f'<tr><td>{c["city"]}, {c["state"]}</td><td>{c["count"]}</td></tr>'

    # Harvest state
    harvest = states.get("harvester", {})
    harvest_total = harvest.get("total_harvested", 0)
    harvest_combos = harvest.get("combos_count", "?")
    harvest_cycle = harvest.get("cycle", 0)

    # v6.2 rescore progress bar
    v62_count = layers.get("v62_scores", 0)
    v62_total = layers.get("total_businesses", 1) or 1
    v62_pct = min(100, v62_count / v62_total * 100)
    v62_color = "#22c55e" if v62_pct >= 95 else "#3b82f6" if v62_pct >= 50 else "#eab308"

    # Price tier bar
    pt = layers.get("price_tiers", {})
    pt_total = sum(pt.values()) or 1
    tier_colors = {"fixed": "#22c55e", "ranged": "#3b82f6", "quote-required": "#eab308", "none": "#666"}
    price_bar = ""
    for tier_name in ["fixed", "ranged", "quote-required", "none"]:
        count = pt.get(tier_name, 0)
        pct = count / pt_total * 100
        color = tier_colors.get(tier_name, "#666")
        label = tier_name.replace("-", " ").title()
        if pct > 3:
            price_bar += f'<div style="flex:{pct};background:{color};text-align:center;color:#fff;font-weight:700;font-size:10px;padding:4px 0;min-width:20px" title="{label}: {count}">{label}: {count}</div>'
        elif count > 0:
            price_bar += f'<div style="flex:{pct};background:{color};min-width:4px" title="{label}: {count}"></div>'

    # Version mix
    version_html = ""
    for v in layers.get("version_mix", []):
        version_html += f'<tr><td>v{v["version"]}</td><td>{v["count"]:,}</td></tr>'

    # Top CMS
    cms_html = ""
    for c in layers.get("top_cms", []):
        cms_html += f'<tr><td>{c["name"]}</td><td>{c["count"]:,}</td></tr>'

    # HTTP status distribution
    status_html = ""
    for s in layers.get("http_statuses", []):
        s_color = "#22c55e" if s["code"] == 200 else "#eab308" if s["code"] in (301, 302) else "#ef4444"
        status_html += f'<tr><td><span style="color:{s_color}">{s["code"]}</span></td><td>{s["count"]:,}</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="300">
<title>Agent Readiness Pipeline Dashboard</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0a0a0a; color: #e5e5e5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 24px; }}
  h1 {{ font-size: 22px; margin-bottom: 8px; color: #fff; }}
  .subtitle {{ color: #888; font-size: 13px; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: #161616; border: 1px solid #262626; border-radius: 10px; padding: 20px; }}
  .card-label {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
  .card-value {{ font-size: 28px; font-weight: 700; color: #fff; }}
  .card-sub {{ font-size: 12px; color: #666; margin-top: 4px; }}
  .health {{ display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 20px; font-weight: 700; font-size: 13px; background: {health_color}22; color: {health_color}; border: 1px solid {health_color}44; }}
  .section {{ margin-bottom: 24px; }}
  .section-title {{ font-size: 14px; font-weight: 600; color: #aaa; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .svc {{ display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: #161616; border: 1px solid #262626; border-radius: 8px; margin-bottom: 6px; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
  .status {{ margin-left: auto; font-size: 12px; color: #888; }}
  .grade-bar {{ display: flex; border-radius: 6px; overflow: hidden; height: 28px; margin-top: 8px; }}
  .chart {{ display: flex; align-items: flex-end; gap: 8px; height: 140px; padding-top: 20px; }}
  .bar-col {{ display: flex; flex-direction: column; align-items: center; flex: 1; }}
  .bar {{ background: linear-gradient(to top, #3b82f6, #60a5fa); border-radius: 4px 4px 0 0; width: 100%; min-height: 4px; }}
  .bar-label {{ font-size: 11px; color: #666; margin-top: 6px; }}
  .bar-count {{ font-size: 11px; color: #aaa; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #262626; font-size: 13px; }}
  th {{ color: #888; font-weight: 600; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 768px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
  .alert {{ background: #ef444422; border: 1px solid #ef444444; color: #ef4444; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-weight: 600; }}
</style>
</head>
<body>

<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
  <div>
    <h1>Agent Readiness Pipeline</h1>
    <div class="subtitle">Auto-refreshes every 5 minutes | DB size: {db_size} | Engine v6.2</div>
  </div>
  <div class="health">{health_icon} {health_text}</div>
</div>

<div style="display:flex;gap:8px;margin-bottom:24px;"><a href="/dashboard" style="padding:8px 16px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600;background:#4353ff;color:#fff;">Pipeline</a><a href="/leads" style="padding:8px 16px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600;background:#161616;color:#888;border:1px solid #262626;">Leads</a></div>

{"<div class='alert'>&#9888; Pipeline may be disrupted. No new scores in " + str(stats.get('mins_since_last', '?')) + " minutes.</div>" if not healthy else ""}

<div class="grid">
  <div class="card">
    <div class="card-label">Total Scores</div>
    <div class="card-value">{stats.get('total_scores', 0):,}</div>
    <div class="card-sub">{stats.get('total_businesses', 0):,} unique businesses</div>
  </div>
  <div class="card">
    <div class="card-label">Today</div>
    <div class="card-value">{stats.get('scores_today', 0):,}</div>
    <div class="card-sub">{stats.get('scores_per_hour', 0)} per hour</div>
  </div>
  <div class="card">
    <div class="card-label">This Week</div>
    <div class="card-value">{stats.get('scores_week', 0):,}</div>
  </div>
  <div class="card">
    <div class="card-label">This Month</div>
    <div class="card-value">{stats.get('scores_month', 0):,}</div>
  </div>
  <div class="card">
    <div class="card-label">This Year</div>
    <div class="card-value">{stats.get('scores_year', 0):,}</div>
  </div>
  <div class="card">
    <div class="card-label">Avg Score</div>
    <div class="card-value">{stats.get('avg_score', 0):.0f}<span style="font-size:16px;color:#888">/100</span></div>
  </div>
  <div class="card">
    <div class="card-label">Coverage</div>
    <div class="card-value">{stats.get('cities', 0)}</div>
    <div class="card-sub">cities, {stats.get('verticals', 0)} verticals</div>
  </div>
  <div class="card">
    <div class="card-label">URLs Harvested</div>
    <div class="card-value">{harvest_total:,}</div>
    <div class="card-sub">{harvest_combos} combos, cycle {harvest_cycle}</div>
  </div>
  <div class="card">
    <div class="card-label">Snapshots Taken</div>
    <div class="card-value">{snapshots['total_snapshots']:,}</div>
    <div class="card-sub">{snapshots['unique_businesses']:,} unique businesses</div>
  </div>
  <div class="card">
    <div class="card-label">Trend History</div>
    <div class="card-value">{snapshots['businesses_with_history']:,}</div>
    <div class="card-sub">businesses with 2+ scores</div>
  </div>
</div>

<div class="section">
  <div class="section-title">Grade Distribution</div>
  <div class="grade-bar">{grade_bars}</div>
</div>

<div class="section">
  <div class="section-title">v6.2 Rescore Progress</div>
  <div style="background:#262626;border-radius:6px;overflow:hidden;height:28px;position:relative;">
    <div style="width:{v62_pct:.1f}%;background:{v62_color};height:100%;border-radius:6px;transition:width 0.5s;"></div>
    <div style="position:absolute;top:0;left:0;right:0;text-align:center;line-height:28px;font-weight:700;font-size:12px;color:#fff;">
      {v62_count:,} / {v62_total:,} ({v62_pct:.1f}%)
    </div>
  </div>
</div>

<div class="section">
  <div class="section-title">Price Tier Distribution</div>
  <div class="grade-bar">{price_bar}</div>
</div>

<div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));">
  <div class="card">
    <div class="card-label">Scan Observations</div>
    <div class="card-value">{layers.get('scan_observations', 0):,}</div>
    <div class="card-sub">HTTP + tech stack snapshots</div>
  </div>
  <div class="card">
    <div class="card-label">Google Observations</div>
    <div class="card-value">{layers.get('google_observations', 0):,}</div>
    <div class="card-sub">Places API snapshots</div>
  </div>
  <div class="card">
    <div class="card-label">Tech Change Events</div>
    <div class="card-value">{layers.get('technology_change_events', 0):,}</div>
    <div class="card-sub">CMS/platform changes detected</div>
  </div>
  <div class="card">
    <div class="card-label">Avg Response Time</div>
    <div class="card-value">{layers.get('rt_avg', 0):,}<span style="font-size:14px;color:#888">ms</span></div>
    <div class="card-sub">min {layers.get('rt_min', 0):,}ms / max {layers.get('rt_max', 0):,}ms</div>
  </div>
</div>

<div class="two-col">
  <div class="section">
    <div class="section-title">7-Day Scoring Trend</div>
    <div class="card">
      <div class="chart">{trend_bars}</div>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Top Cities</div>
    <div class="card" style="padding:0;">
      <table>
        <tr><th>City</th><th>Scored</th></tr>
        {cities_html}
      </table>
    </div>
  </div>
</div>

<div class="two-col">
  <div class="section">
    <div class="section-title">Top CMS Platforms</div>
    <div class="card" style="padding:0;">
      <table>
        <tr><th>Platform</th><th>Sites</th></tr>
        {cms_html if cms_html else '<tr><td colspan="2" style="color:#666;">Collecting data...</td></tr>'}
      </table>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Methodology Versions</div>
    <div class="card" style="padding:0;">
      <table>
        <tr><th>Version</th><th>Scores</th></tr>
        {version_html}
      </table>
    </div>
  </div>
</div>

<div class="two-col" style="margin-top:16px;">
  <div class="section">
    <div class="section-title">HTTP Status Codes</div>
    <div class="card" style="padding:0;">
      <table>
        <tr><th>Status</th><th>Count</th></tr>
        {status_html if status_html else '<tr><td colspan="2" style="color:#666;">Collecting data...</td></tr>'}
      </table>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Services</div>
    {svc_html}
  </div>
</div>


""" + LIVE_FEED_HTML + f"""<div style="margin-top:24px;text-align:center;color:#444;font-size:12px;">
  Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
  Last score: {stats.get('mins_since_last', '?')} min ago
</div>

</body>
</html>"""




# Active scans tracking
active_scans = {}
scan_lock = threading.Lock()


def run_scan_worker(scan_id, url):
    """Background worker that scores a URL and updates the scan record."""
    try:
        # Score the business
        result = score_business(url)

        if not result or "error" in result:
            error_msg = result.get("error", "Scoring failed") if result else "No result returned"
            update_scan(scan_id, status="error", error=error_msg)
            return

        # Save score to database
        score_id = save_score(result)

        # Update scan with results
        update_scan(
            scan_id,
            status="complete",
            score_id=score_id,
            composite_score=result.get("composite_score"),
            grade=result.get("grade"),
        )
    except Exception as e:
        update_scan(scan_id, status="error", error=str(e))
    finally:
        with scan_lock:
            active_scans.pop(scan_id, None)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/scan":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
            except Exception:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
                return

            # Handle email capture for existing scan
            if data.get("action") == "capture_email":
                existing_scan_id = data.get("scan_id", "")
                capture_email = data.get("email", "").strip()
                response_payload = {"status": "ok"}
                if existing_scan_id and capture_email:
                    update_scan_email(existing_scan_id, capture_email)
                    # Send scorecard email in background, and build tier2 gated payload for inline reveal
                    scan_data = get_scan_with_scores(existing_scan_id)
                    if scan_data and scan_data.get("status") == "complete":
                        threading.Thread(
                            target=send_scorecard_email,
                            args=(capture_email, existing_scan_id, scan_data),
                            daemon=True,
                        ).start()
                        if scan_data.get("score_data") and scan_data["score_data"].get("raw_json"):
                            try:
                                raw = json.loads(scan_data["score_data"]["raw_json"])
                            except (json.JSONDecodeError, TypeError):
                                raw = {}
                            response_payload["gated"] = build_gated_score_payload(
                                raw,
                                scan_data["score_data"].get("composite_score"),
                                scan_data["score_data"].get("grade"),
                                email_unlocked=True,
                            )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(response_payload, default=str).encode())
                return

            url = data.get("url", "").strip()
            email = data.get("email", "").strip() or None

            if not url:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "URL is required"}).encode())
                return

            # Normalize URL
            if not url.startswith("http"):
                url = "https://" + url

            scan_id = str(uuid.uuid4())
            create_scan(scan_id, url, email)

            # Launch background scoring thread
            t = threading.Thread(target=run_scan_worker, args=(scan_id, url), daemon=True)
            with scan_lock:
                active_scans[scan_id] = t
            t.start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "scan_id": scan_id,
                "status": "scanning",
                "url": url,
            }).encode())
        elif self.path == "/api/webhook/stripe":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            # Verify Stripe webhook signature
            sig_header = self.headers.get("Stripe-Signature", "")
            if not _verify_stripe_signature(body, sig_header, STRIPE_WEBHOOK_SECRET):
                print("[stripe] Webhook signature verification FAILED")
                self.send_response(401)
                self.end_headers()
                return

            try:
                event = json.loads(body)
            except Exception:
                self.send_response(400)
                self.end_headers()
                return

            # Handle checkout.session.completed
            if event.get("type") == "checkout.session.completed":
                session = event.get("data", {}).get("object", {})
                scan_id = session.get("client_reference_id", "")
                customer_email = session.get("customer_details", {}).get("email", "")

                if scan_id and customer_email:
                    print(f"[stripe] Payment received for scan {scan_id}, email: {customer_email}")
                    log_purchase_event(scan_id, customer_email)
                    # Update scan email if not set
                    update_scan_email(scan_id, customer_email)
                    # Generate and deliver report in background
                    threading.Thread(
                        target=deliver_full_report,
                        args=(scan_id, customer_email),
                        daemon=True,
                    ).start()
                else:
                    print(f"[stripe] Webhook missing scan_id or email: {session}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"received": True}).encode())

        elif self.path == "/api/deliver-report":
            # Manual report delivery (admin use)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                scan_id = data.get("scan_id", "")
                email = data.get("email", "")
                if scan_id and email:
                    threading.Thread(
                        target=deliver_full_report,
                        args=(scan_id, email),
                        daemon=True,
                    ).start()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "delivering"}).encode())
                else:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "scan_id and email required"}).encode())
            except Exception as e:
                self.send_response(500)
                self.end_headers()

        elif self.path == "/api/contact":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                name = data.get("name", "").strip()
                email = data.get("email", "").strip()
                message = data.get("message", "").strip()
                if not email or "@" not in email or not name or not message:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Name, email, and message required"}).encode())
                    return
                success, msg = save_contact_message(name, email, message)
                self.send_response(200 if success else 500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": msg}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        elif self.path == "/api/subscribe":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                email = data.get("email", "").strip()
                source = data.get("source", "unknown")
                if not email or "@" not in email:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Valid email required"}).encode())
                    return
                success, msg = add_subscriber(email, source)
                self.send_response(200 if success else 500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": msg}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        elif self.path == "/api/unsubscribe":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                email = data.get("email", "").strip()
                if not email:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Email required"}).encode())
                    return
                success, msg = remove_subscriber(email)
                self.send_response(200 if success else 500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": msg}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        else:
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/leads":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_leads_dashboard().encode())
        elif self.path == "/" or self.path == "/dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_dashboard().encode())
        elif self.path == "/api/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            stats = get_db_stats()
            stats["services"] = get_service_status()
            stats["db_size"] = get_db_size()
            self.wfile.write(json.dumps(stats, default=str).encode())
        elif self.path == "/api/feed":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            feed = get_recent_scores(15)
            snapshots = get_snapshot_stats()
            self.wfile.write(json.dumps({"feed": feed, "snapshots": snapshots}, default=str).encode())
        elif self.path == "/api/health":
            stats = get_db_stats()
            healthy = stats.get("pipeline_healthy", False)
            self.send_response(200 if healthy else 503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "healthy": healthy,
                "mins_since_last": stats.get("mins_since_last"),
                "total_scores": stats.get("total_scores"),
            }).encode())
        elif self.path.startswith("/api/lookup"):
            # Lookup pre-scored results by domain (for shareable links)
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            domain = qs.get("domain", [""])[0].strip().lower()
            domain = domain.replace("https://", "").replace("http://", "").rstrip("/")

            if not domain:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "domain parameter required"}).encode())
                return

            # Query database for this domain
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            biz = conn.execute(
                "SELECT id, domain, business_name, vertical, city, state FROM businesses WHERE domain = ?",
                (domain,)
            ).fetchone()

            if not biz:
                # Try with www prefix or without
                alt_domain = ("www." + domain) if not domain.startswith("www.") else domain[4:]
                biz = conn.execute(
                    "SELECT id, domain, business_name, vertical, city, state FROM businesses WHERE domain = ?",
                    (alt_domain,)
                ).fetchone()

            if not biz:
                conn.close()
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Domain not found in database", "domain": domain}).encode())
                return

            # Get most recent score
            score_row = conn.execute(
                """SELECT id, composite_score, grade, raw_json, timestamp, methodology_version
                   FROM scores WHERE business_id = ? ORDER BY timestamp DESC LIMIT 1""",
                (biz["id"],)
            ).fetchone()
            conn.close()

            if not score_row:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No scores found for domain", "domain": domain}).encode())
                return

            # v6 gated payload: tier 1 by default, tier 2 only after email capture.
            raw_json = score_row["raw_json"] or "{}"
            try:
                raw = json.loads(raw_json)
            except (json.JSONDecodeError, TypeError):
                raw = {}

            gated = build_gated_score_payload(
                raw,
                score_row["composite_score"],
                score_row["grade"],
                email_unlocked=False,  # domain lookup is always tier1; capture_email unlocks tier2
            )

            # Dynamic business count for credibility
            try:
                from storage import get_score_count
                _count = get_score_count()
                _rounded = (_count // 10_000) * 10_000
                biz_label = f"{_rounded:,}+"
            except Exception:
                biz_label = "330,000+"

            result = {
                "status": "complete",
                "composite_score": score_row["composite_score"],
                "grade": score_row["grade"],
                "source": "database",
                "businesses_scored_label": biz_label,
                "gated": gated,
                "score_data": {
                    "domain": biz["domain"],
                    "business_name": biz["business_name"],
                    "vertical": biz["vertical"],
                    "city": biz["city"],
                    "state": biz["state"],
                },
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(result, default=str).encode())

        elif self.path.startswith("/api/results/"):
            scan_id = self.path.split("/api/results/")[-1].split("?")[0]
            result = get_scan_with_scores(scan_id)
            if result:
                # v6 gated payload: tier1 by default; tier2 unlocked if scan already has captured email.
                email_unlocked = bool(result.get("email"))
                if result.get("score_data") and result["score_data"].get("raw_json"):
                    try:
                        raw = json.loads(result["score_data"]["raw_json"])
                    except (json.JSONDecodeError, TypeError):
                        raw = {}
                    composite = result["score_data"].get("composite_score")
                    grade = result["score_data"].get("grade")
                    result["gated"] = build_gated_score_payload(
                        raw,
                        composite,
                        grade,
                        email_unlocked=email_unlocked,
                    )
                    # Strip raw_json from client response -- gated payload is the sanitized contract.
                    result["score_data"].pop("raw_json", None)
                # Dynamic business count for credibility
                try:
                    from storage import get_score_count
                    _count = get_score_count()
                    _rounded = (_count // 10_000) * 10_000
                    result["businesses_scored_label"] = f"{_rounded:,}+"
                except Exception:
                    result["businesses_scored_label"] = "330,000+"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(result, default=str).encode())
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Scan not found"}).encode())
        elif self.path == "/api/scan-stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            stats = get_scan_stats()
            self.wfile.write(json.dumps(stats).encode())
        elif self.path.startswith("/api/city-stats"):
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            city = qs.get("city", [""])[0].strip()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if not city:
                self.wfile.write(json.dumps({"error": "city parameter required"}).encode())
                return
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            try:
                verticals = conn.execute(
                    "SELECT DISTINCT vertical FROM businesses WHERE city = ? AND vertical IS NOT NULL AND vertical != ''",
                    (city,)
                ).fetchall()
                biz_count = conn.execute(
                    "SELECT COUNT(*) FROM businesses WHERE city = ?", (city,)
                ).fetchone()[0]
                self.wfile.write(json.dumps({
                    "city": city,
                    "vertical_count": len(verticals),
                    "verticals": [r["vertical"] for r in verticals],
                    "business_count": biz_count,
                }).encode())
            finally:
                conn.close()
        elif self.path.startswith("/api/og-image"):
            # Dynamic OG image for social sharing
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            domain = qs.get("domain", [""])[0].strip().lower()
            domain = domain.replace("https://", "").replace("http://", "").rstrip("/")

            if not domain:
                self.send_response(400)
                self.end_headers()
                return

            # Look up score
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            biz = conn.execute(
                "SELECT id FROM businesses WHERE domain = ?", (domain,)
            ).fetchone()
            if not biz:
                alt = ("www." + domain) if not domain.startswith("www.") else domain[4:]
                biz = conn.execute(
                    "SELECT id FROM businesses WHERE domain = ?", (alt,)
                ).fetchone()

            score_val, grade_val = 0, "?"
            if biz:
                sr = conn.execute(
                    "SELECT composite_score, grade FROM scores WHERE business_id = ? ORDER BY timestamp DESC LIMIT 1",
                    (biz["id"],)
                ).fetchone()
                if sr:
                    score_val = int(round(sr["composite_score"] or 0))
                    grade_val = sr["grade"] or "?"
            conn.close()

            # Generate image with Pillow
            from PIL import Image, ImageDraw, ImageFont
            import io, math

            W, H = 1200, 630
            img = Image.new("RGB", (W, H), "#ffffff")
            draw = ImageDraw.Draw(img)

            # Fonts
            try:
                font_bold_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 120)
                font_bold_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
                font_bold_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
                font_reg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
                font_reg_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
            except Exception:
                font_bold_lg = font_bold_md = font_bold_sm = font_reg = font_reg_sm = ImageFont.load_default()

            grade_colors = {
                "A": "#22863a", "B": "#4d7c0f", "C": "#c27803",
                "D": "#c2410c", "F": "#e53e3e",
            }
            score_color = grade_colors.get(grade_val, "#e53e3e")

            # Draw gauge ring
            cx, cy, r = 340, 280, 140
            # Background ring
            draw.ellipse([cx-r-12, cy-r-12, cx+r+12, cy+r+12], outline="#e8eaff", width=16)
            # Score arc
            pct = min(score_val / 100.0, 1.0)
            start_angle = -90
            end_angle = start_angle + int(360 * pct)
            draw.arc([cx-r-12, cy-r-12, cx+r+12, cy+r+12], start_angle, end_angle, fill=score_color, width=16)

            # Score number centered in ring
            score_text = str(int(round(score_val)))
            bbox = draw.textbbox((0, 0), score_text, font=font_bold_lg)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((cx - tw // 2, cy - th // 2 - 20), score_text, fill="#1a202c", font=font_bold_lg)
            # /100
            bbox2 = draw.textbbox((0, 0), "/100", font=font_reg)
            tw2 = bbox2[2] - bbox2[0]
            draw.text((cx - tw2 // 2, cy + th // 2 - 10), "/100", fill="#a0aec0", font=font_reg)

            # Grade badge
            grade_text = f"Grade: {grade_val}"
            bbox3 = draw.textbbox((0, 0), grade_text, font=font_bold_sm)
            tw3 = bbox3[2] - bbox3[0]
            draw.text((cx - tw3 // 2, cy + r + 30), grade_text, fill=score_color, font=font_bold_sm)

            # Right side text
            rx = 560
            # Domain
            draw.text((rx, 140), domain, fill="#a0aec0", font=font_reg_sm)
            # Title
            draw.text((rx, 180), "AI Agent Optimization", fill="#1a202c", font=font_bold_md)
            draw.text((rx, 240), "Score", fill="#1a202c", font=font_bold_md)

            # Tagline
            if score_val >= 90:
                tagline = "Agent Preferred. AI agents choose this business first."
            elif score_val >= 70:
                tagline = "Agent Optimized. AI agents can transact reliably."
            elif score_val >= 50:
                tagline = "Agent Ready. AI agents can work with some friction."
            elif score_val >= 30:
                tagline = "Agent Functional. AI agents struggle to complete tasks."
            elif score_val >= 10:
                tagline = "Agent Detected. AI agents can find but not transact."
            else:
                tagline = "Agent Incompatible. AI agents skip this business entirely."
            draw.text((rx, 320), tagline, fill="#4a5568", font=font_reg)

            # CTA
            draw.text((rx, 390), "Get your free score at gradeforai.com", fill="#4353ff", font=font_reg_sm)

            # Bottom bar
            draw.rectangle([0, H - 50, W, H], fill="#4353ff")
            bbox4 = draw.textbbox((0, 0), "Scored by GradeForAI", font=font_bold_sm)
            tw4 = bbox4[2] - bbox4[0]
            draw.text((W // 2 - tw4 // 2, H - 42), "Scored by GradeForAI", fill="#ffffff", font=font_bold_sm)

            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            buf.seek(0)
            img_data = buf.read()

            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(img_data)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(img_data)

        elif self.path.startswith("/api/share"):
            # Share page with dynamic OG tags for LinkedIn/Twitter previews
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            domain = qs.get("domain", [""])[0].strip().lower()
            domain = domain.replace("https://", "").replace("http://", "").rstrip("/")

            if not domain:
                self.send_response(302)
                self.send_header("Location", "https://gradeforai.com")
                self.end_headers()
                return

            # Look up score for OG tags
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            biz = conn.execute(
                "SELECT id FROM businesses WHERE domain = ?", (domain,)
            ).fetchone()
            if not biz:
                alt = ("www." + domain) if not domain.startswith("www.") else domain[4:]
                biz = conn.execute(
                    "SELECT id FROM businesses WHERE domain = ?", (alt,)
                ).fetchone()

            score_val, grade_val = 0, "?"
            if biz:
                sr = conn.execute(
                    "SELECT composite_score, grade FROM scores WHERE business_id = ? ORDER BY timestamp DESC LIMIT 1",
                    (biz["id"],)
                ).fetchone()
                if sr:
                    score_val = int(round(sr["composite_score"] or 0))
                    grade_val = sr["grade"] or "?"
            conn.close()

            safe_domain = domain.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
            og_image_url = f"https://gradeforai.com/api/og-image?domain={domain}"
            results_url = "https://gradeforai.com"

            html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{safe_domain} scored {score_val}/100 on AI Agent Optimization | GradeForAI</title>
<meta property="og:title" content="{safe_domain} scored {score_val}/100 (Grade: {grade_val}) on AI Agent Optimization">
<meta property="og:description" content="Is your business ready for AI agents? Get your free AI Agent Optimization score at gradeforai.com">
<meta property="og:image" content="{og_image_url}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:url" content="https://gradeforai.com/api/share?domain={safe_domain}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="GradeForAI">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{safe_domain} scored {score_val}/100 on AI Agent Optimization">
<meta name="twitter:description" content="Is your business ready for AI agents? Get your free score at gradeforai.com">
<meta name="twitter:image" content="{og_image_url}">
<meta http-equiv="refresh" content="0;url={results_url}">
</head>
<body>
<p>Redirecting to <a href="{results_url}">your results</a>...</p>
</body>
</html>"""

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress request logging


def main():
    parser = argparse.ArgumentParser(description="Pipeline monitoring dashboard")
    parser.add_argument("--port", type=int, default=8050, help="Port (default: 8050)")
    args = parser.parse_args()

    # Initialize database (creates scans table if needed)
    init_db()

    server = HTTPServer(("0.0.0.0", args.port), DashboardHandler)
    print(f"Dashboard running at http://localhost:{args.port}")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
