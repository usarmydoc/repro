"""Tests for snapshot module."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro import snapshot, lockfile


def test_snapshot_creates_lockfile():
    """Test that snapshot creates a valid lockfile."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "repro.lock")
        data = snapshot.run_snapshot(output_path=path, quiet=True)

        assert os.path.exists(path)
        loaded = lockfile.read_lockfile(path)
        assert loaded["repro_schema_version"] == "1.0"
        assert loaded["repro_version"] == "0.1.0"
        assert "system" in loaded
        assert "languages" in loaded
        print("  Snapshot creates valid lockfile: OK")


def test_snapshot_offline():
    """Test snapshot in offline mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "repro.lock")
        data = snapshot.run_snapshot(output_path=path, quiet=True, offline=True)
        assert os.path.exists(path)
        print("  Offline snapshot: OK")


def test_snapshot_quiet():
    """Test snapshot quiet mode (no output)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "repro.lock")
        data = snapshot.run_snapshot(output_path=path, quiet=True)
        assert os.path.exists(path)
        print("  Quiet mode: OK")


if __name__ == "__main__":
    for t in [test_snapshot_creates_lockfile, test_snapshot_offline, test_snapshot_quiet]:
        print("Running {}...".format(t.__name__))
        t()
        print("  PASSED")
    print("\nAll snapshot tests passed!")
