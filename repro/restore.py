"""Restore: create a NEW isolated environment from repro.lock.

Never touches existing environments. Creates either a Python venv or conda env
depending on the original environment type recorded in the lockfile.
"""

import datetime
import json
import os
import subprocess
from typing import Optional

from rich.console import Console
from rich.table import Table

from repro import lockfile, network

console = Console()


def _generate_env_name(data: dict) -> str:
    """Generate a unique environment name: repro-[pipeline]-[timestamp]."""
    pipeline = data.get("pipeline_type", "env")
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return "repro-{}-{}".format(pipeline, ts)


def _detect_env_type(data: dict) -> str:
    """Determine the environment type from lockfile data.

    Checks virtualenv info first (venv takes priority over conda),
    then falls back to conda if present.

    Returns: "venv", "virtualenv", "poetry", "pipenv", or "conda"
    """
    pm = data.get("package_managers", {})
    venv_info = pm.get("virtualenv", {})
    venv_type = venv_info.get("venv_type", "none")

    # If a venv/virtualenv/poetry/pipenv was active at snapshot time, use it
    if venv_type in ("venv", "virtualenv", "poetry", "pipenv"):
        return venv_type

    # Fall back to conda
    return "conda"


def plan_restore(data: dict) -> dict:
    """Plan what needs to be installed, without executing anything.

    Returns a dict with:
        env_type, conda_packages, pip_packages, r_packages, julia_packages,
        tools_manual, containers, env_name
    """
    env_name = _generate_env_name(data)
    env_type = _detect_env_type(data)

    plan = {
        "env_name": env_name,
        "env_type": env_type,
        "conda_packages": {},
        "pip_packages": {},
        "r_packages": {},
        "julia_packages": {},
        "tools_manual": [],
        "containers": [],
    }

    pm = data.get("package_managers", {})

    # Conda packages
    conda_pkgs = pm.get("conda", {}).get("packages", {})
    plan["conda_packages"] = conda_pkgs

    # Pip packages
    plan["pip_packages"] = pm.get("pip", {})

    # R packages
    plan["r_packages"] = pm.get("R_packages", {})

    # Julia packages
    plan["julia_packages"] = pm.get("julia_packages", {})

    # Compiled tools that need manual installation
    for category in ("bioinformatics", "ml", "climate", "neuroimaging"):
        tools = data.get("tools", {}).get(category, {})
        for name, info in tools.items():
            if isinstance(info, dict) and info.get("found"):
                plan["tools_manual"].append({
                    "name": name,
                    "version": info.get("version"),
                    "category": category,
                })

    # Containers
    container_data = data.get("containers", {})
    if container_data.get("current_image"):
        plan["containers"].append(container_data["current_image"])

    return plan


def run_restore(lockfile_path: str, dry_run: bool = False,
                from_bundle: Optional[str] = None,
                target: Optional[str] = None):
    """Create a new environment from a lockfile.

    Args:
        lockfile_path: Path to the repro.lock file.
        dry_run: Show what would be done without executing.
        from_bundle: Path to offline bundle.
        target: Target path for venv, or conda env name override.
    """
    data = lockfile.read_or_exit(lockfile_path)

    # Run feasibility check first
    from repro.feasibility import assess
    feasibility = assess(data)
    if feasibility["blockers"]:
        console.print("[bold red]Feasibility blockers found:[/bold red]")
        for b in feasibility["blockers"]:
            console.print("  [red]\u2022 {}[/red]".format(b))
        console.print("\n[yellow]Proceeding anyway...[/yellow]")

    plan = plan_restore(data)

    # Override env name / target path if specified
    if target:
        if plan["env_type"] in ("venv", "virtualenv", "poetry", "pipenv"):
            plan["target_path"] = os.path.abspath(target)
        else:
            # For conda, target is the env name
            plan["env_name"] = target

    # Display plan
    console.print("\n[bold]Restore Plan[/bold]")
    console.print("  Environment type: [cyan]{}[/cyan]".format(plan["env_type"]))
    if plan.get("target_path"):
        console.print("  Target path: [cyan]{}[/cyan]".format(plan["target_path"]))
    else:
        console.print("  Environment name: [cyan]{}[/cyan]".format(plan["env_name"]))

    table = Table(title="Packages to Install")
    table.add_column("Type", style="cyan")
    table.add_column("Count", style="green")
    table.add_column("Sample")

    for pkg_type, pkgs in [
        ("conda", plan["conda_packages"]),
        ("pip", plan["pip_packages"]),
        ("R (CRAN/Bioc)", plan["r_packages"]),
        ("Julia", plan["julia_packages"]),
    ]:
        if pkgs:
            sample = ", ".join(list(pkgs.keys())[:3])
            if len(pkgs) > 3:
                sample += "..."
            table.add_row(pkg_type, str(len(pkgs)), sample)

    console.print(table)

    if plan["tools_manual"]:
        console.print("\n[bold]Manual installation required:[/bold]")
        for tool in plan["tools_manual"]:
            console.print("  \u2022 {} {} ({})".format(
                tool["name"], tool["version"] or "", tool["category"]))

    if dry_run:
        console.print("\n[yellow]Dry run — no changes made.[/yellow]")
        console.print("\n[bold]Commands that would be run:[/bold]")

        if plan["env_type"] in ("venv", "virtualenv", "poetry", "pipenv"):
            venv_path = plan.get("target_path", plan["env_name"])
            console.print("  python3 -m venv {}".format(venv_path))
            if plan["pip_packages"]:
                pkgs = " ".join("{}=={}".format(k, v)
                                for k, v in list(plan["pip_packages"].items())[:10])
                console.print("  {}/bin/pip install {}".format(venv_path, pkgs))
        else:
            # Conda create
            if plan["conda_packages"]:
                pkgs = " ".join("{}={}".format(k, v)
                                for k, v in list(plan["conda_packages"].items())[:10])
                console.print("  conda create -n {} {}".format(plan["env_name"], pkgs))
                if len(plan["conda_packages"]) > 10:
                    console.print("  ... and {} more packages".format(
                        len(plan["conda_packages"]) - 10))

            # Pip install
            if plan["pip_packages"]:
                pkgs = " ".join("{}=={}".format(k, v)
                                for k, v in list(plan["pip_packages"].items())[:10])
                console.print("  pip install {}".format(pkgs))

        # R packages
        if plan["r_packages"]:
            cran = list(plan["r_packages"].keys())[:5]
            console.print('  Rscript -e \'install.packages(c("{}"))\' '.format(
                '", "'.join(cran)))

        # Julia packages
        if plan["julia_packages"]:
            julia_pkgs = list(plan["julia_packages"].keys())[:5]
            console.print('  julia -e \'using Pkg; {}\''.format(
                "; ".join('Pkg.add("{}")'.format(p) for p in julia_pkgs)))

        # From bundle
        if from_bundle:
            console.print("\n  [dim]Restoring from offline bundle: {}[/dim]".format(
                from_bundle))

        return

    # Actually execute restore
    console.print("\n[bold]Creating environment...[/bold]")

    if plan["env_type"] in ("venv", "virtualenv", "poetry", "pipenv"):
        _restore_venv(data, plan)
    else:
        _restore_conda(data, plan)

    if plan["tools_manual"]:
        console.print("\n[yellow]Manual steps still required:[/yellow]")
        for tool in plan["tools_manual"]:
            console.print("  \u2022 Install {} {}".format(
                tool["name"], tool["version"] or ""))


