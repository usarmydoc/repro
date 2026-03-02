"""Language runtime detector: Python, R, Julia, Perl, Java, Groovy, Bash."""

import os
import sys
from typing import Any, Dict

from repro.detectors._util import detect_binary, resolve_path


def detect() -> Dict[str, Any]:
    """Detect all supported language runtimes."""
    languages = {}

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
