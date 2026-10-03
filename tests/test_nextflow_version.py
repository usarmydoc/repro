"""Regression tests: Nextflow version parsing and off-PATH detection."""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro.detectors import tools

# Exact `nextflow -version` output of 26.04.6
NF_26 = """
      N E X T F L O W
      version 26.04.6 build 12646
      created 09-07-2026 18:49 UTC (13:49 CDT)
      cite doi:10.1038/nbt.3820
      http://nextflow.io
"""

# Older release, same banner layout
NF_22 = """
      N E X T F L O W
      version 22.10.7 build 5853
      created 23-02-2023 16:50 UTC (10:50 CDT)
      cite doi:10.1038/nbt.3820
      http://nextflow.io
"""


def _nextflow_regex():
    return next(rx for name, _, rx in tools.BIOINFORMATICS_TOOLS if name == "nextflow")


def test_parse_nextflow_26():
    assert re.search(_nextflow_regex(), NF_26).group(1) == "26.04.6"


def test_parse_nextflow_22():
    assert re.search(_nextflow_regex(), NF_22).group(1) == "22.10.7"


def test_nextflow_off_path_reports_version(tmp_path, monkeypatch):
    """Found via --search-paths only: version must still be read (was 'unknown')."""
    bindir = tmp_path / "envbin"
    bindir.mkdir()
    nf = bindir / "nextflow"
    # Shell builtins only: PATH is emptied below
    nf.write_text("#!/bin/sh\n" + "".join(
        "echo '{}'\n".format(line) for line in NF_26.splitlines()))
    nf.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    info = tools.detect(search_paths=[str(bindir)])["bioinformatics"]["nextflow"]
    assert info["found"] and info["path"] == str(nf)
    assert info["version"] == "26.04.6"


def test_unparsed_version_output_is_unknown(tmp_path):
    """Output that doesn't match the regex is not a version; record why."""
    tool = tmp_path / "nextflow"
    tool.write_text("#!/bin/sh\necho 'nextflow: 2: cat: not found'\n")
    tool.chmod(0o755)
    from repro.detectors import _util
    info = _util.detect_binary("nextflow", ["nextflow", "-version"], _nextflow_regex(),
                               [str(tmp_path)])
    assert info["version"] == "unknown"
    assert "no version matching" in info["reason"]
    assert info["version_output"] == "nextflow: 2: cat: not found"
