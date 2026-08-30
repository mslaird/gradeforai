"""
SQLite-based storage for Agent Readiness benchmark data collection.
Database: ~/agent-readiness/data/scores.db
"""

import sqlite3
import json
import os
import csv
import statistics
from datetime import datetime, timezone
from pathlib import Path

DB_DIR = "/opt/agent-readiness/data" if os.path.exists("/opt/agent-readiness/data/scores.db") else os.path.expanduser("~/agent-readiness/data")
DB_PATH = os.path.join(DB_DIR, "scores.db")

DIMENSION_COLUMNS = [
    "agent_compatibility_score",
    "transaction_readiness_score",
    "agentic_commerce_score",
    "operational_data_structure_score",
    "data_accuracy_score",
    "competitive_position_score",
]

# Legacy v3 columns (kept for backward compat with 337K existing scores)
LEGACY_DIMENSION_COLUMNS = [
    "discoverability_score",
    "service_clarity_score",
    "bookability_score",
    "contactability_score",
    "quotability_score",
    "verifiability_score",
    "payability_score",
    "competitive_position_score",
]


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if not exist and ensure data directory exists."""
    os.makedirs(DB_DIR, exist_ok=True)

    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                domain TEXT NOT NULL UNIQUE,
                business_name TEXT,
                city TEXT,
                state TEXT,
                vertical TEXT,
                phone TEXT,
                address TEXT,
                rating REAL,
                review_count INTEGER,
                first_scored TEXT NOT NULL,
                last_scored TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                composite_score REAL,
                grade TEXT,
                discoverability_score REAL,
                service_clarity_score REAL,
                bookability_score REAL,
                contactability_score REAL,
                quotability_score REAL,
                verifiability_score REAL,
                payability_score REAL,
                raw_json TEXT,
                FOREIGN KEY (business_id) REFERENCES businesses(id)
            );

            CREATE INDEX IF NOT EXISTS idx_scores_business_id ON scores(business_id);
            CREATE INDEX IF NOT EXISTS idx_scores_timestamp ON scores(timestamp);
            CREATE INDEX IF NOT EXISTS idx_scores_grade ON scores(grade);
            CREATE INDEX IF NOT EXISTS idx_scores_methodology ON scores(methodology_version);
            CREATE INDEX IF NOT EXISTS idx_businesses_domain ON businesses(domain);
            CREATE INDEX IF NOT EXISTS idx_businesses_vertical ON businesses(vertical);
            CREATE INDEX IF NOT EXISTS idx_businesses_city_state ON businesses(city, state);

            CREATE TABLE IF NOT EXISTS scans (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                email TEXT,
                status TEXT DEFAULT 'scanning',
                composite_score REAL,
                grade TEXT,
                score_id INTEGER,
                error TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT,
                email TEXT,
                event_type TEXT NOT NULL,
                payload TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS contact_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                source TEXT DEFAULT 'unknown',
                subscribed_at TEXT NOT NULL DEFAULT (datetime('now')),
                unsubscribed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);

            -- Append-only observation tables (Layer 5/6/7/8)

            CREATE TABLE IF NOT EXISTS google_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                observed_at TEXT NOT NULL,
                google_rating REAL,
                google_review_count INTEGER,
                google_business_status TEXT,
                google_maps_uri TEXT,
                google_types TEXT,
                google_hours TEXT,
                google_photo_count INTEGER,
                FOREIGN KEY (business_id) REFERENCES businesses(id)
            );
            CREATE INDEX IF NOT EXISTS idx_google_obs_biz ON google_observations(business_id);
            CREATE INDEX IF NOT EXISTS idx_google_obs_ts ON google_observations(observed_at);

            CREATE TABLE IF NOT EXISTS scan_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                observed_at TEXT NOT NULL,
                http_status_code INTEGER,
                response_time_ms INTEGER,
                ssl_valid INTEGER,
                redirect_chain TEXT,
                final_url TEXT,
                cms_detected TEXT,
                payment_platforms TEXT,
                chat_platforms TEXT,
                review_platforms TEXT,
                analytics_platforms TEXT,
                form_platforms TEXT,
                social_links TEXT,
                technology_stack TEXT,
                FOREIGN KEY (business_id) REFERENCES businesses(id)
            );
            CREATE INDEX IF NOT EXISTS idx_scan_obs_biz ON scan_observations(business_id);
            CREATE INDEX IF NOT EXISTS idx_scan_obs_ts ON scan_observations(observed_at);

            CREATE TABLE IF NOT EXISTS technology_change_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                detected_at TEXT NOT NULL,
                change_type TEXT NOT NULL,
                category TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                FOREIGN KEY (business_id) REFERENCES businesses(id)
            );
            CREATE INDEX IF NOT EXISTS idx_tech_changes_biz ON technology_change_events(business_id);
            CREATE INDEX IF NOT EXISTS idx_tech_changes_ts ON technology_change_events(detected_at);
        """)

        # Migrate: add new columns to existing databases
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(businesses)").fetchall()}
        migrations = [
            ("phone", "TEXT"),
            ("address", "TEXT"),
            ("rating", "REAL"),
            ("review_count", "INTEGER"),
        ]
        for col_name, col_type in migrations:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE businesses ADD COLUMN {col_name} {col_type}")

        # Migrate scores table: add methodology_version column
        score_cols = {row[1] for row in conn.execute("PRAGMA table_info(scores)").fetchall()}
        if "methodology_version" not in score_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN methodology_version TEXT")

        # Migrate scores table: add competitive_position_score column
        if "competitive_position_score" not in score_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN competitive_position_score REAL")

        # Migrate scores table: add v5 dimension columns
        v5_columns = [
            ("agent_compatibility_score", "REAL"),
            ("transaction_readiness_score", "REAL"),
            ("agentic_commerce_score", "REAL"),
            ("operational_data_structure_score", "REAL"),
            ("data_accuracy_score", "REAL"),
        ]
        for col_name, col_type in v5_columns:
            if col_name not in score_cols:
                conn.execute(f"ALTER TABLE scores ADD COLUMN {col_name} {col_type}")

        # v6 Phase 1: Booking platform detection columns on businesses table
        v6_biz_columns = [
            ("booking_platform", "TEXT"),
            ("booking_platform_confidence", "TEXT"),
            ("has_online_booking", "INTEGER"),
            ("booking_detection_signals", "TEXT"),
            ("booking_scan_date", "TEXT"),
            ("booking_platform_grade", "INTEGER"),
        ]
        for col_name, col_type in v6_biz_columns:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE businesses ADD COLUMN {col_name} {col_type}")

        # v6 Phase 1: Booking platform columns on scores table (for historical tracking)
        v6_score_columns = [
            ("booking_platform", "TEXT"),
            ("booking_platform_confidence", "TEXT"),
            ("has_online_booking", "INTEGER"),
            ("booking_platform_grade", "INTEGER"),
        ]
        for col_name, col_type in v6_score_columns:
            if col_name not in score_cols:
                conn.execute(f"ALTER TABLE scores ADD COLUMN {col_name} {col_type}")

        # v6 Phase 2: Transaction path mapping columns on businesses table
        v6p2_biz_columns = [
            ("transaction_path_score", "INTEGER"),
            ("transaction_stages_present", "TEXT"),
            ("transaction_stages_missing", "TEXT"),
            ("transaction_failure_points", "TEXT"),
            ("contact_methods", "TEXT"),
            ("has_visible_pricing", "INTEGER"),
            ("has_online_payment", "INTEGER"),
            ("has_quote_request", "INTEGER"),
            ("transaction_scan_date", "TEXT"),
        ]
        for col_name, col_type in v6p2_biz_columns:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE businesses ADD COLUMN {col_name} {col_type}")

        # Price spectrum columns on businesses table
        price_biz_columns = [
            ("price_tier", "TEXT"),
            ("price_signals", "TEXT"),
            ("price_confidence", "TEXT"),
        ]
        for col_name, col_type in price_biz_columns:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE businesses ADD COLUMN {col_name} {col_type}")

        # v6 Phase 2: Transaction path score on scores table (for historical tracking)
        if "transaction_path_score" not in score_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN transaction_path_score INTEGER")

        # Price tier on scores table (for historical tracking)
        if "price_tier" not in score_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN price_tier TEXT")

        # v6 Phase 3: Entity coherence columns on businesses table
        v6p3_biz_columns = [
            ("entity_coherence_score", "REAL"),
            ("entity_name_match", "TEXT"),
            ("entity_address_match", "TEXT"),
            ("entity_phone_match", "TEXT"),
            ("entity_gbp_place_id", "TEXT"),
            ("entity_scan_date", "TEXT"),
        ]
        for col_name, col_type in v6p3_biz_columns:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE businesses ADD COLUMN {col_name} {col_type}")

        # v6 Phase 3: Entity coherence score on scores table (for historical tracking)
        if "entity_coherence_score" not in score_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN entity_coherence_score REAL")

        # v6 Phase 4: AI Agent Preference Score columns
        v6p4_biz_columns = [
            ("ai_preference_score", "REAL"),
            ("ai_preference_dimensions", "TEXT"),
            ("ai_preference_scan_date", "TEXT"),
        ]
        for col_name, col_type in v6p4_biz_columns:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE businesses ADD COLUMN {col_name} {col_type}")

        if "ai_preference_score" not in score_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN ai_preference_score REAL")

        # v6.3: Longitudinal observation columns on scan_observations (additive only)
        scan_obs_cols = {row[1] for row in conn.execute("PRAGMA table_info(scan_observations)").fetchall()}
        v63_scan_columns = [
            ("has_llms_txt", "INTEGER"),
            ("has_agent_json", "INTEGER"),
            ("has_agents_txt", "INTEGER"),
            ("has_ucp", "INTEGER"),
            ("has_acp", "INTEGER"),
            ("has_mcp", "INTEGER"),
            ("robots_ai_bot_policies", "TEXT"),
            ("transaction_stages", "TEXT"),
            ("contact_methods", "TEXT"),
            ("schema_types", "TEXT"),
            ("schema_type_count", "INTEGER"),
            ("price_tier", "TEXT"),
            ("contact_method_count", "INTEGER"),
        ]
        for col_name, col_type in v63_scan_columns:
            if col_name not in scan_obs_cols:
                conn.execute(f"ALTER TABLE scan_observations ADD COLUMN {col_name} {col_type}")

        conn.commit()
    finally:
        conn.close()


