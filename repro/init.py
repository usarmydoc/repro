"""Init: scaffold a new reproducible project.

Creates best-practice directory structure, initial repro.lock,
and optionally sets up git hooks and CI.
"""

import os
import stat

from rich.console import Console
from rich.prompt import Prompt, Confirm

from repro import lockfile

console = Console()

GIT_HOOK_CONTENT = """#!/bin/bash
# repro post-commit hook
# Automatically snapshots the environment after each commit
# and stages the updated repro.lock.
#
# NOTE: This hook fires on git commit events, NOT on conda/pip install.
# If you install or update packages, run 'repro snapshot' manually
# or commit again to capture the change.
#
# To disable: remove or rename .git/hooks/post-commit

# Run snapshot in quiet mode (no progress bars, only errors)
repro snapshot --quiet 2>/dev/null

# Stage the updated lockfile if it changed
if [ -f repro.lock ]; then
    git add repro.lock 2>/dev/null
fi
"""


def run_init(directory: str = "."):
    """Scaffold a new reproducible project."""
    directory = os.path.abspath(directory)

    console.print("[bold]Initializing reproducible project in {}[/bold]\n".format(directory))

    # Get project info
    project_name = Prompt.ask("Project name", default=os.path.basename(directory))
    pipeline_type = Prompt.ask(
        "Pipeline type",
        choices=["nextflow", "snakemake", "wdl", "cwl", "galaxy", "makefile", "script", "other"],
        default="script",
    )
    setup_ci = Confirm.ask("Set up GitHub Actions CI?", default=True)
    setup_hook = Confirm.ask("Set up git post-commit hook?", default=True)

    # Create directory structure
    dirs = [
        "data",
        "scripts",
        "results",
        "config",
    ]

    for d in dirs:
        path = os.path.join(directory, d)
        os.makedirs(path, exist_ok=True)
        # Create .gitkeep in empty dirs
        gitkeep = os.path.join(path, ".gitkeep")
        if not os.listdir(path):
            with open(gitkeep, "w") as f:
                pass

    console.print("  Created directories: {}".format(", ".join(dirs)))

    # Create initial lockfile
    data = lockfile.empty_lockfile()
    import datetime
    from repro import __version__
    data["created_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    data["repro_version"] = __version__
    data["pipeline_type"] = pipeline_type

    lock_path = os.path.join(directory, "repro.lock")
    lockfile.write_lockfile(lock_path, data)
    console.print("  Created repro.lock")

    # Create .gitignore additions
    gitignore_path = os.path.join(directory, ".gitignore")
    gitignore_additions = "\n# repro\nrepro.bundle\nrepro_report/\nrepro_report.zip\n*.lock.bak\n"
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            existing = f.read()
        if "repro" not in existing:
            with open(gitignore_path, "a") as f:
                f.write(gitignore_additions)
            console.print("  Updated .gitignore")
    else:
        with open(gitignore_path, "w") as f:
            f.write(gitignore_additions)
        console.print("  Created .gitignore")

    # Git hook
    if setup_hook:
        git_dir = os.path.join(directory, ".git")
        if os.path.isdir(git_dir):
            hooks_dir = os.path.join(git_dir, "hooks")
            os.makedirs(hooks_dir, exist_ok=True)
            hook_path = os.path.join(hooks_dir, "post-commit")
            with open(hook_path, "w") as f:
                f.write(GIT_HOOK_CONTENT)
            os.chmod(hook_path, os.stat(hook_path).st_mode | stat.S_IEXEC)
            console.print("  Installed git post-commit hook")
        else:
            console.print("  [yellow]Not a git repo — skipping hook. Run 'git init' first.[/yellow]")

    # GitHub Actions
    if setup_ci:
        ci_dir = os.path.join(directory, ".github", "workflows")
        os.makedirs(ci_dir, exist_ok=True)
        ci_path = os.path.join(ci_dir, "repro-check.yml")
        ci_content = """name: Repro Check
on: [push, pull_request]
jobs:
  repro-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install repro
        run: pip install repro-lock
      - name: Update data files
        run: repro update-data --auto
      - name: Feasibility check
        run: repro feasibility repro.lock --json --strict
      - name: Environment check
        run: repro check repro.lock --ci
"""
        with open(ci_path, "w") as f:
            f.write(ci_content)
        console.print("  Created .github/workflows/repro-check.yml")

    console.print("\n[bold green]Project initialized![/bold green]")
    console.print("\nNext steps:")
    console.print("  1. Run [cyan]repro snapshot[/cyan] to capture your environment")
    console.print("  2. Add your pipeline scripts to [cyan]scripts/[/cyan]")
    console.print("  3. Commit repro.lock to version control")
