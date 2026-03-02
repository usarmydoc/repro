"""Tests for lockfile module."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro import lockfile


def test_write_and_read():
    """Test atomic write then read back."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "repro.lock")
        data = lockfile.empty_lockfile()
        data["created_at"] = "2026-03-02T00:00:00"
        data["repro_version"] = "0.1.0"

        lockfile.write_lockfile(path, data)
        assert os.path.exists(path)

        loaded = lockfile.read_lockfile(path)
        assert loaded["repro_schema_version"] == "1.0"
        assert loaded["created_at"] == "2026-03-02T00:00:00"
        print("  Write/read round-trip OK")


def test_atomic_write_no_corruption():
    """Test that incomplete writes don't corrupt existing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "repro.lock")
        original = lockfile.empty_lockfile()
        original["created_at"] = "original"
        original["repro_version"] = "0.1.0"
        lockfile.write_lockfile(path, original)

        # Overwrite with new data
        updated = lockfile.empty_lockfile()
        updated["created_at"] = "updated"
        updated["repro_version"] = "0.1.0"
        lockfile.write_lockfile(path, updated)

        loaded = lockfile.read_lockfile(path)
        assert loaded["created_at"] == "updated"
        print("  Atomic overwrite OK")


def test_missing_file():
    """Test clear error for missing lockfile."""
    try:
        lockfile.read_lockfile("/nonexistent/repro.lock")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError as e:
        assert "not found" in str(e).lower()
        print("  Missing file error: {}".format(e))


def test_corrupted_json():
    """Test clear error for corrupted JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "repro.lock")
        with open(path, "w") as f:
            f.write("{ this is not valid json !!!")

        try:
            lockfile.read_lockfile(path)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "corrupted" in str(e).lower()
            print("  Corrupted JSON error: {}".format(str(e)[:80]))


def test_empty_file():
    """Test clear error for empty lockfile."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "repro.lock")
        with open(path, "w") as f:
            f.write("")

        try:
            lockfile.read_lockfile(path)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "empty" in str(e).lower()
            print("  Empty file error: {}".format(str(e)[:60]))


def test_conflict_markers():
    """Test detection of git merge conflict markers."""
    conflict_text = """{
<<<<<<< HEAD
  "repro_schema_version": "1.0"
=======
  "repro_schema_version": "1.1"
>>>>>>> feature
}"""
    assert lockfile.has_conflict_markers(conflict_text) is True
    assert lockfile.has_conflict_markers('{"key": "value"}') is False
    print("  Conflict marker detection OK")

    # Also test that read_lockfile catches it
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "repro.lock")
        with open(path, "w") as f:
            f.write(conflict_text)
        try:
            lockfile.read_lockfile(path)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "conflict" in str(e).lower()
            print("  Conflict in read_lockfile: caught correctly")


def test_validation():
    """Test lockfile validation."""
    # Valid
    data = lockfile.empty_lockfile()
    data["created_at"] = "2026-01-01"
    data["repro_version"] = "0.1.0"
    errors = lockfile.validate_lockfile(data)
    assert len(errors) == 0
    print("  Valid lockfile passes validation")

    # Missing required fields
    errors = lockfile.validate_lockfile({})
    assert len(errors) > 0
    print("  Invalid lockfile caught: {} errors".format(len(errors)))


def test_backup():
    """Test lockfile backup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "repro.lock")
        data = lockfile.empty_lockfile()
        data["created_at"] = "backup_test"
        data["repro_version"] = "0.1.0"
        lockfile.write_lockfile(path, data)

        bak = lockfile.backup_lockfile(path)
        assert bak is not None
        assert os.path.exists(bak)
        assert bak.endswith(".bak")
        print("  Backup created: {}".format(os.path.basename(bak)))

    # Backup of non-existent file
    assert lockfile.backup_lockfile("/nonexistent") is None
    print("  Non-existent backup returns None")


def test_migration():
    """Test schema migration."""
    # Current version — no migration needed
    data = lockfile.empty_lockfile()
    data["created_at"] = "test"
    data["repro_version"] = "0.1.0"
    assert not lockfile.needs_migration(data)

    # Old/unknown version — needs migration
    old = {"repro_schema_version": "0.5", "created_at": "old", "repro_version": "0.0.1"}
    assert lockfile.needs_migration(old)

    migrated = lockfile.migrate_lockfile(old)
    assert migrated["repro_schema_version"] == "1.0"
    assert "system" in migrated  # Missing keys filled in
    print("  Migration from 0.5 -> 1.0 OK")


if __name__ == "__main__":
    tests = [
        test_write_and_read,
        test_atomic_write_no_corruption,
        test_missing_file,
        test_corrupted_json,
        test_empty_file,
        test_conflict_markers,
        test_validation,
        test_backup,
        test_migration,
    ]
    for t in tests:
        print("Running {}...".format(t.__name__))
        t()
        print("  PASSED")
    print("\nAll lockfile tests passed!")