def _detect_technology_changes(conn, business_id, now, score_result):
    """
    Compare current technology data against the most recent scan observation
    for this business. Insert change events for any additions, removals, or changes.
    Uses the same connection (no commit -- caller commits).
    """
    prev = conn.execute(
        """SELECT cms_detected, payment_platforms, chat_platforms,
                  review_platforms, analytics_platforms, form_platforms, social_links
           FROM scan_observations
           WHERE business_id = ?
           ORDER BY observed_at DESC LIMIT 1 OFFSET 1""",
        (business_id,),
    ).fetchone()

    if not prev:
        return  # First scan for this business -- no comparison possible

    # Categories to compare (list-type fields)
    list_categories = {
        "payment": ("payment_platforms", score_result.get("payment_platforms", [])),
        "chat": ("chat_platforms", score_result.get("chat_platforms", [])),
        "review": ("review_platforms", score_result.get("review_platforms", [])),
        "analytics": ("analytics_platforms", score_result.get("analytics_platforms", [])),
        "form": ("form_platforms", score_result.get("form_platforms", [])),
    }

    for category, (field, current_list) in list_categories.items():
        prev_raw = prev[field]
        prev_list = json.loads(prev_raw) if prev_raw else []
        prev_set = set(prev_list)
        current_set = set(current_list)

        for added in current_set - prev_set:
            conn.execute(
                """INSERT INTO technology_change_events
                   (business_id, detected_at, change_type, category, old_value, new_value)
                   VALUES (?, ?, 'added', ?, NULL, ?)""",
                (business_id, now, category, added),
            )
        for removed in prev_set - current_set:
            conn.execute(
                """INSERT INTO technology_change_events
                   (business_id, detected_at, change_type, category, old_value, new_value)
                   VALUES (?, ?, 'removed', ?, ?, NULL)""",
                (business_id, now, category, removed),
            )

    # CMS: single-value field
    prev_cms = prev["cms_detected"]
    current_cms = score_result.get("cms_detected")
    if prev_cms != current_cms and (prev_cms or current_cms):
        change_type = "changed" if (prev_cms and current_cms) else ("added" if current_cms else "removed")
        conn.execute(
            """INSERT INTO technology_change_events
               (business_id, detected_at, change_type, category, old_value, new_value)
               VALUES (?, ?, ?, 'cms', ?, ?)""",
            (business_id, now, change_type, prev_cms, current_cms),
        )

    # Social links: dict-type field
    prev_social_raw = prev["social_links"]
    prev_social = json.loads(prev_social_raw) if prev_social_raw else {}
    current_social = score_result.get("social_links", {})
    all_platforms = set(list(prev_social.keys()) + list(current_social.keys()))
    for platform in all_platforms:
        old_val = prev_social.get(platform)
        new_val = current_social.get(platform)
        if old_val != new_val:
            if old_val and new_val:
                change_type = "changed"
            elif new_val:
                change_type = "added"
            else:
                change_type = "removed"
            conn.execute(
                """INSERT INTO technology_change_events
                   (business_id, detected_at, change_type, category, old_value, new_value)
                   VALUES (?, ?, ?, 'social', ?, ?)""",
                (business_id, now, change_type, old_val, new_val),
            )


