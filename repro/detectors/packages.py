"""Package detector: pip, R packages, Julia Pkg, npm, cargo."""

import json
import re
from typing import Any, Dict

from repro.detectors._util import NO_USER_SITE, run_cmd, which


def detect_pip(python: str = None) -> Dict[str, str]:
    """Detect installed pip packages with versions.

    Args:
        python: Interpreter whose packages to list. If given, user
            site-packages are excluded so only that environment is seen.
            If None, uses the pip on PATH.
    """
    if python:
        cmd, env = [python, "-m", "pip", "list", "--format=json"], NO_USER_SITE
    else:
        cmd, env = ["pip", "list", "--format=json"], None
    out, rc = run_cmd(cmd, timeout=30, combine_stderr=False, env=env)
    if rc != 0 or not out:
        return {}
    try:
        packages = json.loads(out)
        return {p["name"]: p["version"] for p in packages if "name" in p and "version" in p}
    except (json.JSONDecodeError, KeyError):
        return {}


def detect_user_site(python: str, env_pip: Dict[str, str]) -> Dict[str, Any]:
    """Packages in the user site-packages that `python` imports at runtime.

    User site comes before the environment's site-packages on sys.path, so
    a package present in both is loaded from user site (it shadows the env).
    """
    out, rc = run_cmd(
        [python, "-c", "import site; print(site.ENABLE_USER_SITE); print(site.getusersitepackages())"],
        combine_stderr=False,
    )
    lines = out.splitlines()
    if rc != 0 or len(lines) != 2:
        return {"status": "unknown", "reason": "could not query site module of {}".format(python)}
    if lines[0] != "True":
        return {"enabled": False, "path": lines[1], "packages": {}, "shadows": {}}

    out, rc = run_cmd([python, "-m", "pip", "list", "--user", "--format=json"],
                      timeout=30, combine_stderr=False)
    try:
        if rc != 0:
            raise ValueError
        user = {p["name"]: p["version"] for p in json.loads(out)}
    except (ValueError, KeyError, TypeError):
        return {"status": "unknown", "path": lines[1],
                "reason": "'pip list --user' failed for {}".format(python)}

    env_lower = {k.lower(): v for k, v in env_pip.items()}
    shadows = {
        name: {"user_site": ver, "environment": env_lower[name.lower()]}
        for name, ver in user.items() if name.lower() in env_lower
    }
    return {"enabled": True, "path": lines[1], "packages": user, "shadows": shadows}


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


def detect(python: str = None) -> Dict[str, Any]:
    """Detect all package managers and their installed packages.

    Args:
        python: Interpreter for the pip listing (see detect_pip).
    """
    return {
        "pip": detect_pip(python),
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
