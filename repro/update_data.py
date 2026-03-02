"""Update data files: pull latest breaking_changes, CVEs, pipeline_requirements.

Fetches from public GitHub URLs defined in data_version.json.
Shows clear diff of what changed. Falls back gracefully if unreachable.
"""

import datetime
import json
import os

from rich.console import Console
from rich.table import Table

from repro import network, DATA_DIR

console = Console()


def _load_data_version() -> dict:
    """Load data_version.json."""
    from repro import lockfile
    return lockfile.load_data_file("data_version")


def _check_staleness() -> list:
    """Check if data files are older than 30 days. Returns warnings."""
    warnings = []
    versions = _load_data_version()
    now = datetime.datetime.now()

    for key, info in versions.items():
        last_updated = info.get("last_updated", "")
        if last_updated:
            try:
                updated_dt = datetime.datetime.strptime(last_updated, "%Y-%m-%d")
                age_days = (now - updated_dt).days
                if age_days > 30:
                    warnings.append(
                        "{}: last updated {} ({} days ago). "
                        "Run 'repro update-data' for latest.".format(
                            key, last_updated, age_days
                        )
                    )
            except ValueError:
                pass

    return warnings


def check_staleness_nudge():
    """Print staleness warnings if any. Called on every repro command."""
    warnings = _check_staleness()
    for w in warnings:
        console.print("[yellow]Stale data:[/yellow] {}".format(w))


def run_update_data(auto: bool = False):
    """Pull latest data files from GitHub."""
    if not network.is_online():
        console.print(
            "[yellow]Offline — cannot update data files. "
            "Data files will continue to work in offline mode.[/yellow]"
        )
        return

    versions = _load_data_version()
    if not versions:
        console.print("[red]data_version.json not found or corrupted.[/red]")
        return

    import requests

    updated = []
    failed = []

    for key, info in versions.items():
        source_url = info.get("source")
        if not source_url:
            continue

        target_file = os.path.join(DATA_DIR, "{}.json".format(key))
        old_version = info.get("version", "unknown")

        console.print("[dim]Fetching {}...[/dim]".format(key))

        try:
            resp = requests.get(
                source_url,
                timeout=15,
                proxies=network.get_requests_proxies(),
            )
            if resp.status_code == 200:
                new_data = resp.json()

                # Compare with existing
                try:
                    with open(target_file, "r") as f:
                        old_data = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    old_data = {}

                if new_data != old_data:
                    with open(target_file, "w") as f:
                        json.dump(new_data, f, indent=2)
                    updated.append(key)
                    console.print("  [green]Updated {}[/green]".format(key))
                else:
                    console.print("  [dim]{} — no changes[/dim]".format(key))
            else:
                failed.append("{} (HTTP {})".format(key, resp.status_code))
                console.print("  [yellow]{} — HTTP {}[/yellow]".format(key, resp.status_code))
        except Exception as e:
            failed.append("{} ({})".format(key, str(e)[:50]))
            console.print("  [yellow]{} — failed: {}[/yellow]".format(key, str(e)[:50]))

    # Update data_version.json timestamps
    if updated:
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        for key in updated:
            if key in versions:
                versions[key]["last_updated"] = now

        version_path = os.path.join(DATA_DIR, "data_version.json")
        with open(version_path, "w") as f:
            json.dump(versions, f, indent=2)

    # Summary
    if updated:
        console.print("\n[green]Updated {} data file(s).[/green]".format(len(updated)))
    elif not failed:
        console.print("\n[green]All data files are up to date.[/green]")

    if failed:
        console.print("\n[yellow]Failed to update: {}[/yellow]".format(", ".join(failed)))
        console.print("[dim]Existing local data files will be used as fallback.[/dim]")