def save_score(score_result: dict, vertical: str = None, city: str = None, state: str = None,
               business_name: str = None, phone: str = None, address: str = None,
               rating: float = None, review_count: int = None) -> int:
    """
    Save a scoring result. Creates or updates the business record.
    Returns the score ID.

    score_result should contain at minimum:
        - url, domain
        - composite_score, grade
        - dimensions dict with keys matching DIMENSION_COLUMNS (without _score suffix)

    Harvester enrichment data (business_name, phone, address, rating, review_count)
    can be passed as separate kwargs and will be stored on the business record.
    """
    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        domain = score_result.get("domain", "")
        url = score_result.get("url", "")
        # Prefer explicit kwarg, fall back to score_result, then empty
        biz_name = business_name or score_result.get("business_name", "") or ""

        # v6 Phase 1: Extract booking platform data from score_result
        booking_platform = score_result.get("booking_platform")
        booking_platform_confidence = score_result.get("booking_platform_confidence")
        has_online_booking = 1 if score_result.get("has_online_booking") else 0
        booking_detection_signals = json.dumps(score_result.get("booking_detection_signals", []))
        booking_scan_date = score_result.get("booking_scan_date")
        booking_platform_grade = score_result.get("booking_platform_grade", 0)

        # v6 Phase 2: Extract transaction path data from score_result
        transaction_path_score = score_result.get("transaction_path_score", 0)
        transaction_stages_present = json.dumps(score_result.get("transaction_stages_present", []))
        transaction_stages_missing = json.dumps(score_result.get("transaction_stages_missing", []))
        transaction_failure_points = json.dumps(score_result.get("transaction_failure_points", []))
        contact_methods = json.dumps(score_result.get("contact_methods", []))
        has_visible_pricing = 1 if score_result.get("has_visible_pricing") else 0
        has_online_payment = 1 if score_result.get("has_online_payment") else 0
        has_quote_request = 1 if score_result.get("has_quote_request") else 0
        transaction_scan_date = score_result.get("transaction_scan_date")

        # Price spectrum data
        price_tier = score_result.get("price_tier")
        price_signals = json.dumps(score_result.get("price_signals", []))
        price_confidence = score_result.get("price_confidence")

        # v6 Phase 3: Extract entity coherence data from score_result
        entity_coherence_score = score_result.get("entity_coherence_score")
        entity_name_match = score_result.get("entity_name_match")
        entity_address_match = score_result.get("entity_address_match")
        entity_phone_match = score_result.get("entity_phone_match")
        entity_gbp_place_id = score_result.get("entity_gbp_place_id")
        entity_scan_date = score_result.get("entity_scan_date")

        # v6 Phase 4: Extract AI Agent Preference Score data
        ai_preference_score = score_result.get("ai_preference_score")
        ai_preference_dimensions = json.dumps(score_result.get("ai_preference_dimensions", {}))
        ai_preference_scan_date = score_result.get("ai_preference_scan_date")

        # Upsert business record
        row = conn.execute("SELECT id FROM businesses WHERE domain = ?", (domain,)).fetchone()
        if row:
            business_id = row["id"]
            conn.execute(
                """UPDATE businesses
                   SET url = ?, last_scored = ?,
                       business_name = COALESCE(NULLIF(?, ''), business_name),
                       city = COALESCE(?, city),
                       state = COALESCE(?, state),
                       vertical = COALESCE(?, vertical),
                       phone = COALESCE(?, phone),
                       address = COALESCE(?, address),
                       rating = COALESCE(?, rating),
                       review_count = COALESCE(?, review_count),
                       booking_platform = ?,
                       booking_platform_confidence = ?,
                       has_online_booking = ?,
                       booking_detection_signals = ?,
                       booking_scan_date = ?,
                       booking_platform_grade = ?,
                       transaction_path_score = ?,
                       transaction_stages_present = ?,
                       transaction_stages_missing = ?,
                       transaction_failure_points = ?,
                       contact_methods = ?,
                       has_visible_pricing = ?,
                       has_online_payment = ?,
                       has_quote_request = ?,
                       transaction_scan_date = ?,
                       price_tier = ?,
                       price_signals = ?,
                       price_confidence = ?,
                       entity_coherence_score = COALESCE(?, entity_coherence_score),
                       entity_name_match = COALESCE(?, entity_name_match),
                       entity_address_match = COALESCE(?, entity_address_match),
                       entity_phone_match = COALESCE(?, entity_phone_match),
                       entity_gbp_place_id = COALESCE(?, entity_gbp_place_id),
                       entity_scan_date = COALESCE(?, entity_scan_date),
                       ai_preference_score = ?,
                       ai_preference_dimensions = ?,
                       ai_preference_scan_date = ?
                   WHERE id = ?""",
                (url, now, biz_name, city, state, vertical, phone, address, rating, review_count,
                 booking_platform, booking_platform_confidence, has_online_booking,
                 booking_detection_signals, booking_scan_date, booking_platform_grade,
                 transaction_path_score, transaction_stages_present, transaction_stages_missing,
                 transaction_failure_points, contact_methods, has_visible_pricing,
                 has_online_payment, has_quote_request, transaction_scan_date,
                 price_tier, price_signals, price_confidence,
                 entity_coherence_score, entity_name_match, entity_address_match,
                 entity_phone_match, entity_gbp_place_id, entity_scan_date,
                 ai_preference_score, ai_preference_dimensions, ai_preference_scan_date,
                 business_id),
            )
        else:
            cur = conn.execute(
                """INSERT INTO businesses (url, domain, business_name, city, state, vertical,
                   phone, address, rating, review_count, first_scored, last_scored,
                   booking_platform, booking_platform_confidence, has_online_booking,
                   booking_detection_signals, booking_scan_date, booking_platform_grade,
                   transaction_path_score, transaction_stages_present, transaction_stages_missing,
                   transaction_failure_points, contact_methods, has_visible_pricing,
                   has_online_payment, has_quote_request, transaction_scan_date,
                   price_tier, price_signals, price_confidence,
                   entity_coherence_score, entity_name_match, entity_address_match,
                   entity_phone_match, entity_gbp_place_id, entity_scan_date,
                   ai_preference_score, ai_preference_dimensions, ai_preference_scan_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?,
                           ?, ?, ?, ?, ?, ?,
                           ?, ?, ?)""",
                (url, domain, biz_name, city, state, vertical, phone, address, rating, review_count, now, now,
                 booking_platform, booking_platform_confidence, has_online_booking,
                 booking_detection_signals, booking_scan_date, booking_platform_grade,
                 transaction_path_score, transaction_stages_present, transaction_stages_missing,
                 transaction_failure_points, contact_methods, has_visible_pricing,
                 has_online_payment, has_quote_request, transaction_scan_date,
                 price_tier, price_signals, price_confidence,
                 entity_coherence_score, entity_name_match, entity_address_match,
                 entity_phone_match, entity_gbp_place_id, entity_scan_date,
                 ai_preference_score, ai_preference_dimensions, ai_preference_scan_date),
            )
            business_id = cur.lastrowid

        # Extract dimension scores
        dims = score_result.get("dimension_scores", score_result.get("dimensions", {}))

        def _dim(key):
            """Pull score from dimensions dict, trying both 'key' and 'key_score'."""
            if key in dims:
                val = dims[key]
                return val.get("score") if isinstance(val, dict) else val
            short = key.replace("_score", "")
            if short in dims:
                val = dims[short]
                return val.get("score") if isinstance(val, dict) else val
            return score_result.get(key)

        # Extract methodology version from _internal if present
        methodology_version = None
        internal = score_result.get("_internal", {})
        if internal:
            methodology_version = internal.get("methodology_version")

        # Layer 5/6: Save Google observation data (append-only)
        google_obs = score_result.get("google_observation")
        if google_obs and isinstance(google_obs, dict):
            try:
                conn.execute(
                    """INSERT INTO google_observations
                       (business_id, observed_at, google_rating, google_review_count,
                        google_business_status, google_maps_uri, google_types,
                        google_hours, google_photo_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        business_id, now,
                        google_obs.get("google_rating"),
                        google_obs.get("google_review_count"),
                        google_obs.get("google_business_status"),
                        google_obs.get("google_maps_uri"),
                        json.dumps(google_obs.get("google_types", [])),
                        json.dumps(google_obs.get("google_hours", {})),
                        google_obs.get("google_photo_count"),
                    ),
                )
            except Exception:
                pass  # Non-critical -- don't break scoring if observation save fails

        # Layer 8: Save scan observation data (append-only)
        http_status = score_result.get("http_status_code")
        if http_status is not None:
            try:
                conn.execute(
                    """INSERT INTO scan_observations
                       (business_id, observed_at, http_status_code, response_time_ms,
                        ssl_valid, redirect_chain, final_url, cms_detected,
                        payment_platforms, chat_platforms, review_platforms,
                        analytics_platforms, form_platforms, social_links, technology_stack,
                        has_llms_txt, has_agent_json, has_agents_txt,
                        has_ucp, has_acp, has_mcp,
                        robots_ai_bot_policies, transaction_stages, contact_methods,
                        schema_types, schema_type_count, price_tier, contact_method_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                               ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        business_id, now,
                        http_status,
                        score_result.get("response_time_ms"),
                        1 if score_result.get("ssl_valid") else 0,
                        json.dumps(score_result.get("redirect_chain", [])),
                        score_result.get("final_url"),
                        score_result.get("cms_detected"),
                        json.dumps(score_result.get("payment_platforms", [])),
                        json.dumps(score_result.get("chat_platforms", [])),
                        json.dumps(score_result.get("review_platforms", [])),
                        json.dumps(score_result.get("analytics_platforms", [])),
                        json.dumps(score_result.get("form_platforms", [])),
                        json.dumps(score_result.get("social_links", {})),
                        json.dumps(score_result.get("technology_stack", [])),
                        # v6.3: Longitudinal observation fields
                        1 if score_result.get("has_llms_txt") else 0,
                        1 if score_result.get("has_agent_json") else 0,
                        1 if score_result.get("has_agents_txt") else 0,
                        1 if score_result.get("has_ucp") else 0,
                        1 if score_result.get("has_acp") else 0,
                        1 if score_result.get("has_mcp") else 0,
                        json.dumps(score_result.get("robots_ai_bots", {})),
                        json.dumps(score_result.get("transaction_stages_present", [])),
                        json.dumps(score_result.get("contact_methods", [])),
                        json.dumps(score_result.get("schema_types_found", [])),
                        score_result.get("schema_type_count", 0),
                        score_result.get("price_tier"),
                        score_result.get("contact_method_count", 0),
                    ),
                )
            except Exception:
                pass  # Non-critical -- don't break scoring if observation save fails

        # Layer 7: Technology change event detection
        # Compare current technology stack against previous scan observation
        try:
            _detect_technology_changes(conn, business_id, now, score_result)
        except Exception:
            pass  # Non-critical

        cur = conn.execute(
            """INSERT INTO scores
               (business_id, timestamp, composite_score, grade,
                discoverability_score, service_clarity_score, bookability_score,
                contactability_score, quotability_score, verifiability_score,
                payability_score, competitive_position_score,
                agent_compatibility_score, transaction_readiness_score,
                agentic_commerce_score, operational_data_structure_score,
                data_accuracy_score,
                raw_json, methodology_version,
                booking_platform, booking_platform_confidence,
                has_online_booking, booking_platform_grade,
                transaction_path_score, price_tier, entity_coherence_score,
                ai_preference_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                business_id,
                now,
                score_result.get("composite_score"),
                score_result.get("grade"),
                # Legacy v3 columns (NULL for v5 scores)
                _dim("discoverability_score"),
                _dim("service_clarity_score"),
                _dim("bookability_score"),
                _dim("contactability_score"),
                _dim("quotability_score"),
                _dim("verifiability_score"),
                _dim("payability_score"),
                _dim("competitive_position_score"),
                # v5 columns
                _dim("agent_compatibility_score"),
                _dim("transaction_readiness_score"),
                _dim("agentic_commerce_score"),
                _dim("operational_data_structure_score"),
                _dim("data_accuracy_score"),
                json.dumps(score_result, default=str),
                methodology_version,
                # v6: booking platform fields for historical tracking
                score_result.get("booking_platform"),
                score_result.get("booking_platform_confidence"),
                1 if score_result.get("has_online_booking") else 0,
                score_result.get("booking_platform_grade"),
                # v6 Phase 2: transaction path score for historical tracking
                score_result.get("transaction_path_score", 0),
                # Price spectrum tier for historical tracking
                score_result.get("price_tier"),
                # v6 Phase 3: entity coherence score for historical tracking
                score_result.get("entity_coherence_score"),
                # v6 Phase 4: AI Agent Preference Score for historical tracking
                score_result.get("ai_preference_score"),
            ),
        )
        score_id = cur.lastrowid
        conn.commit()
        return score_id
    finally:
        conn.close()


def get_business_history(domain: str) -> list:
    """Return all scores for a domain over time, oldest first."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT s.*, b.business_name, b.domain, b.vertical, b.city, b.state
               FROM scores s
               JOIN businesses b ON s.business_id = b.id
               WHERE b.domain = ?
               ORDER BY s.timestamp ASC""",
            (domain,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_vertical_benchmarks(vertical: str, city: str = None) -> dict:
    """
    Average scores by dimension for a vertical, optionally filtered by city.
    Returns mean, median, min, max for composite and each dimension.
    """
    conn = _get_conn()
    try:
        if city:
            rows = conn.execute(
                """SELECT s.*
                   FROM scores s
                   JOIN businesses b ON s.business_id = b.id
                   WHERE b.vertical = ? AND b.city = ?
                   ORDER BY s.timestamp DESC""",
                (vertical, city),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT s.*
                   FROM scores s
                   JOIN businesses b ON s.business_id = b.id
                   WHERE b.vertical = ?
                   ORDER BY s.timestamp DESC""",
                (vertical,),
            ).fetchall()

        if not rows:
            return {"vertical": vertical, "city": city, "count": 0, "benchmarks": {}}

        # Deduplicate: keep only the most recent score per business
        seen = set()
        unique_rows = []
        for r in rows:
            bid = r["business_id"]
            if bid not in seen:
                seen.add(bid)
                unique_rows.append(dict(r))

        # Use v5 columns if any v5 data exists, otherwise fall back to legacy
        sample = unique_rows[0] if unique_rows else {}
        has_v5 = any(sample.get(c) is not None for c in DIMENSION_COLUMNS if c in sample)
        dim_cols = DIMENSION_COLUMNS if has_v5 else LEGACY_DIMENSION_COLUMNS
        columns = ["composite_score"] + dim_cols
        benchmarks = {}
        for col in columns:
            values = [r.get(col) for r in unique_rows if r.get(col) is not None]
            if values:
                benchmarks[col] = {
                    "mean": round(statistics.mean(values), 1),
                    "median": round(statistics.median(values), 1),
                    "min": round(min(values), 1),
                    "max": round(max(values), 1),
                    "count": len(values),
                }
            else:
                benchmarks[col] = {"mean": None, "median": None, "min": None, "max": None, "count": 0}

        return {
            "vertical": vertical,
            "city": city,
            "count": len(unique_rows),
            "benchmarks": benchmarks,
        }
    finally:
        conn.close()


