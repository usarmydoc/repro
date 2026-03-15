# Regression test for: CONDA ENVIRONMENT CAPTURE
# Verifies that conda environments are correctly detected and captured
# in the lockfile with exact package versions.
# Files tested:
#   repro/detectors/conda.py (detect function)
#   repro/restore.py (plan_restore env_type detection)

import json
import os
import tempfile
import shutil

import pytest


def test_conda_env_type_when_no_venv():
    """plan_restore returns env_type='conda' when virtualenv is inactive."""
    from repro.restore import plan_restore

    data = {
        "pipeline_type": "nextflow",
        "package_managers": {
            "virtualenv": {
                "active_venv": None,
                "venv_type": "none",
            },
            "conda": {
                "packages": {"numpy": "1.26.0", "pandas": "2.1.0"},
            },
            "pip": {},
        },
    }
    plan = plan_restore(data)
    assert plan["env_type"] == "conda"
    assert plan["conda_packages"] == {"numpy": "1.26.0", "pandas": "2.1.0"}


def test_conda_packages_captured_in_plan():
    """Conda packages from lockfile appear in restore plan."""
    from repro.restore import plan_restore

    data = {
        "pipeline_type": "snakemake",
        "package_managers": {
            "virtualenv": {"venv_type": "none"},
            "conda": {
                "packages": {
                    "numpy": "1.26.0",
                    "pandas": "2.1.0",
                    "python": "3.11.5",
                },
            },
            "pip": {"requests": "2.31.0"},
        },
    }
    plan = plan_restore(data)
    assert plan["conda_packages"]["numpy"] == "1.26.0"
    assert plan["conda_packages"]["pandas"] == "2.1.0"
    assert plan["pip_packages"]["requests"] == "2.31.0"


def test_conda_detector_returns_expected_keys():
    """Conda detector output has all expected keys."""
    from repro.detectors.conda import detect

    result = detect()
    expected_keys = {"found", "binary", "version", "active_env",
                     "packages", "conflicts", "install_in_progress"}
    # All expected keys should be present
    for key in expected_keys:
        assert key in result, "Missing key '{}' in conda detect output".format(key)
