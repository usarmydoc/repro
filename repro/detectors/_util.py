"""Shared utilities for all detectors.

Consolidates common patterns: subprocess execution, binary lookup,
version extraction, and path resolution.
"""

import os
import re
import shutil
import subprocess
from typing import Any, Dict, Optional, Tuple


def run_cmd(cmd, timeout=10, combine_stderr=True) -> Tuple[str, int]:
    """Run a command and return (output, returncode). Never raises.

    Args:
        cmd: Command as a list of strings.
        timeout: Max seconds to wait.
        combine_stderr: If True, fall back to stderr when stdout is empty.
            Useful for tools like java that print version info to stderr.

    Returns:
        (output_string, return_code). On failure returns ("", 1).
    """
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if combine_stderr:
            out = result.stdout.strip() or result.stderr.strip()
        else:
            out = result.stdout.strip()
        return out, result.returncode
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "", 1


def which(binary: str) -> Optional[str]:
    """Find a binary on PATH using shutil.which (no subprocess)."""
    return shutil.which(binary)


def resolve_path(binary: str) -> Dict[str, Optional[str]]:
    """Find binary on PATH and resolve symlinks.

    Returns dict with 'path' (symlink) and 'real_path' (resolved).
    """
    path = shutil.which(binary)
    if path is None:
        return {"path": None, "real_path": None}
    real = os.path.realpath(path)
    return {"path": path, "real_path": real if real != path else path}


def detect_binary(binary: str, version_cmd: list, version_regex: str = None,
                  extra_paths: list = None) -> Dict[str, Any]:
    """Detect a CLI binary: find it, get version, resolve symlinks.

    This is the shared implementation for languages._detect_one,
    tools._detect_tool, and containers._detect_runtime.

    Args:
        binary: Name of the binary to search for.
        version_cmd: Command to get version string.
        version_regex: Regex to extract version (group 1).
        extra_paths: Additional directories to search.

    Returns:
        Dict with found, version, path, real_path.
    """
    path = shutil.which(binary)

    # Search extra paths if not found on PATH
    if path is None and extra_paths:
        for d in extra_paths:
            candidate = os.path.join(d, binary)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                path = candidate
                break

    if path is None:
        return {"found": False, "version": None, "path": None, "real_path": None}

    real_path = os.path.realpath(path)

    out, _ = run_cmd(version_cmd)
    version = out
    if version_regex and out:
        match = re.search(version_regex, out)
        if match:
            version = match.group(1)

    return {
        "found": True,
        "version": version or "unknown",
        "path": path,
        "real_path": real_path if real_path != path else path,
    }