def get_all_scores(limit: int = 100) -> list:
    """Return recent scores, newest first."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT s.*, b.business_name, b.domain, b.vertical, b.city, b.state
               FROM scores s
               JOIN businesses b ON s.business_id = b.id
               ORDER BY s.timestamp DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_local_competitors(vertical: str, city: str, exclude_domain: str = None, limit: int = 3) -> list:
    """
    Return top-scoring businesses in the same vertical + city, excluding the target domain.
    Used for competitor comparison in PDF reports.
    """
    conn = _get_conn()
    try:
        query = """
            SELECT b.domain, b.business_name, b.rating, b.review_count,
                   s.composite_score, s.grade, s.methodology_version,
                   s.agent_compatibility_score, s.transaction_readiness_score,
                   s.agentic_commerce_score, s.operational_data_structure_score,
                   s.data_accuracy_score, s.competitive_position_score,
                   s.discoverability_score, s.service_clarity_score, s.bookability_score,
                   s.contactability_score, s.quotability_score, s.verifiability_score, s.payability_score
            FROM scores s
            JOIN businesses b ON s.business_id = b.id
            WHERE b.vertical = ? AND b.city = ?
        """
        params = [vertical, city]
        if exclude_domain:
            query += " AND b.domain != ?"
            params.append(exclude_domain)
        query += " ORDER BY s.composite_score DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_percentile_rank(vertical: str, composite_score: float, city: str = None) -> tuple:
    """
    Return (percentile_rank, cohort_size) for a score within its vertical,
    optionally filtered by city.

    percentile_rank is 0-100. cohort_size is the number of businesses compared against.
    """
    conn = _get_conn()
    try:
        if city:
            rows = conn.execute(
                """SELECT s.composite_score
                   FROM scores s JOIN businesses b ON s.business_id = b.id
                   WHERE b.vertical = ? AND b.city = ?""",
                (vertical, city),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT s.composite_score
                   FROM scores s JOIN businesses b ON s.business_id = b.id
                   WHERE b.vertical = ?""",
                (vertical,),
            ).fetchall()
        if not rows:
            return 50.0, 0
        scores = [r["composite_score"] for r in rows if r["composite_score"] is not None]
        if not scores:
            return 50.0, 0
        below = sum(1 for s in scores if s < composite_score)
        return round((below / len(scores)) * 100, 0), len(scores)
    finally:
        conn.close()


