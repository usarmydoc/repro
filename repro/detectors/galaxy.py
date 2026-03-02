"""Galaxy workflow detector: .ga file parser, Galaxy API (with timeout).

Parses Galaxy workflow (.ga) JSON files to extract tool versions.
Optionally queries a Galaxy API if online, skips gracefully if offline.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from repro import network


def find_ga_files(directory: str = ".") -> List[str]:
    """Find .ga (Galaxy workflow) files in the given directory."""
    ga_files = []
    try:
        for entry in os.listdir(directory):
            if entry.endswith(".ga"):
                ga_files.append(os.path.join(directory, entry))
    except OSError:
        pass
    return ga_files


def parse_ga_file(path: str) -> Dict[str, Any]:
    """Parse a Galaxy .ga workflow file.

    Galaxy workflow files are JSON with a specific structure containing
    steps, each with a tool_id and tool_version.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {"error": "Failed to parse {}: {}".format(path, str(e))}

    result = {
        "file": os.path.basename(path),
        "name": data.get("name", "unknown"),
        "annotation": data.get("annotation", ""),
        "format_version": data.get("format-version", "unknown"),
        "galaxy_version": data.get("release", data.get("version", "unknown")),
        "tools": {},
    }

    # Extract tools from steps
    steps = data.get("steps", {})
    for step_id, step in steps.items():
        tool_id = step.get("tool_id")
        tool_version = step.get("tool_version")
        if tool_id and tool_id != "":
            # Clean up tool_id — extract base name
            # e.g. "toolshed.g2.bx.psu.edu/repos/devteam/samtools_sort/samtools_sort/2.0.4"
            # -> "samtools_sort"
            parts = tool_id.split("/")
            short_name = parts[-2] if len(parts) >= 2 else tool_id
            result["tools"][short_name] = tool_version or "unknown"

    return result


def query_galaxy_api(url: str = "https://usegalaxy.org") -> Optional[Dict[str, str]]:
    """Query a Galaxy server API for version info. Skips if offline.

    Returns Galaxy version info or None if unavailable.
    """
    if not network.is_online():
        return None

    try:
        import requests
        resp = requests.get(
            "{}/api/version".format(url.rstrip("/")),
            timeout=10,
            proxies=network.get_requests_proxies(),
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def detect(directory: str = ".") -> Dict[str, Any]:
    """Detect Galaxy workflows and their tool versions.

    Args:
        directory: Directory to search for .ga files.
    """
    ga_files = find_ga_files(directory)

    if not ga_files:
        return {
            "found": False,
            "workflows": [],
            "galaxy_server": None,
        }

    workflows = []
    for ga in ga_files:
        parsed = parse_ga_file(ga)
        workflows.append(parsed)

    return {
        "found": True,
        "workflows": workflows,
        "galaxy_server": None,  # Set by query_galaxy_api if online
    }


if __name__ == "__main__":
    # Create a sample .ga file for testing
    import tempfile
    sample_ga = {
        "name": "Variant Calling Pipeline",
        "annotation": "Test workflow",
        "format-version": "0.1",
        "release": "23.1",
        "steps": {
            "0": {
                "tool_id": "toolshed.g2.bx.psu.edu/repos/devteam/trimmomatic/trimmomatic/0.38+galaxy1",
                "tool_version": "0.38+galaxy1",
                "type": "tool",
            },
            "1": {
                "tool_id": "toolshed.g2.bx.psu.edu/repos/devteam/bwa/bwa_mem/0.7.17.5",
                "tool_version": "0.7.17.5",
                "type": "tool",
            },
            "2": {
                "tool_id": "",
                "type": "data_input",
            },
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        ga_path = os.path.join(tmpdir, "variant_calling.ga")
        with open(ga_path, "w") as f:
            json.dump(sample_ga, f)

        result = detect(tmpdir)
        print(json.dumps(result, indent=2))
