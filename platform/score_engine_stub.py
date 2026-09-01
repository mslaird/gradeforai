"""STUB. Not the real scoring engine.

The real `score_engine.py` (5,661 lines) is private: it holds the dimension
weights, the per-vertical calibration tables, and the signal checks that decide
what a score means. Those are the proprietary core and they are not published.

This file exists so the rest of the platform is runnable from a clean clone.
It satisfies the one symbol the published modules import --

    from score_engine import score_business

-- and returns a result with the same shape, populated with obviously fake,
deterministic values derived from a hash of the URL. Nothing here scrapes,
measures, or scores anything. Any number it produces is meaningless.

To use it:

    cp platform/score_engine_stub.py platform/score_engine.py
    python platform/cli.py score https://example.com --vertical plumber --city Dallas --state TX

The band cutoffs below (90/70/50/30/10) are the only real thing in this file.
They are already public in the README and in the sample PDF reports, so they
leak nothing. The weights that decide which side of a cutoff a business lands
on are what stays private.
"""
import hashlib
from datetime import datetime, timezone

METHODOLOGY_VERSION = "stub"

# Published in the README and on every sample report. Not proprietary.
_BANDS = (
    (90, "Agent Preferred"),
    (70, "Agent Optimized"),
    (50, "Agent Ready"),
    (30, "Agent Functional"),
    (10, "Agent Detected"),
    (0, "Agent Incompatible"),
)

_DIMENSIONS = (
    "agent_compatibility",
    "transaction_readiness",
    "agentic_commerce",
    "operational_data_structure",
    "data_accuracy",
    "competitive_position",
)


def compute_grade(score):
    """Map a 0-100 score to a capability band. Real, and already public."""
    for floor, label in _BANDS:
        if score >= floor:
            return label
    return _BANDS[-1][1]


def _fake(url, salt, lo=0, hi=100):
    """Deterministic pseudo-value so repeated runs are stable. Not a measurement."""
    h = hashlib.sha256(f"{salt}:{url}".encode()).digest()
    return lo + (int.from_bytes(h[:4], "big") % (hi - lo + 1))


def score_business(url):
    """Stubbed entry point. Same shape as the real one, meaningless values."""
    domain = url.split("//")[-1].split("/")[0].lstrip("www.")
    composite = _fake(url, "composite")
    dimension_scores = {d: _fake(url, d) for d in _DIMENSIONS}

    # The summary line in report.py reads the legacy v3 dimension names, while
    # scores/ carries the v5/v6 set. The real engine wrote both during the
    # migration; the stub does too, so the CLI output is not a row of dashes.
    legacy = ("discoverability", "service_clarity", "bookability", "contactability",
              "quotability", "verifiability", "payability")
    for name in legacy:
        dimension_scores[name] = {"score": _fake(url, name)}

    return {
        "url": url,
        "domain": domain,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "composite_score": composite,
        "grade": compute_grade(composite),
        "dimension_scores": dimension_scores,
        "methodology_version": METHODOLOGY_VERSION,

        # Shape-only fields. storage.save_score() reads everything through
        # .get() with defaults, so a partial result is safe.
        "raw_data": {"_stub": True, "note": "no site was fetched"},
        "pages_scraped": 0,
        "phones": [],
        "emails": [],
        "addresses": [],
        "schemas_found": [],
        "booking_platform": None,
        "booking_platform_confidence": None,
        "has_online_booking": False,
        "transaction_path_score": _fake(url, "tx"),
        "transaction_stages_present": ["DISCOVER", "EVALUATE"],
        "transaction_stages_missing": ["CONTACT", "BOOK", "PAY"],
        "contact_methods": [],
        "has_visible_pricing": False,
        "has_online_payment": False,

        "_internal": {
            "stub": True,
            "warning": "Values are hash-derived placeholders, not measurements.",
        },
    }


if __name__ == "__main__":
    import json, sys
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(json.dumps(score_business(target), indent=2))
