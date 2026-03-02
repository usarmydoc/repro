"""Virtual environment detector: venv, virtualenv, Poetry, pipenv."""

import os
from typing import Any, Dict, Optional

from repro.detectors._util import run_cmd


def _detect_active_venv() -> Optional[str]:
    """Detect if a Python virtual environment is active."""
    return os.environ.get("VIRTUAL_ENV")


def _detect_venv_type(venv_path: str) -> str:
    """Determine venv type from its structure."""
    if not venv_path:
        return "none"

    if os.environ.get("POETRY_ACTIVE"):
        return "poetry"
    if os.environ.get("PIPENV_ACTIVE"):
        return "pipenv"

    cfg = os.path.join(venv_path, "pyvenv.cfg")
    if os.path.exists(cfg):
        try:
            with open(cfg, "r") as f:
                content = f.read()
            if "virtualenv" in content.lower():
                return "virtualenv"
        except OSError:
            pass
        return "venv"

    return "unknown"


def _detect_poetry() -> Dict[str, Any]:
    """Detect Poetry configuration."""
    if os.path.exists("pyproject.toml"):
        try:
            with open("pyproject.toml", "r") as f:
                content = f.read()
            if "[tool.poetry]" in content:
                out, rc = run_cmd(["poetry", "--version"])
                version = out.split()[-1].strip("()") if rc == 0 and out else None
                return {"found": True, "version": version, "pyproject_toml": True}
        except OSError:
            pass
    return {"found": False, "version": None}


def _detect_pipenv() -> Dict[str, Any]:
    """Detect Pipenv configuration."""
    if os.path.exists("Pipfile"):
        out, rc = run_cmd(["pipenv", "--version"])
        version = None
        if rc == 0 and out:
            parts = out.split("version")
            if len(parts) > 1:
                version = parts[-1].strip()
        return {"found": True, "version": version, "pipfile": True}
    return {"found": False, "version": None}


def detect() -> Dict[str, Any]:
    """Detect virtual environment state."""
    active = _detect_active_venv()

    result = {
        "active_venv": active,
        "venv_type": _detect_venv_type(active) if active else "none",
        "poetry": _detect_poetry(),
        "pipenv": _detect_pipenv(),
    }

    conda_env = os.environ.get("CONDA_DEFAULT_ENV")
    if active and conda_env:
        result["warning"] = (
            "Both a virtual environment and conda environment are active. "
            "This can cause package resolution conflicts."
        )

    return result


if __name__ == "__main__":
    import json
    print(json.dumps(detect(), indent=2))
