"""Band boundary tests. The cutoffs are public (README + every sample PDF);
the weights that decide which side of a cutoff a business lands on are not."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "platform"))
from score_engine_stub import compute_grade


def test_band_boundaries_are_inclusive_lower_bounds():
    assert compute_grade(90) == "Agent Preferred"
    assert compute_grade(89) == "Agent Optimized"
    assert compute_grade(70) == "Agent Optimized"
    assert compute_grade(69) == "Agent Ready"
    assert compute_grade(50) == "Agent Ready"
    assert compute_grade(49) == "Agent Functional"
    assert compute_grade(30) == "Agent Functional"
    assert compute_grade(29) == "Agent Detected"
    assert compute_grade(10) == "Agent Detected"
    assert compute_grade(9) == "Agent Incompatible"


def test_extremes():
    assert compute_grade(100) == "Agent Preferred"
    assert compute_grade(0) == "Agent Incompatible"


def test_stub_is_deterministic():
    """Same URL must score the same twice, or the demo is confusing."""
    from score_engine_stub import score_business
    a, b = score_business("https://x.com"), score_business("https://x.com")
    assert a["composite_score"] == b["composite_score"]
    assert a["dimension_scores"] == b["dimension_scores"]


def test_stub_is_clearly_marked():
    """A reviewer must never mistake stub output for a real score."""
    from score_engine_stub import score_business
    r = score_business("https://x.com")
    assert r["_internal"]["stub"] is True
    assert r["methodology_version"] == "stub"
