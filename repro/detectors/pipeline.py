"""Pipeline type detector: auto-detect from files, nested pipelines, config checksums.

Detects Nextflow, Snakemake, WDL/Cromwell, CWL, Galaxy, Makefile-based, and
script-based pipelines. Also detects nested pipelines (e.g., Nextflow calling
Snakemake).
"""

import os
import re
from typing import Any, Dict, List, Optional

from repro.detectors._util import run_cmd, sha256_file


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


def _file_sha256(path: str) -> Optional[str]:
    """Compute SHA-256 checksum of a file."""
    try:
        return sha256_file(path)
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
        "main.nf",
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
                        digest = _file_sha256(os.path.join(directory, entry))
                        if digest:
                            checksums[entry] = digest
                elif entry == pattern:
                    digest = _file_sha256(os.path.join(directory, entry))
                    if digest:
                        checksums[entry] = digest
    except OSError:
        pass

    return checksums


_MANIFEST_NAME_RES = [
    re.compile(r"manifest\s*\{[^}]*?\bname\s*=\s*['\"]([^'\"]+)['\"]", re.DOTALL),
    re.compile(r"manifest\.name\s*=\s*['\"]([^'\"]+)['\"]"),
]


def _pipeline_name(directory: str) -> Dict[str, Any]:
    """Pipeline name from the nextflow.config manifest."""
    config = os.path.join(directory, "nextflow.config")
    try:
        with open(config, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return {"name": None, "name_reason": "no readable nextflow.config"}
    for pattern in _MANIFEST_NAME_RES:
        match = pattern.search(content)
        if match:
            return {"name": match.group(1)}
    return {"name": None, "name_reason": "no manifest name in nextflow.config"}


def _git_state(directory: str) -> Dict[str, Any]:
    """Git commit and working-tree cleanliness of the pipeline directory."""
    # --no-optional-locks: reading status must not rewrite the repo's index
    git = ["git", "--no-optional-locks", "-C", directory]
    commit, rc = run_cmd(git + ["rev-parse", "HEAD"], combine_stderr=False)
    if rc != 0 or not commit:
        return {"git_commit": None, "git_clean": None,
                "git_reason": "not a git repository, or git unavailable"}
    status, rc = run_cmd(git + ["status", "--porcelain"], timeout=60, combine_stderr=False)
    if rc != 0:
        return {"git_commit": commit, "git_clean": None, "git_reason": "git status failed"}
    changed = [line for line in status.splitlines() if line.strip()]
    toplevel, _ = run_cmd(git + ["rev-parse", "--show-toplevel"], combine_stderr=False)
    return {
        "git_commit": commit,
        "git_toplevel": toplevel or None,
        "git_clean": not changed,
        "git_changed_paths": len(changed),
    }


def detect_source(directory: str) -> Dict[str, Any]:
    """Identify an explicitly given pipeline directory: name, path, git state."""
    path = os.path.abspath(directory)
    if not os.path.isdir(path):
        return {"path": path, "error": "pipeline directory not found"}
    source = {"path": path}
    source.update(_pipeline_name(path))
    source.update(_git_state(path))
    return source


def detect(directory: str = ".", explicit: bool = False) -> Dict[str, Any]:
    """Full pipeline detection.

    Args:
        directory: Directory to scan for pipeline files.
        explicit: The directory was given with --pipeline; also record
            its name, path and git state.
    """
    primary = detect_pipeline_type(directory)
    nested = detect_nested_pipelines(directory)
    checksums = detect_config_checksums(directory)

    # Remove primary type from nested list
    nested = [n for n in nested if n != primary]

    result = {
        "primary_type": primary,
        "nested_pipelines": nested,
        "config_checksums": checksums,
        "checksum_algorithm": "sha256",
    }
    if explicit:
        result["source"] = detect_source(directory)
    return result


if __name__ == "__main__":
    import json
    result = detect()
    print(json.dumps(result, indent=2))
