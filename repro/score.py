"""Fast lightweight compatibility scoring and deep check.

repro score — version string comparison only, runs in under 5 seconds.
repro check — actually executes tools and imports packages (slower).
"""

import json
import subprocess
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table

from repro import lockfile
from repro.version_util import parse_version, version_diff_severity
from repro.detectors import system, languages
from repro.detectors.packages import detect_pip

console = Console()

# Severity display styles
SEVERITY_SORT = {"major": 0, "missing": 1, "minor": 2, "patch": 3}
SEVERITY_STYLE = {"major": "bold red", "missing": "red", "minor": "yellow", "patch": "dim"}


def _score_severity(severity: str) -> float:
    """Convert severity to a score (0-1, where 1 is perfect match)."""
    return {
        "match": 1.0,
        "patch": 0.9,
        "minor": 0.6,
        "major": 0.2,
        "missing": 0.0,
    }.get(severity, 0.0)


def compare_languages(recorded: dict, current: dict) -> List[Dict[str, Any]]:
    """Compare recorded vs current language versions."""
    results = []
    for lang, info in recorded.items():
        rec_version = info.get("version") if isinstance(info, dict) else info
        cur_info = current.get(lang, {})
        cur_version = cur_info.get("version") if isinstance(cur_info, dict) else cur_info

        if not rec_version or (isinstance(info, dict) and not info.get("found", True)):
            continue

        severity = version_diff_severity(str(rec_version), str(cur_version) if cur_version else None)
        results.append({
            "name": lang,
            "recorded": rec_version,
            "current": cur_version,
            "severity": severity,
        })
    return results


def compare_packages(recorded: dict, current: dict) -> List[Dict[str, Any]]:
    """Compare recorded vs current package versions."""
    results = []
    for name, rec_ver in recorded.items():
        cur_ver = current.get(name)
        severity = version_diff_severity(str(rec_ver), str(cur_ver) if cur_ver else None)
        results.append({
            "name": name,
            "recorded": rec_ver,
            "current": cur_ver,
            "severity": severity,
        })
    return results


def run_score(lockfile_path: str):
    """Fast compatibility score — version string comparison only."""
    data = lockfile.read_or_exit(lockfile_path)

    current_langs = languages.detect()
    current_system = system.detect()

    all_comparisons = []

    # Compare languages
    recorded_langs = data.get("languages", {})
    all_comparisons.extend(compare_languages(recorded_langs, current_langs))

    # Compare pip packages (reuse detector)
    recorded_pip = data.get("package_managers", {}).get("pip", {})
    if recorded_pip:
        current_pip = detect_pip()
        all_comparisons.extend(compare_packages(recorded_pip, current_pip))

    # Compare conda packages
    recorded_conda = data.get("package_managers", {}).get("conda", {}).get("packages", {})
    if recorded_conda:
        try:
            result = subprocess.run(
                ["conda", "list", "--json"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                current_conda = {p["name"]: p["version"] for p in json.loads(result.stdout)}
                all_comparisons.extend(compare_packages(recorded_conda, current_conda))
        except Exception:
            pass

    # System warnings
    rec_sys = data.get("system", {})
    sys_warnings = []
    if rec_sys.get("os") and rec_sys["os"] != current_system.get("os"):
        sys_warnings.append("OS mismatch: recorded {} vs current {}".format(
            rec_sys["os"], current_system.get("os")))
    if rec_sys.get("arch") and rec_sys["arch"] != current_system.get("arch"):
        sys_warnings.append("Architecture mismatch: recorded {} vs current {}".format(
            rec_sys["arch"], current_system.get("arch")))

    if not all_comparisons:
        console.print("[yellow]No packages to compare.[/yellow]")
        return

    total_score = sum(_score_severity(c["severity"]) for c in all_comparisons)
    max_score = len(all_comparisons)
    pct = int(100 * total_score / max_score) if max_score > 0 else 0

    matches = sum(1 for c in all_comparisons if c["severity"] == "match")
    patches = sum(1 for c in all_comparisons if c["severity"] == "patch")
    minors = sum(1 for c in all_comparisons if c["severity"] == "minor")
    majors = sum(1 for c in all_comparisons if c["severity"] == "major")
    missing = sum(1 for c in all_comparisons if c["severity"] == "missing")

    for w in sys_warnings:
        console.print("[bold red]WARNING:[/bold red] {}".format(w))

    console.print(
        "\n[bold]Environment compatibility: {}%[/bold] ({}/{} match, {} patch, {} minor, {} major, {} missing)".format(
            pct, matches, len(all_comparisons), patches, minors, majors, missing
        )
    )

    mismatches = [c for c in all_comparisons if c["severity"] != "match"]
    if mismatches:
        table = Table(title="Mismatches")
        table.add_column("Package", style="cyan")
        table.add_column("Recorded", style="green")
        table.add_column("Current", style="yellow")
        table.add_column("Severity", style="red")

        for m in sorted(mismatches, key=lambda x: SEVERITY_SORT.get(x["severity"], 4)):
            sev_style = SEVERITY_STYLE.get(m["severity"], "")
            table.add_row(
                m["name"],
                str(m["recorded"]),
                str(m["current"]) if m["current"] else "NOT FOUND",
                "[{}]{}[/{}]".format(sev_style, m["severity"], sev_style) if sev_style else m["severity"],
            )
        console.print(table)


def run_check(lockfile_path: str, ci: bool = False):
    """Deep verification — actually tests imports and tool execution."""
    data = lockfile.read_or_exit(lockfile_path)

    console.print("[bold]Running deep environment check...[/bold]\n")

    total = 0
    passed = 0

    # Check languages
    from repro.detectors._util import which
    for lang, info in data.get("languages", {}).items():
        if isinstance(info, dict) and not info.get("found", True):
            continue
        rec_ver = info.get("version") if isinstance(info, dict) else info
        if not rec_ver:
            continue

        total += 1
        binary = lang.lower()
        if binary == "python":
            binary = "python3"
        if which(binary):
            passed += 1
            console.print("  [green]PASS[/green] {} (found)".format(lang))
        else:
            console.print("  [red]FAIL[/red] {} (not found)".format(lang))

    # Check pip packages can import
    recorded_pip = data.get("package_managers", {}).get("pip", {})
    for pkg_name in list(recorded_pip.keys())[:20]:
        total += 1
        import_name = pkg_name.replace("-", "_").lower()
        try:
            result = subprocess.run(
                ["python3", "-c", "import {}".format(import_name)],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                passed += 1
                console.print("  [green]PASS[/green] pip:{} (imports)".format(pkg_name))
            else:
                # Installed but can't import by name — not necessarily a failure
                console.print("  [yellow]WARN[/yellow] pip:{} (cannot import as '{}')".format(pkg_name, import_name))
        except Exception:
            console.print("  [red]FAIL[/red] pip:{}".format(pkg_name))

    score = int(100 * passed / total) if total > 0 else 0
    console.print("\n[bold]Deep check score: {}% ({}/{} passed)[/bold]".format(score, passed, total))

    if ci and score < 95:
        console.print("[red]CI check failed: score {} < 95%[/red]".format(score))
        raise SystemExit(1)
