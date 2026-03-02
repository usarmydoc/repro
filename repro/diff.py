"""Diff two repro.lock files and show rich comparison table."""

from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table

from repro import lockfile

console = Console()


def _flatten(data: dict, prefix: str = "") -> Dict[str, str]:
    """Flatten a nested dict into dot-separated keys with string values."""
    flat = {}
    for key, val in data.items():
        full_key = "{}.{}".format(prefix, key) if prefix else key
        if isinstance(val, dict):
            flat.update(_flatten(val, full_key))
        elif isinstance(val, list):
            flat[full_key] = "[{} items]".format(len(val))
        else:
            flat[full_key] = str(val) if val is not None else "null"
    return flat


def compute_diff(data1: dict, data2: dict) -> List[Dict[str, Any]]:
    """Compute differences between two lockfile dicts.

    Returns a list of {key, old, new, change_type} dicts.
    """
    flat1 = _flatten(data1)
    flat2 = _flatten(data2)

    all_keys = sorted(set(flat1.keys()) | set(flat2.keys()))
    diffs = []

    for key in all_keys:
        v1 = flat1.get(key)
        v2 = flat2.get(key)

        if v1 == v2:
            continue

        if v1 is None:
            change_type = "added"
        elif v2 is None:
            change_type = "removed"
        else:
            change_type = "changed"

        diffs.append({
            "key": key,
            "old": v1,
            "new": v2,
            "change_type": change_type,
        })

    return diffs


def run_diff(path1: str, path2: str):
    """Compare two repro.lock files and show differences."""
    data1 = lockfile.read_or_exit(path1)
    data2 = lockfile.read_or_exit(path2)

    diffs = compute_diff(data1, data2)

    if not diffs:
        console.print("[green]No differences found.[/green]")
        return

    # Filter out noisy keys like timestamps
    skip_prefixes = {"created_at", "data_versions_used"}
    meaningful = [d for d in diffs if not any(d["key"].startswith(s) for s in skip_prefixes)]
    meta = [d for d in diffs if any(d["key"].startswith(s) for s in skip_prefixes)]

    if meaningful:
        table = Table(title="Differences ({} changes)".format(len(meaningful)))
        table.add_column("Key", style="cyan", max_width=50)
        table.add_column("Old", style="red", max_width=30)
        table.add_column("New", style="green", max_width=30)
        table.add_column("Type", style="yellow")

        for d in meaningful:
            table.add_row(
                d["key"],
                d["old"] or "-",
                d["new"] or "-",
                d["change_type"],
            )
        console.print(table)
    else:
        console.print("[green]Only metadata differences (timestamps, etc).[/green]")

    if meta:
        console.print("\n[dim]({} metadata changes hidden)[/dim]".format(len(meta)))
