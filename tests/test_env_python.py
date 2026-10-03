"""Regression tests: --env snapshots report the environment's own Python."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro import snapshot
from repro.detectors import conda, languages

NOT_FOUND = {"found": False, "version": None, "path": None, "real_path": None}


def _stub_other_languages(monkeypatch):
    monkeypatch.setattr(languages, "detect_binary", lambda *a, **k: dict(NOT_FOUND))


def test_env_python_path_and_version(tmp_path, monkeypatch):
    """The env's interpreter is run for its version, not the running one assumed."""
    _stub_other_languages(monkeypatch)
    prefix = tmp_path / "envs" / "myenv"
    (prefix / "bin").mkdir(parents=True)
    os.symlink(sys.executable, prefix / "bin" / "python")
    monkeypatch.setattr(conda, "env_prefix", lambda name: str(prefix))

    py = snapshot._detect_languages(snapshot._resolve_env("myenv"))["python"]
    assert py["found"] is True
    assert py["path"] == str(prefix / "bin" / "python")
    assert py["real_path"] == os.path.realpath(sys.executable)
    assert py["version"] == "{}.{}.{}".format(*sys.version_info[:3])


def test_env_without_python_is_not_found(tmp_path, monkeypatch):
    _stub_other_languages(monkeypatch)
    prefix = tmp_path / "envs" / "nopy"
    (prefix / "bin").mkdir(parents=True)
    monkeypatch.setattr(conda, "env_prefix", lambda name: str(prefix))

    py = snapshot._detect_languages(snapshot._resolve_env("nopy"))["python"]
    assert py["found"] is False and py["version"] is None and py["path"] is None
    assert "no Python interpreter" in py["reason"]


def test_broken_interpreter_version_is_unknown(tmp_path):
    bad = tmp_path / "python"
    bad.write_text("#!/bin/sh\nexit 3\n")
    bad.chmod(0o755)
    py = languages.detect_python(str(bad))
    assert py["version"] == "unknown" and py["reason"]