def _restore_venv(data: dict, plan: dict):
    """Create a Python venv and install pip packages."""
    langs = data.get("languages", {})
    python_path = langs.get("python", {}).get("path", "python3")
    venv_path = plan.get("target_path", plan["env_name"])

    # Create venv
    cmd = [python_path, "-m", "venv", venv_path]
    console.print("[dim]Running: python3 -m venv {}[/dim]".format(venv_path))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        # Fallback to python3
        cmd = ["python3", "-m", "venv", venv_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        console.print("[red]Venv creation failed:[/red] {}".format(
            result.stderr[:200]))
        raise SystemExit(1)
    console.print("[green]Virtual environment created.[/green]")

    # Upgrade pip in the new venv
    pip_path = os.path.join(venv_path, "bin", "pip")
    subprocess.run([pip_path, "install", "--upgrade", "pip"],
                   capture_output=True, text=True, timeout=120)

    # Install pip packages
    if plan["pip_packages"]:
        pkg_specs = ["{}=={}".format(k, v) for k, v in plan["pip_packages"].items()]
        cmd = [pip_path, "install"] + pkg_specs
        console.print("[dim]Installing {} pip packages...[/dim]".format(
            len(plan["pip_packages"])))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            console.print("[green]Pip packages installed.[/green]")
        else:
            console.print("[yellow]Some pip packages may have failed:[/yellow]")
            # Show last few lines of stderr for debugging
            err_lines = result.stderr.strip().split("\n")
            for line in err_lines[-3:]:
                console.print("  [dim]{}[/dim]".format(line))

    # Summary
    console.print("\n[bold green]Restore complete.[/bold green]")
    console.print("  Activate: [cyan]source {}/bin/activate[/cyan]".format(venv_path))


def _restore_conda(data: dict, plan: dict):
    """Create a conda environment and install packages."""
    env_name = plan["env_name"]

    # Step 1: Create conda env
    if plan["conda_packages"]:
        pkg_specs = ["{}={}".format(k, v) for k, v in plan["conda_packages"].items()]
        cmd = ["conda", "create", "-n", env_name, "-y"] + pkg_specs
        console.print("[dim]Running: conda create -n {}...[/dim]".format(env_name))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            console.print("[green]Conda environment created.[/green]")
        else:
            console.print("[red]Conda create failed:[/red] {}".format(
                result.stderr[:200]))
    else:
        # Create empty env with python
        langs = data.get("languages", {})
        py_ver = langs.get("python", {}).get("version", "3.11")
        cmd = ["conda", "create", "-n", env_name,
               "python={}".format(py_ver), "-y"]
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    # Step 2: Pip install in the new env
    if plan["pip_packages"]:
        pkg_specs = ["{}=={}".format(k, v) for k, v in plan["pip_packages"].items()]
        cmd = ["conda", "run", "-n", env_name, "pip", "install"] + pkg_specs
        console.print("[dim]Installing pip packages...[/dim]")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            console.print("[green]Pip packages installed.[/green]")
        else:
            console.print("[yellow]Some pip packages may have failed.[/yellow]")

    # Summary
    console.print("\n[bold green]Restore complete.[/bold green]")
    console.print("  Activate: [cyan]conda activate {}[/cyan]".format(env_name))
