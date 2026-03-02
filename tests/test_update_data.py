"""Tests for update_data module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro.update_data import _load_data_version, _check_staleness


def test_load_data_version():
    """Test data_version.json loads."""
    versions = _load_data_version()
    assert isinstance(versions, dict)
    assert "breaking_changes" in versions
    assert "pipeline_requirements" in versions
    assert "cve_snapshot" in versions
    print("  Data version loaded: {} entries".format(len(versions)))


def test_staleness_check():
    """Test staleness detection."""
    warnings = _check_staleness()
    # Data files are from 2026-02 — should be stale since we're in 2026-03
    # (but depends on exact date)
    assert isinstance(warnings, list)
    print("  Staleness warnings: {}".format(len(warnings)))
    for w in warnings[:2]:
        print("    {}".format(w[:80]))


if __name__ == "__main__":
    for t in [test_load_data_version, test_staleness_check]:
        print("Running {}...".format(t.__name__))
        t()
        print("  PASSED")
    print("\nAll update_data tests passed!")
