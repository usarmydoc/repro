"""Tests for explain module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro.explain import find_breaking_changes
from repro.lockfile import load_data_file


def test_load_database():
    """Test that breaking_changes.json loads correctly."""
    db = load_data_file("breaking_changes")
    assert isinstance(db, dict)
    assert "samtools" in db
    assert len(db) >= 15
    print("  Database loaded: {} tools".format(len(db)))


def test_find_breaking_samtools():
    """Test finding breaking changes for samtools."""
    db = load_data_file("breaking_changes")
    changes = find_breaking_changes("samtools", "1.17", "1.18", db)
    assert len(changes) >= 1
    assert changes[0]["severity"] == "high"
    print("  samtools 1.17->1.18: {} breaking change(s)".format(len(changes)))


def test_no_breaking_changes():
    """Test no breaking changes found for same version."""
    db = load_data_file("breaking_changes")
    changes = find_breaking_changes("samtools", "1.17", "1.17", db)
    assert len(changes) == 0
    print("  Same version: no breaking changes")


def test_unknown_tool():
    """Test graceful handling of unknown tool."""
    db = load_data_file("breaking_changes")
    changes = find_breaking_changes("nonexistent_tool", "1.0", "2.0", db)
    assert len(changes) == 0
    print("  Unknown tool: graceful empty result")


if __name__ == "__main__":
    for t in [test_load_database, test_find_breaking_samtools,
              test_no_breaking_changes, test_unknown_tool]:
        print("Running {}...".format(t.__name__))
        t()
        print("  PASSED")
    print("\nAll explain tests passed!")
