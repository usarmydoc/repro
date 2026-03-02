"""Tests for update module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro.update import plan_update
from repro import lockfile


def test_plan_update_no_changes():
    """Test update planning when environment matches."""
    data = lockfile.empty_lockfile()
    data["created_at"] = "2026-01-01"
    data["repro_version"] = "0.1.0"
    # Empty packages = nothing to compare
    changes = plan_update(data)
    assert len(changes["pip_upgrades"]) == 0
    assert len(changes["pip_installs"]) == 0
    print("  No changes detected: OK")


def test_plan_update_os_mismatch():
    """Test update detects OS mismatch."""
    data = lockfile.empty_lockfile()
    data["created_at"] = "2026-01-01"
    data["repro_version"] = "0.1.0"
    data["system"]["os"] = "Darwin"  # Different from current Linux

    changes = plan_update(data)
    assert changes["os_mismatch"] is not None
    print("  OS mismatch detected: {} vs {}".format(
        changes["os_mismatch"]["recorded"],
        changes["os_mismatch"]["current"]))


if __name__ == "__main__":
    for t in [test_plan_update_no_changes, test_plan_update_os_mismatch]:
        print("Running {}...".format(t.__name__))
        t()
        print("  PASSED")
    print("\nAll update tests passed!")
