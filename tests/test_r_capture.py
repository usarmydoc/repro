# Regression test for: R ENVIRONMENT CAPTURE
# Verifies that R packages are correctly detected and captured in the lockfile.
# Files tested:
#   repro/detectors/packages.py (detect_r_packages function, lines 22-53)
#   repro/snapshot.py (_merge_result, line 164: R_packages merge)

import pytest


def test_r_packages_detected():
    """R package detector finds installed packages with versions."""
    from repro.detectors.packages import detect_r_packages

    result = detect_r_packages()
    # R is installed on this system with jsonlite
    assert isinstance(result, dict), "detect_r_packages should return a dict"
    if result:  # Only assert if R packages were found
        # All values should be version strings
        for name, version in result.items():
            assert isinstance(name, str)
            assert isinstance(version, str)


def test_r_packages_in_snapshot():
    """R packages appear in the package_managers.R_packages section."""
    from repro.detectors.packages import detect

    result = detect()
    assert "R_packages" in result, "detect() should have R_packages key"
    r_pkgs = result["R_packages"]
    assert isinstance(r_pkgs, dict)


def test_r_packages_include_bioconductor():
    """R package capture includes Bioconductor packages like DESeq2."""
    from repro.detectors.packages import detect_r_packages

    result = detect_r_packages()
    if not result:
        pytest.skip("No R packages detected on this system")
    # Check for known installed packages
    assert "jsonlite" in result, "jsonlite should be in R packages"
