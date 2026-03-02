"""GPG signing and verification for repro.lock files.

For pharma, clinical, and audit environments requiring provenance.
If GPG is not installed, fails with clear install instructions.
"""

import os
import subprocess
from typing import Optional

from rich.console import Console

console = Console()


def _check_gpg() -> Optional[str]:
    """Check if GPG is available. Returns path or None."""
    import shutil
    for binary in ("gpg2", "gpg"):
        path = shutil.which(binary)
        if path:
            return path
    return None


def _gpg_not_found_message():
    """Print clear installation instructions for GPG."""
    console.print("[bold red]GPG is not installed.[/bold red]\n")
    console.print("Install GPG for your platform:")
    console.print("  [cyan]Ubuntu/Debian:[/cyan]  sudo apt install gnupg")
    console.print("  [cyan]RHEL/Fedora:[/cyan]    sudo dnf install gnupg2")
    console.print("  [cyan]macOS:[/cyan]           brew install gnupg")
    console.print("  [cyan]Windows:[/cyan]         https://gpg4win.org/")
    console.print("\nGPG signing is required for pharma/clinical audit trails.")


def run_sign(lockfile_path: str):
    """GPG sign a repro.lock file."""
    gpg = _check_gpg()
    if not gpg:
        _gpg_not_found_message()
        raise SystemExit(1)

    if not os.path.exists(lockfile_path):
        console.print("[red]File not found: {}[/red]".format(lockfile_path))
        raise SystemExit(1)

    sig_path = lockfile_path + ".sig"

    # Create detached signature
    cmd = [gpg, "--detach-sign", "--armor", "--output", sig_path, lockfile_path]
    console.print("[dim]Signing {}...[/dim]".format(lockfile_path))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            console.print("[green]Signed successfully.[/green]")
            console.print("  Signature: {}".format(sig_path))
            console.print("  Verify with: [cyan]repro verify-signature {}[/cyan]".format(lockfile_path))
        else:
            error = result.stderr.strip()
            console.print("[red]Signing failed:[/red] {}".format(error))
            if "no default secret key" in error.lower() or "no secret key" in error.lower():
                console.print("\n[yellow]You need a GPG key. Generate one with:[/yellow]")
                console.print("  gpg --full-generate-key")
            raise SystemExit(1)
    except subprocess.TimeoutExpired:
        console.print("[red]GPG timed out.[/red]")
        raise SystemExit(1)


def run_verify_signature(lockfile_path: str):
    """Verify GPG signature on a repro.lock file."""
    gpg = _check_gpg()
    if not gpg:
        _gpg_not_found_message()
        raise SystemExit(1)

    if not os.path.exists(lockfile_path):
        console.print("[red]File not found: {}[/red]".format(lockfile_path))
        raise SystemExit(1)

    sig_path = lockfile_path + ".sig"
    if not os.path.exists(sig_path):
        console.print("[red]Signature file not found: {}[/red]".format(sig_path))
        console.print("Sign first with: [cyan]repro sign {}[/cyan]".format(lockfile_path))
        raise SystemExit(1)

    cmd = [gpg, "--verify", sig_path, lockfile_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            console.print("[green]Signature is valid.[/green]")
            # Extract signer info from stderr (GPG prints there)
            for line in result.stderr.split("\n"):
                if "Good signature" in line or "key" in line.lower():
                    console.print("  {}".format(line.strip()))
        else:
            console.print("[red]Signature verification failed.[/red]")
            console.print(result.stderr)
            raise SystemExit(1)
    except subprocess.TimeoutExpired:
        console.print("[red]GPG timed out.[/red]")
        raise SystemExit(1)
