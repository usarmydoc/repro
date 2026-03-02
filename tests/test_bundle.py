"""Tests for bundle module."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro import lockfile, network


def test_bundle_offline():
    """Test bundle creation in offline mode (no downloads)."""
    from repro.bundle import run_bundle

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a minimal lockfile
        lock_path = os.path.join(tmpdir, "repro.lock")
        data = lockfile.empty_lockfile()
        data["created_at"] = "2026-01-01"
        data["repro_version"] = "0.1.0"
        lockfile.write_lockfile(lock_path, data)

        # Force offline to skip downloads
        network.force_offline(True)
        bundle_path = os.path.join(tmpdir, "test.bundle")
        run_bundle(lock_path, bundle_path)
        network.reset_cache()

        assert os.path.exists(bundle_path)
        size = os.path.getsize(bundle_path)
        print("  Offline bundle created: {:.1f} KB".format(size / 1024))


if __name__ == "__main__":
    for t in [test_bundle_offline]:
        print("Running {}...".format(t.__name__))
        t()
        print("  PASSED")
    print("\nAll bundle tests passed!")
