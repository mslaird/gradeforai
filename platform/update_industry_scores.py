#!/usr/bin/env python3
"""
Queries scores.db and regenerates website/industry_data.json with current averages.

Run on VPS where the full database lives:
    python3 update_industry_scores.py

Or specify a custom DB path:
    python3 update_industry_scores.py --db /path/to/scores.db

After running, rebuild the site:
    python3 website/build.py
"""

import argparse
import json
import math
import os
import sqlite3
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(SCRIPT_DIR, "data", "scores.db")
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "website", "industry_data.json")

# Map vertical names in DB to our canonical keys
VERTICAL_MAP = {
    "plumber": "plumbing",
    "plumbing": "plumbing",
    "hvac": "hvac",
    "dentist": "dental",
    "dental": "dental",
    "lawyer": "legal",
    "legal": "legal",
    "auto repair": "auto_repair",
    "auto_repair": "auto_repair",
    "roofing": "roofing",
    "roofer": "roofing",
    "cleaning service": "cleaning",
    "cleaning": "cleaning",
    "electrician": "electrical",
    "electrical": "electrical",
    "pest control": "pest_control",
    "landscaping": "landscaping",
    "medical practice": "medical",
    "medical": "medical",
    "med spa": "med_spa",
}

# Industry pages we generate (must have data)
INDUSTRY_PAGES = ["plumbing", "hvac", "dental", "legal", "auto_repair", "roofing"]

# Cities we have pages for
CITY_NAMES = {
    "dallas": ["Dallas", "Fort Worth", "Plano", "Arlington", "Frisco", "McKinney", "Irving", "Garland", "Grand Prairie", "Mesquite", "Denton", "Carrollton", "Lewisville", "Allen", "Flower Mound", "Richardson"],
    "houston": ["Houston", "Sugar Land", "Pasadena", "Pearland", "League City", "Baytown", "Missouri City", "Conroe", "Spring"],
    "phoenix": ["Phoenix", "Mesa", "Scottsdale", "Chandler", "Tempe", "Gilbert", "Glendale", "Peoria", "Surprise"],
    "chicago": ["Chicago", "Naperville", "Aurora", "Joliet", "Elgin", "Evanston", "Schaumburg", "Arlington Heights"],
    "denver": ["Denver", "Aurora", "Lakewood", "Thornton", "Arvada", "Westminster", "Centennial", "Boulder", "Longmont"],
    "miami": ["Miami", "Fort Lauderdale", "Hialeah", "Hollywood", "Coral Springs", "Pembroke Pines", "Miramar", "Doral"],
}

# What verticals to show per city page
CITY_VERTICALS = {
    "dallas": ["plumbing", "hvac", "dental", "legal", "auto_repair", "roofing"],
    "houston": ["auto_repair", "hvac", "plumbing", "medical", "roofing", "cleaning"],
    "phoenix": ["hvac", "roofing", "plumbing", "landscaping", "auto_repair", "cleaning"],
    "chicago": ["legal", "dental", "cleaning", "auto_repair", "plumbing", "hvac"],
    "denver": ["roofing", "hvac", "plumbing", "landscaping", "cleaning", "auto_repair"],
    "miami": ["dental", "med_spa", "legal", "cleaning", "hvac", "auto_repair"],
}


def grade_from_score(score):
    """Capability band system. Boundaries updated for methodology v6."""
    if score >= 90: return "Agent Preferred"
    if score >= 70: return "Agent Optimized"
    if score >= 50: return "Agent Ready"
    if score >= 30: return "Agent Functional"
    if score >= 10: return "Agent Detected"
    return "Agent Incompatible"


def fmt_count(n):
    """Format count for public display.

    For business totals (>= 10,000) we floor to the nearest 10,000 so the
    marketing number can never overstate the scored dataset. The "+" suffix is
    added by consuming templates (e.g. footer.html writes `{{BUSINESS_COUNT}}+`).

    Smaller counts (per-city, per-vertical) round to the nearest 100 so the
    legacy city/industry copy stays readable.
    """
    if n >= 10000:
        return f"{(n // 10000) * 10000:,}"
    if n >= 1000:
        return f"{round(n / 100) * 100:,}"
    return str(n)


def query_averages(cursor, where_clause="1=1", params=None):
    """Get average scores for a WHERE clause."""
    if params is None:
        params = []
    sql = f"""
        SELECT
            COUNT(DISTINCT b.id) as cnt,
            ROUND(AVG(s.composite_score), 0) as avg_score,
            ROUND(AVG(s.agent_compatibility_score), 0) as avg_agent_compat,
            ROUND(AVG(s.transaction_readiness_score), 0) as avg_transaction,
            ROUND(AVG(s.agentic_commerce_score), 0) as avg_agentic,
            ROUND(AVG(s.operational_data_structure_score), 0) as avg_ops_data,
            ROUND(AVG(s.data_accuracy_score), 0) as avg_accuracy
        FROM scores s
        JOIN businesses b ON s.business_id = b.id
        WHERE s.methodology_version = '5.4'
          AND s.composite_score IS NOT NULL
          AND {where_clause}
    """
    cursor.execute(sql, params)
    row = cursor.fetchone()
    if not row or row[0] == 0:
        return None
    return {
        "count": int(row[0]),
        "avg": int(row[1] or 0),
        "agent_compat": int(row[2] or 0),
        "transaction": int(row[3] or 0),
        "agentic": int(row[4] or 0),
        "ops_data": int(row[5] or 0),
        "accuracy": int(row[6] or 0),
    }


