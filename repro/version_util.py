"""Shared version parsing and comparison utilities.

Single source of truth for version string handling across
score.py, explain.py, security.py, and update.py.
"""

import re
from typing import Tuple


def parse_version(v: str) -> Tuple:
    """Parse a version string into a comparable tuple.

    Strips leading 'v', comparison operators, and build metadata.
    Converts numeric parts to int, keeps non-numeric parts as strings.

    Examples:
        "1.2.3"       -> (1, 2, 3)
        "v2.0.1-beta" -> (2, 0, 1)
        "<2.31.0"     -> (2, 31, 0)
        "22.x"        -> (22, 0)
    """
    if not v:
        return (0,)
    v = str(v)
    # Strip comparison operators (for constraint strings like "<2.31.0")
    v = re.sub(r'^[<>=!~]+', '', v)
    # Strip leading 'v'
    v = re.sub(r'^v', '', v)
    # Replace wildcard .x with .0
    v = v.replace(".x", ".0")
    # Strip build metadata after - or +
    v = re.sub(r'[-+].*$', '', v)

    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(p)
    return tuple(parts) if parts else (0,)


def parse_major_minor(v: str) -> Tuple[int, int]:
    """Parse version to (major, minor) tuple. Convenience for coarse comparison."""
    t = parse_version(v)
    major = t[0] if len(t) > 0 and isinstance(t[0], int) else 0
    minor = t[1] if len(t) > 1 and isinstance(t[1], int) else 0
    return (major, minor)


def version_diff_severity(recorded: str, current: str) -> str:
    """Compare two versions and return severity string.

    Returns one of: 'match', 'patch', 'minor', 'major', 'missing'.
    """
    if not recorded or not current:
        return "missing"
    if recorded == current:
        return "match"

    rec = parse_version(recorded)
    cur = parse_version(current)

    if rec == cur:
        return "match"

    rec_parts = list(rec) + [0, 0, 0]
    cur_parts = list(cur) + [0, 0, 0]

    try:
        if rec_parts[0] != cur_parts[0]:
            return "major"
        if rec_parts[1] != cur_parts[1]:
            return "minor"
        return "patch"
    except (IndexError, TypeError):
        return "minor"


def version_lt(version: str, threshold: str) -> bool:
    """Check if version < threshold. Used for CVE range checks."""
    return parse_version(version) < parse_version(threshold)
