"""Snapshot orchestrator: captures everything, writes repro.lock.

Coordinates all detectors and writes a complete environment snapshot
to a repro.lock file. Respects --offline, --refs, --all-envs, etc.
"""

import datetime
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from repro import __version__, network, lockfile
from repro.detectors import (
    system,
    languages,
    conda,
    virtualenv,
    packages,
    tools,
    containers,
    gpu,
    galaxy,
    pipeline,
    refs,
    environment,
)

console = Console()


def run_snapshot(
    output_path: str = "repro.lock",
    offline: bool = False,
    capture_refs: bool = False,
    all_envs: bool = False,
    env_name: str = None,
    search_paths: list = None,
    quiet: bool = False,
    ref_dirs: list = None,
) -> dict:
    """Run a full environment snapshot.

    Args:
        output_path: Where to write the lockfile.
        offline: Force offline mode (skip all network calls).
        capture_refs: Also capture reference genome versions.
        all_envs: Capture all conda environments.
        env_name: Snapshot a specific conda environment.
        search_paths: Additional directories to search for tools.
        quiet: Suppress progress output (for git hooks).
        ref_dirs: Additional directories to scan for reference data.

    Returns:
        The complete snapshot dict.
    """
    if offline:
        network.force_offline(True)

    data = lockfile.empty_lockfile()
    data["created_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    data["repro_version"] = __version__

    steps = [
        ("System", lambda: system.detect()),
        ("Languages", lambda: languages.detect()),
        ("Conda/Mamba", lambda: conda.detect(all_envs=all_envs, env_name=env_name)),
        ("Virtual environments", lambda: virtualenv.detect()),
        ("Packages", lambda: packages.detect()),
        ("CLI tools", lambda: tools.detect(search_paths=search_paths)),
        ("Containers", lambda: containers.detect()),
        ("GPU/CUDA", lambda: gpu.detect()),
        ("Galaxy workflows", lambda: galaxy.detect()),
        ("Pipeline type", lambda: pipeline.detect()),
        ("Environment", lambda: environment.detect()),
    ]

    if capture_refs:
        steps.append(("Reference data", lambda: refs.detect(ref_dirs=ref_dirs)))

    if quiet:
        # Silent mode for git hooks
        for name, func in steps:
            try:
                result = func()
                _merge_result(data, name, result)
            except Exception as e:
                # Never crash in quiet mode
                pass
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning environment...", total=len(steps))

            for name, func in steps:
                progress.update(task, description="Scanning {}...".format(name))
                try:
                    result = func()
                    _merge_result(data, name, result)
                except Exception as e:
                    if not quiet:
                        console.print(
                            "[yellow]Warning:[/yellow] {} detection failed: {}".format(name, e)
                        )
                progress.advance(task)

    # Add data file versions
    data["data_versions_used"] = _get_data_versions()

    # Write lockfile atomically
    lockfile.write_lockfile(output_path, data)

    if not quiet:
        console.print(
            "\n[green]Snapshot saved to {}[/green] ({} keys captured)".format(
                output_path, _count_captured(data)
            )
        )
        net_status = network.online_status_message()
        console.print("[dim]Network: {}[/dim]".format(net_status))

    return data


def _merge_result(data: dict, step_name: str, result: dict):
    """Merge detector results into the lockfile data structure."""
    name_map = {
        "System": "system",
        "Languages": "languages",
        "Packages": "_packages",  # Merged specially
        "CLI tools": "tools",
        "Containers": "containers",
        "GPU/CUDA": "_gpu",
        "Galaxy workflows": "galaxy",
        "Pipeline type": "_pipeline",
        "Environment": "environment",
        "Reference data": "references",
        "Conda/Mamba": "_conda",
        "Virtual environments": "_venv",
    }

    key = name_map.get(step_name)
    if not key:
        return

    if key == "_conda":
        # Merge conda into package_managers
        data["package_managers"]["conda"] = {
            "binary": result.get("binary"),
            "version": result.get("version"),
            "env_name": result.get("env_name"),
            "packages": result.get("packages", {}),
            "conflicts": result.get("conflicts", []),
        }
        if result.get("all_envs"):
            data["package_managers"]["conda"]["all_envs"] = result["all_envs"]
    elif key == "_venv":
        data["package_managers"]["virtualenv"] = result
    elif key == "_packages":
        data["package_managers"]["pip"] = result.get("pip", {})
        data["package_managers"]["R_packages"] = result.get("R_packages", {})
        data["package_managers"]["julia_packages"] = result.get("julia_packages", {})
        data["package_managers"]["npm"] = result.get("npm", {})
        data["package_managers"]["cargo"] = result.get("cargo", {})
    elif key == "_gpu":
        # Merge GPU into tools section
        if "tools" not in data:
            data["tools"] = {}
        data["tools"]["ml"] = {
            "cuda": result.get("cuda", {}),
            "cudnn": result.get("cudnn", {}),
            "gpus": result.get("gpus", []),
        }
    elif key == "_pipeline":
        data["pipeline_type"] = result.get("primary_type", "unknown")
        data["pipeline"] = result
    else:
        data[key] = result


def _count_captured(data: dict) -> int:
    """Count non-empty top-level sections."""
    count = 0
    for key, val in data.items():
        if isinstance(val, dict) and val:
            count += 1
        elif isinstance(val, str) and val:
            count += 1
    return count


def _get_data_versions() -> dict:
    """Read data file versions if available."""
    versions = lockfile.load_data_file("data_version")
    if versions:
        return {
            "breaking_changes": versions.get("breaking_changes", {}).get("version", "unknown"),
            "pipeline_requirements": versions.get("pipeline_requirements", {}).get("version", "unknown"),
            "cve_snapshot": versions.get("cve_snapshot", {}).get("version", "unknown"),
        }
    return {}
