"""Reference data detector: genome builds, Ensembl versions, file checksums.

Detects reference genomes and databases commonly used in bioinformatics.
Computes MD5 checksums of reference files for reproducibility.
"""

import hashlib
import os
import re
from typing import Any, Dict, List, Optional


# Common reference genome paths
_COMMON_REF_DIRS = [
    "/reference",
    "/refs",
    "/data/references",
    "/opt/references",
    os.path.expanduser("~/references"),
    os.path.expanduser("~/genomes"),
]

# File extensions for reference data
_REF_EXTENSIONS = {
    ".fa", ".fasta", ".fa.gz", ".fasta.gz",
    ".fai", ".dict",
    ".gtf", ".gtf.gz", ".gff", ".gff3",
    ".bed", ".bed.gz",
    ".vcf", ".vcf.gz",
    ".2bit",
}


def _file_md5(path: str, partial: bool = True) -> Optional[str]:
    """Compute MD5 of a file. For large files, hash first+last 1MB.

    Args:
        path: File path.
        partial: If True and file > 100MB, hash first+last 1MB only.
    """
    try:
        size = os.path.getsize(path)
        h = hashlib.md5()

        if partial and size > 100 * 1024 * 1024:
            # Hash first 1MB + last 1MB + file size for quick fingerprint
            with open(path, "rb") as f:
                h.update(f.read(1024 * 1024))
                f.seek(-1024 * 1024, 2)
                h.update(f.read(1024 * 1024))
            h.update(str(size).encode())
            return h.hexdigest() + "-partial"
        else:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
    except OSError:
        return None


def _file_size_gb(path: str) -> float:
    """Get file size in GB."""
    try:
        return round(os.path.getsize(path) / (1024 ** 3), 2)
    except OSError:
        return 0.0


def detect_genome_build(ref_dir: str) -> Optional[str]:
    """Try to detect genome build from filenames and directory structure."""
    builds = ["GRCh38", "hg38", "GRCh37", "hg19", "GRCm39", "mm39",
              "GRCm38", "mm10", "T2T", "chm13"]

    try:
        for entry in os.listdir(ref_dir):
            for build in builds:
                if build.lower() in entry.lower():
                    return build
    except OSError:
        pass
    return None


def detect_ensembl_version(ref_dir: str) -> Optional[str]:
    """Try to detect Ensembl version from GTF/GFF filenames."""
    try:
        for entry in os.listdir(ref_dir):
            match = re.search(r'[Ee]nsembl[._-]?(\d+)', entry)
            if match:
                return match.group(1)
            # Also try release number pattern like "release-109"
            match = re.search(r'release[._-]?(\d+)', entry)
            if match:
                return match.group(1)
    except OSError:
        pass
    return None


def scan_ref_directory(ref_dir: str) -> Dict[str, Dict[str, Any]]:
    """Scan a directory for reference files and compute checksums."""
    files = {}
    try:
        for entry in os.listdir(ref_dir):
            path = os.path.join(ref_dir, entry)
            if not os.path.isfile(path):
                continue
            # Check if it matches reference file extensions
            for ext in _REF_EXTENSIONS:
                if entry.endswith(ext):
                    files[entry] = {
                        "size_gb": _file_size_gb(path),
                        "md5": _file_md5(path),
                    }
                    break
    except OSError:
        pass
    return files


def detect(ref_dirs: list = None) -> Dict[str, Any]:
    """Detect reference data in known locations.

    Args:
        ref_dirs: Additional directories to scan for reference data.
    """
    search_dirs = list(_COMMON_REF_DIRS)
    if ref_dirs:
        search_dirs = ref_dirs + search_dirs

    found_dirs = []
    all_files = {}
    genome_build = None
    ensembl_version = None

    for d in search_dirs:
        if os.path.isdir(d):
            found_dirs.append(d)
            files = scan_ref_directory(d)
            all_files.update(files)
            if genome_build is None:
                genome_build = detect_genome_build(d)
            if ensembl_version is None:
                ensembl_version = detect_ensembl_version(d)

    return {
        "genome_build": genome_build,
        "ensembl_version": ensembl_version,
        "ref_directories": found_dirs,
        "files": all_files,
    }


if __name__ == "__main__":
    import json
    result = detect()
    file_count = len(result.get("files", {}))
    result_summary = dict(result)
    if file_count > 10:
        result_summary["files"] = "{} files found (showing count only)".format(file_count)
    print(json.dumps(result_summary, indent=2, default=str))
