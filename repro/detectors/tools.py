"""CLI tool detector: bioinformatics, ML, climate, neuroimaging tools.

Detects installed tools, their versions, paths, and resolves symlinks.
"""

import os
from typing import Any, Dict

from repro.detectors._util import detect_binary

# Tool category names — used here and in explain.py, restore.py
TOOL_CATEGORIES = ("bioinformatics", "ml", "climate", "neuroimaging")

# Tool definitions: (binary, version_cmd, version_regex)
BIOINFORMATICS_TOOLS = [
    ("nextflow", ["nextflow", "-version"], r"version ([\d.]+)"),
    ("snakemake", ["snakemake", "--version"], r"([\d.]+)"),
    ("cromwell", ["cromwell", "--version"], r"([\d.]+)"),
    ("cwltool", ["cwltool", "--version"], r"([\d.]+)"),
    ("bwa", ["bwa"], r"Version: ([\d.]+)"),
    ("bowtie2", ["bowtie2", "--version"], r"version ([\d.]+)"),
    ("STAR", ["STAR", "--version"], r"([\d.]+)"),
    ("minimap2", ["minimap2", "--version"], r"([\d.]+)"),
    ("hisat2", ["hisat2", "--version"], r"version ([\d.]+)"),
    ("gatk", ["gatk", "--version"], r"v([\d.]+)"),
    ("samtools", ["samtools", "--version"], r"samtools ([\d.]+)"),
    ("bcftools", ["bcftools", "--version"], r"bcftools ([\d.]+)"),
    ("freebayes", ["freebayes", "--version"], r"v([\d.]+)"),
    ("deepvariant", ["run_deepvariant", "--version"], r"([\d.]+)"),
    ("fastqc", ["fastqc", "--version"], r"v([\d.]+)"),
    ("multiqc", ["multiqc", "--version"], r"version ([\d.]+)"),
    ("trimmomatic", ["trimmomatic", "-version"], r"([\d.]+)"),
    ("fastp", ["fastp", "--version"], r"([\d.]+)"),
    ("spades.py", ["spades.py", "--version"], r"v([\d.]+)"),
    ("flye", ["flye", "--version"], r"([\d.]+)"),
    ("hifiasm", ["hifiasm", "--version"], r"([\d.]+)"),
    ("prokka", ["prokka", "--version"], r"([\d.]+)"),
    ("augustus", ["augustus", "--version"], r"([\d.]+)"),
]

CLIMATE_TOOLS = [
    ("nco", ["ncks", "--version"], r"NCO ([\d.]+)"),
    ("cdo", ["cdo", "-V"], r"Climate Data Operators version ([\d.]+)"),
    ("ferret", ["ferret", "-version"], r"([\d.]+)"),
    ("grads", ["grads", "-V"], r"([\d.]+)"),
]

NEUROIMAGING_TOOLS = [
    ("afni", ["afni", "-version"], r"AFNI_([\d.]+)"),
    ("ants", ["antsRegistration", "--version"], r"([\d.]+)"),
]


def _detect_fsl() -> Dict[str, Any]:
    """Detect FSL via FSLDIR environment variable."""
    fsldir = os.environ.get("FSLDIR")
    if fsldir and os.path.isdir(fsldir):
        ver_file = os.path.join(fsldir, "etc", "fslversion")
        version = "unknown"
        if os.path.isfile(ver_file):
            try:
                with open(ver_file) as f:
                    version = f.read().strip()
            except OSError:
                pass
        return {"found": True, "version": version, "path": fsldir, "real_path": fsldir}
    return {"found": False, "version": None, "path": None, "real_path": None}


def _detect_freesurfer() -> Dict[str, Any]:
    """Detect FreeSurfer via FREESURFER_HOME."""
    home = os.environ.get("FREESURFER_HOME")
    if home and os.path.isdir(home):
        ver_file = os.path.join(home, "build-stamp.txt")
        version = "unknown"
        if os.path.isfile(ver_file):
            try:
                with open(ver_file) as f:
                    version = f.read().strip()
            except OSError:
                pass
        return {"found": True, "version": version, "path": home, "real_path": home}
    return {"found": False, "version": None, "path": None, "real_path": None}


def detect(search_paths: list = None) -> Dict[str, Dict[str, Any]]:
    """Detect all CLI tools.

    Args:
        search_paths: Additional directories to search for tools.
    """
    extra = search_paths or []

    result = {cat: {} for cat in TOOL_CATEGORIES}

    for binary, ver_cmd, ver_re in BIOINFORMATICS_TOOLS:
        result["bioinformatics"][binary] = detect_binary(binary, ver_cmd, ver_re, extra)

    for binary, ver_cmd, ver_re in CLIMATE_TOOLS:
        result["climate"][binary] = detect_binary(binary, ver_cmd, ver_re, extra)

    # Neuroimaging — FSL and FreeSurfer use env vars
    result["neuroimaging"]["fsl"] = _detect_fsl()
    result["neuroimaging"]["freesurfer"] = _detect_freesurfer()
    for binary, ver_cmd, ver_re in NEUROIMAGING_TOOLS:
        result["neuroimaging"][binary] = detect_binary(binary, ver_cmd, ver_re, extra)

    return result


if __name__ == "__main__":
    import json
    result = detect()
    summary = {}
    for category, tools in result.items():
        found = {k: v for k, v in tools.items() if v.get("found")}
        not_found = [k for k, v in tools.items() if not v.get("found")]
        summary[category] = {"found": found, "not_found_count": len(not_found)}
    print(json.dumps(summary, indent=2))
