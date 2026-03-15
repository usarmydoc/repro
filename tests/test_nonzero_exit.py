# Regression test for: VERIFY EXITS NON-ZERO ON FAILURE
# Bug: verify.py had no comparison logic, so it always exited 0 regardless
#      of file state. BioOrchestrator L4 execution layer depends on non-zero
#      exit to block pipeline continuation on verification failure.
# Fix:
#   repro/verify.py (lines 199-270: comparison mode with SystemExit(1) on failure)
#   Missing files, tampered files, and corrupted lockfiles all exit non-zero.

import json
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="repro_test_exit_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_missing_file_exits_nonzero(tmp_dir):
    """verify exits non-zero when a registered output file is missing."""
    from repro.verify import run_verify

    lockfile_path = os.path.join(tmp_dir, "test.lock")
    missing_file = os.path.join(tmp_dir, "does_not_exist.tsv")

    data = {
        "repro_schema_version": "1.0",
        "created_at": "2026-01-01T00:00:00",
        "repro_version": "0.1.0",
        "verified_outputs": {
            "verified_at": "2026-01-01T00:00:00",
            "file_count": 1,
            "files": {
                missing_file: {
                    "md5": "d41d8cd98f00b204e9800998ecf8427e",
                    "size_bytes": 0,
                    "type": "text",
                },
            },
        },
    }
    with open(lockfile_path, "w") as f:
        json.dump(data, f)

    with pytest.raises(SystemExit) as exc_info:
        run_verify(output_dir=".", lockfile_path=lockfile_path)
    assert exc_info.value.code == 1


def test_corrupted_lockfile_exits_nonzero(tmp_dir):
    """verify exits non-zero when lockfile is corrupted JSON."""
    from repro.verify import run_verify

    lockfile_path = os.path.join(tmp_dir, "corrupted.lock")
    with open(lockfile_path, "w") as f:
        f.write('{"repro_schema_version": "1.0"}\nCORRUPTED')

    with pytest.raises(SystemExit) as exc_info:
        run_verify(output_dir=".", lockfile_path=lockfile_path)
    assert exc_info.value.code == 1


def test_missing_lockfile_exits_nonzero(tmp_dir):
    """verify exits non-zero when lockfile does not exist."""
    from repro.verify import run_verify

    lockfile_path = os.path.join(tmp_dir, "nonexistent.lock")

    with pytest.raises(SystemExit) as exc_info:
        run_verify(output_dir=".", lockfile_path=lockfile_path)
    assert exc_info.value.code == 1


def test_pass_exits_zero(tmp_dir):
    """verify exits zero when all hashes match."""
    from repro.snapshot import run_snapshot
    from repro.verify import run_verify

    output_file = os.path.join(tmp_dir, "good.tsv")
    lockfile_path = os.path.join(tmp_dir, "test.lock")

    with open(output_file, "w") as f:
        f.write("good data\n")

    run_snapshot(
        output_path=lockfile_path,
        offline=True,
        quiet=True,
        output_files=[output_file],
    )

    # Should not raise SystemExit
    run_verify(output_dir=".", lockfile_path=lockfile_path)
