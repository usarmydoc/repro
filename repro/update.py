"""Update: modify CURRENT environment to match repro.lock.

Non-destructive — never creates a new environment (that's restore's job).
Runs feasibility first, saves .bak backup, prints manual commands for
things it cannot change automatically.
"""

import json
import os
import subprocess
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table

from repro import lockfile, network
from repro.detectors import languages

console = Console()


def plan_update(data: dict) -> Dict[str, Any]:
    """Plan what needs to change in the current environment.

    Returns dict with upgrades, downgrades, installs, manual steps.
    """
    changes = {
        "pip_upgrades": [],
        "pip_downgrades": [],
        "pip_installs": [],
        "conda_changes": [],
        "manual_steps": [],
        "os_mismatch": None,
    }

    # Check OS mismatch
    from repro.detectors import system as sys_det
    current_sys = sys_det.detect()
    rec_sys = data.get("system", {})
    if rec_sys.get("os") and rec_sys["os"] != current_sys.get("os"):
        changes["os_mismatch"] = {
            "recorded": rec_sys["os"],
            "current": current_sys["os"],
        }

    # Compare pip packages
    recorded_pip = data.get("package_managers", {}).get("pip", {})
    if recorded_pip:
        try:
            result = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=15
            )
            current_pip = {}
            if result.returncode == 0:
                current_pip = {p["name"]: p["version"] for p in json.loads(result.stdout)}
        except Exception:
            current_pip = {}

        for pkg, rec_ver in recorded_pip.items():
            cur_ver = current_pip.get(pkg)
            if cur_ver is None:
                changes["pip_installs"].append({"name": pkg, "version": rec_ver})
            elif cur_ver != rec_ver:
                from repro.version_util import parse_version
                rec = parse_version(rec_ver)
                cur = parse_version(cur_ver)
                if rec > cur:
                    changes["pip_upgrades"].append({
                        "name": pkg, "from": cur_ver, "to": rec_ver})
                else:
                    changes["pip_downgrades"].append({
                        "name": pkg, "from": cur_ver, "to": rec_ver})

    # Language version mismatches -> manual
    current_langs = languages.detect()
    for lang, info in data.get("languages", {}).items():
        rec_ver = info.get("version") if isinstance(info, dict) else info
        cur_info = current_langs.get(lang, {})
        cur_ver = cur_info.get("version") if isinstance(cur_info, dict) else None
        if rec_ver and cur_ver and rec_ver != cur_ver:
            changes["manual_steps"].append(
                "{}: {} -> {} (install the correct version manually)".format(
                    lang, cur_ver, rec_ver
                )
            )

    return changes


def run_update(lockfile_path: str, dry_run: bool = False, force: bool = False):
    """Update current environment to match lockfile."""
    data = lockfile.read_or_exit(lockfile_path)

    # Run feasibility first
    from repro.feasibility import assess
    feasibility = assess(data)
    if feasibility["blockers"] and not force:
        console.print("[bold red]Feasibility blockers:[/bold red]")
        for b in feasibility["blockers"]:
            console.print("  [red]\u2022 {}[/red]".format(b))
        console.print("[yellow]Use --force to proceed anyway.[/yellow]")
        raise SystemExit(1)

    changes = plan_update(data)

    # Show what will change
    total = (len(changes["pip_upgrades"]) + len(changes["pip_downgrades"]) +
             len(changes["pip_installs"]) + len(changes["conda_changes"]))

    if total == 0 and not changes["manual_steps"] and not changes["os_mismatch"]:
        console.print("[green]Environment already matches lockfile.[/green]")
        return

    table = Table(title="Planned Changes")
    table.add_column("Action", style="cyan")
    table.add_column("Package", style="bold")
    table.add_column("From", style="red")
    table.add_column("To", style="green")

    for pkg in changes["pip_upgrades"]:
        table.add_row("upgrade", pkg["name"], pkg["from"], pkg["to"])
    for pkg in changes["pip_downgrades"]:
        table.add_row("downgrade", pkg["name"], pkg["from"], pkg["to"])
    for pkg in changes["pip_installs"]:
        table.add_row("install", pkg["name"], "-", pkg["version"])

    console.print(table)

    if changes["os_mismatch"]:
        console.print(
            "\n[yellow]OS mismatch: recorded {} vs current {}. "
            "Some packages may have different names.[/yellow]".format(
                changes["os_mismatch"]["recorded"],
                changes["os_mismatch"]["current"],
            )
        )

    if changes["manual_steps"]:
        console.print("\n[bold]Manual steps required:[/bold]")
        for step in changes["manual_steps"]:
            console.print("  \u2022 {}".format(step))

    if dry_run:
        console.print("\n[yellow]Dry run — no changes made.[/yellow]")
        return

    # Backup lockfile
    bak = lockfile.backup_lockfile(lockfile_path)
    if bak:
        console.print("[dim]Backup saved: {}[/dim]".format(bak))

    # Execute pip changes
    all_pip = []
    for pkg in changes["pip_upgrades"] + changes["pip_installs"]:
        all_pip.append("{}=={}".format(pkg.get("name"), pkg.get("to", pkg.get("version"))))
    for pkg in changes["pip_downgrades"]:
        all_pip.append("{}=={}".format(pkg["name"], pkg["to"]))

    if all_pip:
        cmd = ["pip", "install"] + all_pip
        console.print("[dim]Running pip install...[/dim]")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            console.print("[green]Pip packages updated successfully.[/green]")
        else:
            console.print("[red]Some pip installs failed:[/red] {}".format(result.stderr[:200]))

    console.print("\n[bold green]Update complete.[/bold green]")
    console.print("[dim]Run 'repro check {}' to verify.[/dim]".format(lockfile_path))
