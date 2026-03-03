# repro

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue)
![Platform: Linux | macOS | WSL](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20WSL-lightgrey)
![CI](https://img.shields.io/badge/CI-GitHub%20Actions-brightgreen)

**repro is for scientific pipelines with non-Python dependencies.** If you are building a pure Python project, use [uv](https://github.com/astral-sh/uv) or [Poetry](https://python-poetry.org/) instead — they are excellent tools and repro adds nothing for that use case. repro works alongside those tools.

![demo](demo.gif)

## The Problem

Computational science pipelines break constantly when moved between machines. The reproducibility crisis is real: **only ~26% of published analyses can be successfully re-executed** (Trisovic et al., 2022, *Scientific Data*). This happens despite researchers using package managers — because package managers only solve part of the problem.

A typical pipeline depends on:
- **Multiple languages**: Python, R, Julia, Java, Perl, Bash
- **Compiled binaries**: samtools, STAR, BWA, GATK — each with version-specific behavior
- **GPU/CUDA stacks**: driver versions, cuDNN, GPU memory
- **Container images**: Docker, Singularity, Apptainer
- **Reference data**: genome builds, Ensembl releases, database versions
- **System configuration**: kernel version, locale, architecture (x86 vs ARM)

No single package manager captures all of this. `repro` does.

## What repro is NOT

- **Not a Python package manager.** pip, conda, uv, Poetry, pipenv already do this well.
- **Not a workflow engine.** Nextflow, Snakemake, CWL, WDL already do this well.
- **Not a container builder.** Docker, Singularity already do this well.

repro is the **glue layer** that captures everything those tools cannot: the full environment state across all tools, languages, and system configuration, frozen into a single lockfile that anyone can use to recreate it.

## Install

```bash
pip install repro-lock
```

Requires Python 3.9+. Works on Linux, macOS, and WSL.

## Quick Start

```bash
# Capture your entire environment
repro snapshot

# Check compatibility on another machine
repro score repro.lock

# Deep verification (actually runs tools)
repro check repro.lock

# See what changed between two snapshots
repro diff old.repro.lock new.repro.lock

# Can this machine run the pipeline?
repro feasibility repro.lock

# Recreate the environment on a new machine
repro restore repro.lock
```

## Commands

| Command | Speed | What it does |
|---|---|---|
| `repro snapshot` | ~15s | Capture entire environment to `repro.lock` |
| `repro score` | <5s | Fast version string comparison — compatibility % |
| `repro check` | ~30s | Deep verification — actually imports packages and runs tools |
| `repro diff` | <1s | Compare two lockfiles, show what changed |
| `repro explain` | <1s | Explain why mismatches matter (uses breaking_changes.json) |
| `repro feasibility` | ~5s | Can this machine run the pipeline? CPU/RAM/GPU/disk check |
| `repro restore` | varies | Create a NEW isolated environment from lockfile |
| `repro update` | varies | Modify CURRENT environment to match lockfile |
| `repro verify` | varies | Hash output files for reproducibility |
| `repro bundle` | varies | Create portable offline archive |
| `repro security` | <2s | Check for known CVE vulnerabilities |
| `repro share` | <1s | Generate shareable HTML report |
| `repro init` | <5s | Scaffold a new reproducible project |
| `repro sign` | <2s | GPG sign a lockfile |
| `repro verify-signature` | <1s | Verify GPG signature |
| `repro update-data` | ~5s | Pull latest breaking changes and CVE data |

### `repro score` vs `repro check`

These are **different commands** for different situations:

- **`repro score`** — Fast (<5s). Compares version strings only. Use in CI for quick gates.
- **`repro check`** — Slow (~30s). Actually executes `python -c "import pkg"` and `which tool`. Use for thorough pre-run verification.

## Snapshot Output

```bash
$ repro snapshot
⠋ Scanning System...
⠋ Scanning Languages...
⠋ Scanning Conda/Mamba...
...
Snapshot saved to repro.lock (13 keys captured)
Network: Online
```

## Feasibility Assessment

```bash
$ repro feasibility repro.lock
```

```
                  FEASIBILITY ASSESSMENT
┏━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃     ┃ Item            ┃ Detail                                ┃
┡━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ✅  │ CPU cores       │ 24 available (24 required)             │
├─────┼─────────────────┼───────────────────────────────────────┤
│ ✅  │ RAM             │ 60.4GB available (60.4GB required)     │
├─────┼─────────────────┼───────────────────────────────────────┤
│ ✅  │ Disk space      │ 1609.7GB free (50GB estimated)         │
├─────┼─────────────────┼───────────────────────────────────────┤
│ ✅  │ GPU             │ 1 (NVIDIA GeForce RTX 4070 Ti)         │
├─────┼─────────────────┼───────────────────────────────────────┤
│ ✅  │ OS              │ Linux                                  │
├─────┼─────────────────┼───────────────────────────────────────┤
│ ✅  │ Architecture    │ x86_64                                 │
├─────┼─────────────────┼───────────────────────────────────────┤
│ ✅  │ Container       │ Not required                           │
├─────┼─────────────────┼───────────────────────────────────────┤
│ ✅  │ Internet        │ Connected                              │
└─────┴─────────────────┴───────────────────────────────────────┘

VERDICT: This machine can run this pipeline.
```

When problems are detected:

```
VERDICT: This machine cannot run this pipeline reliably.

BLOCKERS:
  • No GPU found. deepvariant will fail. No CPU fallback.

WARNINGS:
  • RAM 8x lower than recorded. OOM risk on large input.
  • macOS may cause samtools and STAR behavioral diffs.

RECOMMENDATIONS:
  • AWS: p3.2xlarge ~$3.06/hr
  • GCP: n1-standard-32+T4 ~$1.80/hr
  • Terra (Broad Institute) -- Free for GATK pipelines
  • Galaxy Europe -- Free, large tool library
```

## Score Output

```bash
$ repro score repro.lock
Environment compatibility: 97% (367/375 match, 0 patch, 0 minor, 1 major, 7 missing)

                   Mismatches
┏━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Package     ┃ Recorded ┃ Current   ┃ Severity ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│ torch       │ 2.8.0    │ NOT FOUND │ missing  │
│ scipy       │ 1.17.0   │ NOT FOUND │ missing  │
│ tzdata      │ 2025b    │ 2025.3    │ major    │
└─────────────┴──────────┴───────────┴──────────┘
```

## Offline & Air-Gapped Usage

repro is designed to work without internet:

```bash
# Create an offline bundle on a connected machine
repro bundle repro.lock -o pipeline.bundle

# Transfer to air-gapped machine, then:
repro restore repro.lock --from-bundle pipeline.bundle
```

All commands auto-detect network status with a 2-second timeout and switch to offline mode automatically. The `--offline` flag forces offline mode explicitly.

CVE checks fall back to the bundled `cve_snapshot.json` when offline, with a clear warning about staleness.

## HPC Usage

repro detects HPC environments (no sudo, shared filesystems):

- Defaults to user-space conda installs
- Detects module systems
- Warns about shared PATH conflicts
- `repro restore` uses `conda create` which works without root

```bash
# On HPC login node
repro feasibility repro.lock    # Check if node is suitable
repro restore repro.lock        # Creates user-space conda env
```

## Cloud Recommendations

`repro feasibility` suggests cloud instances with pricing from `pipeline_requirements.json`:

| Tier | AWS | GCP | Azure |
|---|---|---|---|
| GPU pipeline | p3.2xlarge ($3.06/hr) | n1-standard-32+T4 ($1.80/hr) | NC6s_v3 ($3.06/hr) |
| Large memory | r5.4xlarge ($1.01/hr) | m1-ultramem-40 ($6.30/hr) | Standard_M32ms ($8.68/hr) |
| Standard | c5.4xlarge ($0.68/hr) | c2-standard-16 ($0.67/hr) | Standard_F16s_v2 ($0.68/hr) |

Free platforms: Terra, Galaxy Europe, Nextflow Tower (Seqera), Google Colab.

## CI/CD Integration

Add to your GitHub Actions workflow:

```yaml
name: Repro Check
on: [push, pull_request]
jobs:
  repro-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install repro
        run: pip install repro-lock
      - name: Update data files
        run: repro update-data --auto
      - name: Feasibility check
        run: repro feasibility repro.lock --json --strict
      - name: Environment check
        run: repro check repro.lock --ci
```

The `--ci` flag on `repro check` exits with code 1 if the score falls below 95%.

## Data File Updates

repro bundles curated data files for breaking changes, CVEs, and pipeline requirements. These are versioned independently from the tool:

```bash
repro update-data          # Interactive — shows diff of changes
repro update-data --auto   # Non-interactive for CI
```

A background staleness check nudges you if data files are older than 30 days.

### Contributing Data

Submit breaking changes and pipeline requirements via PR to the [data repository](https://github.com/usarmydoc/repro-data). Each entry follows a strict schema:

```json
{
  "samtools": [
    {
      "from": "1.17",
      "to": "1.18",
      "severity": "high",
      "description": "Changed CIGAR string handling...",
      "source_url": "https://github.com/samtools/samtools/releases/tag/1.18",
      "affected_tools": ["gatk", "bcftools"]
    }
  ]
}
```

## GPG Signing

For pharma, clinical, and audit environments:

```bash
repro sign repro.lock              # Creates repro.lock.sig
repro verify-signature repro.lock  # Verifies signature
```

Requires GPG installed. If missing, repro gives clear platform-specific install instructions.

## What repro Captures

| Category | Items |
|---|---|
| **System** | OS, kernel, arch, CPU, RAM, disk, WSL, ARM |
| **Languages** | Python, R, Julia, Perl, Java, Groovy, Bash |
| **Package managers** | conda/mamba, pip, venv/Poetry/pipenv, R, npm, cargo, Julia Pkg |
| **Bioinformatics** | nextflow, snakemake, samtools, STAR, GATK, BWA, and 20+ more |
| **ML/AI** | PyTorch, TensorFlow, JAX, CUDA, cuDNN, all GPUs |
| **Climate** | NCO, CDO, Ferret, GrADS |
| **Neuroimaging** | FSL, FreeSurfer, AFNI, ANTs |
| **Containers** | Docker, Singularity, Apptainer, Podman |
| **Galaxy** | .ga workflow parsing, tool versions |
| **Reference data** | Genome build, Ensembl version, file checksums |
| **Environment** | Locale, timezone, PATH, proxy variables |

## Error Handling

repro handles every edge case without crashing:

- **No internet** — auto-detect, switch to offline mode
- **No GPU** — clean graceful result, never hangs
- **No sudo** — skip system-level operations, show manual instructions
- **Read-only filesystem** — use `-o /path/to/output.lock`
- **Corrupted lockfile** — clear human-readable error message
- **Git merge conflicts in lockfile** — detect markers, tell user how to resolve
- **Concurrent writes** — atomic writes via temp file + rename
- **Stale data files** — nudge to run `repro update-data`
- **ARM architecture** — detect and warn about incompatible tools
- **WSL** — detect, note behavioral differences
- **Nested pipelines** — detect Nextflow calling Snakemake

## Roadmap

- Automated data update agent
- Cloud execution support (submit jobs directly from repro)
- Web dashboard for team-wide environment tracking
- GPG key management improvements
- Conda lock integration
- Singularity/Apptainer image pinning
- DOI generation for lockfiles

---

If repro saved you time, star the repo — it helps others find it.