def query_grade_distribution(cursor):
    """Get band distribution percentages."""
    cursor.execute("""
        SELECT grade, COUNT(*) as cnt
        FROM scores
        WHERE methodology_version = '5.4' AND composite_score IS NOT NULL
        GROUP BY grade
    """)
    rows = cursor.fetchall()
    total = sum(r[1] for r in rows)
    if total == 0:
        return None
    dist = {}
    for grade, cnt in rows:
        dist[grade] = {"count": cnt, "pct": round(cnt / total * 100)}
    return dist, total


def query_incompatible_pct(cursor, where_clause="1=1", params=None):
    """Get % scoring Agent Incompatible (0-24) for a filter."""
    if params is None:
        params = []
    cursor.execute(f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN s.composite_score < 25 THEN 1 ELSE 0 END) as low_count
        FROM scores s
        JOIN businesses b ON s.business_id = b.id
        WHERE s.methodology_version = '5.4'
          AND s.composite_score IS NOT NULL
          AND {where_clause}
    """, params)
    row = cursor.fetchone()
    if not row or row[0] == 0:
        return 0
    return round(row[1] / row[0] * 100)


def build_city_clause(city_key):
    """Build WHERE clause for city names."""
    names = CITY_NAMES.get(city_key, [])
    if not names:
        return "1=0", []
    placeholders = ",".join(["?"] * len(names))
    return f"b.city IN ({placeholders})", names


def canonical_vertical(v):
    """Map DB vertical name to canonical key."""
    if v is None:
        return None
    return VERTICAL_MAP.get(v.lower(), v.lower().replace(" ", "_"))


def vertical_where(canonical):
    """Build WHERE clause matching a canonical vertical."""
    db_names = [k for k, v in VERTICAL_MAP.items() if v == canonical]
    if not db_names:
        return "1=0", []
    placeholders = ",".join(["?"] * len(db_names))
    return f"LOWER(b.vertical) IN ({placeholders})", db_names


def main():
    parser = argparse.ArgumentParser(description="Update industry_data.json from scores.db")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to scores.db")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON without writing")
    args = parser.parse_args()

    # Auto-detect VPS path
    if not os.path.exists(args.db) and os.path.exists("/opt/agent-readiness/data/scores.db"):
        args.db = "/opt/agent-readiness/data/scores.db"
        print(f"Using VPS database: {args.db}")

    if not os.path.exists(args.db):
        print(f"Database not found: {args.db}")
        print("Run this script on the VPS where the full database lives.")
        sys.exit(1)

    conn = sqlite3.connect(args.db)
    cursor = conn.cursor()

    # Check we have v5 data
    cursor.execute("SELECT COUNT(*) FROM scores WHERE methodology_version = '5.4'")
    v5_count = cursor.fetchone()[0]
    if v5_count < 100:
        print(f"Only {v5_count} v5 scores found. Need at least 100 for meaningful averages.")
        print("Run the batch rescore first, then re-run this script.")
        sys.exit(1)

    print(f"Found {v5_count} v5 scores. Computing averages...")

    # Load existing JSON as fallback
    existing = {}
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON) as f:
            existing = json.load(f)

    data = {
        "meta": {
            "generated": datetime.now().strftime("%Y-%m-%d"),
            "source": args.db,
            "v5_scores": v5_count,
        }
    }

    # Total business count
    cursor.execute("SELECT COUNT(*) FROM businesses")
    total_businesses = cursor.fetchone()[0]
    data["business_count"] = fmt_count(total_businesses)
    data["business_count_raw"] = str(total_businesses)

    # City and vertical counts
    cursor.execute("SELECT COUNT(DISTINCT city) FROM businesses WHERE city IS NOT NULL AND city != ''")
    data["city_count"] = str(cursor.fetchone()[0])
    cursor.execute("SELECT COUNT(DISTINCT vertical) FROM businesses WHERE vertical IS NOT NULL AND vertical != ''")
    data["vertical_count"] = str(cursor.fetchone()[0])

    # National averages
    natl = query_averages(cursor)
    grade_dist = query_grade_distribution(cursor)
    if natl and grade_dist:
        dist, total = grade_dist
        data["national"] = {
            "avg": natl["avg"],
            "incompatible_pct": dist.get("Agent Incompatible", {}).get("pct", 0),
            "detected_pct": dist.get("Agent Detected", {}).get("pct", 0),
            "functional_pct": dist.get("Agent Functional", {}).get("pct", 0),
            "ready_pct": dist.get("Agent Ready", {}).get("pct", 0),
            "optimized_pct": dist.get("Agent Optimized", {}).get("pct", 0),
            "native_pct": dist.get("Agent Preferred", {}).get("pct", 0),
            "incompatible_count": fmt_count(dist.get("Agent Incompatible", {}).get("count", 0)),
            "detected_count": fmt_count(dist.get("Agent Detected", {}).get("count", 0)),
            "functional_count": fmt_count(dist.get("Agent Functional", {}).get("count", 0)),
            "ready_count": fmt_count(dist.get("Agent Ready", {}).get("count", 0)),
            "optimized_count": fmt_count(dist.get("Agent Optimized", {}).get("count", 0)),
            "native_count": fmt_count(dist.get("Agent Preferred", {}).get("count", 0)),
            "below_ready_pct": (dist.get("Agent Incompatible", {}).get("pct", 0) +
                                dist.get("Agent Detected", {}).get("pct", 0) +
                                dist.get("Agent Functional", {}).get("pct", 0)),
            "agent_compat": natl["agent_compat"],
            "transaction": natl["transaction"],
            "agentic": natl["agentic"],
            "ops_data": natl["ops_data"],
            "accuracy": natl["accuracy"],
            "no_llms_pct": existing.get("national", {}).get("no_llms_pct", 96),
            "no_schema_pct": existing.get("national", {}).get("no_schema_pct", 78),
            "no_structured_service_pct": existing.get("national", {}).get("no_structured_service_pct", 5),
        }
    else:
        data["national"] = existing.get("national", {})

    # Industry reference (all-industries avg per dimension, used on industry pages)
    if natl:
        data["industry_ref"] = {
            "_note": "All Industries Avg column used on industry pages (per-dimension)",
            "agent_compat": natl["agent_compat"],
            "transaction": natl["transaction"],
            "agentic": natl["agentic"],
            "ops_data": natl["ops_data"],
            "accuracy": natl["accuracy"],
        }
    else:
        data["industry_ref"] = existing.get("industry_ref", {})

    # Per-industry averages
    data["industries"] = {}
    for ind in INDUSTRY_PAGES:
        vw, vp = vertical_where(ind)
        result = query_averages(cursor, vw, vp)
        if result:
            data["industries"][ind] = {
                "avg": result["avg"],
                "grade": grade_from_score(result["avg"]),
                "agent_compat": result["agent_compat"],
                "transaction": result["transaction"],
                "agentic": result["agentic"],
                "ops_data": result["ops_data"],
                "accuracy": result["accuracy"],
            }
        else:
            data["industries"][ind] = existing.get("industries", {}).get(ind, {})

    # Benchmark verticals table
    data["benchmark_verticals"] = {}
    for vert_key in ["medical", "dental", "legal", "hvac", "cleaning", "plumbing",
                      "auto_repair", "roofing", "electrical", "pest_control"]:
        vw, vp = vertical_where(vert_key)
        result = query_averages(cursor, vw, vp)
        f_pct = query_incompatible_pct(cursor, vw, vp)
        if result:
            data["benchmark_verticals"][vert_key] = {
                "count": fmt_count(result["count"]),
                "avg": result["avg"],
                "grade": grade_from_score(result["avg"]),
                "f_pct": f_pct,
            }
        else:
            data["benchmark_verticals"][vert_key] = existing.get("benchmark_verticals", {}).get(vert_key, {})

    # City averages
    data["cities"] = {}
    for city_key in CITY_NAMES:
        cw, cp = build_city_clause(city_key)
        city_result = query_averages(cursor, cw, cp)
        city_f_pct = query_incompatible_pct(cursor, cw, cp)

        if city_result and city_result["count"] >= 10:
            city_data = {
                "avg": city_result["avg"],
                "f_pct": city_f_pct,
                "verticals": {},
            }

            for vert_key in CITY_VERTICALS.get(city_key, []):
                vw, vp = vertical_where(vert_key)
                combined_where = f"({cw}) AND ({vw})"
                combined_params = cp + vp
                vert_result = query_averages(cursor, combined_where, combined_params)
                if vert_result:
                    below = city_result["avg"] - vert_result["avg"]
                    city_data["verticals"][vert_key] = {
                        "avg": vert_result["avg"],
                        "grade": grade_from_score(vert_result["avg"]),
                        "below_avg": max(0, below),
                        "gap": existing.get("cities", {}).get(city_key, {}).get("verticals", {}).get(vert_key, {}).get("gap", "Transaction Readiness"),
                    }
                else:
                    city_data["verticals"][vert_key] = existing.get("cities", {}).get(city_key, {}).get("verticals", {}).get(vert_key, {})

            data["cities"][city_key] = city_data
        else:
            data["cities"][city_key] = existing.get("cities", {}).get(city_key, {})

    output = json.dumps(data, indent=4)

    if args.dry_run:
        print(output)
    else:
        with open(OUTPUT_JSON, "w") as f:
            f.write(output + "\n")
        print(f"Written to {OUTPUT_JSON}")
        print("Now run: python3 website/build.py")

    conn.close()


if __name__ == "__main__":
    main()
