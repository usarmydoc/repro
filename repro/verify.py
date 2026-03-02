"""Verify: hash pipeline output files for reproducibility.

Classifies files as binary or text:
- Binary: .fa, .fasta, .bam, .vcf, .gz, .zip, etc., or >100MB
- Text (normalize line endings before hashing): .txt, .csv, .tsv, .log, etc.
"""

import hashlib
import os
import datetime
from typing import Any, Dict, List, Optional, Set

from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from repro import lockfile

console = Console()

# Always binary
BINARY_EXTENSIONS = {
    ".fa", ".fasta", ".fastq", ".fq",
    ".bam", ".sam", ".cram",
    ".vcf", ".bcf",
    ".gz", ".bz2", ".zip", ".tar", ".xz", ".zst",
    ".h5", ".hdf5", ".h5ad",
    ".rds", ".rda", ".rdata",
    ".npy", ".npz", ".pkl", ".pickle",
    ".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".svg",
    ".parquet", ".feather", ".arrow",
}

# Always text (normalize CRLF before hashing)
TEXT_EXTENSIONS = {
    ".txt", ".csv", ".tsv", ".log",
    ".md", ".html", ".htm",
    ".json", ".yaml", ".yml", ".xml",
    ".r", ".py", ".sh", ".jl", ".pl",
    ".nf", ".smk", ".wdl", ".cwl",
}

BINARY_SIZE_THRESHOLD = 100 * 1024 * 1024  # 100MB

# Default sample limit
SAMPLE_SIZE_THRESHOLD = 10 * 1024 * 1024 * 1024  # 10GB


def _classify_file(path: str) -> str:
    """Classify a file as 'binary' or 'text'."""
    _, ext = os.path.splitext(path.lower())

    if ext in BINARY_EXTENSIONS:
        return "binary"
    if ext in TEXT_EXTENSIONS:
        return "text"

    # Size check — large files are binary
    try:
        if os.path.getsize(path) > BINARY_SIZE_THRESHOLD:
            return "binary"
    except OSError:
        pass

    # Default to binary for unknown extensions
    return "binary"


def _hash_file(path: str, normalize_text: bool = False) -> str:
    """Compute MD5 hash of a file.

    Args:
        path: File path.
        normalize_text: If True, normalize CRLF to LF before hashing.
    """
    h = hashlib.md5()
    try:
        if normalize_text:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    # Normalize line endings to LF
                    h.update(line.replace("\r\n", "\n").encode("utf-8"))
        else:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
    except OSError:
        return "error"
    return h.hexdigest()


def _should_exclude(path: str, excludes: Optional[List[str]] = None) -> bool:
    """Check if a path matches any exclusion pattern."""
    if not excludes:
        return False
    basename = os.path.basename(path)
    for pattern in excludes:
        pattern = pattern.strip()
        if pattern.startswith("*."):
            if basename.endswith(pattern[1:]):
                return True
        elif pattern in path:
            return True
    return False


def _get_dir_size(directory: str) -> int:
    """Get total size of a directory in bytes."""
    total = 0
    try:
        for dirpath, _, filenames in os.walk(directory):
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def scan_and_hash(directory: str, sample: bool = False,
                  excludes: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
    """Scan directory and hash all files.

    Args:
        directory: Directory to scan.
        sample: If True, use sampling for dirs > 10GB.
        excludes: Patterns to exclude.

    Returns:
        Dict mapping relative paths to {md5, size_bytes, type}.
    """
    results = {}
    dir_size = _get_dir_size(directory)

    if sample and dir_size > SAMPLE_SIZE_THRESHOLD:
        console.print(
            "[yellow]Directory is {:.1f}GB — using sample mode. "
            "Pass --no-sample to hash everything.[/yellow]".format(dir_size / (1024**3))
        )

    file_list = []
    for dirpath, _, filenames in os.walk(directory):
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            relpath = os.path.relpath(fpath, directory)

            if _should_exclude(relpath, excludes):
                continue

            file_list.append((relpath, fpath))

    # Sample mode: hash representative subset
    if sample and dir_size > SAMPLE_SIZE_THRESHOLD:
        # Take first 100 + every Nth file
        n = max(1, len(file_list) // 100)
        file_list = file_list[:100] + file_list[100::n]
        console.print("[dim]Sampling {} of {} files[/dim]".format(len(file_list), len(file_list)))

    # Detect case sensitivity warning
    seen_lower = set()
    case_warnings = []
    for relpath, _ in file_list:
        lower = relpath.lower()
        if lower in seen_lower:
            case_warnings.append(relpath)
        seen_lower.add(lower)

    if case_warnings:
        console.print(
            "[yellow]Warning: {} files have case-only differences in names. "
            "Hashes may differ on case-insensitive filesystems (macOS).[/yellow]".format(
                len(case_warnings)
            )
        )

    with Progress(console=console) as progress:
        task = progress.add_task("Hashing files...", total=len(file_list))
        for relpath, fpath in file_list:
            ftype = _classify_file(fpath)
            normalize = ftype == "text"
            md5 = _hash_file(fpath, normalize_text=normalize)
            try:
                size = os.path.getsize(fpath)
            except OSError:
                size = 0

            results[relpath] = {
                "md5": md5,
                "size_bytes": size,
                "type": ftype,
            }
            progress.advance(task)

    return results


def run_verify(output_dir: str, lockfile_path: str,
               sample: bool = False, excludes: Optional[List[str]] = None):
    """Hash output files and store in lockfile."""
    if not os.path.isdir(output_dir):
        console.print("[red]Error:[/red] Directory not found: {}".format(output_dir))
        raise SystemExit(1)

    results = scan_and_hash(output_dir, sample=sample, excludes=excludes)

    # Read existing lockfile or create new
    try:
        data = lockfile.read_lockfile(lockfile_path)
    except FileNotFoundError:
        data = lockfile.empty_lockfile()
        data["created_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        from repro import __version__
        data["repro_version"] = __version__
    except ValueError as e:
        console.print("[red]Error reading lockfile:[/red] {}".format(e))
        raise SystemExit(1)

    data["verified_outputs"] = {
        "verified_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "directory": os.path.abspath(output_dir),
        "file_count": len(results),
        "files": results,
    }

    lockfile.write_lockfile(lockfile_path, data)

    # Summary
    table = Table(title="Verification Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Files hashed", str(len(results)))
    total_size = sum(f["size_bytes"] for f in results.values())
    table.add_row("Total size", "{:.1f} MB".format(total_size / (1024 * 1024)))
    text_count = sum(1 for f in results.values() if f["type"] == "text")
    binary_count = sum(1 for f in results.values() if f["type"] == "binary")
    table.add_row("Text files", str(text_count))
    table.add_row("Binary files", str(binary_count))
    table.add_row("Stored in", lockfile_path)

    console.print(table)
