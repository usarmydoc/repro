# Regression test for: MID-PIPELINE SNAPSHOT
# Verifies that repro snapshot can be called multiple times during a pipeline
# without corrupting the lockfile, and that each snapshot correctly updates
# the verified_outputs section.
# Files tested:
#   repro/snapshot.py (run_snapshot with output_files, lines 77-108)
#   repro/lockfile.py (write_lockfile atomic write, lines 128-172)
#   repro/verify.py (run_verify comparison mode, lines 199-270)

import json
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="repro_test_pipeline_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_sequential_snapshots_no_corruption(tmp_dir):
    """Multiple snapshots to the same lockfile produce valid JSON."""
    from repro.snapshot import run_snapshot

    lockfile_path = os.path.join(tmp_dir, "pipeline.lock")
    file1 = os.path.join(tmp_dir, "stage1.tsv")
    file2 = os.path.join(tmp_dir, "stage2.tsv")

    # Stage 1
    with open(file1, "w") as f:
        f.write("stage1,complete\n")
    run_snapshot(
        output_path=lockfile_path,
        offline=True,
        quiet=True,
        output_files=[file1],
    )

    # Verify lockfile is valid JSON after first snapshot
    with open(lockfile_path) as f:
        data1 = json.load(f)
    assert data1["verified_outputs"]["file_count"] == 1

    # Stage 2 — overwrite with both files
    with open(file2, "w") as f:
        f.write("stage2,complete\n")
    run_snapshot(
        output_path=lockfile_path,
        offline=True,
        quiet=True,
        output_files=[file1, file2],
    )

    # Verify lockfile is still valid and has both files
    with open(lockfile_path) as f:
        data2 = json.load(f)
    assert data2["verified_outputs"]["file_count"] == 2


def test_verify_after_multi_stage_snapshot(tmp_dir):
    """verify passes after a multi-stage snapshot."""
    from repro.snapshot import run_snapshot
    from repro.verify import run_verify

    lockfile_path = os.path.join(tmp_dir, "pipeline.lock")
    file1 = os.path.join(tmp_dir, "stage1.tsv")
    file2 = os.path.join(tmp_dir, "stage2.tsv")

    with open(file1, "w") as f:
        f.write("stage1,complete\n")
    with open(file2, "w") as f:
        f.write("stage2,complete\n")

    run_snapshot(
        output_path=lockfile_path,
        offline=True,
        quiet=True,
        output_files=[file1, file2],
    )

    # Should not raise
    run_verify(output_dir=".", lockfile_path=lockfile_path)


def test_overwritten_snapshot_updates_hashes(tmp_dir):
    """A second snapshot correctly updates hashes for changed files."""
    from repro.snapshot import run_snapshot

    lockfile_path = os.path.join(tmp_dir, "pipeline.lock")
    output_file = os.path.join(tmp_dir, "output.tsv")

    # First version
    with open(output_file, "w") as f:
        f.write("version1\n")
    run_snapshot(
        output_path=lockfile_path,
        offline=True,
        quiet=True,
        output_files=[output_file],
    )
    with open(lockfile_path) as f:
        data1 = json.load(f)
    hash1 = list(data1["verified_outputs"]["files"].values())[0]["md5"]

    # Second version (file changed)
    with open(output_file, "w") as f:
        f.write("version2\n")
    run_snapshot(
        output_path=lockfile_path,
        offline=True,
        quiet=True,
        output_files=[output_file],
    )
    with open(lockfile_path) as f:
        data2 = json.load(f)
    hash2 = list(data2["verified_outputs"]["files"].values())[0]["md5"]

    assert hash1 != hash2, "Hash should change when file content changes"
