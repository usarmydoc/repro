"""CLI entry point for repro — all commands wired to typer."""

from typing import List, Optional

import typer
from rich.console import Console

app = typer.Typer(
    name="repro",
    help="Universal pipeline reproducibility tool for computational science.",
    no_args_is_help=True,
)
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Universal pipeline reproducibility tool for computational science."""
    if ctx.invoked_subcommand is None:
        raise typer.Exit()


@app.command()
def version():
    """Show repro version."""
    from repro import __version__
    console.print("repro {}".format(__version__))


@app.command()
def snapshot(
    output: str = typer.Option("repro.lock", "-o", "--output", help="Output lockfile path"),
    offline: bool = typer.Option(False, "--offline", help="Skip all network calls"),
    refs: bool = typer.Option(False, "--refs", help="Capture reference genome versions"),
    all_envs: bool = typer.Option(False, "--all-envs", help="Capture all conda environments"),
    env: Optional[str] = typer.Option(None, "--env", help="Snapshot a specific conda environment"),
    search_paths: Optional[str] = typer.Option(None, "--search-paths", help="Additional tool search paths (colon-separated)"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="No progress output (for git hooks)"),
):
    """Capture entire environment into a repro.lock file."""
    from repro.snapshot import run_snapshot

    paths = search_paths.split(":") if search_paths else None
    run_snapshot(
        output_path=output,
        offline=offline,
        capture_refs=refs,
        all_envs=all_envs,
        env_name=env,
        search_paths=paths,
        quiet=quiet,
    )


@app.command()
def score(
    lockfile_path: str = typer.Argument("repro.lock", help="Path to repro.lock"),
):
    """Fast lightweight compatibility score (version string comparison only)."""
    from repro.score import run_score
    run_score(lockfile_path)


@app.command()
def diff(
    lockfile1: str = typer.Argument(..., help="First repro.lock"),
    lockfile2: str = typer.Argument(..., help="Second repro.lock"),
):
    """Compare two repro.lock files and show differences."""
    from repro.diff import run_diff
    run_diff(lockfile1, lockfile2)


@app.command()
def explain(
    lockfile_path: str = typer.Argument("repro.lock", help="Path to repro.lock"),
):
    """Explain why version mismatches matter using breaking_changes.json."""
    from repro.explain import run_explain
    run_explain(lockfile_path)


@app.command()
def feasibility(
    lockfile_path: str = typer.Argument("repro.lock", help="Path to repro.lock"),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as blockers"),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON"),
):
    """Assess whether this machine can run the pipeline."""
    from repro.feasibility import run_feasibility
    run_feasibility(lockfile_path, strict=strict, json_output=json_output)


@app.command()
def restore(
    lockfile_path: str = typer.Argument("repro.lock", help="Path to repro.lock"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done"),
    from_bundle: Optional[str] = typer.Option(None, "--from-bundle", help="Restore from offline bundle"),
):
    """Create a NEW isolated environment from repro.lock."""
    from repro.restore import run_restore
    run_restore(lockfile_path, dry_run=dry_run, from_bundle=from_bundle)


@app.command()
def update(
    lockfile_path: str = typer.Argument("repro.lock", help="Path to repro.lock"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change"),
    force: bool = typer.Option(False, "--force", help="Apply changes without confirmation"),
):
    """Modify CURRENT environment to match repro.lock."""
    from repro.update import run_update
    run_update(lockfile_path, dry_run=dry_run, force=force)


@app.command()
def verify(
    output_dir: str = typer.Argument(".", help="Directory to hash"),
    lockfile_path: str = typer.Option("repro.lock", "-l", "--lockfile", help="Lockfile to store hashes in"),
    sample: bool = typer.Option(False, "--sample", help="Sample mode for large directories"),
    exclude: Optional[str] = typer.Option(None, "--exclude", help="Comma-separated exclude patterns"),
):
    """Hash output files for reproducibility verification."""
    from repro.verify import run_verify
    excludes = exclude.split(",") if exclude else None
    run_verify(output_dir, lockfile_path, sample=sample, excludes=excludes)


@app.command()
def bundle(
    lockfile_path: str = typer.Argument("repro.lock", help="Path to repro.lock"),
    output: str = typer.Option("repro.bundle", "-o", "--output", help="Output bundle path"),
):
    """Create portable offline bundle for air-gapped machines."""
    from repro.bundle import run_bundle
    run_bundle(lockfile_path, output)


@app.command()
def security(
    lockfile_path: str = typer.Argument("repro.lock", help="Path to repro.lock"),
):
    """Check packages for known CVE vulnerabilities."""
    from repro.security import run_security
    run_security(lockfile_path)


@app.command()
def share(
    lockfile_path: str = typer.Argument("repro.lock", help="Path to repro.lock"),
    output: str = typer.Option("repro_report", "-o", "--output", help="Output directory"),
):
    """Generate shareable HTML report from lockfile."""
    from repro.share import run_share
    run_share(lockfile_path, output)


@app.command(name="init")
def init_cmd(
    directory: str = typer.Argument(".", help="Directory to initialize"),
):
    """Scaffold a new reproducible project."""
    from repro.init import run_init
    run_init(directory)


@app.command()
def sign(
    lockfile_path: str = typer.Argument("repro.lock", help="Path to repro.lock to sign"),
):
    """GPG sign a repro.lock file."""
    from repro.sign import run_sign
    run_sign(lockfile_path)


@app.command(name="verify-signature")
def verify_signature(
    lockfile_path: str = typer.Argument("repro.lock", help="Path to repro.lock"),
):
    """Verify GPG signature on a repro.lock file."""
    from repro.sign import run_verify_signature
    run_verify_signature(lockfile_path)


@app.command(name="update-data")
def update_data(
    auto: bool = typer.Option(False, "--auto", help="Non-interactive mode for CI"),
):
    """Pull latest data files (breaking_changes, CVEs, etc)."""
    from repro.update_data import run_update_data
    run_update_data(auto=auto)


@app.command()
def check(
    lockfile_path: str = typer.Argument("repro.lock", help="Path to repro.lock"),
    ci: bool = typer.Option(False, "--ci", help="Exit with code 1 if score < 95%%"),
):
    """Deep verification — actually tests whether packages import and tools run."""
    from repro.score import run_check
    run_check(lockfile_path, ci=ci)


if __name__ == "__main__":
    app()
