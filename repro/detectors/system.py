"""System detector: OS, kernel, arch, hostname, WSL, ARM, CPU, RAM, disk."""

import os
import platform
import shutil
import subprocess
from typing import Any, Dict

from repro.detectors._util import run_cmd


def detect_os_family() -> str:
    """Detect OS family: debian, redhat, arch, alpine, macos, windows, unknown."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        try:
            with open("/etc/os-release", "r") as f:
                content = f.read().lower()
            if any(d in content for d in ("ubuntu", "debian", "mint", "pop")):
                return "debian"
            if any(d in content for d in ("rhel", "centos", "fedora", "rocky", "alma", "redhat")):
                return "redhat"
            if "arch" in content:
                return "arch"
            if "alpine" in content:
                return "alpine"
            if "suse" in content:
                return "suse"
        except FileNotFoundError:
            pass
    return "unknown"


def detect_wsl() -> bool:
    """Detect if running under Windows Subsystem for Linux."""
    try:
        with open("/proc/version", "r") as f:
            content = f.read().lower()
        if "microsoft" in content or "wsl" in content:
            return True
    except FileNotFoundError:
        pass

    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSLENV"):
        return True

    return False


def _detect_wsl_windows_version() -> str:
    """Try to detect the host Windows version (only called when WSL is True)."""
    out, _ = run_cmd(["cmd.exe", "/c", "ver"])
    if out:
        return out
    try:
        with open("/proc/version", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "unknown"


def detect_arm() -> bool:
    """Detect ARM architecture (Apple Silicon, Graviton, Raspberry Pi, etc)."""
    machine = platform.machine().lower()
    return machine in ("aarch64", "arm64", "armv7l", "armv8l")


def detect_cpu_count() -> int:
    """Detect number of CPU cores."""
    try:
        return os.cpu_count() or 0
    except Exception:
        return 0


def detect_ram_gb() -> float:
    """Detect total RAM in GB."""
    system = platform.system()
    if system == "Linux":
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return round(kb / (1024 * 1024), 1)
        except (FileNotFoundError, ValueError):
            pass
    elif system == "Darwin":
        out, _ = run_cmd(["sysctl", "-n", "hw.memsize"])
        if out:
            try:
                return round(int(out) / (1024 ** 3), 1)
            except ValueError:
                pass
    return 0.0


def detect_disk_free_gb(path: str = ".") -> float:
    """Detect free disk space in GB for the given path."""
    try:
        usage = shutil.disk_usage(os.path.abspath(path))
        return round(usage.free / (1024 ** 3), 1)
    except OSError:
        return 0.0


def detect_has_sudo() -> bool:
    """Check if the current user has sudo access (non-interactively)."""
    try:
        proc = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True, timeout=5
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def detect_root() -> bool:
    """Check if running as root."""
    return os.geteuid() == 0 if hasattr(os, "geteuid") else False


def detect() -> Dict[str, Any]:
    """Run full system detection. Returns dict for the 'system' key in lockfile."""
    is_wsl = detect_wsl()

    return {
        "os": platform.system(),
        "os_family": detect_os_family(),
        "os_release": platform.platform(),
        "kernel": platform.release(),
        "arch": platform.machine(),
        "hostname": platform.node(),
        "cpus": detect_cpu_count(),
        "ram_gb": detect_ram_gb(),
        "disk_free_gb": detect_disk_free_gb(),
        "wsl": is_wsl,
        "wsl_windows_version": _detect_wsl_windows_version() if is_wsl else None,
        "arm": detect_arm(),
        "is_root": detect_root(),
        "has_sudo": detect_has_sudo(),
    }


if __name__ == "__main__":
    import json
    result = detect()
    print(json.dumps(result, indent=2))
