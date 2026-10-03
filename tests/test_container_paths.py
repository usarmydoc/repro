"""Regression tests: container runtimes found via PATH, --search-paths, or --env bin."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro import snapshot
from repro.detectors import _util, conda, containers


def _fake_apptainer(directory):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "apptainer")
    with open(path, "w") as f:
        f.write("#!/bin/sh\necho 'apptainer version 1.5.4'\n")
    os.chmod(path, 0o755)
    return path


def test_apptainer_found_on_path(tmp_path, monkeypatch):
    path = _fake_apptainer(str(tmp_path / "bin"))
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    rt = containers.detect()["runtimes"]["apptainer"]
    assert rt["found"] and rt["version"] == "1.5.4" and rt["path"] == path


def test_apptainer_found_in_search_paths(tmp_path, monkeypatch):
    path = _fake_apptainer(str(tmp_path / "extra"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    result = containers.detect(search_paths=[str(tmp_path / "extra")])
    rt = result["runtimes"]["apptainer"]
    assert rt["found"] and rt["version"] == "1.5.4" and rt["path"] == path
    assert result["active_runtime"] == "apptainer" and result["active_version"] == "1.5.4"


def test_apptainer_found_in_env_bin(tmp_path, monkeypatch):
    prefix = tmp_path / "envs" / "nf"
    path = _fake_apptainer(str(prefix / "bin"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(conda, "env_prefix", lambda name: str(prefix))

    paths = snapshot._container_paths(snapshot._resolve_env("nf"), None)
    rt = containers.detect(search_paths=paths)["runtimes"]["apptainer"]
    assert rt["found"] and rt["version"] == "1.5.4" and rt["path"] == path


def test_version_comes_from_the_binary_found_off_path(tmp_path, monkeypatch):
    """A tool found in an extra path must be run by that path, not bare name."""
    _fake_apptainer(str(tmp_path / "extra"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    info = _util.detect_binary("apptainer", ["apptainer", "--version"], r"([\d.]+)",
                               [str(tmp_path / "extra")])
    assert info["version"] == "1.5.4"
