"""Tests for security module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro.security import check_vulnerabilities
from repro.lockfile import load_data_file


def test_load_cve_snapshot():
    """Test CVE snapshot loads."""
    data = load_data_file("cve_snapshot")
    assert isinstance(data, dict)
    assert "vulnerabilities" in data
    assert len(data["vulnerabilities"]) > 0
    print("  CVE snapshot: {} entries".format(len(data["vulnerabilities"])))


def test_detect_vulnerability():
    """Test vulnerability detection for an old package."""
    cve_data = load_data_file("cve_snapshot")
    # requests < 2.31.0 has CVE-2023-32681
    packages = {"requests": "2.28.0"}
    vulns = check_vulnerabilities(packages, cve_data)
    assert len(vulns) >= 1
    assert vulns[0]["cve"] == "CVE-2023-32681"
    print("  Detected CVE for old requests: {}".format(vulns[0]["cve"]))


def test_no_vulnerability():
    """Test no vulnerability for current package."""
    cve_data = load_data_file("cve_snapshot")
    packages = {"requests": "2.31.0"}
    vulns = check_vulnerabilities(packages, cve_data)
    assert len(vulns) == 0
    print("  No CVE for current requests: OK")


def test_unknown_package():
    """Test unknown package handled gracefully."""
    cve_data = load_data_file("cve_snapshot")
    packages = {"my_custom_lib": "1.0.0"}
    vulns = check_vulnerabilities(packages, cve_data)
    assert len(vulns) == 0
    print("  Unknown package: no false positives")


if __name__ == "__main__":
    for t in [test_load_cve_snapshot, test_detect_vulnerability,
              test_no_vulnerability, test_unknown_package]:
        print("Running {}...".format(t.__name__))
        t()
        print("  PASSED")
    print("\nAll security tests passed!")
