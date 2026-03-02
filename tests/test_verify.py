"""Tests for verify module."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro.verify import _classify_file, _hash_file, scan_and_hash


def test_classify_binary():
    """Test binary file classification."""
    assert _classify_file("data.bam") == "binary"
    assert _classify_file("genome.fa.gz") == "binary"
    assert _classify_file("model.h5") == "binary"
    print("  Binary classification: OK")


def test_classify_text():
    """Test text file classification."""
    assert _classify_file("results.csv") == "text"
    assert _classify_file("log.txt") == "text"
    assert _classify_file("config.yaml") == "text"
    print("  Text classification: OK")


def test_hash_text_normalization():
    """Test that CRLF and LF produce same hash for text files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lf_file = os.path.join(tmpdir, "lf.txt")
        crlf_file = os.path.join(tmpdir, "crlf.txt")

        with open(lf_file, "wb") as f:
            f.write(b"line1\nline2\nline3\n")
        with open(crlf_file, "wb") as f:
            f.write(b"line1\r\nline2\r\nline3\r\n")

        h_lf = _hash_file(lf_file, normalize_text=True)
        h_crlf = _hash_file(crlf_file, normalize_text=True)
        assert h_lf == h_crlf, "CRLF and LF should produce same hash"
        print("  Line ending normalization: OK ({})".format(h_lf[:16]))


def test_scan_and_hash():
    """Test directory scanning and hashing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        with open(os.path.join(tmpdir, "results.csv"), "w") as f:
            f.write("a,b,c\n1,2,3\n")
        with open(os.path.join(tmpdir, "data.bin"), "wb") as f:
            f.write(b"\x00\x01\x02\x03")

        results = scan_and_hash(tmpdir)
        assert len(results) == 2
        assert "results.csv" in results
        assert results["results.csv"]["type"] == "text"
        print("  Scan and hash: {} files".format(len(results)))


if __name__ == "__main__":
    for t in [test_classify_binary, test_classify_text, test_hash_text_normalization, test_scan_and_hash]:
        print("Running {}...".format(t.__name__))
        t()
        print("  PASSED")
    print("\nAll verify tests passed!")
