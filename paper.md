---
title: "repro: A Universal Environment Capture Tool for Computational Pipeline Reproducibility"
tags:
  - Python
  - reproducibility
  - bioinformatics
  - computational science
  - environment management
authors:
  - name: Ross Meade
    orcid: 0009-0000-3654-6185
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 2 March 2026
bibliography: paper.bib
---

# Summary

`repro` is a command-line tool that captures the complete computational
environment of a scientific pipeline into a single JSON lockfile. Unlike
language-specific package managers, `repro` records system configuration,
compiled binaries, GPU hardware, container runtimes, reference data versions,
and packages across multiple language ecosystems simultaneously. The resulting
`repro.lock` file enables researchers to assess compatibility on a new machine,
diagnose version mismatches, and restore environments --- without requiring
familiarity with each tool's individual version-checking syntax. `repro` is
written in Python, works on Linux, macOS, and WSL, and operates fully offline
for air-gapped and HPC environments.

# Statement of Need

Computational reproducibility remains a persistent challenge in the sciences.
A large-scale study of Harvard Dataverse code found that only 26% of R scripts
could be successfully re-executed [@trisovic2022]. The problem is particularly
acute in domains like bioinformatics, climate science, and neuroimaging, where
pipelines depend on compiled C/C++ binaries (e.g., samtools, STAR, BWA),
GPU-accelerated frameworks (CUDA, cuDNN), multiple language runtimes
(Python, R, Julia, Java), container images, and reference datasets that are
versioned independently of any package manager.

Existing tools solve individual pieces of this problem well. Conda
[@gruning2018] and pip manage Python and R packages. Nextflow [@ditommaso2017]
and Snakemake [@molder2021] manage workflow execution. Docker and Singularity
[@kurtzer2017] provide containerized environments. However, no single tool
captures the full cross-cutting state: the CUDA driver version, the kernel,
the architecture, the locale, and the 30 compiled bioinformatics binaries
installed via `apt`, `brew`, or manual compilation --- all of which affect
whether a pipeline will produce identical results.

Researchers moving pipelines between a laptop, an HPC cluster, and a cloud
instance currently resort to ad hoc shell scripts, scattered README notes, or
trial-and-error installation. `repro` replaces this workflow with a single
command (`repro snapshot`) that produces a machine-readable lockfile, and a
complementary set of commands for comparison, diagnosis, and restoration.

# State of the Field

Several tools address parts of the reproducibility stack.
Bioconda [@gruning2018] and its Bioconda channel provide cross-platform package
management for bioinformatics software, but do not capture system-level state,
GPU hardware, or tools installed outside the Conda ecosystem. Workflow managers
such as Nextflow [@ditommaso2017] and Snakemake [@molder2021] version-control
pipeline logic but delegate environment specification to Conda, Docker, or
module files. Container solutions like Docker and Singularity [@kurtzer2017]
freeze entire operating systems but add friction on HPC systems that restrict
root access. ReproZip [@chirigati2016] traces system calls to capture
dependencies, but requires running the full pipeline first and does not support
prospective assessment.

`repro` occupies a complementary niche: it is a lightweight, read-only scanner
that captures the current environment state without executing the pipeline,
modifying the system, or requiring root access. It is designed to work
*alongside* Conda, Docker, and workflow managers --- not to replace them. Its
lockfile format enables machine-readable comparison, feasibility assessment,
and offline bundling, none of which are provided by the tools above.

# Software Design

`repro` is organized around 12 environment detectors and 17 CLI commands.

**Detectors** run independently and return structured dictionaries for system
properties, language runtimes (Python, R, Julia, Perl, Java, Groovy, Bash),
package managers (pip, Conda, npm, cargo, CRAN, Julia Pkg), compiled CLI tools
(25+ bioinformatics, climate, and neuroimaging binaries), container runtimes
(Docker, Singularity, Apptainer, Podman), GPU hardware (NVIDIA GPUs, CUDA,
cuDNN), Galaxy workflows, pipeline type inference, reference data checksums,
and environment variables. Each detector handles missing software gracefully,
never hanging or crashing.

**Commands** operate on the resulting `repro.lock` JSON file:

- `snapshot` captures the environment.
- `score` provides a fast compatibility percentage via version string comparison.
- `check` performs deep verification by actually importing packages and executing binaries.
- `diff` compares two lockfiles.
- `explain` cross-references a curated database of known breaking changes.
- `feasibility` assesses CPU, RAM, GPU, disk, and architecture requirements, with cloud instance recommendations and pricing from a bundled data file.
- `restore` creates a new isolated Conda environment matching the lockfile.
- `bundle` produces a portable offline archive for air-gapped machines.
- `security` checks packages against a bundled CVE snapshot.
- `sign` and `verify-signature` provide GPG-based provenance for clinical and audit contexts.

All file I/O uses atomic writes (temporary file plus rename) to prevent
corruption from concurrent or interrupted snapshots. Network access is
auto-detected with a two-second timeout; all commands degrade gracefully to
offline mode. Data files for breaking changes, CVE snapshots, and pipeline
requirements are versioned independently and updated via `repro update-data`.

# Research Impact Statement

`repro` addresses a gap identified across multiple reproducibility studies: the
lack of standardized, machine-readable environment documentation in
computational science. It is designed for immediate adoption in bioinformatics,
machine learning, climate modeling, and neuroimaging workflows where
multi-tool, multi-language environments are the norm. The tool's feasibility
assessment and offline bundling capabilities are specifically intended for
researchers working across heterogeneous infrastructure (laptops, HPC clusters,
cloud instances) who currently lack a systematic way to evaluate environment
compatibility before attempting to run a pipeline.

# AI Usage Disclosure

This software was developed with assistance from Claude (Anthropic), a large
language model. Claude was used for code generation, code review, and drafting
of documentation and this manuscript. All code was reviewed, tested (47 unit
tests), and validated by the author prior to release.

# Acknowledgements

The author thanks the developers of Typer, Rich, Conda, and the bioinformatics
community for the tools and ecosystem that `repro` builds upon.

# References
