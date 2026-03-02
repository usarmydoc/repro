"""Tests for restore module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro.restore import plan_restore
from repro import lockfile


def test_plan_restore():
    """Test restore planning."""
    data = lockfile.empty_lockfile()
    data["created_at"] = "2026-01-01"
    data["repro_version"] = "0.1.0"
    data["package_managers"]["pip"] = {"numpy": "1.24.0", "pandas": "2.0.1"}
    data["package_managers"]["conda"] = {"packages": {"scipy": "1.11.0"}}

    plan = plan_restore(data)
    assert "env_name" in plan
    assert plan["env_name"].startswith("repro-")
    assert len(plan["pip_packages"]) == 2
    assert len(plan["conda_packages"]) == 1
    print("  Plan: env={}, pip={}, conda={}".format(
        plan["env_name"], len(plan["pip_packages"]), len(plan["conda_packages"])))


def test_plan_with_tools():
    """Test restore planning with manual tools."""
    data = lockfile.empty_lockfile()
    data["created_at"] = "2026-01-01"
    data["repro_version"] = "0.1.0"
    data["tools"] = {
        "bioinformatics": {
            "samtools": {"found": True, "version": "1.17"}
        }
    }

    plan = plan_restore(data)
    assert len(plan["tools_manual"]) == 1
    assert plan["tools_manual"][0]["name"] == "samtools"
    print("  Manual tools: {}".format(len(plan["tools_manual"])))


if __name__ == "__main__":
    for t in [test_plan_restore, test_plan_with_tools]:
        print("Running {}...".format(t.__name__))
        t()
        print("  PASSED")
    print("\nAll restore tests passed!")
