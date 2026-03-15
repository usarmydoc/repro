# Regression test for: VENV RESTORE BUG
# Bug: restore.py always created conda environments regardless of env_type.
# Fix: repro/restore.py — added _detect_env_type() and _restore_venv()
#      repro/cli.py — added --target option to restore command
# Files changed:
#   repro/restore.py (lines 35-50: _detect_env_type, lines 186-230: _restore_venv)
#   repro/cli.py (line 101: --target option)

import json
import os
import shutil
import subprocess
import tempfile

import pytest


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="repro_test_venv_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_detect_env_type_venv():
    """plan_restore returns env_type='venv' when lockfile records a venv."""
    from repro.restore import plan_restore

    data = {
        "pipeline_type": "script",
        "package_managers": {
            "virtualenv": {
                "active_venv": "/tmp/test_venv",
                "venv_type": "venv",
                "poetry": {"found": False},
                "pipenv": {"found": False},
            },
            "conda": {"packages": {}},
            "pip": {"numpy": "1.26.4"},
        },
    }
    plan = plan_restore(data)
    assert plan["env_type"] == "venv", (
        "Expected env_type='venv' but got '{}'".format(plan["env_type"])
    )


def test_detect_env_type_conda_when_no_venv():
    """plan_restore returns env_type='conda' when no venv is active."""
    from repro.restore import plan_restore

    data = {
        "pipeline_type": "nextflow",
        "package_managers": {
            "virtualenv": {
                "active_venv": None,
                "venv_type": "none",
            },
            "conda": {"packages": {"numpy": "1.26.0"}},
            "pip": {},
        },
    }
    plan = plan_restore(data)
    assert plan["env_type"] == "conda"


def test_venv_restore_creates_venv(tmp_dir):
    """Restoring a venv lockfile creates a venv, not a conda env."""
    lockfile_path = os.path.join(tmp_dir, "test.lock")
    venv_path = os.path.join(tmp_dir, "restored_venv")

    data = {
        "repro_schema_version": "1.0",
        "created_at": "2026-01-01T00:00:00",
        "repro_version": "0.1.0",
        "pipeline_type": "script",
        "languages": {"python": {"version": "3.12", "path": "python3"}},
        "package_managers": {
            "virtualenv": {
                "active_venv": "/tmp/original_venv",
                "venv_type": "venv",
                "poetry": {"found": False},
                "pipenv": {"found": False},
            },
            "conda": {"packages": {}},
            "pip": {},
        },
        "system": {},
        "tools": {},
        "containers": {},
        "galaxy": {},
        "references": {},
        "environment": {},
        "verified_outputs": {},
        "data_versions_used": {},
    }
    with open(lockfile_path, "w") as f:
        json.dump(data, f)

    from repro.restore import run_restore
    run_restore(lockfile_path, target=venv_path)

    # Verify it's a venv, not a conda env
    assert os.path.isfile(os.path.join(venv_path, "bin", "activate")), (
        "Expected venv activate script at {}/bin/activate".format(venv_path)
    )
    assert os.path.isfile(os.path.join(venv_path, "pyvenv.cfg")), (
        "Expected pyvenv.cfg (venv marker) in restored environment"
    )


def test_venv_restore_installs_pip_packages(tmp_dir):
    """Restoring a venv lockfile installs pip packages correctly."""
    lockfile_path = os.path.join(tmp_dir, "test.lock")
    venv_path = os.path.join(tmp_dir, "restored_venv")

    data = {
        "repro_schema_version": "1.0",
        "created_at": "2026-01-01T00:00:00",
        "repro_version": "0.1.0",
        "pipeline_type": "script",
        "languages": {"python": {"version": "3.12", "path": "python3"}},
        "package_managers": {
            "virtualenv": {
                "active_venv": "/tmp/original_venv",
                "venv_type": "venv",
                "poetry": {"found": False},
                "pipenv": {"found": False},
            },
            "conda": {"packages": {}},
            "pip": {"six": "1.17.0"},
        },
        "system": {},
        "tools": {},
        "containers": {},
        "galaxy": {},
        "references": {},
        "environment": {},
        "verified_outputs": {},
        "data_versions_used": {},
    }
    with open(lockfile_path, "w") as f:
        json.dump(data, f)

    from repro.restore import run_restore
    run_restore(lockfile_path, target=venv_path)

    # Check package is installed
    pip_path = os.path.join(venv_path, "bin", "pip")
    result = subprocess.run(
        [pip_path, "show", "six"], capture_output=True, text=True
    )
    assert result.returncode == 0, "six package not found in restored venv"
    assert "1.17.0" in result.stdout, "six version mismatch"
