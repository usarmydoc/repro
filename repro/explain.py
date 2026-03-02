"""Explain why version mismatches matter using breaking_changes.json.

For each mismatch between the lockfile and current environment,
looks up known breaking changes and explains the impact.
"""

from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from repro import lockfile
from repro.version_util import parse_major_minor
from repro.detectors import languages

console = Console()


def find_breaking_changes(tool: str, recorded_ver: str, current_ver: str,
                          changes_db: dict) -> List[dict]:
    """Find relevant breaking changes for a tool version transition."""
    if not recorded_ver or not current_ver:
        return []

    tool_changes = changes_db.get(tool, [])
    relevant = []

    rec = parse_major_minor(recorded_ver)
    cur = parse_major_minor(current_ver)

    for change in tool_changes:
        from_ver = parse_major_minor(change.get("from", ""))
        to_ver = parse_major_minor(change.get("to", ""))

        # Check if the version transition crosses this breaking change
        # Recorded is at or before 'from', current is at or after 'to'
        if rec <= from_ver and cur >= to_ver:
            relevant.append(change)
        # Or if recorded is at 'from' and current is at 'to'
        elif rec >= from_ver and rec < to_ver and cur >= to_ver:
            relevant.append(change)

    return relevant


def run_explain(lockfile_path: str):
    """Explain mismatches between lockfile and current environment."""
    data = lockfile.read_or_exit(lockfile_path)

    changes_db = lockfile.load_data_file("breaking_changes")
    current_langs = languages.detect()

    found_any = False

    # Check languages
    for lang, info in data.get("languages", {}).items():
        if isinstance(info, dict):
            rec_ver = info.get("version")
            found = info.get("found", True)
        else:
            rec_ver = info
            found = True

        if not found or not rec_ver:
            continue

        cur_info = current_langs.get(lang, {})
        cur_ver = cur_info.get("version") if isinstance(cur_info, dict) else None

        if rec_ver == cur_ver:
            continue

        breaks = find_breaking_changes(lang.lower(), rec_ver, cur_ver, changes_db)
        if breaks:
            found_any = True
            for b in breaks:
                severity_color = {"high": "red", "medium": "yellow", "low": "dim"}.get(
                    b.get("severity", ""), "white"
                )
                console.print(Panel(
                    "[bold]{}: {} -> {}[/bold]\n"
                    "[{sev}]Severity: {severity}[/{sev}]\n\n"
                    "{desc}\n\n"
                    "[dim]Source: {url}[/dim]".format(
                        lang, rec_ver, cur_ver,
                        sev=severity_color,
                        severity=b.get("severity", "unknown"),
                        desc=b.get("description", "No details available."),
                        url=b.get("source_url", "N/A"),
                    ),
                    title="Breaking Change",
                    border_style=severity_color,
                ))
        elif rec_ver != cur_ver and cur_ver:
            found_any = True
            console.print(
                "  [yellow]{}: {} -> {}[/yellow] "
                "(no known breaking changes in database)".format(lang, rec_ver, cur_ver)
            )

    # Check tools
    for category in ("bioinformatics", "ml", "climate", "neuroimaging"):
        tools = data.get("tools", {}).get(category, {})
        for tool_name, info in tools.items():
            if isinstance(info, dict):
                rec_ver = info.get("version")
                if not info.get("found", True) or not rec_ver:
                    continue
            else:
                continue

            # TODO: detect current tool versions for proper comparison
            breaks = find_breaking_changes(tool_name, rec_ver, rec_ver, changes_db)  # no current ver available
            # We can still show known issues even without a current version to compare
            if tool_name in changes_db:
                found_any = True
                console.print(
                    "  [cyan]{} {}[/cyan]: {} known breaking change(s) in database".format(
                        tool_name, rec_ver, len(changes_db[tool_name])
                    )
                )

    if not found_any:
        console.print(
            "[green]No version mismatches with known breaking changes.[/green]\n"
            "[dim]Database covers {} tools. Run 'repro update-data' for latest.[/dim]".format(
                len(changes_db)
            )
        )