def get_business_info_by_domain(domain: str) -> dict:
    """Return business record (vertical, city, state, etc.) for a domain, or None."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM businesses WHERE domain = ?", (domain,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_score_count() -> int:
    """Return total number of unique businesses scored."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM businesses").fetchone()
        return row["cnt"]
    finally:
        conn.close()


def write_db_stats_file():
    """Write current DB stats to data/db_stats.json for use by PDF generator
    and other consumers. Called by the scorer after each batch."""
    import json as _json
    stats_path = os.path.join(os.path.dirname(DB_PATH), "db_stats.json")
    try:
        conn = _get_conn()
        try:
            biz_count = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
            score_count = conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
            cities = conn.execute("SELECT COUNT(DISTINCT city) FROM businesses WHERE city IS NOT NULL").fetchone()[0]
        finally:
            conn.close()
        verticals = conn.execute("SELECT COUNT(DISTINCT vertical) FROM businesses WHERE vertical IS NOT NULL").fetchone()[0]
        stats = {
            "unique_businesses": biz_count,
            "total_scores": score_count,
            "cities": cities,
            "verticals": verticals,
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        tmp = stats_path + ".tmp"
        with open(tmp, "w") as f:
            _json.dump(stats, f)
        os.replace(tmp, stats_path)
    except Exception as e:
        print(f"[stats] Failed to write db_stats.json: {e}")


def get_grade_distribution() -> dict:
    """Return percentage distribution of grades across all scored businesses.
    Returns dict like {'A': 1, 'B': 4, 'C': 10, 'D': 18, 'F': 67}.
    Uses each business's most recent score only."""
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT s.grade, COUNT(*) as cnt
            FROM scores s
            INNER JOIN (
                SELECT business_id, MAX(timestamp) as max_ts
                FROM scores
                GROUP BY business_id
            ) latest ON s.business_id = latest.business_id AND s.timestamp = latest.max_ts
            WHERE s.grade IS NOT NULL
            GROUP BY s.grade
        """).fetchall()
        total = sum(r["cnt"] for r in rows)
        if total == 0:
            return {"A": 1, "B": 4, "C": 10, "D": 18, "F": 67}
        dist = {}
        for r in rows:
            dist[r["grade"]] = round(r["cnt"] * 100 / total)
        for g in ("A", "B", "C", "D", "F"):
            dist.setdefault(g, 0)
        return dist
    finally:
        conn.close()


def get_band_distribution() -> dict:
    """Return percentage distribution of capability bands across all scored businesses.
    Returns dict like {'Agent Incompatible': 12, 'Agent Detected': 35, ...}.
    Uses each business's most recent score only."""
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT s.grade, COUNT(*) as cnt
            FROM scores s
            INNER JOIN (
                SELECT business_id, MAX(timestamp) as max_ts
                FROM scores
                GROUP BY business_id
            ) latest ON s.business_id = latest.business_id AND s.timestamp = latest.max_ts
            WHERE s.grade IS NOT NULL
            GROUP BY s.grade
        """).fetchall()
        total = sum(r["cnt"] for r in rows)
        if total == 0:
            return {
                "Agent Incompatible": 12, "Agent Detected": 35, "Agent Functional": 30,
                "Agent Ready": 15, "Agent Optimized": 6, "Agent Preferred": 2,
            }
        dist = {}
        # Map legacy letter grades to bands for backward compat
        _legacy_map = {"F": "Agent Incompatible", "D": "Agent Detected",
                       "C": "Agent Functional", "B": "Agent Ready", "A": "Agent Optimized"}
        for r in rows:
            grade_val = r["grade"]
            band_name = _legacy_map.get(grade_val, grade_val)
            dist[band_name] = dist.get(band_name, 0) + r["cnt"]
        # Convert to percentages
        for k in dist:
            dist[k] = round(dist[k] * 100 / total)
        # Ensure all bands present
        for b in ("Agent Incompatible", "Agent Detected", "Agent Functional",
                  "Agent Ready", "Agent Optimized", "Agent Preferred"):
            dist.setdefault(b, 0)
        return dist
    finally:
        conn.close()


def get_cities_count() -> int:
    """Return count of distinct cities in the businesses table."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(DISTINCT city) as cnt FROM businesses WHERE city IS NOT NULL AND city != ''"
        ).fetchone()
        return row["cnt"]
    finally:
        conn.close()


