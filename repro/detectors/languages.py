"""Language runtime detector: Python, R, Julia, Perl, Java, Groovy, Bash."""

import os
import sys
from typing import Any, Dict

from repro.detectors._util import detect_binary, resolve_path, run_cmd


def detect_python(python: str) -> Dict[str, Any]:
    """Detect a specific Python interpreter by running it."""
    out, rc = run_cmd([python, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
                      combine_stderr=False)
    info = {"found": True, "version": out, "path": python, "real_path": os.path.realpath(python)}
    if rc != 0 or not out:
        info["version"] = "unknown"
        info["reason"] = "running {} to read its version failed".format(python)
    return info


def detect(python: str = None) -> Dict[str, Any]:
    """Detect all supported language runtimes.

    Args:
        python: Interpreter to report (e.g. the --env environment's). If
            None, reports python3 on PATH with the running version.
    """
    languages = {}

    if python:
        languages["python"] = detect_python(python)
    else:
        # Python — use the current interpreter's version for accuracy
        python_paths = resolve_path("python3")
        languages["python"] = {
            "found": True,
            "version": "{}.{}.{}".format(*sys.version_info[:3]),
            "path": python_paths["path"] or sys.executable,
            "real_path": python_paths["real_path"] or os.path.realpath(sys.executable),
        }

    # R
    languages["R"] = detect_binary("R", ["R", "--version"], r"R version ([\d.]+)")

    # Julia
    languages["julia"] = detect_binary("julia", ["julia", "--version"], r"julia version ([\d.]+)")

    # Perl
    languages["perl"] = detect_binary("perl", ["perl", "--version"], r"\(v([\d.]+)\)")

    # Java
    languages["java"] = detect_binary("java", ["java", "-version"], r'version "([^"]+)"')

    # Groovy
    languages["groovy"] = detect_binary("groovy", ["groovy", "--version"], r"Groovy Version: ([\d.]+)")

    # Bash
    languages["bash"] = detect_binary("bash", ["bash", "--version"], r"version ([\d.]+)")

    return languages


if __name__ == "__main__":
    import json
    result = detect()
    print(json.dumps(result, indent=2))
