# Regression test for: OUTPUT HASH VERIFICATION
# Bug: snapshot had no --outputs flag; verify only stored hashes, never compared.
# Fix:
#   repro/cli.py (line 38: --outputs option added to snapshot)
#   repro/snapshot.py (lines 77-108: output_files hashing in run_snapshot)
#   repro/verify.py (lines 199-270: comparison mode in run_verify)

import json
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="repro_test_hash_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_snapshot_stores_output_hashes(tmp_dir):
    """snapshot with output_files stores hashes in verified_outputs."""
    from repro.snapshot import run_snapshot

    output_file = os.path.join(tmp_dir, "results.tsv")
    lockfile_path = os.path.join(tmp_dir, "test.lock")

    with open(output_file, "w") as f:
        f.write("gene1,0.001,2.3\n")

    run_snapshot(
        output_path=lockfile_path,
        offline=True,
        quiet=True,
        output_files=[output_file],
    )

    with open(lockfile_path) as f:
        data = json.load(f)

    vo = data.get("verified_outputs", {})
    assert vo.get("file_count") == 1
    assert output_file in vo.get("files", {}) or os.path.abspath(output_file) in vo.get("files", {})


def test_verify_passes_unchanged_file(tmp_dir):
    """verify returns success when output file is unchanged."""
    from repro.snapshot import run_snapshot
    from repro.verify import run_verify

    output_file = os.path.join(tmp_dir, "results.tsv")
    lockfile_path = os.path.join(tmp_dir, "test.lock")

    with open(output_file, "w") as f:
        f.write("gene1,0.001,2.3\n")

    run_snapshot(
        output_path=lockfile_path,
        offline=True,
        quiet=True,
        output_files=[output_file],
    )

    # verify should not raise SystemExit
    run_verify(output_dir=".", lockfile_path=lockfile_path)


def test_verify_hash_is_md5(tmp_dir):
    """Stored hashes are valid MD5 hex strings (32 chars)."""
    from repro.snapshot import run_snapshot

    output_file = os.path.join(tmp_dir, "results.tsv")
    lockfile_path = os.path.join(tmp_dir, "test.lock")

    with open(output_file, "w") as f:
        f.write("test data\n")

    run_snapshot(
        output_path=lockfile_path,
        offline=True,
        quiet=True,
        output_files=[output_file],
    )

    with open(lockfile_path) as f:
        data = json.load(f)

    files = data["verified_outputs"]["files"]
    for path, info in files.items():
        md5 = info["md5"]
        assert len(md5) == 32, "MD5 hash should be 32 hex chars, got {}".format(len(md5))
        assert all(c in "0123456789abcdef" for c in md5)
