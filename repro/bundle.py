"""Bundle: create portable offline archive for air-gapped machines.

Downloads all pip wheels and conda packages, bundles with lockfile
into a single repro.bundle archive.
"""

import json
import os
import shutil
import subprocess
import tempfile
from typing import Optional

from rich.console import Console
from rich.progress import Progress

from repro import lockfile, network, DATA_DIR

console = Console()


def run_bundle(lockfile_path: str, output: str = "repro.bundle"):
    """Create a portable offline bundle."""
    data = lockfile.read_or_exit(lockfile_path)

    console.print("[bold]Creating offline bundle...[/bold]")

    with tempfile.TemporaryDirectory(prefix="repro_bundle_") as tmpdir:
        bundle_dir = os.path.join(tmpdir, "repro_bundle")
        os.makedirs(bundle_dir)

        # Copy lockfile
        shutil.copy2(lockfile_path, os.path.join(bundle_dir, "repro.lock"))

        # Copy data files
        data_src = DATA_DIR
        data_dst = os.path.join(bundle_dir, "data")
        if os.path.isdir(data_src):
            shutil.copytree(data_src, data_dst)

        # Download pip wheels
        pip_packages = data.get("package_managers", {}).get("pip", {})
        if pip_packages and network.is_online():
            wheels_dir = os.path.join(bundle_dir, "wheels")
            os.makedirs(wheels_dir)

            pkg_specs = ["{}=={}".format(k, v) for k, v in pip_packages.items()]

            console.print("[dim]Downloading {} pip packages...[/dim]".format(len(pkg_specs)))

            # Download in batches to avoid command line length limits
            batch_size = 50
            for i in range(0, len(pkg_specs), batch_size):
                batch = pkg_specs[i:i + batch_size]
                cmd = ["pip", "download", "-d", wheels_dir] + batch
                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=300
                    )
                    if result.returncode != 0:
                        console.print(
                            "[yellow]Some packages failed to download[/yellow]"
                        )
                except subprocess.TimeoutExpired:
                    console.print("[yellow]Download timed out for batch[/yellow]")

            wheel_count = len(os.listdir(wheels_dir))
            console.print("[dim]Downloaded {} wheel files[/dim]".format(wheel_count))
        elif not network.is_online():
            console.print(
                "[yellow]Offline — skipping package downloads. "
                "Bundle will contain lockfile and data only.[/yellow]"
            )

        # Create archive
        console.print("[dim]Creating archive...[/dim]")

        # Calculate size estimate
        total_size = 0
        for dirpath, _, filenames in os.walk(bundle_dir):
            for f in filenames:
                total_size += os.path.getsize(os.path.join(dirpath, f))

        console.print("[dim]Bundle size: {:.1f} MB[/dim]".format(total_size / (1024 * 1024)))

        # Create tar.gz
        archive_base = output.replace(".bundle", "")
        archive_path = shutil.make_archive(
            archive_base, "gztar", tmpdir, "repro_bundle"
        )

        # Rename to .bundle
        if not output.endswith(".tar.gz"):
            final_path = output
            os.rename(archive_path, final_path)
        else:
            final_path = archive_path

        final_size = os.path.getsize(final_path)
        console.print(
            "\n[green]Bundle created:[/green] {} ({:.1f} MB)".format(
                final_path, final_size / (1024 * 1024)
            )
        )
        console.print(
            "[dim]Restore with: repro restore repro.lock --from-bundle {}[/dim]".format(final_path)
        )
