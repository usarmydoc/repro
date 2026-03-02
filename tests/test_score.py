"""Tests for score module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro.version_util import parse_version as _parse_version, version_diff_severity as _version_diff_severity
from repro.score import _score_severity


def test_parse_version():
    """Test version string parsing."""
    assert _parse_version("1.2.3") == (1, 2, 3)
    assert _parse_version("v2.0") == (2, 0)
    assert _parse_version("3.11.4") == (3, 11, 4)
    print("  Version parsing: OK")


def test_severity():
    """Test version diff severity classification."""
    assert _version_diff_severity("1.2.3", "1.2.3") == "match"
    assert _version_diff_severity("1.2.3", "1.2.4") == "patch"
    assert _version_diff_severity("1.2.3", "1.3.0") == "minor"
    assert _version_diff_severity("1.2.3", "2.0.0") == "major"
    assert _version_diff_severity("1.2.3", None) == "missing"
    print("  Severity classification: OK")


def test_score_values():
    """Test score mapping."""
    assert _score_severity("match") == 1.0
    assert _score_severity("patch") == 0.9
    assert _score_severity("minor") == 0.6
    assert _score_severity("major") == 0.2
    assert _score_severity("missing") == 0.0
    print("  Score values: OK")


if __name__ == "__main__":
    for t in [test_parse_version, test_severity, test_score_values]:
        print("Running {}...".format(t.__name__))
        t()
        print("  PASSED")
    print("\nAll score tests passed!")