def get_verticals_count() -> int:
    """Return count of distinct verticals in the businesses table."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(DISTINCT vertical) as cnt FROM businesses WHERE vertical IS NOT NULL AND vertical != ''"
        ).fetchone()
        return row["cnt"]
    finally:
        conn.close()


def get_businesses_needing_rescore(max_age_days=30, limit=100):
    """
    Return businesses whose last_scored is older than max_age_days.

    Returns a list of dicts with: url, domain, vertical, city, state,
    last_scored, last_score (the most recent composite_score).
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT b.url, b.domain, b.vertical, b.city, b.state, b.last_scored,
                      s.composite_score AS last_score
               FROM businesses b
               JOIN scores s ON s.business_id = b.id
               WHERE b.last_scored < datetime('now', ? || ' days')
                 AND s.id = (
                     SELECT s2.id FROM scores s2
                     WHERE s2.business_id = b.id
                     ORDER BY s2.timestamp DESC
                     LIMIT 1
                 )
               ORDER BY b.last_scored ASC
               LIMIT ?""",
            (str(-max_age_days), limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def export_csv(output_path: str):
    """Export all scores to CSV with business info joined."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT b.domain, b.business_name, b.city, b.state, b.vertical,
                      s.timestamp, s.composite_score, s.grade, s.methodology_version,
                      s.agent_compatibility_score, s.transaction_readiness_score,
                      s.agentic_commerce_score, s.operational_data_structure_score,
                      s.data_accuracy_score, s.competitive_position_score,
                      s.discoverability_score, s.service_clarity_score,
                      s.bookability_score, s.contactability_score,
                      s.quotability_score, s.verifiability_score,
                      s.payability_score
               FROM scores s
               JOIN businesses b ON s.business_id = b.id
               ORDER BY s.timestamp DESC"""
        ).fetchall()

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with open(output_path, "w", newline="") as f:
            if rows:
                writer = csv.writer(f)
                writer.writerow(rows[0].keys())
                for r in rows:
                    writer.writerow(tuple(r))

        return len(rows)
    finally:
        conn.close()


# === Scan management functions (used by dashboard API) ===

def create_scan(scan_id, url, email=None):
    """Create a new scan record."""
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO scans (id, url, email, status, created_at)
               VALUES (?, ?, ?, 'scanning', ?)""",
            (scan_id, url, email, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def update_scan(scan_id, **kwargs):
    """Update scan fields."""
    conn = _get_conn()
    try:
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [scan_id]
        conn.execute(f"UPDATE scans SET {sets} WHERE id = ?", vals)
        conn.commit()
    finally:
        conn.close()


def update_scan_email(scan_id, email):
    """Update the email on a scan record."""
    conn = _get_conn()
    try:
        conn.execute("UPDATE scans SET email = ? WHERE id = ?", (email, scan_id))
        conn.commit()
    finally:
        conn.close()


def get_scan(scan_id):
    """Get a scan record by ID."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_scan_with_scores(scan_id):
    """Get scan with associated score data."""
    conn = _get_conn()
    try:
        scan = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        if not scan:
            return None
        result = dict(scan)
        if scan["score_id"]:
            score = conn.execute(
                "SELECT * FROM scores WHERE id = ?", (scan["score_id"],)
            ).fetchone()
            if score:
                result["score_data"] = dict(score)
                # Add domain from businesses table
                biz = conn.execute(
                    "SELECT domain, business_name, vertical FROM businesses WHERE id = ?",
                    (score["business_id"],)
                ).fetchone()
                if biz:
                    result["score_data"]["domain"] = biz["domain"]
                    result["score_data"]["business_name"] = biz["business_name"]
                    result["score_data"]["vertical"] = biz["vertical"]
        return result
    finally:
        conn.close()


def get_scan_stats():
    """Get aggregate scan statistics."""
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
        biz_count = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
        avg = conn.execute("SELECT AVG(composite_score) FROM scores").fetchone()[0]
        return {
            "businesses_scored": biz_count,
            "total_scores": total,
            "average_score": round(avg, 1) if avg else 0,
        }
    finally:
        conn.close()


def save_contact_message(name, email, message):
    """Save a contact form submission. Returns (success, message)."""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO contact_messages (name, email, message) VALUES (?, ?, ?)",
            (name.strip(), email.lower().strip(), message.strip())
        )
        conn.commit()
        return True, "saved"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def add_subscriber(email, source="unknown"):
    """Add an email subscriber. Returns (success, message)."""
    conn = _get_conn()
    try:
        existing = conn.execute(
            "SELECT id, unsubscribed_at FROM subscribers WHERE email = ?",
            (email.lower().strip(),)
        ).fetchone()

        if existing:
            if existing["unsubscribed_at"]:
                # Re-subscribe
                conn.execute(
                    "UPDATE subscribers SET unsubscribed_at = NULL, source = ?, subscribed_at = datetime('now') WHERE id = ?",
                    (source, existing["id"])
                )
                conn.commit()
                return True, "re-subscribed"
            return True, "already subscribed"

        conn.execute(
            "INSERT INTO subscribers (email, source) VALUES (?, ?)",
            (email.lower().strip(), source)
        )
        conn.commit()
        return True, "subscribed"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def remove_subscriber(email):
    """Unsubscribe an email. Returns (success, message)."""
    conn = _get_conn()
    try:
        result = conn.execute(
            "UPDATE subscribers SET unsubscribed_at = datetime('now') WHERE email = ? AND unsubscribed_at IS NULL",
            (email.lower().strip(),)
        )
        conn.commit()
        if result.rowcount > 0:
            return True, "unsubscribed"
        return True, "not found or already unsubscribed"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


# === Append-only observation storage (Layers 5-8) ===

def save_google_observation(business_id: int, data: dict) -> int:
    """
    Save a timestamped Google Places observation. Append-only -- never overwrites.
    Returns the observation ID.

    data keys: google_rating, google_review_count, google_business_status,
               google_maps_uri, google_types, google_hours, google_photo_count
    """
    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """INSERT INTO google_observations
               (business_id, observed_at, google_rating, google_review_count,
                google_business_status, google_maps_uri, google_types,
                google_hours, google_photo_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                business_id, now,
                data.get("google_rating"),
                data.get("google_review_count"),
                data.get("google_business_status"),
                data.get("google_maps_uri"),
                json.dumps(data.get("google_types", [])),
                json.dumps(data.get("google_hours", {})),
                data.get("google_photo_count"),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def save_scan_observation(business_id: int, data: dict) -> int:
    """
    Save a timestamped scan observation (HTTP metadata + technology detection).
    Append-only -- never overwrites. Returns the observation ID.

    data keys: http_status_code, response_time_ms, ssl_valid, redirect_chain,
               final_url, cms_detected, payment_platforms, chat_platforms,
               review_platforms, analytics_platforms, form_platforms,
               social_links, technology_stack
    """
    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """INSERT INTO scan_observations
               (business_id, observed_at, http_status_code, response_time_ms,
                ssl_valid, redirect_chain, final_url, cms_detected,
                payment_platforms, chat_platforms, review_platforms,
                analytics_platforms, form_platforms, social_links, technology_stack)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                business_id, now,
                data.get("http_status_code"),
                data.get("response_time_ms"),
                1 if data.get("ssl_valid") else 0,
                json.dumps(data.get("redirect_chain", [])),
                data.get("final_url"),
                data.get("cms_detected"),
                json.dumps(data.get("payment_platforms", [])),
                json.dumps(data.get("chat_platforms", [])),
                json.dumps(data.get("review_platforms", [])),
                json.dumps(data.get("analytics_platforms", [])),
                json.dumps(data.get("form_platforms", [])),
                json.dumps(data.get("social_links", {})),
                json.dumps(data.get("technology_stack", [])),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def save_technology_change_event(business_id: int, change_type: str,
                                  category: str, old_value: str = None,
                                  new_value: str = None) -> int:
    """
    Record a technology change event (added, removed, or changed).
    Append-only. Returns the event ID.

    change_type: 'added', 'removed', 'changed'
    category: 'cms', 'payment', 'chat', 'review', 'analytics', 'form', 'booking', 'social'
    """
    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """INSERT INTO technology_change_events
               (business_id, detected_at, change_type, category, old_value, new_value)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (business_id, now, change_type, category, old_value, new_value),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_google_observation_history(business_id: int, limit: int = 50) -> list:
    """Return Google observations for a business, newest first."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM google_observations
               WHERE business_id = ?
               ORDER BY observed_at DESC LIMIT ?""",
            (business_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_scan_observation_history(business_id: int, limit: int = 50) -> list:
    """Return scan observations for a business, newest first."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM scan_observations
               WHERE business_id = ?
               ORDER BY observed_at DESC LIMIT ?""",
            (business_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_latest_scan_observation(business_id: int) -> dict:
    """Return the most recent scan observation for a business, or None."""
    conn = _get_conn()
    try:
        row = conn.execute(
            """SELECT * FROM scan_observations
               WHERE business_id = ?
               ORDER BY observed_at DESC LIMIT 1""",
            (business_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_technology_changes(business_id: int, limit: int = 100) -> list:
    """Return technology change events for a business, newest first."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM technology_change_events
               WHERE business_id = ?
               ORDER BY detected_at DESC LIMIT ?""",
            (business_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
