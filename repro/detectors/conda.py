"""Conda/mamba detector: active env, all envs, packages, conflicts."""

import json
import os
from typing import Any, Dict, List, Optional

from repro.detectors._util import run_cmd, which


def _find_conda_binary() -> Optional[str]:
    """Find conda or mamba binary, preferring mamba."""
    for binary in ("mamba", "conda"):
        if which(binary):
            return binary
    return None


def _detect_active_env() -> Optional[str]:
    """Detect the currently active conda environment."""
    env = os.environ.get("CONDA_DEFAULT_ENV")
    if env:
        return env
    prefix = os.environ.get("CONDA_PREFIX")
    if prefix:
        return os.path.basename(prefix)
    return None


def _detect_active_install() -> bool:
    """Detect if a conda/pip install is currently in progress."""
    prefix = os.environ.get("CONDA_PREFIX", "")
    if prefix:
        lock_path = os.path.join(prefix, ".conda_lock")
        if os.path.exists(lock_path):
            return True
    out, rc = run_cmd(["pgrep", "-f", "conda install|mamba install|pip install"])
    if rc == 0 and out.strip():
        return True
    return False


def _list_envs(binary: str) -> List[Dict[str, str]]:
    """List all conda environments."""
    out, rc = run_cmd([binary, "env", "list", "--json"], timeout=30, combine_stderr=False)
    if rc != 0 or not out:
        return []
    try:
        data = json.loads(out)
        envs = []
        for path in data.get("envs", []):
            name = os.path.basename(path) if path else "base"
            if path == data.get("envs", [""])[0]:
                name = "base"
            envs.append({"name": name, "path": path})
        return envs
    except (json.JSONDecodeError, KeyError):
        return []


def _list_packages(binary: str, env_name: str = None) -> List[dict]:
    """List raw package dicts in a conda environment (for reuse)."""
    cmd = [binary, "list", "--json"]
    if env_name and env_name != "base":
        cmd.extend(["-n", env_name])

    out, rc = run_cmd(cmd, timeout=60, combine_stderr=False)
    if rc != 0 or not out:
        return []

    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def _packages_to_dict(raw_packages: list) -> Dict[str, str]:
    """Convert raw conda JSON package list to {name: version} dict."""
    return {
        pkg.get("name", ""): pkg.get("version", "")
        for pkg in raw_packages
        if pkg.get("name")
    }


def _detect_conflicts(raw_packages: list) -> List[str]:
    """Detect packages managed by both conda and pip from raw package list."""
    pip_packages = set()
    conda_packages = set()

    for pkg in raw_packages:
        name = pkg.get("name", "")
        channel = pkg.get("channel", "")
        if channel == "pypi":
            pip_packages.add(name)
        elif name:
            conda_packages.add(name)

    return sorted(pip_packages & conda_packages)


def detect(all_envs: bool = False, env_name: str = None) -> Dict[str, Any]:
    """Detect conda/mamba environment state.

    Args:
        all_envs: If True, snapshot all conda environments.
        env_name: Snapshot a specific named environment.
    """
    binary = _find_conda_binary()
    if binary is None:
        return {
            "found": False,
            "binary": None,
            "version": None,
            "active_env": None,
            "packages": {},
            "all_envs": [],
            "conflicts": [],
            "install_in_progress": False,
        }

    out, _ = run_cmd([binary, "--version"])
    version = out.split()[-1] if out else "unknown"

    active = _detect_active_env()
    installing = _detect_active_install()

    target_env = env_name or active or "base"

    # Fetch raw packages once, derive both dict and conflicts from it
    raw_packages = _list_packages(binary, target_env)
    packages = _packages_to_dict(raw_packages)
    conflicts = _detect_conflicts(raw_packages)

    result = {
        "found": True,
        "binary": binary,
        "version": version,
        "active_env": active,
        "env_name": target_env,
        "packages": packages,
        "conflicts": conflicts,
        "install_in_progress": installing,
    }

    if all_envs:
        envs = _list_envs(binary)
        result["all_envs"] = []
        for env in envs:
            env_pkgs = _list_packages(binary, env["name"])
            result["all_envs"].append({
                "name": env["name"],
                "path": env["path"],
                "package_count": len(env_pkgs),
            })
    else:
        result["all_envs"] = []

    return result


if __name__ == "__main__":
    result = detect(all_envs=True)
    summary = dict(result)
    pkg_count = len(summary.pop("packages", {}))
    summary["package_count"] = pkg_count
    print(json.dumps(summary, indent=2))
