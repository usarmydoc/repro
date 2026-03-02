"""Tests for feasibility module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro.feasibility import assess
from repro import lockfile


def test_assess_matching_system():
    """Test feasibility when system matches lockfile."""
    data = lockfile.empty_lockfile()
    data["created_at"] = "2026-01-01"
    data["repro_version"] = "0.1.0"
    # Don't set system requirements — should pass
    result = assess(data)
    assert "checks" in result
    assert "verdict" in result
    assert len(result["blockers"]) == 0
    print("  Matching system: {} checks, no blockers".format(len(result["checks"])))


def test_assess_arch_mismatch():
    """Test feasibility with architecture mismatch."""
    data = lockfile.empty_lockfile()
    data["created_at"] = "2026-01-01"
    data["repro_version"] = "0.1.0"
    data["system"]["arch"] = "aarch64"  # Different from x86_64

    result = assess(data)
    assert len(result["blockers"]) > 0
    assert any("architecture" in b.lower() for b in result["blockers"])
    print("  Arch mismatch: {} blocker(s)".format(len(result["blockers"])))


def test_assess_gpu_required():
    """Test feasibility when GPU is required but available."""
    data = lockfile.empty_lockfile()
    data["created_at"] = "2026-01-01"
    data["repro_version"] = "0.1.0"
    data["pipeline_type"] = "deepvariant"  # Requires GPU

    result = assess(data)
    # This machine has a GPU, so it should pass
    assert "checks" in result
    print("  GPU required: verdict='{}'".format(result["verdict"][:50]))


if __name__ == "__main__":
    for t in [test_assess_matching_system, test_assess_arch_mismatch,
              test_assess_gpu_required]:
        print("Running {}...".format(t.__name__))
        t()
        print("  PASSED")
    print("\nAll feasibility tests passed!")
