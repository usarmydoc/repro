"""Security: CVE and vulnerability checking.

Online: queries CVE databases (future).
Offline: falls back to bundled cve_snapshot.json.
"""

from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table

from repro import lockfile, network
from repro.version_util import version_lt

console = Console()


def check_vulnerabilities(packages: Dict[str, str],
                          cve_data: dict) -> List[Dict[str, Any]]:
    """Check packages against CVE database.

    Args:
        packages: Dict of {package_name: version}.
        cve_data: CVE snapshot data.

    Returns:
        List of vulnerability dicts.
    """
    vulns = cve_data.get("vulnerabilities", [])
    found = []

    # Build lowercase lookup for O(V+P) instead of O(V*P)
    pkg_lookup = {name.lower(): (name, ver) for name, ver in packages.items()}

    for vuln in vulns:
        pkg_name = vuln.get("package", "")
        affected = vuln.get("affected_versions", "")
        fixed_in = vuln.get("fixed_in", "")

        match = pkg_lookup.get(pkg_name.lower())
        if match:
            installed_name, installed_ver = match
            if affected.startswith("<") and version_lt(installed_ver, affected[1:]):
                found.append({
                    "package": installed_name,
                    "installed_version": installed_ver,
                    "cve": vuln.get("cve", "unknown"),
                    "severity": vuln.get("severity", "unknown"),
                    "description": vuln.get("description", ""),
                    "fixed_in": fixed_in,
                })

    return found


def run_security(lockfile_path: str):
    """Run security check on packages in lockfile."""
    data = lockfile.read_or_exit(lockfile_path)

    # Collect all packages
    all_packages = {}
    pm = data.get("package_managers", {})
    all_packages.update(pm.get("pip", {}))
    conda_pkgs = pm.get("conda", {}).get("packages", {})
    all_packages.update(conda_pkgs)

    if not all_packages:
        console.print("[yellow]No packages found in lockfile.[/yellow]")
        return

    # Load CVE data
    cve_data = lockfile.load_data_file("cve_snapshot")
    if not cve_data:
        console.print("[red]No CVE data available. Run 'repro update-data' first.[/red]")
        return

    online = network.is_online()
    if not online:
        metadata = cve_data.get("_metadata", {})
        console.print(
            "[yellow]Offline mode — using bundled CVE snapshot "
            "(last updated: {}).[/yellow]".format(metadata.get("last_updated", "unknown"))
        )

    vulns = check_vulnerabilities(all_packages, cve_data)

    if not vulns:
        console.print("[green]No known vulnerabilities found in {} packages.[/green]".format(
            len(all_packages)
        ))
        return

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    vulns.sort(key=lambda v: severity_order.get(v["severity"], 4))

    table = Table(title="Vulnerabilities Found ({})".format(len(vulns)))
    table.add_column("Severity", style="bold")
    table.add_column("Package", style="cyan")
    table.add_column("Version", style="yellow")
    table.add_column("CVE")
    table.add_column("Fixed In", style="green")
    table.add_column("Description", max_width=40)

    for v in vulns:
        sev = v["severity"]
        sev_style = {
            "critical": "[bold red]CRITICAL[/bold red]",
            "high": "[red]HIGH[/red]",
            "medium": "[yellow]MEDIUM[/yellow]",
            "low": "[dim]LOW[/dim]",
        }.get(sev, sev)

        table.add_row(
            sev_style, v["package"], v["installed_version"],
            v["cve"], v["fixed_in"], v["description"][:40]
        )

    console.print(table)
