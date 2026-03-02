"""Tests for diff module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro.diff import compute_diff


def test_identical():
    """Test diff of identical lockfiles."""
    data = {"key": "value", "nested": {"a": "1"}}
    diffs = compute_diff(data, data)
    assert len(diffs) == 0
    print("  Identical: no diffs")


def test_changed():
    """Test diff detects changes."""
    d1 = {"system": {"os": "Linux"}, "languages": {"python": "3.11"}}
    d2 = {"system": {"os": "Darwin"}, "languages": {"python": "3.12"}}
    diffs = compute_diff(d1, d2)
    assert len(diffs) == 2
    assert any(d["key"] == "system.os" for d in diffs)
    print("  Changed values detected: {} diffs".format(len(diffs)))


def test_added_removed():
    """Test diff detects added and removed keys."""
    d1 = {"a": "1"}
    d2 = {"b": "2"}
    diffs = compute_diff(d1, d2)
    types = {d["change_type"] for d in diffs}
    assert "added" in types
    assert "removed" in types
    print("  Added/removed detection: OK")


if __name__ == "__main__":
    for t in [test_identical, test_changed, test_added_removed]:
        print("Running {}...".format(t.__name__))
        t()
        print("  PASSED")
    print("\nAll diff tests passed!")
