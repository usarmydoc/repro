"""Pipeline type detector: auto-detect from files, nested pipelines, config checksums.

Detects Nextflow, Snakemake, WDL/Cromwell, CWL, Galaxy, Makefile-based, and
script-based pipelines. Also detects nested pipelines (e.g., Nextflow calling
Snakemake).
"""

import hashlib
import os
import re
from typing import Any, Dict, List, Optional


# Pipeline file patterns: (glob pattern, pipeline type)
PIPELINE_SIGNATURES = [
    ("nextflow.config", "nextflow"),
    ("main.nf", "nextflow"),
    ("Snakefile", "snakemake"),
    ("workflow/Snakefile", "snakemake"),
    ("Makefile", "makefile"),
    ("Rakefile", "rake"),
    ("Jenkinsfile", "jenkins"),
    ("Dockerfile", "docker"),
]

# File extensions that indicate a pipeline type
EXTENSION_MAP = {
    ".nf": "nextflow",
    ".smk": "snakemake",
    ".wdl": "wdl",
    ".cwl": "cwl",
    ".ga": "galaxy",
    ".snake": "snakemake",
}


def _file_md5(path: str) -> Optional[str]:
    """Compute MD5 checksum of a file."""
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def detect_pipeline_type(directory: str = ".") -> str:
    """Auto-detect the primary pipeline type from files in the directory."""
    # Check signature files first
    for filename, ptype in PIPELINE_SIGNATURES:
        if os.path.isfile(os.path.join(directory, filename)):
            return ptype

    # Check file extensions
    try:
        for entry in os.listdir(directory):
            _, ext = os.path.splitext(entry)
            if ext in EXTENSION_MAP:
                return EXTENSION_MAP[ext]
    except OSError:
        pass

    # Check for common script patterns
    for ext in (".sh", ".py", ".R", ".jl"):
        try:
            for entry in os.listdir(directory):
                if entry.endswith(ext):
                    return "script"
        except OSError:
            pass

    return "unknown"


def detect_nested_pipelines(directory: str = ".") -> List[str]:
    """Detect nested pipeline types (e.g., Nextflow calling Snakemake).

    Scans pipeline config files for references to other pipeline tools.
    """
    nested = set()

    # Map of tool references to pipeline types
    tool_refs = {
        "snakemake": "snakemake",
        "nextflow": "nextflow",
        "cromwell": "wdl",
        "cwltool": "cwl",
    }

    # Scan .nf, .smk, .wdl, .config files for cross-references
    scan_extensions = (".nf", ".smk", ".wdl", ".config", ".sh", ".py")
    try:
        for entry in os.listdir(directory):
            _, ext = os.path.splitext(entry)
            if ext in scan_extensions:
                path = os.path.join(directory, entry)
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    for tool, ptype in tool_refs.items():
                        # Look for tool invocations, not just imports
                        patterns = [
                            r'\b{}\b'.format(tool),
                            r'process.*{}'.format(tool),
                        ]
                        for pattern in patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                nested.add(ptype)
                except OSError:
                    continue
    except OSError:
        pass

    return sorted(nested)


def detect_config_checksums(directory: str = ".") -> Dict[str, str]:
    """Compute checksums for pipeline configuration files."""
    config_patterns = [
        "nextflow.config",
        "Snakefile",
        "*.wdl",
        "*.cwl",
        "Makefile",
        "config.yaml",
        "config.yml",
        "params.yaml",
        "params.yml",
    ]

    checksums = {}
    try:
        for entry in os.listdir(directory):
            for pattern in config_patterns:
                if pattern.startswith("*"):
                    if entry.endswith(pattern[1:]):
                        md5 = _file_md5(os.path.join(directory, entry))
                        if md5:
                            checksums[entry] = md5
                elif entry == pattern:
                    md5 = _file_md5(os.path.join(directory, entry))
                    if md5:
                        checksums[entry] = md5
    except OSError:
        pass

    return checksums


def detect(directory: str = ".") -> Dict[str, Any]:
    """Full pipeline detection.

    Args:
        directory: Directory to scan for pipeline files.
    """
    primary = detect_pipeline_type(directory)
    nested = detect_nested_pipelines(directory)
    checksums = detect_config_checksums(directory)

    # Remove primary type from nested list
    nested = [n for n in nested if n != primary]

    return {
        "primary_type": primary,
        "nested_pipelines": nested,
        "config_checksums": checksums,
    }


if __name__ == "__main__":
    import json
    result = detect()
    print(json.dumps(result, indent=2))
