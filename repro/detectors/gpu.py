"""GPU detector: CUDA, cuDNN, nvidia-smi, multiple GPUs.

Gracefully handles machines with no GPU — never hangs or crashes.
"""

import os
import re
from typing import Any, Dict, List, Optional

from repro.detectors._util import run_cmd, which


def _detect_gpus() -> List[Dict[str, Any]]:
    """Detect all NVIDIA GPUs using nvidia-smi CSV output."""
    out, rc = run_cmd([
        "nvidia-smi",
        "--query-gpu=index,name,memory.total,driver_version",
        "--format=csv,noheader,nounits"
    ], timeout=10)

    if rc != 0 or not out:
        return []

    gpus = []
    for line in out.split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 4:
            try:
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "memory_gb": round(int(parts[2]) / 1024, 1),
                    "driver": parts[3],
                })
            except (ValueError, IndexError):
                continue
    return gpus


def _detect_cuda_version() -> Optional[str]:
    """Detect CUDA version from nvcc or nvidia-smi."""
    out, rc = run_cmd(["nvcc", "--version"])
    if rc == 0 and out:
        match = re.search(r"release ([\d.]+)", out)
        if match:
            return match.group(1)

    out, rc = run_cmd(["nvidia-smi"])
    if rc == 0 and out:
        match = re.search(r"CUDA Version: ([\d.]+)", out)
        if match:
            return match.group(1)

    cuda_home = os.environ.get("CUDA_HOME") or os.environ.get("CUDA_PATH")
    if cuda_home:
        version_file = os.path.join(cuda_home, "version.txt")
        if os.path.isfile(version_file):
            try:
                with open(version_file) as f:
                    content = f.read()
                match = re.search(r"([\d.]+)", content)
                if match:
                    return match.group(1)
            except OSError:
                pass

    return None


def _detect_cudnn_version() -> Optional[str]:
    """Detect cuDNN version from header file."""
    cuda_home = os.environ.get("CUDA_HOME", "/usr/local/cuda")
    candidates = [
        os.path.join(cuda_home, "include", "cudnn_version.h"),
        os.path.join(cuda_home, "include", "cudnn.h"),
        "/usr/include/cudnn_version.h",
        "/usr/include/cudnn.h",
    ]

    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    content = f.read()
                major = re.search(r"CUDNN_MAJOR\s+(\d+)", content)
                minor = re.search(r"CUDNN_MINOR\s+(\d+)", content)
                patch = re.search(r"CUDNN_PATCHLEVEL\s+(\d+)", content)
                if major and minor and patch:
                    return "{}.{}.{}".format(
                        major.group(1), minor.group(1), patch.group(1)
                    )
            except OSError:
                continue

    return None


def detect() -> Dict[str, Any]:
    """Detect GPU hardware and CUDA/cuDNN software.

    Returns clean not-found results when no GPU is present.
    """
    has_nvidia_smi = which("nvidia-smi") is not None
    gpus = _detect_gpus() if has_nvidia_smi else []
    cuda = _detect_cuda_version()
    cudnn = _detect_cudnn_version()

    return {
        "nvidia_smi": has_nvidia_smi,
        "cuda": {"found": cuda is not None, "version": cuda},
        "cudnn": {"found": cudnn is not None, "version": cudnn},
        "gpus": gpus,
    }


if __name__ == "__main__":
    import json
    result = detect()
    print(json.dumps(result, indent=2))

    if not result["gpus"]:
        print("\nNo GPU found — this is a clean graceful result, not an error.")
    else:
        print("\nFound {} GPU(s):".format(len(result["gpus"])))
        for gpu in result["gpus"]:
            print("  [{}] {} ({} GB)".format(gpu["index"], gpu["name"], gpu["memory_gb"]))
