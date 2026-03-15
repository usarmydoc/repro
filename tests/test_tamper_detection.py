# Regression test for: DELIBERATE OUTPUT MODIFICATION DETECTION
# Bug: verify.py only stored hashes — it never compared against stored values,
#      so tampered files were never detected.
# Fix:
#   repro/verify.py (lines 199-270: added comparison mode in run_verify)
#   When lockfile has verified_outputs.files, rehash each file and compare.
#   Exit non-zero (SystemExit(1)) on any mismatch.

import json
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="repro_test_tamper_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_tampered_file_detected(tmp_dir):
    """verify exits non-zero when an output file has been modified."""
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

    # Tamper with the file
    with open(output_file, "a") as f:
        f.write("TAMPERED_ROW,0.0,fake\n")

    with pytest.raises(SystemExit) as exc_info:
        run_verify(output_dir=".", lockfile_path=lockfile_path)

    assert exc_info.value.code == 1, (
        "Expected exit code 1 on tampered file, got {}".format(exc_info.value.code)
    )


def test_unmodified_file_passes(tmp_dir):
    """verify does not exit when output file is unchanged."""
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

    # Should not raise
    run_verify(output_dir=".", lockfile_path=lockfile_path)


def test_multiple_files_one_tampered(tmp_dir):
    """verify catches tampering even when only one of multiple files changed."""
    from repro.snapshot import run_snapshot
    from repro.verify import run_verify

    file1 = os.path.join(tmp_dir, "clean.tsv")
    file2 = os.path.join(tmp_dir, "tampered.tsv")
    lockfile_path = os.path.join(tmp_dir, "test.lock")

    with open(file1, "w") as f:
        f.write("clean data\n")
    with open(file2, "w") as f:
        f.write("original data\n")

    run_snapshot(
        output_path=lockfile_path,
        offline=True,
        quiet=True,
        output_files=[file1, file2],
    )

    # Only tamper file2
    with open(file2, "w") as f:
        f.write("REPLACED content\n")

    with pytest.raises(SystemExit) as exc_info:
        run_verify(output_dir=".", lockfile_path=lockfile_path)
    assert exc_info.value.code == 1
