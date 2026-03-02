"""Feasibility assessment: can this machine run the pipeline?

Checks CPU, RAM, disk, GPU, CUDA, architecture, OS, internet, containers.
Cross-references data/pipeline_requirements.json for known minimums.
Cloud pricing comes exclusively from the data file — never hardcoded here.
"""

import json
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from repro import lockfile, network
from repro.detectors import system, gpu, containers

console = Console()


def assess(data: dict) -> Dict[str, Any]:
    """Run feasibility assessment against a lockfile.

    Returns dict with checks, blockers, warnings, verdict, and recommendations.
    """
    reqs_db = lockfile.load_data_file("pipeline_requirements")
    current_sys = system.detect()
    current_gpu = gpu.detect()
    current_containers = containers.detect()
    online = network.is_online()

    recorded_sys = data.get("system", {})
    pipeline_type = data.get("pipeline_type", "unknown")

    # Look up known requirements for this pipeline type
    known_reqs = reqs_db.get(pipeline_type, {})

    checks = []
    blockers = []
    warnings = []

    # CPU cores
    rec_cores = recorded_sys.get("cpus", 0)
    req_cores = known_reqs.get("min_cores", rec_cores)
    cur_cores = current_sys.get("cpus", 0)
    if cur_cores >= req_cores:
        checks.append({"item": "CPU cores", "status": "ok",
                       "detail": "{} available ({} required)".format(cur_cores, req_cores)})
    elif cur_cores > 0:
        warnings.append("CPU: {} cores available, {} required. May be slow.".format(cur_cores, req_cores))
        checks.append({"item": "CPU cores", "status": "warn",
                       "detail": "{} available ({} required)".format(cur_cores, req_cores)})
    else:
        checks.append({"item": "CPU cores", "status": "ok", "detail": "Could not detect"})

    # RAM
    rec_ram = recorded_sys.get("ram_gb", 0)
    req_ram = known_reqs.get("min_ram_gb", rec_ram)
    cur_ram = current_sys.get("ram_gb", 0)
    if cur_ram >= req_ram:
        checks.append({"item": "RAM", "status": "ok",
                       "detail": "{}GB available ({}GB required)".format(cur_ram, req_ram)})
    elif cur_ram > 0:
        ratio = rec_ram / cur_ram if cur_ram > 0 else 999
        if ratio > 4:
            blockers.append("RAM {}GB available, {}GB recorded. High OOM risk.".format(cur_ram, rec_ram))
            checks.append({"item": "RAM", "status": "fail",
                           "detail": "{}GB available ({}GB recorded)".format(cur_ram, rec_ram)})
        else:
            warnings.append("RAM {}GB available, {}GB recorded. OOM risk on large inputs.".format(cur_ram, rec_ram))
            checks.append({"item": "RAM", "status": "warn",
                           "detail": "{}GB available ({}GB recorded)".format(cur_ram, rec_ram)})

    # Disk space
    rec_disk = recorded_sys.get("disk_free_gb", 0)
    req_disk = known_reqs.get("typical_disk_gb", 50)
    cur_disk = current_sys.get("disk_free_gb", 0)
    if cur_disk >= req_disk:
        checks.append({"item": "Disk space", "status": "ok",
                       "detail": "{}GB free ({}GB estimated)".format(cur_disk, req_disk)})
    else:
        warnings.append("Disk: {}GB free, {}GB estimated needed.".format(cur_disk, req_disk))
        checks.append({"item": "Disk space", "status": "warn",
                       "detail": "{}GB free ({}GB estimated)".format(cur_disk, req_disk)})

    # GPU
    rec_gpus = data.get("tools", {}).get("ml", {}).get("gpus", [])
    requires_gpu = known_reqs.get("requires_gpu", bool(rec_gpus))
    gpu_fallback = known_reqs.get("gpu_fallback", True)
    cur_gpus = current_gpu.get("gpus", [])

    if requires_gpu and not cur_gpus:
        if gpu_fallback:
            warnings.append("No GPU found. Pipeline recorded with GPU. CPU fallback available but much slower.")
            checks.append({"item": "GPU", "status": "warn", "detail": "None (CPU fallback available)"})
        else:
            blockers.append("No GPU found. Pipeline requires GPU with no CPU fallback.")
            checks.append({"item": "GPU", "status": "fail", "detail": "None (required, no fallback)"})
    elif cur_gpus:
        gpu_names = ", ".join(g["name"] for g in cur_gpus)
        checks.append({"item": "GPU", "status": "ok",
                       "detail": "{} ({})".format(len(cur_gpus), gpu_names)})
    else:
        checks.append({"item": "GPU", "status": "ok", "detail": "Not required"})

    # OS
    rec_os = recorded_sys.get("os", "")
    cur_os = current_sys.get("os", "")
    if rec_os and cur_os and rec_os != cur_os:
        warnings.append("{} may cause behavioral differences (recorded on {}).".format(cur_os, rec_os))
        checks.append({"item": "OS", "status": "warn",
                       "detail": "{} (recorded: {})".format(cur_os, rec_os)})
    else:
        checks.append({"item": "OS", "status": "ok",
                       "detail": cur_os or "unknown"})

    # Architecture
    rec_arch = recorded_sys.get("arch", "")
    cur_arch = current_sys.get("arch", "")
    if rec_arch and cur_arch and rec_arch != cur_arch:
        blockers.append("Architecture mismatch: {} vs recorded {}. Binary tools will not work.".format(
            cur_arch, rec_arch))
        checks.append({"item": "Architecture", "status": "fail",
                       "detail": "{} (recorded: {})".format(cur_arch, rec_arch)})
    else:
        checks.append({"item": "Architecture", "status": "ok", "detail": cur_arch or "unknown"})

    # Container runtime
    rec_container = data.get("containers", {}).get("active_runtime")
    cur_runtime = current_containers.get("active_runtime")
    if rec_container and not cur_runtime:
        warnings.append("No container runtime found (recorded: {}). Container-based steps will fail.".format(
            rec_container))
        checks.append({"item": "Container", "status": "warn",
                       "detail": "None (recorded: {})".format(rec_container)})
    elif cur_runtime:
        checks.append({"item": "Container", "status": "ok",
                       "detail": "{} {}".format(cur_runtime, current_containers.get("active_version", ""))})
    else:
        checks.append({"item": "Container", "status": "ok", "detail": "Not required"})

    # Internet
    if online:
        checks.append({"item": "Internet", "status": "ok", "detail": "Connected"})
    else:
        warnings.append("No internet. Package installation will require offline bundle.")
        checks.append({"item": "Internet", "status": "warn", "detail": "Not connected"})

    # Verdict
    if blockers:
        verdict = "This machine cannot run this pipeline reliably."
    elif warnings:
        verdict = "This machine can run this pipeline with caveats."
    else:
        verdict = "This machine can run this pipeline."

    # Cloud recommendations from data file
    cloud_recs = reqs_db.get("cloud_recommendations", {})
    free_platforms = reqs_db.get("free_platforms", [])

    recommendations = []
    if blockers or len(warnings) > 2:
        # Suggest appropriate cloud tier
        if requires_gpu and not cur_gpus:
            tier = cloud_recs.get("gpu_pipeline", {})
        elif req_ram > 64:
            tier = cloud_recs.get("large_memory_pipeline", {})
        else:
            tier = cloud_recs.get("standard_pipeline", {})

        for provider, info in tier.items():
            if isinstance(info, dict):
                recommendations.append(
                    "{}: {} ~${}/hr".format(
                        provider.upper(), info.get("instance", "?"), info.get("price_per_hr", "?")
                    )
                )

        # Free platforms
        for plat in free_platforms:
            suitable = plat.get("suitable_for", [])
            if pipeline_type in suitable or any(t in suitable for t in ["gatk", "nextflow", "galaxy"]):
                recommendations.append(
                    "{} -- {}".format(plat["name"], plat.get("notes", ""))
                )

    return {
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "verdict": verdict,
        "recommendations": recommendations,
    }


