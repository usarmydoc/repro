"""Package detector: pip, R packages, Julia Pkg, npm, cargo."""

import json
import re
from typing import Any, Dict

from repro.detectors._util import run_cmd, which


def detect_pip() -> Dict[str, str]:
    """Detect installed pip packages with versions."""
    out, rc = run_cmd(["pip", "list", "--format=json"], timeout=30, combine_stderr=False)
    if rc != 0 or not out:
        return {}
    try:
        packages = json.loads(out)
        return {p["name"]: p["version"] for p in packages if "name" in p and "version" in p}
    except (json.JSONDecodeError, KeyError):
        return {}


def detect_r_packages() -> Dict[str, str]:
    """Detect installed R packages with versions."""
    if not which("Rscript"):
        return {}

    r_script = 'cat(toJSON(as.data.frame(installed.packages()[,c("Package","Version")]), auto_unbox=TRUE))'
    out, rc = run_cmd(
        ["Rscript", "-e", "library(jsonlite); " + r_script],
        timeout=60, combine_stderr=False,
    )
    if rc != 0 or not out:
        # Fallback without jsonlite
        r_simple = 'ip <- installed.packages(); cat(paste(ip[,"Package"], ip[,"Version"], sep="="), sep="\\n")'
        out, rc = run_cmd(["Rscript", "-e", r_simple], timeout=60, combine_stderr=False)
        if rc != 0 or not out:
            return {}
        result = {}
        for line in out.split("\n"):
            if "=" in line:
                name, version = line.split("=", 1)
                result[name.strip()] = version.strip()
        return result

    try:
        packages = json.loads(out)
        if isinstance(packages, list):
            return {p.get("Package", ""): p.get("Version", "") for p in packages}
        elif isinstance(packages, dict):
            return {packages.get("Package", ""): packages.get("Version", "")}
    except json.JSONDecodeError:
        return {}
    return {}


def detect_julia_packages() -> Dict[str, str]:
    """Detect installed Julia packages with versions."""
    if not which("julia"):
        return {}

    julia_cmd = """
    import Pkg
    for (uuid, info) in Pkg.dependencies()
        if info.is_direct_dep
            println(info.name, "=", info.version)
        end
    end
    """
    out, rc = run_cmd(["julia", "-e", julia_cmd], timeout=60, combine_stderr=False)
    if rc != 0 or not out:
        return {}
    result = {}
    for line in out.split("\n"):
        if "=" in line:
            name, version = line.split("=", 1)
            result[name.strip()] = version.strip()
    return result


def detect_npm() -> Dict[str, str]:
    """Detect globally installed npm packages."""
    if not which("npm"):
        return {}

    out, rc = run_cmd(["npm", "list", "-g", "--json", "--depth=0"], timeout=30, combine_stderr=False)
    if rc not in (0, 1) or not out:
        return {}
    try:
        data = json.loads(out)
        deps = data.get("dependencies", {})
        return {name: info.get("version", "unknown") for name, info in deps.items()}
    except json.JSONDecodeError:
        return {}


def detect_cargo() -> Dict[str, str]:
    """Detect installed cargo packages."""
    if not which("cargo"):
        return {}

    out, rc = run_cmd(["cargo", "install", "--list"], timeout=30)
    if rc != 0 or not out:
        return {}
    result = {}
    for line in out.split("\n"):
        match = re.match(r'^(\S+)\s+v([\d.]+)', line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def detect() -> Dict[str, Any]:
    """Detect all package managers and their installed packages."""
    return {
        "pip": detect_pip(),
        "R_packages": detect_r_packages(),
        "julia_packages": detect_julia_packages(),
        "npm": detect_npm(),
        "cargo": detect_cargo(),
    }


if __name__ == "__main__":
    result = detect()
    summary = {}
    for key, pkgs in result.items():
        summary[key] = {"count": len(pkgs), "sample": dict(list(pkgs.items())[:5])}
    print(json.dumps(summary, indent=2))
