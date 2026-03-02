"""Container runtime detector: Docker, Singularity, Apptainer, Podman.

Gracefully handles missing runtimes — never crashes, always returns
a clean not-found result.
"""

import os
from typing import Any, Dict, Optional

from repro.detectors._util import detect_binary


def _detect_docker_in_docker() -> bool:
    """Detect if running inside a Docker container (Docker-in-Docker)."""
    if os.path.exists("/.dockerenv"):
        return True
    try:
        with open("/proc/1/cgroup", "r") as f:
            content = f.read()
        if "docker" in content or "containerd" in content:
            return True
    except (FileNotFoundError, PermissionError):
        pass
    return False


def _detect_current_image() -> Optional[str]:
    """If inside a container, try to detect the current image."""
    for var in ("SINGULARITY_CONTAINER", "APPTAINER_CONTAINER"):
        val = os.environ.get(var)
        if val:
            return val
    return None


def detect() -> Dict[str, Any]:
    """Detect all container runtimes.

    Returns a dict with each runtime's status. Missing runtimes
    get a clean {found: false} entry — never crashes.
    """
    runtimes = {
        "docker": detect_binary("docker", ["docker", "--version"], r"Docker version ([\d.]+)"),
        "singularity": detect_binary("singularity", ["singularity", "--version"], r"([\d.]+)"),
        "apptainer": detect_binary("apptainer", ["apptainer", "--version"], r"([\d.]+)"),
        "podman": detect_binary("podman", ["podman", "--version"], r"version ([\d.]+)"),
    }

    # Find the preferred / active runtime
    active_runtime = None
    active_version = None
    for name in ("apptainer", "singularity", "docker", "podman"):
        if runtimes[name]["found"]:
            active_runtime = name
            active_version = runtimes[name]["version"]
            break

    return {
        "runtimes": runtimes,
        "active_runtime": active_runtime,
        "active_version": active_version,
        "docker_in_docker": _detect_docker_in_docker(),
        "current_image": _detect_current_image(),
    }


if __name__ == "__main__":
    import json
    result = detect()
    print(json.dumps(result, indent=2))

    found = [k for k, v in result["runtimes"].items() if v["found"]]
    not_found = [k for k, v in result["runtimes"].items() if not v["found"]]
    print("\nFound: {}".format(", ".join(found) if found else "none"))
    print("Not found (graceful): {}".format(", ".join(not_found)))
