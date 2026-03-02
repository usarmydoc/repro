"""Lockfile read/write, versioning, migration, and atomic writes.

Handles all I/O for repro.lock files including:
- Atomic writes (temp file + rename) so concurrent snapshots never corrupt
- Schema version detection and migration
- Git merge conflict detection
- Corruption handling with clear error messages
"""

import json
import os
import re
import tempfile
from typing import Any, Dict, Optional

from rich.console import Console

CURRENT_SCHEMA_VERSION = "1.0"

# Regex to detect git merge conflict markers
_CONFLICT_RE = re.compile(r'^(<{7}|={7}|>{7})\s', re.MULTILINE)


def empty_lockfile() -> Dict[str, Any]:
    """Return a minimal valid lockfile skeleton."""
    return {
        "repro_schema_version": CURRENT_SCHEMA_VERSION,
        "created_at": "",
        "repro_version": "",
        "pipeline_type": "unknown",
        "system": {},
        "languages": {},
        "package_managers": {},
        "tools": {},
        "containers": {},
        "galaxy": {},
        "references": {},
        "environment": {},
        "verified_outputs": {},
        "data_versions_used": {},
    }


def validate_lockfile(data: Dict[str, Any]) -> list:
    """Validate lockfile structure. Returns list of error strings (empty = valid)."""
    errors = []

    if not isinstance(data, dict):
        errors.append("Lockfile root must be a JSON object")
        return errors

    if "repro_schema_version" not in data:
        errors.append("Missing required field: repro_schema_version")

    # Check for expected top-level keys
    expected = {"repro_schema_version", "created_at", "repro_version"}
    for key in expected:
        if key not in data:
            errors.append("Missing required field: {}".format(key))

    return errors


def has_conflict_markers(text: str) -> bool:
    """Detect git merge conflict markers in lockfile text."""
    return bool(_CONFLICT_RE.search(text))


def read_lockfile(path: str) -> Dict[str, Any]:
    """Read and parse a lockfile, with full error handling.

    Args:
        path: Path to the repro.lock file.

    Returns:
        Parsed lockfile dict.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is corrupted, has conflicts, or is invalid.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise FileNotFoundError("Lockfile not found: {}".format(path))
    except PermissionError:
        raise ValueError(
            "Cannot read lockfile (permission denied): {}\n"
            "Try: chmod 644 {}".format(path, path)
        )

    if not text.strip():
        raise ValueError(
            "Lockfile is empty: {}\n"
            "Run 'repro snapshot' to create a new one.".format(path)
        )

    # Check for git merge conflicts
    if has_conflict_markers(text):
        raise ValueError(
            "Lockfile contains git merge conflict markers: {}\n"
            "Resolve the conflict manually, then run 'repro snapshot' to regenerate.\n"
            "Tip: 'git checkout --theirs {}' to keep the incoming version, or\n"
            "     'git checkout --ours {}' to keep your version.".format(path, path, path)
        )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            "Lockfile is corrupted (invalid JSON): {}\n"
            "Error: {}\n"
            "Run 'repro snapshot' to regenerate.".format(path, str(e))
        )

    errors = validate_lockfile(data)
    if errors:
        raise ValueError(
            "Lockfile validation failed: {}\n{}".format(
                path, "\n".join("  - " + e for e in errors)
            )
        )

    return data


def write_lockfile(path: str, data: Dict[str, Any]):
    """Write lockfile atomically using temp file + rename.

    This ensures that concurrent writes never produce a corrupted file.
    If the write fails, the original file is untouched.

    Args:
        path: Destination path for the lockfile.
        data: Lockfile dict to write.

    Raises:
        OSError: If the target directory is not writable.
    """
    target_dir = os.path.dirname(os.path.abspath(path))

    if not os.path.isdir(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    if not os.access(target_dir, os.W_OK):
        raise OSError(
            "Cannot write to directory: {}\n"
            "Use -o /path/to/output.lock to specify a writable location.".format(
                target_dir
            )
        )

    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    # Atomic write: write to temp file in same directory, then rename
    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp",
        prefix=".repro_lock_",
        dir=target_dir,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def backup_lockfile(path: str) -> Optional[str]:
    """Create a .bak backup of an existing lockfile.

    Returns the backup path, or None if the original doesn't exist.
    """
    if not os.path.exists(path):
        return None

    bak_path = path + ".bak"
    try:
        with open(path, "r", encoding="utf-8") as src:
            content = src.read()
        with open(bak_path, "w", encoding="utf-8") as dst:
            dst.write(content)
        return bak_path
    except OSError:
        return None


def migrate_lockfile(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate an old-schema lockfile to the current version.

    Currently only version 1.0 exists. This function is a placeholder
    for future migrations (1.0 -> 1.1, etc).

    Returns the migrated data dict.
    """
    version = data.get("repro_schema_version", "unknown")

    if version == CURRENT_SCHEMA_VERSION:
        return data

    # Future migrations would go here:
    # if version == "0.9":
    #     data = _migrate_0_9_to_1_0(data)

    # If we don't know the version, stamp it as current and fill missing keys
    template = empty_lockfile()
    for key, default in template.items():
        if key not in data:
            data[key] = default

    data["repro_schema_version"] = CURRENT_SCHEMA_VERSION
    return data


def get_schema_version(data: Dict[str, Any]) -> str:
    """Extract schema version from lockfile data."""
    return data.get("repro_schema_version", "unknown")


def needs_migration(data: Dict[str, Any]) -> bool:
    """Check if a lockfile needs schema migration."""
    return get_schema_version(data) != CURRENT_SCHEMA_VERSION


def read_or_exit(path: str) -> Dict[str, Any]:
    """Read a lockfile or print a rich error and exit.

    Consolidates the try/except pattern used by all CLI commands.
    """
    try:
        return read_lockfile(path)
    except (FileNotFoundError, ValueError) as e:
        Console().print("[red]Error:[/red] {}".format(e))
        raise SystemExit(1)


def load_data_file(name: str) -> dict:
    """Load a JSON data file from the data/ directory.

    Args:
        name: Filename without .json extension (e.g., 'breaking_changes').

    Returns:
        Parsed dict, or {} if file is missing or corrupted.
    """
    from repro import DATA_DIR
    path = os.path.join(DATA_DIR, "{}.json".format(name))
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