def run_feasibility(lockfile_path: str, strict: bool = False, json_output: bool = False):
    """Run and display feasibility assessment."""
    data = lockfile.read_or_exit(lockfile_path)

    result = assess(data)

    if json_output:
        console.print_json(json.dumps(result, indent=2))
        if strict and (result["blockers"] or result["warnings"]):
            raise SystemExit(1)
        elif result["blockers"]:
            raise SystemExit(1)
        return

    # Rich display
    status_icons = {"ok": "[green]\u2705[/green]", "warn": "[yellow]\u26a0\ufe0f[/yellow]", "fail": "[red]\u274c[/red]"}

    table = Table(title="FEASIBILITY ASSESSMENT", show_header=True, header_style="bold",
                  border_style="bright_blue", show_lines=True)
    table.add_column("", width=3)
    table.add_column("Item", style="bold", width=15)
    table.add_column("Detail", width=50)

    for check in result["checks"]:
        icon = status_icons.get(check["status"], "")
        table.add_row(icon, check["item"], check["detail"])

    console.print(table)

    # Verdict
    if result["blockers"]:
        console.print("\n[bold red]VERDICT: {}[/bold red]".format(result["verdict"]))
        console.print("\n[bold red]BLOCKERS:[/bold red]")
        for b in result["blockers"]:
            console.print("  [red]\u2022 {}[/red]".format(b))
    elif result["warnings"]:
        console.print("\n[bold yellow]VERDICT: {}[/bold yellow]".format(result["verdict"]))
    else:
        console.print("\n[bold green]VERDICT: {}[/bold green]".format(result["verdict"]))

    if result["warnings"]:
        console.print("\n[bold yellow]WARNINGS:[/bold yellow]")
        for w in result["warnings"]:
            console.print("  [yellow]\u2022 {}[/yellow]".format(w))

    if result["recommendations"]:
        console.print("\n[bold]RECOMMENDATIONS:[/bold]")
        for r in result["recommendations"]:
            console.print("  \u2022 {}".format(r))

    if strict and (result["blockers"] or result["warnings"]):
        raise SystemExit(1)
    elif result["blockers"]:
        raise SystemExit(1)
