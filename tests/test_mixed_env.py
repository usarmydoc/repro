# Regression test for: R + PYTHON MIXED ENVIRONMENT
# Verifies that when a Python venv uses rpy2, the lockfile captures
# both Python pip packages AND R packages, with env_type="venv".
# Files tested:
#   repro/detectors/virtualenv.py (detect, lines 66-84)
#   repro/detectors/packages.py (detect, lines 112-120)
#   repro/restore.py (_detect_env_type, lines 35-50)

import pytest


def test_mixed_env_type_is_venv():
    """env_type should be 'venv' in a mixed Python+R environment."""
    from repro.restore import _detect_env_type

    data = {
        "package_managers": {
            "virtualenv": {
                "active_venv": "/tmp/test_venv",
                "venv_type": "venv",
            },
            "conda": {"packages": {"numpy": "1.26.0"}},
            "pip": {"rpy2": "3.5.17", "numpy": "1.26.4"},
            "R_packages": {"ggplot2": "3.5.0", "jsonlite": "2.0.0"},
        },
    }
    env_type = _detect_env_type(data)
    assert env_type == "venv", (
        "Mixed env should be 'venv', not '{}'".format(env_type)
    )


def test_mixed_env_captures_both_pip_and_r():
    """Lockfile should have both pip and R_packages in a mixed env."""
    from repro.restore import plan_restore

    data = {
        "pipeline_type": "snakemake",
        "package_managers": {
            "virtualenv": {
                "active_venv": "/tmp/test_venv",
                "venv_type": "venv",
            },
            "conda": {"packages": {}},
            "pip": {"rpy2": "3.5.17", "numpy": "1.26.4"},
            "R_packages": {"ggplot2": "3.5.0"},
        },
    }
    plan = plan_restore(data)
    assert plan["env_type"] == "venv"
    assert "rpy2" in plan["pip_packages"]
    assert "ggplot2" in plan["r_packages"]


def test_venv_priority_over_conda():
    """When both venv and conda are detected, venv takes priority."""
    from repro.restore import _detect_env_type

    data = {
        "package_managers": {
            "virtualenv": {
                "active_venv": "/home/user/myenv",
                "venv_type": "venv",
                "warning": "Both a virtual environment and conda environment are active.",
            },
            "conda": {
                "packages": {"python": "3.12.0"},
            },
        },
    }
    assert _detect_env_type(data) == "venv"
